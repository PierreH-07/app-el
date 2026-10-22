"""Import des courses d'eau libre World Aquatics (temps de passage) dans la base de l'application.

- complète les courses 5/10 km déjà présentes (nageurs manquants, temps WA pour tous les nageurs retrouvés) ;
- ajoute les courses absentes qui ont des temps intermédiaires (seniors + juniors) ;
- ajoute les KO listés dans KO_NOUVEAUX (temps par manche).
Positions, écarts, groupes (seuil 3 s), fiches nageurs, historiques KO et stratégies sont recalculés.

Variables : WA_DATA (copie de la branche data, modifiée en place), WA_CACHE (cache des réponses WA),
WA_LOG (journal JSON). Usage : python ow_import.py [--dry]
"""
import difflib, json, os, re, sys, time, unicodedata, statistics
from datetime import date, datetime, timedelta
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategie as S

DATA = os.environ.get('WA_DATA', 'data')
CACHE = os.environ.get('WA_CACHE', 'wa_cache')
LOG = os.environ.get('WA_LOG', 'ow_import_log.json')
B = 'https://api.worldaquatics.com/fina'
H = {'origin': 'https://www.worldaquatics.com', 'referer': 'https://www.worldaquatics.com/', 'user-agent': 'Mozilla/5.0'}
SESS = requests.Session(); SESS.headers.update(H)

# distances par tour lues dans les bulletins d'information WA (rubrique « Venue & course information »)
BULLETINS = {('Setubal', 2026): 1660}
KO_NOUVEAUX = [('Setubal', 2025), ('Setubal', 2026)]
SEUIL_GROUPE = 3.0
SANITY = []
CITY_FR = {'Setubal': 'Sétubal', 'Somabay': 'Soma Bay', 'Golfo Aranci': 'Golfo Aranci', 'Singapore': 'Singapour',
           'Hong Kong': 'Hong Kong', 'NEOM': 'Neom', 'Abu Dhabi': 'Abu Dhabi', 'Mahé': 'Mahé', 'Alghero': 'Alghero',
           'Santa Fe': 'Santa Fe', 'Budapest': 'Budapest', 'Fukuoka': 'Fukuoka', 'Doha': 'Doha', 'Paris': 'Paris',
           'Tokyo': 'Tokyo', 'Eilat': 'Eilat', 'Funchal': 'Funchal', 'Ibiza': 'Ibiza', 'Ohrid': 'Ohrid'}
APPCITY = {'somabay': 'Somabay', 'golfoaranci': 'Golfo Aranci', 'golfo': 'Golfo Aranci', 'singapour': 'Singapore',
           'setubal': 'Setubal', 'tokoyo': 'Tokyo', 'tokyo': 'Tokyo', 'paris': 'Paris', 'doha': 'Doha', 'budapest': 'Budapest',
           'fukuoka': 'Fukuoka', 'funchal': 'Funchal', 'eilat': 'Eilat', 'ohrid': 'Ohrid', 'abudhabi': 'Abu Dhabi',
           'hkg': 'Hong Kong', 'neom': 'NEOM', 'ibiza': 'Ibiza'}


# ---------------------------------------------------------------- utilitaires
def get(path, params=None):
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r'[^A-Za-z0-9]+', '_', path + json.dumps(params or {}, sort_keys=True))[:180]
    f = os.path.join(CACHE, key + '.json')
    if os.path.exists(f):
        return json.load(open(f))
    for a in range(4):
        try:
            r = SESS.get(B + path, params=params, timeout=30)
            if r.status_code == 200:
                d = r.json(); json.dump(d, open(f, 'w'), ensure_ascii=False); time.sleep(0.3)
                return d
        except requests.RequestException:
            pass
        time.sleep(2 + 2 * a)
    raise RuntimeError(f'WA injoignable : {path}')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r"[-'’.]", ' ', s).upper().split())


def split_nom(nom):
    toks = nom.split()
    lu = max((i for i, t in enumerate(toks) if t.isupper() and len(t) > 1 and not t.endswith('.')), default=0)
    return ' '.join(toks[:lu + 1]), ' '.join(toks[lu + 1:])


def tsec(t):
    if not t or not re.match(r'^\d', str(t)):
        return None
    v = 0.0
    for x in str(t).split(':'):
        v = v * 60 + float(x)
    return v


def fmt_t(s):
    m, r = divmod(round(s, 1), 60)
    return f'{int(m)}:{r:04.1f}'


def name_match(app_nom, app_noc, last, first, nat):
    al, af = split_nom(app_nom)
    at, wt = set(norm(al).split()), set(norm(last).split())
    if not at or not (at <= wt or wt <= at):
        return False
    if app_noc and nat and app_noc != nat and app_noc not in ('NAB', 'AIN', 'ROC', 'RUS', 'UNK') and nat not in ('AIN', 'NAB'):
        return False
    fa, fw = norm(af).split(), norm(first).split()
    if not fa or not fw:
        return True
    a0, w0 = fa[0], fw[0]
    return a0 == w0 or a0.startswith(w0) or w0.startswith(a0) or ''.join(fa) == ''.join(fw)


