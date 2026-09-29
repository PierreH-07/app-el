"""Fusion des doublons de nageurs (même athlète WA sous plusieurs orthographes) dans toute la base.
Lit les originaux (branche data + HTML), écrit dans dedup/. Mode --dry : rapport seulement."""
import json, os, re, sys, unicodedata
from collections import defaultdict, Counter
import os as _os
SCR = _os.environ.get('WA_WORK', _os.getcwd())
DATA = _os.environ.get('WA_DATA', _os.path.join(SCR, 'data'))
APP = _os.environ.get('WA_APP', _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))


OUT = f'{SCR}/dedup'
HTMLS = ['Ponton10km.html', 'ponton_ko_setubal2026.html']


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r"[-'’.]", ' ', s).upper().split())


def split_nom(nom):
    toks = nom.split()
    lu = max((i for i, t in enumerate(toks) if t.isupper() and len(t) > 1 and not t.endswith('.')), default=0)
    return ' '.join(toks[:lu + 1]), ' '.join(toks[lu + 1:])


def load():
    return (json.load(open(f'{DATA}/resultats_10km_nageurs_el.json')),
            json.load(open(f'{DATA}/resultats_ko_el.json')),
            json.load(open(f'{DATA}/resultats_10km_courses_el.json')),
            {f: open(f'{APP}/{f}', encoding='utf-8').read() for f in HTMLS})


def ko_race_lists(co):
    for p in ('finale', 'placement_finale', 'demi', 'placement_demi'):
        if co.get(p):
            yield p, co[p]
    for s, l in (co.get('series') or {}).items():
        yield f'series/{s}', l


def occurrences(n10, ko, cr, html, g, nom):
    occ = Counter()
    occ['fiche10'] = sum(1 for x in n10['DATA_' + g] if x['nom'] == nom)
    occ['bib'] = sum(1 for x in n10['DATA_' + g] if x['nom'] == nom and x.get('bib') is not None)
    occ['ficheKO'] = sum(1 for x in ko['DATA_' + g] if x['nom'] == nom)
    occ['courses10'] = sum(1 for co in cr['C' + g].values() for n in co['nageurs'] if n['nom'] == nom)
    occ['histKO'] = len(ko['KO_HF' if g == 'F' else 'KO_HH'].get(nom, []))
    occ['coursesKO'] = sum(1 for k, co in ko['KO_DATA'].items() if k.endswith('_' + g.lower())
                           for _, l in ko_race_lists(co) for n in l if n['nom'] == nom)
    occ['startlist'] = sum(1 for t in html.values() for m in re.finditer(r'STARTLIST_' + g + r'\s*=\s*\[(.*?)\];', t, re.S)
                           if f"nom:'{nom}'" in m.group(1))
    return occ


def groups():
    raw = json.load(open(f'{SCR}/wa_raw.json'))['swimmers']
    by = defaultdict(list)
    for k, v in raw.items():
        if v.get('status') == 'ok':
            by[(v['base']['genre'], v['athlete']['id'])].append(v)
    return [(g, vs) for (g, _), vs in by.items() if len(vs) > 1]


def canonical(g, vs, n10, ko, cr, html):
    names = sorted({v['base']['nom'] for v in vs})
    occ = {n: occurrences(n10, ko, cr, html, g, n) for n in names}
    cands = [n for n in names if occ[n]['startlist']] or names
    full = [n for n in cands if not any(t.endswith('.') for t in n.split())]
    cands = full or cands
    cands.sort(key=lambda n: (-occ[n]['startlist'], -occ[n]['bib'], -sum(occ[n].values()), -len(n)))
    best = cands[0]
    last, first = split_nom(best)
    wa_first = vs[0]['athlete'].get('firstName') or ''
    f0 = first.rstrip('.')
    if wa_first and f0 and norm(wa_first).startswith(norm(f0)) and norm(wa_first) != norm(f0):
        best = f'{last} {wa_first}'
    return best, names, occ


def plan():
    n10, ko, cr, html = load()
    out = []
    for g, vs in groups():
        can, names, occ = canonical(g, vs, n10, ko, cr, html)
        out.append({'genre': g, 'wa': vs[0]['athlete']['fullName'], 'wa_id': vs[0]['athlete']['id'],
                    'canonique': can, 'variantes': names, 'occ': {n: dict(o) for n, o in occ.items()}})
    return out


