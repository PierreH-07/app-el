"""2e passe : correspondance par tokens, recherche multi-requêtes paginée, fusion des profils WA en double."""
import json, time, random
from wa_collect import BASE, HEADERS, DIST_RE, norm, split_nom, get, OUT
import requests


def name_ok(c, sw):
    last, first = split_nom(sw['nom'])
    lt, ft = set(norm(last).split()), norm(first).split()
    cl, cf = set(norm(c.get('lastName')).split()), norm(c.get('firstName')).split()
    if not (lt & cl):
        return False
    if not ft or not cf:
        return True
    f0, c0 = ft[0], cf[0]
    if f0 == c0 or c0.startswith(f0) or f0.startswith(c0):
        return True
    if len(f0) == 1 and c0[0] == f0:
        return True
    # prénom WA en plusieurs mots collés ("Pen-Han" vs "Pen Han")
    return ''.join(ft) == ''.join(cf)


def score(c, sw):
    last, first = split_nom(sw['nom'])
    s = 0
    if set(norm(last).split()) == set(norm(c.get('lastName')).split()):
        s += 2
    if norm(first) and norm(first) == norm(c.get('firstName')):
        s += 2
    if 'OW' in (c.get('disciplines') or []):
        s += 1
    noc = sw.get('noc') if sw.get('noc') not in ('NAB', 'AIN') else None
    if noc and c.get('nationality') == noc:
        s += 3
    elif noc and c.get('nationality'):
        s -= 3
    if sw.get('annee') and c.get('dateOfBirth'):
        s += 3 if c['dateOfBirth'][:4] == str(sw['annee']) else -4
    return s


def search_all(sess, sw):
    last, first = split_nom(sw['nom'])
    qs = [f'{first} {last}'.strip(), last] + [t for t in norm(last).split() if len(t) >= 3]
    if first:
        qs.append(f"{first.split()[0]} {norm(last).split()[0]}")
    seen = {}
    for q in dict.fromkeys(qs):
        for page in range(3):
            res, _ = get(sess, f'{BASE}/athletes', {'gender': '', 'discipline': '', 'nationality': (sw.get('noc') if sw.get('noc') not in ('NAB', 'AIN') else '') or '',
                                                     'name': q, 'page': page, 'pageSize': 50})
            if not res:
                break
            for c in res.get('content', []):
                seen[c['id']] = c
            if page + 1 >= (res.get('pageInfo') or {}).get('numPages', 1):
                break
            time.sleep(0.3)
        time.sleep(0.3)
    g = 'F' if sw['genre'] == 'F' else 'M'
    return [c for c in seen.values() if (c.get('gender') or g) == g and name_ok(c, sw)]


def resolve(cands, sw):
    if not cands:
        return None, 'introuvable', []
    scored = sorted(((score(c, sw), c) for c in cands), key=lambda x: -x[0])
    top = scored[0][0]
    best = [c for s, c in scored if s == top]
    persons = {(c.get('dateOfBirth'), c.get('nationality')) for c in best if c.get('dateOfBirth')}
    undated = [c for c in best if not c.get('dateOfBirth')]
    if len(persons) == 1:
        dob, noc = persons.pop()
        ids = [c for c in cands if c.get('dateOfBirth') == dob and c.get('nationality') == noc]
        # profils sans date de naissance mais même nom/nation : rattachés s'ils existent
        ids += [c for c in undated if c.get('nationality') == noc]
        return ids, 'ok', [c for _, c in scored[:5]]
    if not persons and len(best) == 1:
        return best, 'ok', [c for _, c in scored[:5]]
    return None, 'ambigu', [c for _, c in scored[:5]]


def fetch_results(sess, ids):
    keep, ow, seen, failed = [], [], set(), []
    for c in ids:
        rj, why = get(sess, f"{BASE}/athletes/{c['id']}/results", retries=2)
        if rj is None:
            failed.append((c['id'], why))
            continue
        for r in rj.get('Results', []):
            sig = (r.get('SportCode'), r.get('DisciplineName'), r.get('Date'), r.get('Time'), r.get('PhaseName'))
            if sig in seen:
                continue
            seen.add(sig)
            if r.get('SportCode') == 'SW' and DIST_RE.search(r.get('DisciplineName') or ''):
                keep.append({k: r.get(k) for k in ('DisciplineName', 'Date', 'Time', 'Points', 'CompetitionName',
                                                    'CompetitionType', 'CompetitionCountry', 'CompetitionCity', 'PhaseName', 'Rank')})
            elif r.get('SportCode') == 'OW':
                ow.append({k: r.get(k) for k in ('DisciplineName', 'Date', 'Time', 'Rank', 'CompetitionName', 'CompetitionCity')})
        time.sleep(0.4)
    if len(failed) == len(ids):
        return None, None, failed[0][1]
    return keep, ow, 'ok'


def main():
    data = json.load(open(OUT))
    sess = requests.Session()
    sess.headers.update(HEADERS)
    todo = []
    for k, e in data['swimmers'].items():
        if e.get('passe') != 2:
            todo.append(k)
    print(len(todo), 'a retraiter', flush=True)
    for i, k in enumerate(todo, 1):
        e = data['swimmers'][k]
        sw = e['base']
        if not sw.get('noc') or not split_nom(sw['nom'])[0]:
            e['status'] = 'introuvable'
            e['note'] = 'nom/NOC inexploitable dans la base'
            continue
        cands = search_all(sess, sw)
        ids, status, top = resolve(cands, sw)
        new = {'base': sw, 'status': status, 'passe': 2,
               'candidats': [{x: c.get(x) for x in ('id', 'fullName', 'dateOfBirth', 'nationality', 'gender')} for c in top]}
        if ids:
            keep, ow, why = fetch_results(sess, ids)
            if keep is None:
                new['status'] = f'erreur_resultats_{why}'
            else:
                c = ids[0]
                new['athlete'] = {x: c.get(x) for x in ('id', 'fullName', 'firstName', 'lastName', 'dateOfBirth', 'nationality', 'gender')}
                new['athlete']['ids_fusionnes'] = [x['id'] for x in ids]
                new['results'], new['ow'] = keep, ow
        prev = e.get('athlete', {}).get('fullName')
        data['swimmers'][k] = new
        print(f"[{i}/{len(todo)}] {sw['nom']} ({sw['noc']}) -> {new['status']}"
              f"{' ' + new['athlete']['fullName'] + ' ' + str(new['athlete']['dateOfBirth']) + ' ids=' + str(new['athlete']['ids_fusionnes']) if ids and 'athlete' in new else ''}"
              f"{' (avant: ' + prev + ')' if prev else ''}", flush=True)
        json.dump(data, open(OUT, 'w'), ensure_ascii=False)
        time.sleep(random.uniform(0.3, 0.7))
    from collections import Counter
    print('BILAN', Counter(v['status'] for v in data['swimmers'].values()), flush=True)


if __name__ == '__main__':
    main()