# ---------------------------------------------------------------- inventaire WA
def wa_events():
    comps = get('/competitions', {'pageSize': 200, 'venueDateFrom': '2021-01-01T00:00:00+00:00',
                                  'venueDateTo': '2026-12-31T00:00:00+00:00', 'disciplines': 'OW', 'group': 'FINA'})['content']
    out = []
    for c in comps:
        if c['name'].startswith('CANCELLED'):
            continue
        city = (c.get('location') or {}).get('city', '')
        ev = get(f"/competitions/{c['id']}/events")
        for sp in ev.get('Sports', []):
            for e in sp.get('DisciplineList', []):
                dn = e.get('DisciplineName') or ''
                m = re.match(r"(Women|Men)'s (\d+(?:\.\d+)?)km( Knockout Sprint)?(?: \((\d+) ?- ?(\d+)\))?$", dn)
                if not m:
                    continue
                d = get(f"/events/{e['Id']}")
                if d.get('SportCode') != 'OW':
                    continue
                out.append(dict(comp=c, city=city, year=int(c['dateFrom'][:4]), genre='F' if m.group(1) == 'Women' else 'H',
                                dist=float(m.group(2)), ko=bool(m.group(3)), junior=('Junior' in c['name']), age=m.group(4), age2=m.group(5),
                                disc=dn, ev=d))
    return out


def finals(ev):
    for h in ev['ev'].get('Heats') or []:
        if h.get('PhaseName') == 'Finals' and h.get('Results'):
            return h
    return None


def wa_cum(r):
    """{Order: secondes cumulées} + temps final (numérotation WA brute)."""
    d = {s['Order']: tsec(s.get('Time')) for s in r.get('Splits') or [] if tsec(s.get('Time'))}
    return d, tsec(r.get('Time'))


def align(res):
    """Points de passage alignés. Les nageurs ayant le jeu complet de points gardent la numérotation WA et
    servent de référence (fraction médiane temps/temps final par point) ; pour les autres, WA renumérote
    parfois quand un point manque : leurs temps sont recalés sur les références par alignement ordonné.
    Renvoie (centres, {rid: ({point: s}, final)}) ; les points sont indexés 0..n-1 (hors arrivée)."""
    data = {rid(r): wa_cum(r) for r in res}
    fins = [fin for _, fin in data.values() if fin]
    med = statistics.median(fins) if fins else None
    bad_fin = {k for k, (d, fin) in data.items() if fin and med and fin > 1.5 * med}  # ex. 9:59:59 fictif
    data = {k: ((d, None) if k in bad_fin else (d, fin)) for k, (d, fin) in data.items()}
    nmax = max([len(d) for d, _ in data.values()] or [0])
    full = [(d, fin) for d, fin in data.values() if len(d) == nmax and fin]
    orders = sorted({o for d, _ in full for o in d})
    centers, keep = [], []
    for o in orders:
        v = [d[o] / fin for d, fin in full if d.get(o)]
        c = statistics.median(v)
        if c < 0.995:  # le dernier point est parfois l'arrivée
            centers.append(c); keep.append(o)
    out = {}
    for k, (d, fin) in data.items():
        if not fin:  # temps final inconnu : numérotation WA conservée
            pos = {o: i for i, o in enumerate(keep)}
            out[k] = ({pos[o]: t for o, t in d.items() if o in pos}, None); continue
        if len(d) == nmax:
            out[k] = ({i: d[o] for i, o in enumerate(keep) if d.get(o)}, fin); continue
        xs = sorted(t for t in d.values() if t / fin < 0.995)
        n, m = len(xs), len(centers)
        if n == 0 or n > m:
            out[k] = ({}, fin); continue
        INF = float('inf')
        # dp[i][j] : coût minimal en plaçant les i premiers temps sur des points < j
        dp = [[INF] * (m + 1) for _ in range(n + 1)]
        for j in range(m + 1):
            dp[0][j] = 0.0
        for i in range(1, n + 1):
            for j in range(i, m + 1):
                dp[i][j] = min(dp[i][j - 1], dp[i - 1][j - 1] + abs(xs[i - 1] / fin - centers[j - 1]))
        a, i, j = {}, n, m
        while i > 0:
            if dp[i][j] == dp[i][j - 1] and j > i:
                j -= 1
            else:
                a[j - 1] = xs[i - 1]; i -= 1; j -= 1
        if any(abs(t / fin - centers[p]) > 0.04 for p, t in a.items()):
            a = {p: t for p, t in a.items() if abs(t / fin - centers[p]) <= 0.04}
        out[k] = (a, fin)
    return centers, out


