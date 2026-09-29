"""Applique les meilleurs temps WA (bassin 50m validé, fenêtre 24 mois) à la base, en mémoire,
et produit le journal des modifications. N'écrit rien dans le dépôt : voir wa_apply.py."""
import json, re, unicodedata
from datetime import date
from wa_pool import parse, build_refs, classify, to_sec
import os as _os
SCR = _os.environ.get('WA_WORK', _os.getcwd())
DATA = _os.environ.get('WA_DATA', _os.path.join(SCR, 'data'))
APP = _os.environ.get('WA_APP', _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))


TODAY = date.fromisoformat(_os.environ['WA_TODAY']) if _os.environ.get('WA_TODAY') else date.today()
DISTS = (400, 800, 1500)


def months_ago(d, n):
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


CUTOFF = months_ago(TODAY, 24)


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r"[-'’.]", ' ', s).upper().split())


def fmt_json(sec):
    m = int(sec // 60)
    return f"{m}:{sec - 60 * m:06.3f}"


def fmt_html(sec):
    m = int(sec // 60)
    return f"{m}:{sec - 60 * m:05.2f}"


def load_wa():
    import os
    raw = json.load(open(os.environ.get('WA_RAW', f'{SCR}/wa_raw.json')))['swimmers']
    parsed_all = []
    for k, e in raw.items():
        e['_parsed'] = [p for p in (parse(r) for r in e.get('results') or []) if p]
        parsed_all += e['_parsed']
    refs = build_refs(parsed_all)
    for e in raw.values():
        for p in e['_parsed']:
            p['bassin'], p['motif'] = classify(p, refs)
    return raw, refs


def best_window(parsed, dist, start, end, genre):
    c = [p for p in parsed if p['dist'] == dist and p['bassin'] == '50m' and p['genre'] == genre
         and start <= p['date'] <= end]
    return min(c, key=lambda p: p['sec']) if c else None


def update_entry(x, genre, raw, fmt, src, log, flags):
    """Met à jour un dict nageur {nom, t400.., v400.., annee} en place. Renvoie True si modifié."""
    key = f"{genre}|{norm(x['nom'])}"
    e = raw.get(key)
    changed = False
    # nettoyage formats + v manquantes/incohérentes
    for d in DISTS:
        t, v = x.get(f't{d}'), x.get(f'v{d}')
        s = to_sec(t) if t else None
        if t and s is None or (t and s is not None and s < 60):
            log.append(dict(src=src, nom=x['nom'], champ=f't{d}', avant=t, apres=None, motif='placeholder/format invalide -> null'))
            x[f't{d}'] = None
            if x.get(f'v{d}') is not None:
                log.append(dict(src=src, nom=x['nom'], champ=f'v{d}', avant=x[f'v{d}'], apres=None, motif='placeholder/format invalide -> null'))
                x[f'v{d}'] = None
            changed = True
            continue
        if s:
            if fmt(s) != t and not re.match(r'^\d{1,2}:\d{2}\.\d{2,3}$', t):
                log.append(dict(src=src, nom=x['nom'], champ=f't{d}', avant=t, apres=fmt(s), motif='format normalise'))
                x[f't{d}'] = fmt(s)
                changed = True
            vv = round(d / s, 4)
            if v is None or abs(v - vv) > 0.0006:
                log.append(dict(src=src, nom=x['nom'], champ=f'v{d}', avant=v, apres=vv, motif='vitesse recalculee depuis le temps'))
                x[f'v{d}'] = vv
                changed = True
    if not e or e.get('status') != 'ok':
        return changed
    ath = e['athlete']
    # année de naissance
    wy = int(ath['dateOfBirth'][:4]) if ath.get('dateOfBirth') else None
    if wy:
        if not x.get('annee'):
            log.append(dict(src=src, nom=x['nom'], champ='annee', avant=x.get('annee'), apres=wy, motif='annee de naissance WA ajoutee'))
            x['annee'] = wy
            changed = True
        elif x['annee'] != wy:
            flags.append(dict(nom=x['nom'], src=src, probleme=f"annee base {x['annee']} != WA {wy} ({ath['fullName']}, {ath['nationality']})"))
    if x.get('noc') and ath.get('nationality') and x['noc'] != ath['nationality']:
        flags.append(dict(nom=x['nom'], src=src, probleme=f"NOC base {x['noc']} != WA {ath['nationality']} ({ath['fullName']})"))
    # meilleurs temps fenêtre 24 mois
    for d in DISTS:
        b = best_window(e['_parsed'], d, CUTOFF, TODAY, genre)
        if not b:
            continue
        s_base = to_sec(x.get(f't{d}')) if x.get(f't{d}') else None
        if s_base is None or b['sec'] < s_base - 0.004:
            log.append(dict(src=src, nom=x['nom'], champ=f't{d}', avant=x.get(f't{d}'), apres=fmt(b['sec']),
                            motif='amelioration WA' if s_base else 'ajout WA (absent de la base)',
                            date_perf=b['date'].isoformat(), competition=b['competition'], validation=b['motif']))
            x[f't{d}'] = fmt(b['sec'])
            nv = round(d / b['sec'], 4)
            if x.get(f'v{d}') != nv:
                x[f'v{d}'] = nv
            changed = True
    return changed


def run():
    raw, refs = load_wa()
    log, flags = [], []
    n10 = json.load(open(f'{DATA}/resultats_10km_nageurs_el.json'))
    ko = json.load(open(f'{DATA}/resultats_ko_el.json'))
    for g, key in [('F', 'DATA_F'), ('H', 'DATA_H')]:
        for x in n10[key]:
            update_entry(x, g, raw, fmt_json, f'10km/{key}', log, flags)
        for x in ko[key]:
            update_entry(x, g, raw, fmt_json, f'KO/{key}', log, flags)
    html = {}
    ent_re = re.compile(r"\{[^{}]*?nom:'([^']+)'[^{}]*\}")
    for f in ['Ponton10km.html', 'ponton_ko_setubal2026.html', 'ponton_ko_ibiza2026.html']:
        txt = open(f'{APP}/{f}', encoding='utf-8').read()
        for g in ['F', 'H']:
            m = re.search(r'(STARTLIST_' + g + r'\s*=\s*\[)(.*?)(\];)', txt, re.S)
            if not m:
                continue
            block = m.group(2)

            def repl(mm):
                ent = mm.group(0)
                d = {}
                for kv in re.finditer(r"(\w+):('([^']*)'|[-\d.]+|null)", ent):
                    k, val = kv.group(1), kv.group(2)
                    d[k] = kv.group(3) if val.startswith("'") else (None if val == 'null' else (int(val) if re.match(r'^-?\d+$', val) else float(val)))
                before = dict(d)
                update_entry(d, g, raw, fmt_html, f'{f}/STARTLIST_{g}', log, flags)
                if d == before:
                    return ent
                order = ['bib', 'nom', 'noc', 'annee', 't400', 't800', 't1500', 'v400', 'v800', 'v1500']
                keys = [k for k in order if k in d or k in ('t400', 't800', 't1500', 'v400', 'v800', 'v1500')] + [k for k in d if k not in order]
                parts = []
                for k in keys:
                    v = d.get(k)
                    if v is None:
                        continue
                    parts.append(f"{k}:'{v}'" if isinstance(v, str) else f"{k}:{v}")
                return '{' + ','.join(parts) + '}'

            new_block = ent_re.sub(repl, block)
            txt = txt[:m.start(2)] + new_block + txt[m.end(2):]
        html[f] = txt
    for k, e in raw.items():
        if e.get('status') != 'ok' and any(not x.startswith('participant') for x in e['base']['sources']):
            flags.append(dict(nom=e['base']['nom'], src=','.join(sorted(set(e['base']['sources']))),
                              probleme=f"WA {e.get('status')}: " + '; '.join(
                                  f"{c['fullName']} {c.get('dateOfBirth')} {c.get('nationality')}" for c in e.get('candidats') or [])))
        else:
            for p in e['_parsed']:
                if p['bassin'] in ('conflit',) and p['date'] >= CUTOFF:
                    flags.append(dict(nom=e['base']['nom'], src='WA', probleme=f"{p['dist']} {p['time']} {p['date']} {p['competition']}: {p['motif']}"))
    return raw, refs, n10, ko, html, log, flags


if __name__ == '__main__':
    raw, refs, n10, ko, html, log, flags = run()
    from collections import Counter
    print('modifs par motif:', Counter(l['motif'] for l in log))
    print('flags:', len(flags))
    pools = Counter(p['bassin'] for e in raw.values() for p in e.get('_parsed', []))
    print('classification bassin:', pools)
