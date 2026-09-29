#!/usr/bin/env python3
"""Collecte World Aquatics (inspiré de worldaquatics_curl.py) pour tous les nageurs de la base.
Sortie : wa_raw.json (checkpoint) = par nageur : athlete WA + tous les résultats SW 200/400/800/1500 NL."""
import json, re, time, random, unicodedata, os, sys
import requests
import os as _os
SCR = _os.environ.get('WA_WORK', _os.getcwd())
DATA = _os.environ.get('WA_DATA', _os.path.join(SCR, 'data'))
APP = _os.environ.get('WA_APP', _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))


OUT = f'{SCR}/wa_raw.json'

BASE = "https://api.worldaquatics.com/fina"
HEADERS = {
    "accept": "*/*",
    "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://www.worldaquatics.com",
    "referer": "https://www.worldaquatics.com/",
    "user-agent": ("Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"),
}
DIST_RE = re.compile(r"\b(200|400|800|1500)m\s+Freestyle\b(?!\s*Relay)", re.I)


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r"[-'’.]", ' ', s).upper().split())


def split_nom(nom):
    """'MARTINEZ GUILLEN Angela' -> ('MARTINEZ GUILLEN', 'Angela'); 'van ROUWENDAAL Sharon' -> ('van ROUWENDAAL','Sharon')."""
    toks = nom.split()
    last_upper = max((i for i, t in enumerate(toks) if t.isupper() and len(t) > 1 and not t.endswith('.')), default=0)
    return ' '.join(toks[:last_upper + 1]), ' '.join(toks[last_upper + 1:])


def build_universe():
    uni = {}

    def add(genre, nom, noc, annee, src):
        k = (genre, norm(nom))
        e = uni.setdefault(k, {'genre': genre, 'nom': nom, 'noc': noc, 'annee': annee, 'sources': []})
        if not e.get('annee') and annee:
            e['annee'] = annee
        if not e.get('noc') and noc:
            e['noc'] = noc
        e['sources'].append(src)

    n10 = json.load(open(f'{DATA}/resultats_10km_nageurs_el.json'))
    for g, key in [('F', 'DATA_F'), ('H', 'DATA_H')]:
        for x in n10[key]:
            add(g, x['nom'], x.get('noc'), x.get('annee'), '10km')
    ko = json.load(open(f'{DATA}/resultats_ko_el.json'))
    for g, key in [('F', 'DATA_F'), ('H', 'DATA_H')]:
        for x in ko[key]:
            add(g, x['nom'], x.get('noc'), x.get('annee'), 'KO')
    ent_re = re.compile(r"\{[^{}]*?nom:'([^']+)',noc:'([A-Z]{3})'(?:,annee:(\d{4}))?[^{}]*\}")
    for f in ['Ponton10km.html', 'ponton_ko_setubal2026.html', 'ponton_ko_ibiza2026.html']:
        txt = open(f'{APP}/{f}', encoding='utf-8').read()
        for g in ['F', 'H']:
            m = re.search(r'STARTLIST_' + g + r'\s*=\s*\[(.*?)\];', txt, re.S)
            if not m:
                continue
            for nom, noc, annee in ent_re.findall(m.group(1)):
                add(g, nom, noc, int(annee) if annee else None, f)
    return list(uni.values())


def get(sess, url, params=None, retries=4):
    last = '?'
    for a in range(retries):
        try:
            r = sess.get(url, params=params, timeout=25)
            if r.status_code == 200:
                return r.json(), 'ok'
            last = f'http{r.status_code}'
        except Exception as e:
            last = type(e).__name__
        time.sleep(2 + 3 * a + random.random())
    return None, last