def pick(centers, targets, dists_full):
    """Fins de tour = points les plus proches des fractions cibles ; un point introuvable fusionne deux tours."""
    mp, dists, acc, used = [], [], 0, set()
    for i, d in enumerate(dists_full):
        acc += d
        if i == len(dists_full) - 1:
            mp.append('final'); dists.append(acc); break
        t = targets[i]
        k = min((j for j in range(len(centers)) if j not in used), key=lambda j: abs(centers[j] - t), default=None)
        if k is not None and abs(centers[k] - t) < 0.04 and (not mp or mp[-1] == 'final' or k > mp[-1]):
            mp.append(k); used.add(k); dists.append(acc); acc = 0
    return mp, dists


def rid(r):
    return r['ResultId'] + str(r.get('Bib'))


# ---------------------------------------------------------------- base de l'application
def load():
    j = lambda f: json.load(open(os.path.join(DATA, f), encoding='utf-8'))
    return j('resultats_10km_courses_el.json'), j('resultats_10km_nageurs_el.json'), j('resultats_ko_el.json'), \
        (j('historique_bassin_el.json') if os.path.exists(os.path.join(DATA, 'historique_bassin_el.json')) else None)


def app_city(key):
    x = re.sub(r'^(cdm|chm|che|jo|chmj)_', '', key.lower())
    x = re.sub(r'\d{2}(_[fh]|_5k|_10k|_7_5k)?$', '', x)
    return APPCITY.get(x)


class Names:
    """Rattache un résultat WA à un nom déjà utilisé dans la base (fiches + alias + courses), sinon crée « NOM Prénom »."""

    def __init__(self, cr, nag, ko):
        self.pool = {'F': {}, 'H': {}}
        for g in 'FH':
            for x in nag['DATA_' + g] + ko['DATA_' + g]:
                for nm in [x['nom']] + (x.get('alias') or []):
                    self.pool[g].setdefault(x['nom'], x.get('noc'))
            for co in cr['C' + g].values():
                for x in co['nageurs']:
                    self.pool[g].setdefault(x['nom'], x.get('noc'))
            for k, co in ko['KO_DATA'].items():
                if co.get('genre') == g:
                    for part in ('finale', 'demi'):
                        for x in co.get(part) or []:
                            self.pool[g].setdefault(x['nom'], x.get('noc'))
                    for lst in (co.get('series') or {}).values():
                        for x in lst:
                            self.pool[g].setdefault(x['nom'], x.get('noc'))
        self.alias = {g: {norm(a): x['nom'] for x in nag['DATA_' + g] for a in x.get('alias') or []} for g in 'FH'}

    def resolve(self, g, r, local=None):
        last, first, nat = r.get('LastName') or '', r.get('FirstName') or '', r.get('NAT')
        full = norm(f'{last} {first}')
        if full in self.alias[g]:
            return self.alias[g][full]
        for cands in ((local or {}), self.pool[g]):
            exact = [n for n in cands if norm(n) == full]
            if exact:
                return exact[0]
            m = [n for n, noc in cands.items() if name_match(n, noc, last, first, nat)]
            if len(m) == 1:
                return m[0]
            if len(m) > 1:
                m.sort(key=lambda n: (-len(set(norm(n).split()) & set(full.split())), len(n)))
                return m[0]
        nom = f'{last} {first}'.strip()
        self.pool[g][nom] = nat
        return nom


# ---------------------------------------------------------------- calcul d'une course
def sane(cum, dists):
    """Temps intermédiaires incohérents (vitesse de tour hors [0,6 ; 2,2] m/s) : on ne garde que l'arrivée."""
    prev_t, acc = 0.0, 0
    for i, c in enumerate(cum):
        acc += dists[i]
        if c is None:
            continue
        if c <= prev_t or not (0.6 <= acc / (c - prev_t) <= 2.2):
            return [None] * (len(cum) - 1) + [cum[-1]], False
        prev_t, acc = c, 0
    return cum, True


def build_rows(points, dists, dist_cumul, kind, rows_in):
    """rows_in : [{nom, noc, rang, cum:[s|None]*nt, keep: dict}] -> lignes app avec pos/ecart/vit."""
    nt = len(dists)
    for r in rows_in:
        r['cum'], ok = sane(r['cum'], dists)
        if not ok:
            SANITY.append(r['nom'])
    for i in range(nt):
        valid = sorted([r for r in rows_in if r['cum'][i] is not None], key=lambda r: (r['cum'][i], r['rang'] or 999))
        mn = valid[0]['cum'][i] if valid else 0
        for k, r in enumerate(valid, 1):
            r.setdefault('pos', [None] * nt)[i] = k
            r.setdefault('ecart', [None] * nt)[i] = round(r['cum'][i] - mn, 1)
    out = []
    for r in sorted(rows_in, key=lambda r: (r['rang'] is None, r['rang'] or 0)):
        pos, ec = r.get('pos') or [None] * nt, r.get('ecart') or [None] * nt
        vit = []
        for i in range(nt):
            c = r['cum'][i]
            if kind == 'cumul':
                vit.append(round(dist_cumul[i] / c, 4) if c else None)
            else:
                prev = 0.0 if i == 0 else r['cum'][i - 1]
                vit.append(round(dists[i] / (c - prev), 4) if c and prev is not None and c > prev else None)
        row = dict(r.get('keep') or {})
        row.update({'nom': r['nom'], 'noc': r['noc'], 'rang': r['rang'], 'pos': pos, 'ecart': ec, 'vit': vit})
        row.setdefault('rv', None); row.setdefault('di', None)
        out.append(row)
    return out