def apply(pl):
    n10, ko, cr, html = load()
    rename = {}
    for p in pl:
        for n in p['variantes']:
            if n != p['canonique']:
                rename[(p['genre'], n)] = p['canonique']
    log, collisions = [], []

    def rn(g, nom):
        return rename.get((g, nom), nom)

    # 1) fiches 10 km et KO : fusion
    def merge_fiches(lst, g, src):
        by = defaultdict(list)
        for x in lst:
            by[rn(g, x['nom'])].append(x)
        new = []
        seen = set()
        for x in lst:
            c = rn(g, x['nom'])
            if c in seen:
                continue
            seen.add(c)
            grp = by[c]
            prim = max(grp, key=lambda y: (y['nom'] == c, y.get('bib') is not None, len(y.get('courses') or []), len(y)))
            m = dict(prim)
            aliases = sorted({y['nom'] for y in grp if y['nom'] != c} | ({prim['nom']} - {c}))
            m['nom'] = c
            for y in grp:
                if y is prim:
                    continue
                for k, v in y.items():
                    if k in ('nom', 'courses', 'strategie', 'bib'):
                        continue
                    if m.get(k) in (None, [], {}, 0) and v not in (None, [], {}, 0):
                        m[k] = v
                for d in (400, 800, 1500):
                    ty, tm = y.get(f't{d}'), m.get(f't{d}')
                    from wa_pool import to_sec
                    sy, sm = to_sec(ty) if ty else None, to_sec(tm) if tm else None
                    if sy and (not sm or sy < sm):
                        m[f't{d}'], m[f'v{d}'] = ty, y.get(f'v{d}')
                if 'courses' in m or 'courses' in y:
                    have = {cc.get('sheet') for cc in (m.get('courses') or [])}
                    m['courses'] = list(m.get('courses') or []) + [cc for cc in (y.get('courses') or []) if cc.get('sheet') not in have]
            if aliases:
                m['alias'] = sorted(set(m.get('alias') or []) | set(aliases))
            if len(grp) > 1 or aliases:
                log.append(dict(fichier=src, canonique=c, fusionnes=[y['nom'] for y in grp],
                                courses=len(m.get('courses') or []) if 'courses' in m else None))
            new.append(m)
        return new

    for g in ('F', 'H'):
        n10['DATA_' + g] = merge_fiches(n10['DATA_' + g], g, f'10km/DATA_{g}')
        ko['DATA_' + g] = merge_fiches(ko['DATA_' + g], g, f'KO/DATA_{g}')
        # 2) historique KO
        hk = 'KO_HF' if g == 'F' else 'KO_HH'
        newh = {}
        for nom, l in ko[hk].items():
            c = rn(g, nom)
            if c in newh:
                have = {(h.get('l'), h.get('d')) for h in newh[c]}
                add = [h for h in l if (h.get('l'), h.get('d')) not in have]
                newh[c] = newh[c] + add
                log.append(dict(fichier=f'KO/{hk}', canonique=c, fusionnes=[nom], courses=len(newh[c])))
            else:
                newh[c] = list(l)
        ko[hk] = newh
        # 3) courses 10 km
        for key, co in cr['C' + g].items():
            names = Counter(rn(g, n['nom']) for n in co['nageurs'])
            for n in co['nageurs']:
                n['nom'] = rn(g, n['nom'])
            dropped = []
            for c, k in names.items():
                if k > 1:
                    rows = [n for n in co['nageurs'] if n['nom'] == c]
                    others = Counter(n.get('rang') for n in co['nageurs'] if n['nom'] != c)
                    if all(r.get('pos') == rows[0].get('pos') for r in rows):
                        bad = [r for r in rows if others.get(r.get('rang'))]
                        bad = bad[:len(rows) - 1] if len(bad) >= len(rows) else bad
                    else:
                        bad = sorted(rows, key=lambda r: -abs((r.get('pos') or [0])[-1] - (r.get('rang') or 0)))[:len(rows) - 1]
                    keep = [r for r in rows if r not in bad][0]
                    for b in bad:
                        co['nageurs'].remove(b)
                        dropped.append(c)
                    collisions.append(dict(course=f'C{g}/{key}', nom=c,
                                           supprimees=[(b.get('rang'), b.get('pos')) for b in bad],
                                           conservee=(keep.get('rang'), keep.get('pos'))))
                    # synchronise la fiche nageur (positions_tour = pos, vitesses_tour = vit)
                    for x in n10['DATA_' + g]:
                        if rn(g, x['nom']) == c:
                            for cc in x.get('courses') or []:
                                if cc.get('sheet') == key and (cc.get('positions_tour') != keep.get('pos') or cc.get('rang') != keep.get('rang')):
                                    log.append(dict(fichier=f'10km/DATA_{g}', canonique=c, fusionnes=[],
                                                    courses=f"{key}: positions_tour {cc.get('positions_tour')} -> {keep.get('pos')}"))
                                    cc['positions_tour'], cc['vitesses_tour'], cc['rang'] = keep.get('pos'), keep.get('vit'), keep.get('rang')
            for tour in co.get('groupes') or []:
                for grp in tour:
                    mem = [rn(g, m) for m in grp.get('membres') or []]
                    uniq = list(dict.fromkeys(mem))
                    grp['membres'] = uniq
                    if len(uniq) != len(mem):
                        grp['n'] = len(uniq)
            if dropped:
                co['nb'] = len(co['nageurs'])
    # resynchronise les fiches fusionnées sur les courses (référence) : positions_tour = pos, vitesses_tour = vit
    for g in ('F', 'H'):
        idx = {(key, x['nom']): x for key, co in cr['C' + g].items() for x in co['nageurs']}
        for f in n10['DATA_' + g]:
            if not f.get('alias'):
                continue
            for cc in f.get('courses') or []:
                r = idx.get((cc.get('sheet'), f['nom']))
                if r and (cc.get('positions_tour') != r.get('pos') or cc.get('rang') != r.get('rang')):
                    log.append(dict(fichier=f'10km/DATA_{g}', canonique=f['nom'], fusionnes=[],
                                    courses=f"{cc['sheet']}: resynchronise sur la course (rang {cc.get('rang')} -> {r.get('rang')})"))
                    cc['positions_tour'], cc['vitesses_tour'], cc['rang'] = r.get('pos'), r.get('vit'), r.get('rang')
    for key, co in ko['KO_DATA'].items():
        g = 'F' if key.endswith('_f') else 'H'
        for part, l in ko_race_lists(co):
            names = Counter(rn(g, n['nom']) for n in l)
            for n in l:
                n['nom'] = rn(g, n['nom'])
            for c, k in names.items():
                if k > 1:
                    collisions.append(dict(course=f'KO_DATA/{key}/{part}', nom=c, lignes=[n.get('rang') for n in l if n['nom'] == c]))
    # 4) STARTLIST HTML
    for f, t in html.items():
        for (g, old), new in rename.items():
            pat = re.compile(r"(STARTLIST_" + g + r"\s*=\s*\[)(.*?)(\];)", re.S)
            m = pat.search(t)
            if m and f"nom:'{old}'" in m.group(2):
                blk = m.group(2).replace(f"nom:'{old}'", f"nom:'{new}'")
                t = t[:m.start(2)] + blk + t[m.end(2):]
                log.append(dict(fichier=f, canonique=new, fusionnes=[old], courses=None))
        html[f] = t
    return n10, ko, cr, html, log, collisions, rename


if __name__ == '__main__':
    pl = plan()
    for p in pl:
        print(f"{p['genre']} {p['canonique']!r:38s} <- {[n for n in p['variantes'] if n != p['canonique']]}")
    n10, ko, cr, html, log, col, rename = apply(pl)
    print('\ncollisions (meme course, deux variantes):', len(col))
    for c in col:
        print('  ', c)
    if '--dry' not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        dump = lambda o, f: open(f, 'w', encoding='utf-8').write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))
        dump(n10, f'{OUT}/resultats_10km_nageurs_el.json')
        dump(ko, f'{OUT}/resultats_ko_el.json')
        dump(cr, f'{OUT}/resultats_10km_courses_el.json')
        for f, t in html.items():
            open(f'{OUT}/{f}', 'w', encoding='utf-8').write(t)
        json.dump({'plan': pl, 'log': log, 'collisions': col}, open(f'{OUT}/dedup_log.json', 'w'), ensure_ascii=False, indent=1)
        print('ecrit dans', OUT)
