"""Stratégie ponton : placement moyen aux jalons 20/40/60/80/100 % selon le résultat final (top5 / hors5).
vz_norm = vitesse du tour du nageur / vitesse médiane du peloton sur ce tour (1.00 = vitesse du peloton),
moyennée sur les courses du groupe."""
import statistics

JALONS = (20, 40, 60, 80, 100)


def lap_for(dist_cumul, pct):
    target = pct / 100 * dist_cumul[-1]
    return min(range(len(dist_cumul)), key=lambda i: (abs(dist_cumul[i] - target), i))


def storage_type(co):
    """'cumul' si vit = dist_cumul/temps cumulé (écarts recalculés cohérents), sinon 'tour'."""
    dc, errs = co['dist_cumul'], []
    for i in range(co['nb_tours']):
        t = [(dc[i] / n['vit'][i], n['ecart'][i]) for n in co['nageurs']
             if n.get('vit') and n['vit'][i] and n.get('ecart') and n['ecart'][i] is not None]
        if t:
            mn = min(x for x, _ in t)
            errs += [abs((x - mn) - e) for x, e in t]
    return 'cumul' if errs and statistics.median(errs) < 1 else 'tour'


def lap_speeds(vit, dists, dist_cumul, kind):
    if kind == 'tour':
        return list(vit)
    out, prev = [], 0.0
    for i, v in enumerate(vit):
        if not v:
            out.append(None)
            prev = None
            continue
        t = dist_cumul[i] / v
        out.append(dists[i] / (t - prev) if prev is not None and t > prev else (v if i == 0 else None))
        prev = t
    return out


def build_ref(courses_json, key):
    """Par course : type de stockage et vitesse médiane du peloton à chaque tour."""
    ref = {}
    for sheet, co in courses_json[key].items():
        kind = storage_type(co)
        laps = [lap_speeds(n.get('vit') or [], co['dists'], co['dist_cumul'], kind) for n in co['nageurs'] if n.get('vit')]
        med = []
        for i in range(co['nb_tours']):
            vals = [l[i] for l in laps if i < len(l) and l[i]]
            med.append(statistics.median(vals) if vals else None)
        ref[sheet] = {'type': kind, 'med': med}
    return ref


def eligible(cc):
    pt = cc.get('positions_tour') or []
    return cc.get('format') == '10km' and pt and cc.get('rang') is not None and cc.get('dist_cumul')


def compute(courses, ref):
    cs = [cc for cc in courses if eligible(cc)]
    if not cs:
        return None
    out = {}
    for grp, sel in (('top5', [c for c in cs if c['rang'] <= 5]), ('hors5', [c for c in cs if c['rang'] > 5])):
        rows = []
        if sel:
            for pct in JALONS:
                ps, rs, nbs = [], [], []
                for c in sel:
                    i = lap_for(c['dist_cumul'], pct)
                    p = c['positions_tour'][i] if i < len(c['positions_tour']) else None
                    if p is None:
                        continue
                    ps.append(p)
                    nbs.append(c.get('nb_nageurs') or 0)
                    r = ref.get(c['sheet'])
                    vt = c.get('vitesses_tour') or []
                    if r and len(vt) == len(c['dist_cumul']):
                        lv = lap_speeds(vt, c['dists'], c['dist_cumul'], r['type'])
                        if lv[i] and r['med'][i]:
                            rs.append(lv[i] / r['med'][i])
                if ps:
                    rows.append({'pct': pct, 'pos_moy': round(sum(ps) / len(ps), 1), 'nb_moy': round(sum(nbs) / len(nbs), 1),
                                 'vz_norm': round(sum(rs) / len(rs), 4) if rs else None, 'n_courses': len(ps)})
        out[grp] = rows
    return out