def groupes(rows, nt):
    out = []
    for i in range(nt):
        rs = sorted([r for r in rows if r['pos'][i] is not None and r['ecart'][i] is not None], key=lambda r: r['pos'][i])
        gs, prev = [], None
        for r in rs:
            e = r['ecart'][i]
            if prev is None or e - prev > SEUIL_GROUPE:
                gs.append({'n': 0, 'ecart_fin': None, 'membres': []})
            gs[-1]['membres'].append(r['nom']); gs[-1]['n'] += 1; gs[-1]['ecart_fin'] = e; prev = e
        out.append(gs)
    return out


def app_cum(co, n, kind):
    dc, dl, cum, t = co['dist_cumul'], co['dists'], [], 0.0
    for i, v in enumerate(n.get('vit') or []):
        if not v:
            cum.append(None); t = None; continue
        if kind == 'cumul':
            cum.append(dc[i] / v)
        else:
            t = None if t is None else t + dl[i] / v
            cum.append(t)
    return cum + [None] * (co['nb_tours'] - len(cum))


def order_map(co, res, local_names, names, g, kind, al):
    """Pour chaque tour de l'app : point physique WA (index) ou 'final', calé sur les temps de l'app."""
    centers, A = al
    nt = co['nb_tours']
    pairs = []
    loc_noc = {k: v['row'].get('noc') for k, v in local_names.items()}
    for r in res:
        nom = names.resolve(g, r, loc_noc)
        if nom in local_names:
            pairs.append((app_cum(co, local_names[nom]['row'], kind), A[rid(r)]))
    mp, last = [], -1
    for i in range(nt):
        best = None
        for o in [x for x in range(len(centers)) if x > last] + ['final']:
            diffs = [abs(a[i] - (fin if o == 'final' else d.get(o))) for a, (d, fin) in pairs
                     if a[i] and (fin if o == 'final' else d.get(o))]
            if len(diffs) >= 3:
                md = statistics.median(diffs)
                if best is None or md < best[1]:
                    best = (o, md, len(diffs))
        if not best or best[1] > 3.0:
            return None, best
        mp.append(best[0])
        if best[0] != 'final':
            last = best[0]
    return mp, None


def cum_from_map(r, mp, al):
    d, fin = al[1][rid(r)]
    return [fin if o == 'final' else d.get(o) for o in mp]


