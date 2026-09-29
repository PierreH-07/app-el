"""Stratégie ponton : placement moyen aux jalons 20/40/60/80/100 % selon le résultat final (top5 / hors5)."""
JALONS = (20, 40, 60, 80, 100)


def lap_for(dist_cumul, pct):
    target = pct / 100 * dist_cumul[-1]
    return min(range(len(dist_cumul)), key=lambda i: (abs(dist_cumul[i] - target), i))


def eligible(cc):
    pt = cc.get('positions_tour') or []
    return cc.get('format') == '10km' and pt and cc.get('rang') is not None and cc.get('dist_cumul')


def compute(courses):
    cs = [cc for cc in courses if eligible(cc)]
    if not cs:
        return None
    out = {}
    for grp, sel in (('top5', [c for c in cs if c['rang'] <= 5]), ('hors5', [c for c in cs if c['rang'] > 5])):
        rows = []
        if sel:
            for pct in JALONS:
                ps, vs, nbs = [], [], []
                for c in sel:
                    i = lap_for(c['dist_cumul'], pct)
                    p = c['positions_tour'][i] if i < len(c['positions_tour']) else None
                    if p is None:
                        continue
                    ps.append(p)
                    nbs.append(c.get('nb_nageurs') or 0)
                    vt = c.get('vitesses_tour') or []
                    if i < len(vt) and vt[i] is not None:
                        vs.append(vt[i])
                if ps:
                    rows.append({'pct': pct, 'pos_moy': round(sum(ps) / len(ps), 1), 'nb_moy': round(sum(nbs) / len(nbs), 1),
                                 'vz_norm': round(sum(vs) / len(vs), 4) if vs else None, 'n_courses': len(ps)})
        out[grp] = rows
    return out
