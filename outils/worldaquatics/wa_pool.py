"""Classification bassin 50m/25m des résultats WA via les points (base implicite = t*(pts/1000)^(1/3))."""
import json, re, statistics
from datetime import date

DIST_RE = re.compile(r"\b(200|400|800|1500)m\s+Freestyle\b", re.I)
TOL = 0.005  # 0,5 % autour de la base 50m de référence


def to_sec(t):
    if not t or not re.match(r'^\d', str(t)):
        return None
    t = str(t).replace(',', '.')
    p = t.split(':')
    try:
        if len(p) == 1:
            s = float(p[0])
        elif len(p) == 2:
            s = int(p[0]) * 60 + float(p[1])
        else:
            s = int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    except ValueError:
        return None
    return s if s > 0 else None


def parse(r):
    m = DIST_RE.search(r.get('DisciplineName') or '')
    sec = to_sec(r.get('Time'))
    try:
        d = date.fromisoformat(r.get('Date') or '')
    except ValueError:
        d = None
    if not m or sec is None or d is None:
        return None
    g = 'F' if (r.get('DisciplineName') or '').startswith('Women') else 'H'
    comp = r.get('CompetitionName') or ''
    label = '25m' if '(25m)' in comp else ('50m' if '(50m)' in comp else None)
    pts = r.get('Points')
    base = sec * (pts / 1000) ** (1 / 3) if pts else None
    return {'dist': int(m.group(1)), 'genre': g, 'sec': sec, 'time': r.get('Time'), 'date': d,
            'points': pts, 'label': label, 'base': base, 'competition': comp,
            'city': r.get('CompetitionCity'), 'country': r.get('CompetitionCountry')}


def build_refs(all_parsed):
    """Base de référence par (genre, dist, année, bassin) = médiane des bases implicites des résultats étiquetés."""
    buckets = {}
    for p in all_parsed:
        if p['label'] and p['base']:
            buckets.setdefault((p['genre'], p['dist'], p['date'].year, p['label']), []).append(p['base'])
    return {k: (statistics.median(v), len(v)) for k, v in buckets.items() if len(v) >= 3}


def ref_for(refs, g, dist, year, pool):
    for dy in (0, -1, 1, -2, 2):
        v = refs.get((g, dist, year + dy, pool))
        if v:
            return v[0]
    return None


def classify(p, refs):
    """Renvoie ('50m'|'25m'|'non_verifie'|'conflit', motif)."""
    if p['label'] == '25m':
        return '25m', 'etiquette (25m)'
    if not p['base']:
        return 'non_verifie', 'pas de points WA'
    r50 = ref_for(refs, p['genre'], p['dist'], p['date'].year, '50m')
    r25 = ref_for(refs, p['genre'], p['dist'], p['date'].year, '25m')
    if r50 is None:
        return 'non_verifie', 'pas de base de reference 50m'
    d50 = abs(p['base'] - r50) / r50
    d25 = abs(p['base'] - r25) / r25 if r25 else 9
    by_points = '50m' if (d50 <= TOL and d50 < d25) else ('25m' if d25 < d50 else 'non_verifie')
    if p['label'] == '50m' and by_points != '50m':
        return 'conflit', f'etiquette 50m mais points -> {by_points}'
    if by_points == '50m':
        return '50m', 'etiquette (50m)' if p['label'] == '50m' else 'points WA coherents 50m'
    return by_points, 'points WA coherents 25m' if by_points == '25m' else f'ecart base {d50:.2%}'