# ---------------------------------------------------------------- traitement principal
def main(dry=False):
    cr, nag, ko, hist = load()
    names = Names(cr, nag, ko)
    evs = wa_events()
    log = {'completees': [], 'nouvelles': [], 'ignorees': [], 'ko': [], 'dates': [], 'fiches': 0, 'appariements': [], 'retires': []}
    used = set()
    lap_maps = {}  # (comp_id, genre, dist) -> (map, dists)

    # 1) courses existantes
    for g in 'FH':
        for key, co in cr['C' + g].items():
            dist = 5.0 if '5K' in key.upper() and '10K' not in key.upper() else 10.0
            yr = int(re.search(r'(20\d\d)', co['label']).group(1))
            cands = [e for e in evs if not e['ko'] and not e['junior'] and e['genre'] == g and e['dist'] == dist
                     and e['year'] == yr and e['city'] == app_city(key)]
            if len(cands) != 1:
                log['ignorees'].append(dict(course=f'C{g}/{key}', motif='pas d evenement WA unique')); continue
            e = cands[0]; h = finals(e)
            if not h or max(len(r.get('Splits') or []) for r in h['Results']) < 2:
                log['ignorees'].append(dict(course=f'C{g}/{key}', motif='pas de temps intermediaires sur WA')); continue
            used.add(e['ev']['Id'])
            kind = S.storage_type(co)
            local = {n['nom']: {'row': n} for n in co['nageurs']}
            res = [r for r in h['Results'] if r.get('Rank')]
            al = align(res)
            mp, why = order_map(co, res, local, names, g, kind, al)
            if mp is None:
                log['ignorees'].append(dict(course=f'C{g}/{key}', motif=f'calage des tours impossible {why}')); continue
            lap_maps[(e['comp']['id'], g, dist)] = (mp, co['dists'], al[0])
            loc_noc = {k: v['row'].get('noc') for k, v in local.items()}
            res_nom = [(r, names.resolve(g, r, loc_noc)) for r in res]
            # appariement de secours : orthographe différente, même rang (ou rang voisin) et même nation
            unm_app = [n for n in local if n not in {nm for _, nm in res_nom}]
            for i, (r, nm) in enumerate(res_nom):
                if nm in local or not unm_app:
                    continue
                best = None
                for a in unm_app:
                    ar = local[a]['row']
                    if ar.get('noc') not in (None, '', 'UNK') and r.get('NAT') and ar['noc'] != r['NAT']:
                        continue
                    sim = difflib.SequenceMatcher(None, norm(split_nom(a)[0]), norm(r.get('LastName'))).ratio()
                    fa, fw = norm(split_nom(a)[1]).split(), norm(r.get('FirstName')).split()
                    same_first = bool(fa and fw and (fa[0] == fw[0] or fa[0].startswith(fw[0]) or fw[0].startswith(fa[0])))
                    dr = abs((ar.get('rang') or 999) - r['Rank'])
                    # même rang + même prénom : changement de nom (mariage) ou orthographe différente
                    if (dr == 0 and (sim >= 0.5 or same_first)) or (dr <= 2 and sim >= 0.8) or sim == 1.0:
                        if best is None or (dr, -sim) < best[0]:
                            best = ((dr, -sim), a)
                if best:
                    res_nom[i] = (r, best[1]); unm_app.remove(best[1])
                    log['appariements'].append(dict(course=f'C{g}/{key}', app=best[1], wa=r['FullName']))
            rows, seen, added = [], set(), []
            for r, nom in res_nom:
                if nom in seen:
                    continue
                seen.add(nom)
                keep = {k: v for k, v in local[nom]['row'].items() if k in ('rv', 'di')} if nom in local else {}
                if nom not in local:
                    added.append(nom)
                cum = cum_from_map(r, mp, al)
                if nom in local:  # temps WA manquant : repli sur le temps de la base (même source)
                    ac = app_cum(co, local[nom]['row'], kind)
                    cum = [c if c is not None else ac[i] for i, c in enumerate(cum)]
                rows.append(dict(nom=nom, noc=r.get('NAT') or (local.get(nom, {}).get('row', {}).get('noc')),
                                 rang=r['Rank'], cum=cum, keep=keep, wa=True))
            unranked = {names.resolve(g, r, loc_noc): r.get('ScoringAbbr') or 'non classe'
                        for r in h['Results'] if not r.get('Rank')}
            wa_rk = {r['rang'] for r in rows}
            retires = []
            for nom, v in local.items():
                if nom in seen:
                    continue
                n = v['row']
                if nom in unranked:  # non classé sur WA (DSQ, DNF...) : le résultat officiel fait foi
                    retires.append(dict(nom=nom, rang_app=n.get('rang'), motif=f'WA : {unranked[nom]}')); continue
                if n.get('rang') in wa_rk:  # rang attribué à un autre nageur sur WA
                    retires.append(dict(nom=nom, rang_app=n.get('rang'), motif='absent de WA, rang attribue a un autre nageur')); continue
                rows.append(dict(nom=nom, noc=n.get('noc'), rang=n.get('rang'), cum=app_cum(co, n, kind),
                                 keep={k: n.get(k) for k in ('rv', 'di')}, wa=False))
            if retires:
                log['retires'].append(dict(course=f'C{g}/{key}', nageurs=retires))
            co['nageurs'] = build_rows(None, co['dists'], co['dist_cumul'], kind, rows)
            co['groupes'] = groupes(co['nageurs'], co['nb_tours'])
            co['nb'] = len(co['nageurs'])
            wd = datetime.strptime(h['Date'][:10], '%Y-%m-%d').strftime('%d/%m/%Y') if h.get('Date') else None
            if wd and wd != co.get('date'):
                log['dates'].append(dict(course=f'C{g}/{key}', avant=co.get('date'), apres=wd)); co['date'] = wd
            co['source_temps'] = 'World Aquatics'; co['wa_competition_id'] = e['comp']['id']; co['distance_km'] = dist
            log['completees'].append(dict(course=f'C{g}/{key}', ajoutes=added, nb=co['nb'], points=mp))

    # 2) nouvelles courses (5/10 km seniors + juniors) avec temps intermédiaires
    for e in evs:
        if e['ko'] or e['ev']['Id'] in used:
            continue
        h = finals(e)
        if not h:
            continue
        res = [r for r in h['Results'] if r.get('Rank')]
        nsp = max([len(r.get('Splits') or []) for r in res] or [0])
        if nsp < 2:
            continue
        g, dist, comp = e['genre'], e['dist'], e['comp']
        if dist > 10:
            continue
        city, yr = e['city'], e['year']
        ref = lap_maps.get((comp['id'], g, dist)) or lap_maps.get((comp['id'], 'H' if g == 'F' else 'F', dist))
        ref10 = lap_maps.get((comp['id'], g, 10.0)) or lap_maps.get((comp['id'], 'H' if g == 'F' else 'F', 10.0))
        al = align(res); centers = al[0]
        total = int(round(dist * 1000))
        if ref:  # même compétition, autre genre : même parcours
            mp_r, d_r, c_r = ref
            targets = [c_r[o] for o in mp_r[:-1]]
            mp, dists = pick(centers, targets, d_r); src = 'meme_competition'
        elif ref10 and dist < 10 and not e['junior']:  # 5 km d'un ChM : même boucle que le 10 km
            lap = round(statistics.median(ref10[1]))
            nl = max(1, round(total / lap))
            mp, dists = pick(centers, [(i + 1) / nl for i in range(nl - 1)], [lap] * (nl - 1) + [total - lap * (nl - 1)])
            src = 'meme_competition_10km'
        elif BULLETINS.get((city, yr)):
            lap = BULLETINS[(city, yr)]; nl = max(1, round(total / lap))
            mp, dists = pick(centers, [(i + 1) / nl for i in range(nl - 1)], [lap] * (nl - 1) + [total - lap * (nl - 1)])
            src = 'bulletin'
        else:  # tours égaux entre points de passage
            nl = len(centers) + 1
            base = total // nl
            mp, dists = list(range(len(centers))) + ['final'], [base] * (nl - 1) + [total - base * (nl - 1)]
            src = 'egal'
        dc = [sum(dists[:i + 1]) for i in range(len(dists))]
        typ = 'JO' if 'Olympic' in comp['name'] else ('CHMJ' if e['junior'] else ('CHM' if 'Championships' in comp['name'] else 'CDM'))
        sig = {'CDM': 'CdM', 'CHM': 'ChM', 'JO': 'JO', 'CHMJ': 'ChMJ'}[typ]
        dlab = f'{dist:g}'.replace('.', ',')
        suffix = '' if (typ == 'CDM' and dist == 10) else f' {dlab}K'
        age = f" {e['age']}-{e['age2']} ans" if e['age'] else ''
        label = f"{sig} {CITY_FR.get(city, city)} {yr}{suffix}{age}"
        other = 'H' if g == 'F' else 'F'
        key = next((k for k, c2 in cr['C' + other].items() if c2.get('wa_competition_id') == comp['id'] and c2.get('distance_km') == dist), None)
        if key is None:
            cityk = unicodedata.normalize('NFKD', CITY_FR.get(city, city)).encode('ascii', 'ignore').decode().replace(' ', '')
            key = f"{sig}_{cityk}{str(yr)[2:]}" + ('' if suffix == '' else '_' + f'{dist:g}'.replace('.', '_') + 'K')
        if key in cr['C' + g] and cr['C' + g][key].get('source_temps') != 'World Aquatics':
            key += '_wa'
        rows, seen = [], set()
        for r in res:
            nom = names.resolve(g, r)
            if nom in seen:
                continue
            seen.add(nom)
            rows.append(dict(nom=nom, noc=r.get('NAT'), rang=r['Rank'], cum=cum_from_map(r, mp, al)))
        nag_rows = build_rows(None, dists, dc, 'tour', rows)
        co = {'sheet': key, 'label': label, 'type': typ, 'date': datetime.strptime(h['Date'][:10], '%Y-%m-%d').strftime('%d/%m/%Y'),
              'conditions': None, 'nb_tours': len(dists), 'dists': dists, 'dist_cumul': dc, 'nb': len(nag_rows),
              'groupes': groupes(nag_rows, len(dists)), 'nageurs': nag_rows,
              'source_temps': 'World Aquatics', 'dists_source': src, 'vit_type': 'tour',
              'wa_competition_id': comp['id'], 'distance_km': dist}
        if e['junior']:
            co['categorie'] = 'junior'
        cr['C' + g][key] = co
        log['nouvelles'].append(dict(course=f'C{g}/{key}', label=label, nb=len(nag_rows), tours=len(dists), dists=src, points=mp))

    # 3) KO
    for (city, yr) in KO_NOUVEAUX:
        for e in [x for x in evs if x['ko'] and not x['junior'] and x['city'] == city and x['year'] == yr]:
            g = e['genre']; key = f"{re.sub(r'[^a-z]', '', city.lower())}{str(yr)[2:]}_{g.lower()}"
            if key in ko['KO_DATA']:
                continue
            ko['KO_DATA'][key] = build_ko(e, names, hist, nag)
            log['ko'].append(dict(course=key, label=ko['KO_DATA'][key]['label']))

    sync_fiches(cr, nag, ko, log)
    refs = {'F': S.build_ref(cr, 'CF'), 'H': S.build_ref(cr, 'CH')}
    for g in 'FH':
        for x in nag['DATA_' + g]:
            if 'strategie' in x:
                x['strategie'] = S.compute(x.get('courses') or [], refs[g])
    if hist:
        sync_hist(cr, hist)
    log['temps_incoherents_ecartes'] = SANITY
    json.dump(log, open(LOG, 'w'), ensure_ascii=False, indent=1)
    if not dry:
        for f, o in (('resultats_10km_courses_el.json', cr), ('resultats_10km_nageurs_el.json', nag), ('resultats_ko_el.json', ko),
                     ('historique_bassin_el.json', hist)):
            if o is not None:
                open(os.path.join(DATA, f), 'w', encoding='utf-8').write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))
    return log