def pick(cands, sw):
    last, first = split_nom(sw['nom'])
    nl, nf = norm(last), norm(first)
    g = sw['genre'] if sw['genre'] == 'F' else 'M'
    scored = []
    for c in cands:
        if (c.get('gender') or g) != g:
            continue
        cl, cf = norm(c.get('lastName')), norm(c.get('firstName'))
        if cl != nl and not (nl in cl or cl in nl):
            continue
        s = 0
        if cl == nl:
            s += 2
        if nf and cf:
            if cf == nf:
                s += 3
            elif cf.split()[0] == nf.split()[0]:
                s += 2
            elif cf[0] == nf[0]:
                s += 0.5
            else:
                continue
        if sw.get('noc') and (c.get('nationality') or '') == sw['noc']:
            s += 2
        if sw.get('annee') and (c.get('dateOfBirth') or '')[:4] == str(sw['annee']):
            s += 2
        elif sw.get('annee') and c.get('dateOfBirth'):
            s -= 3
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None, 'introuvable', []
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, 'ambigu', [c for _, c in scored[:5]]
    return scored[0][1], 'ok', [c for _, c in scored[:5]]


def main():
    uni = build_universe()
    data = json.load(open(OUT)) if os.path.exists(OUT) else {'swimmers': {}}
    sess = requests.Session()
    sess.headers.update(HEADERS)
    print(f'{len(uni)} nageurs uniques', flush=True)
    for i, sw in enumerate(uni, 1):
        key = f"{sw['genre']}|{norm(sw['nom'])}"
        prev = data['swimmers'].get(key)
        if prev and prev.get('status') in ('ok', 'introuvable', 'ambigu'):
            continue
        last, first = split_nom(sw['nom'])
        res, why = get(sess, f'{BASE}/athletes', {'gender': '', 'discipline': '', 'nationality': '',
                                                   'name': last, 'page': 0, 'pageSize': 50})
        if res is None:
            data['swimmers'][key] = {'base': sw, 'status': f'erreur_recherche_{why}'}
            continue
        cands = res.get('content', [])
        if not cands and first:
            res, why = get(sess, f'{BASE}/athletes', {'gender': '', 'discipline': '', 'nationality': '',
                                                       'name': f'{first} {last}', 'page': 0, 'pageSize': 50})
            cands = (res or {}).get('content', [])
        c, status, top = pick(cands, sw)
        entry = {'base': sw, 'status': status,
                 'candidats': [{k: x.get(k) for k in ('id', 'fullName', 'dateOfBirth', 'nationality', 'gender')} for x in top]}
        if c:
            entry['athlete'] = {k: c.get(k) for k in ('id', 'fullName', 'firstName', 'lastName', 'dateOfBirth', 'nationality', 'gender')}
            rj, why = get(sess, f"{BASE}/athletes/{c['id']}/results")
            if rj is None:
                entry['status'] = f'erreur_resultats_{why}'
            else:
                keep = []
                for r in rj.get('Results', []):
                    if r.get('SportCode') == 'SW' and DIST_RE.search(r.get('DisciplineName') or ''):
                        keep.append({k: r.get(k) for k in ('DisciplineName', 'Date', 'Time', 'Points', 'CompetitionName',
                                                            'CompetitionType', 'CompetitionCountry', 'CompetitionCity',
                                                            'PhaseName', 'Rank')})
                    elif r.get('SportCode') == 'OW':
                        entry.setdefault('ow', []).append({k: r.get(k) for k in ('DisciplineName', 'Date', 'Time', 'Rank',
                                                                                   'CompetitionName', 'CompetitionCity')})
                entry['results'] = keep
        data['swimmers'][key] = entry
        print(f"[{i}/{len(uni)}] {sw['nom']} ({sw['noc']}) -> {entry['status']}"
              f"{' ' + entry['athlete']['fullName'] + ' ' + str(entry['athlete']['dateOfBirth']) if c else ''}", flush=True)
        if i % 10 == 0:
            json.dump(data, open(OUT, 'w'), ensure_ascii=False)
        time.sleep(random.uniform(0.4, 0.9))
    json.dump(data, open(OUT, 'w'), ensure_ascii=False)
    from collections import Counter
    print('BILAN', Counter(v['status'] for v in data['swimmers'].values()), flush=True)


if __name__ == '__main__':
    main()