# ---------------------------------------------------------------- KO
def pool_best(hist, g, nom, before):
    if not hist:
        return {}
    n = hist['nageurs'].get(f'{g}|{norm(nom)}')
    if not n:
        return {}
    lo = before.replace(year=before.year - 2)
    out = {}
    for d in (400, 800, 1500):
        ps = [p['s'] for p in n.get('perfs') or [] if p['d'] == d and p['bassin'] == '50m' and lo <= date.fromisoformat(p['date']) < before]
        if ps:
            out[f't{d}'] = round(min(ps), 2)
    return out


def ko_round(results, g, names, hist, day, with_q=True):
    rs = sorted([r for r in results if r.get('Rank') and tsec(r.get('Time'))], key=lambda r: r['Rank'])
    t0 = tsec(rs[0]['Time']) if rs else 0
    out = []
    for r in rs:
        nom = names.resolve(g, r); t = tsec(r['Time'])
        row = {'rang': r['Rank'], 'nom': nom, 'noc': r.get('NAT'), 'temps': fmt_t(t), 'temps_s': round(t, 1), 'ecart_s': round(t - t0, 1)}
        if with_q:
            row['qualifie'] = bool(r.get('Qualified'))
        row.update(pool_best(hist, g, nom, day))
        out.append(row)
    ranked = sorted([x for x in out if x.get('t1500')], key=lambda x: x['t1500'])
    for k, x in enumerate(ranked, 1):
        x['rv'] = k; x['di'] = k - x['rang']
    for x in out:
        x.setdefault('rv', None); x.setdefault('di', None)
    return out


def build_ko(e, names, hist, nag):
    g = e['genre']; heats = e['ev']['Heats']
    day = date.fromisoformat((e['ev'].get('DisciplineStartDate') or e['comp']['dateFrom'])[:10])
    hs = sorted([h for h in heats if h['PhaseName'] == 'Heats' and h.get('Results')], key=lambda h: (h.get('UnitCode') or '', h.get('Time') or ''))
    semi = [h for h in heats if h['PhaseName'] == 'Semifinals' and h.get('Results')]
    fin = [h for h in heats if h['PhaseName'] == 'Finals' and h.get('Results')]
    series = {str(i + 1): ko_round(h['Results'], g, names, hist, day) for i, h in enumerate(hs)}
    starts = {str(i + 1): sum(1 for r in h['Results'] if r.get('ScoringAbbr') != 'DNS') for i, h in enumerate(hs)}
    stats = {}
    for s, rows in series.items():
        q = [r for r in rows if r['qualifie']]; nq = [r for r in rows if not r['qualifie']]
        stats[s] = {'1er': rows[0]['temps'], 'dernier_q': q[-1]['temps'] if q else None, 'premier_elim': nq[0]['temps'] if nq else None,
                    'ecart_1_q': round(q[-1]['temps_s'] - rows[0]['temps_s'], 1) if q else None,
                    'marge_coupure': round(nq[0]['temps_s'] - q[-1]['temps_s'], 1) if q and nq else None,
                    'nb_starts': starts[s], 'nb_qualifies': len(q)}
    pd = sorted([dict(r, serie=int(s)) for s, rows in series.items() for r in rows if r['qualifie']], key=lambda r: (r['rang'], r['serie']))
    placement_demi = [{'position_depart': i + 1, 'nom': r['nom'], 'noc': r['noc'], 'rang_serie': r['rang'], 'serie': r['serie'],
                       'temps': r['temps'], **{k: r[k] for k in ('t400', 't800', 't1500') if k in r}} for i, r in enumerate(pd)]
    demi = ko_round(semi[0]['Results'], g, names, hist, day) if semi else []
    placement_finale = [{'position_depart': i + 1, 'nom': r['nom'], 'noc': r['noc'], 'rang_demi': r['rang'], 'temps': r['temps'],
                         **{k: r[k] for k in ('t400', 't800', 't1500') if k in r}} for i, r in enumerate([r for r in demi if r['qualifie']])]
    finale = ko_round(fin[0]['Results'], g, names, hist, day, with_q=False) if fin else []
    city = CITY_FR.get(e['city'], e['city'])
    fastest = min(series, key=lambda s: series[s][0]['temps_s']) if series else None
    return {'conditions': '', 'label': f"CdM {city} {e['year']}", 'date': day.strftime('%d/%m/%Y'), 'genre': g, 'type': 'CDM',
            'nb_series': len(series), 'nq_par_serie': max([v['nb_qualifies'] for v in stats.values()] or [0]),
            'fastest_serie': int(fastest) if fastest else None, 'stats_series': stats, 'series': series,
            'placement_demi': placement_demi, 'demi': demi, 'placement_finale': placement_finale, 'finale': finale,
            'source_temps': 'World Aquatics'}


# ---------------------------------------------------------------- fiches, historiques
def sync_fiches(cr, nag, ko, log):
    n_upd = 0
    for g in 'FH':
        fiches = {x['nom']: x for x in nag['DATA_' + g]}
        for key, co in cr['C' + g].items():
            if co.get('source_temps') != 'World Aquatics':
                continue
            present = {r['nom'] for r in co['nageurs']}
            for f in nag['DATA_' + g]:
                if f['nom'] not in present and any(c.get('sheet') == key for c in f.get('courses') or []):
                    f['courses'] = [c for c in f['courses'] if c.get('sheet') != key]
            hk0 = ko['KO_HF' if g == 'F' else 'KO_HH']
            for nm, lst in hk0.items():
                if nm not in present:
                    hk0[nm] = [x for x in lst if x.get('l') != co['label']]
            fmt = 'junior' if co.get('categorie') == 'junior' else '10km'
            for r in co['nageurs']:
                f = fiches.get(r['nom'])
                if not f:
                    continue
                cs = f.setdefault('courses', [])
                cc = next((c for c in cs if c.get('sheet') == key), None)
                if cc is None:
                    cc = {'sheet': key}; cs.append(cc)
                cc.update({'label': co['label'], 'type': co['type'], 'format': fmt, 'manche': 'Finale', 'nb_nageurs': co['nb'],
                           'date': co['date'], 'dists': co['dists'], 'dist_cumul': co['dist_cumul'], 'nb_tours': co['nb_tours'],
                           'rang': r['rang'], 'rv': r.get('rv'), 'di': r.get('di'),
                           'positions_tour': list(r['pos']), 'vitesses_tour': list(r['vit'])})
                n_upd += 1
        for key, k in ko['KO_DATA'].items():
            if k.get('source_temps') != 'World Aquatics' or k['genre'] != g:
                continue
            for r in k['finale'] + k['demi'] + [x for s in k['series'].values() for x in s]:
                f = fiches.get(r['nom'])
                if not f or any(c.get('sheet') == key for c in f.get('courses') or []):
                    continue
                manche = 'Finale' if r in k['finale'] else ('Demi' if r in k['demi'] else 'Série')
                f.setdefault('courses', []).append({'sheet': key, 'label': k['label'], 'type': 'CDM', 'format': 'KO', 'rang': r['rang'],
                                                    'manche': manche, 'nb_nageurs': 0, 'date': k['date'], 'dists': [], 'dist_cumul': [],
                                                    'positions_tour': [], 'vitesses_tour': [], 'nb_tours': 0, 'rv': None, 'di': None})
                n_upd += 1
        hk = ko['KO_HF' if g == 'F' else 'KO_HH']
        for key, co in cr['C' + g].items():
            if co.get('source_temps') != 'World Aquatics' or co.get('categorie') == 'junior':
                continue
            for r in co['nageurs']:
                if r['nom'] not in hk:
                    continue
                h = next((x for x in hk[r['nom']] if x.get('l') == co['label']), None)
                if h is None:
                    hk[r['nom']].append({'l': co['label'], 'd': co['date'][-4:], 't': co['type'], 'r': r['rang'], 'n': co['nb'],
                                         'rv': r.get('rv'), 'di': r.get('di')})
                else:
                    h['n'] = co['nb']; h['r'] = r['rang']
            for lst in hk.values():
                lst.sort(key=lambda x: x.get('d') or '')
    log['fiches'] = n_upd


def sync_hist(cr, hist):
    def best(n, d, lo, hi):
        ps = [p for p in n.get('perfs') or [] if p['d'] == d and p['bassin'] == '50m' and lo <= date.fromisoformat(p['date']) <= hi]
        if not ps:
            return None
        p = min(ps, key=lambda p: p['s'])
        return {'t': p['t'], 's': p['s'], 'date': p['date'], 'comp': p.get('comp'), 'pts': p.get('pts'), 'valid': p.get('valid')}
    for g in 'FH':
        for key, co in cr['C' + g].items():
            if co.get('source_temps') != 'World Aquatics':
                continue
            d = datetime.strptime(co['date'], '%d/%m/%Y').date()
            end, lo = d - timedelta(days=1), (d - timedelta(days=1)).replace(year=d.year - 2)
            parts = []
            for r in co['nageurs']:
                p = {'nom': r['nom'], 'rang': r['rang']}
                n = hist['nageurs'].get(f"{g}|{norm(r['nom'])}")
                if n:
                    for dd in (400, 800, 1500):
                        p[str(dd)] = best(n, dd, lo, end)
                    p['vc'] = round(1100 / (p['1500']['s'] - p['400']['s']), 4) if p.get('400') and p.get('1500') else None
                    p['fenetre'] = [lo.isoformat(), end.isoformat()]
                parts.append(p)
            hist['courses'][f'10km|{g}|{key}'] = {'source': '10km', 'genre': g, 'key': key, 'label': co['label'], 'date': d.isoformat(),
                                                   'date_base': co['date'], 'date_verifiee_wa': True, 'participants': parts}


if __name__ == '__main__':
    lg = main(dry='--dry' in sys.argv)
    print('completees', len(lg['completees']), '| nouvelles', len(lg['nouvelles']), '| KO', len(lg['ko']),
          '| ignorees', len(lg['ignorees']), '| dates', len(lg['dates']), '| fiches', lg['fiches'])
