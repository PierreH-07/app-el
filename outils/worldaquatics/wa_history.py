"""Historique des meilleurs temps bassin 50m (fenêtre glissante 24 mois) :
 - par course d'eau libre de la base (ancrage = veille de la course)
 - par année civile (ancrage = 31/12, ou aujourd'hui pour l'année en cours)
Produit historique_bassin_el.json (format machine) + dates de course vérifiées via WA."""
import json, re, unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from wa_process import load_wa, norm, months_ago, fmt_html, TODAY, DISTS
import os as _os
SCR = _os.environ.get('WA_WORK', _os.getcwd())
DATA = _os.environ.get('WA_DATA', _os.path.join(SCR, 'data'))
APP = _os.environ.get('WA_APP', _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))



CITY = {'somabay': 'soma bay', 'golfoaranci': 'golfo aranci', 'golfo': 'golfo aranci', 'singapour': 'singapore',
        'setubal': 'setubal', 'tokoyo': 'tokyo', 'tokyo': 'tokyo', 'belgrade': 'belgrade', 'paris': 'paris',
        'doha': 'doha', 'budapest': 'budapest', 'fukuoka': 'fukuoka', 'starigrad': 'stari grad', 'funchal': 'funchal',
        'eilat': 'eilat', 'ohrid': 'ohrid', 'abudhabi': 'abu dhabi', 'hkg': 'hong kong', 'neom': 'neom', 'ibiza': 'ibiza',
        'meet4': None}


def plain(s):
    return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()


def race_city(key):
    k = re.sub(r'^(cdm|chm|che|jo)_', '', key.lower())
    k = re.sub(r'\d{2}(_[fh]|_5k|_10k)?$', '', k)
    return CITY.get(k, k)


def best(parsed, dist, start, end, genre):
    c = [p for p in parsed if p['dist'] == dist and p['bassin'] == '50m' and p['genre'] == genre and start <= p['date'] <= end]
    return min(c, key=lambda p: p['sec']) if c else None


def pack(p):
    if not p:
        return None
    return {'t': fmt_html(p['sec']), 's': round(p['sec'], 2), 'date': p['date'].isoformat(),
            'comp': p['competition'], 'pts': p['points'], 'valid': p['motif']}


def vc(b400, b1500):
    if b400 and b1500 and b1500['s'] > b400['s']:
        return round(1100 / (b1500['s'] - b400['s']), 4)
    return None


def window_bests(parsed, end, genre):
    start = months_ago(end, 24)
    out = {str(d): pack(best(parsed, d, start, end, genre)) for d in DISTS}
    out['vc'] = vc(out['400'], out['1500'])
    out['fenetre'] = [start.isoformat(), end.isoformat()]
    return out


def races():
    """Liste des courses de la base : (source, genre, key, label, date_base, participants[(nom, rang)], discipline)."""
    out = []
    c = json.load(open(f'{DATA}/resultats_10km_courses_el.json'))
    for g, k in [('F', 'CF'), ('H', 'CH')]:
        for key, co in c[k].items():
            disc = '5km' if '5K' in key.upper() and '10K' not in key.upper() else '10km'
            out.append(dict(source='10km', genre=g, key=key, label=co.get('label'), date_base=co.get('date'),
                            participants=[(n['nom'], n.get('rang')) for n in co['nageurs']], discipline=disc))
    ko = json.load(open(f'{DATA}/resultats_ko_el.json'))
    for key, co in ko['KO_DATA'].items():
        g = 'F' if key.endswith('_f') else 'H'
        hist = ko['KO_HF'] if g == 'F' else ko['KO_HH']
        noms = {}
        for part in ('finale', 'placement_finale', 'demi', 'placement_demi'):
            for n in co.get(part) or []:
                noms.setdefault(n['nom'], None)
        for s in (co.get('series') or {}).values():
            for n in s:
                noms.setdefault(n['nom'], None)
        parts = []
        for nom in noms:
            r = next((h.get('r') for h in hist.get(nom, []) if h.get('l') == co.get('label')), None)
            parts.append((nom, r))
        out.append(dict(source='KO', genre=g, key=key, label=co.get('label'), date_base=co.get('date'),
                        participants=parts, discipline='KO'))
    return out


def verify_date(race, raw):
    """Date de course d'après les résultats OW WA des participants (même ville, même année)."""
    city = race_city(race['key'])
    year = int(re.search(r'(20\d{2})', race['label'] or '').group(1)) if re.search(r'(20\d{2})', race['label'] or '') else None
    dates = Counter()
    for nom, _ in race['participants']:
        e = raw.get(f"{race['genre']}|{norm(nom)}")
        if not e or e.get('status') != 'ok':
            continue
        for o in e.get('ow') or []:
            d = o.get('Date') or ''
            if not d or (year and int(d[:4]) != year):
                continue
            if city and city not in plain(o.get('CompetitionCity')) and city not in plain(o.get('CompetitionName')):
                continue
            dn = (o.get('DisciplineName') or '').lower()
            if race['discipline'] == '10km' and '10km' not in dn:
                continue
            if race['discipline'] == '5km' and '5km' not in dn:
                continue
            if race['discipline'] == 'KO' and not re.search(r'3km|knock|sprint', dn):
                continue
            dates[d] += 1
    if not dates:
        return None, 0
    d, n = dates.most_common(1)[0]
    return (d, n) if n >= 3 else (None, n)


def run():
    raw, refs = load_wa()
    out = {'meta': {'genere_le': TODAY.isoformat(), 'source': 'api.worldaquatics.com (/athletes, /athletes/{id}/results)',
                    'fenetre_mois': 24,
                    'bassin': "50m uniquement ; (25m) exclu ; bassin valide par etiquette '(50m)' ou par coherence des points WA "
                              "(base implicite = temps*(points/1000)^(1/3) comparee aux bases de reference 50m/25m de l'annee, tolerance 0,5%)",
                    'ancrage_course': 'fenetre = [date course - 24 mois, veille de la course]',
                    'ancrage_annee': "fenetre = [31/12 - 24 mois, 31/12] (annee en cours : jusqu'a aujourd'hui)",
                    'champs_perf': 'd=distance, t=temps, s=secondes, date, pts=points WA, bassin, valid=motif de validation, comp=competition'},
           'nageurs': {}, 'courses': {}}
    for k, e in raw.items():
        base = e['base']
        rec = {'nom': base['nom'], 'genre': base['genre'], 'noc': base.get('noc'), 'annee': base.get('annee'),
               'sources': sorted(set(base['sources'])), 'statut_wa': e.get('status'), 'alias': e.get('alias') or []}
        if e.get('status') == 'ok':
            a = e['athlete']
            rec['wa'] = {'id': a['id'], 'nom': a['fullName'], 'naissance': a.get('dateOfBirth'), 'noc': a.get('nationality')}
            rec['annee'] = rec['annee'] or (int(a['dateOfBirth'][:4]) if a.get('dateOfBirth') else None)
            rec['perfs'] = [{'d': p['dist'], 't': p['time'], 's': round(p['sec'], 2), 'date': p['date'].isoformat(),
                             'pts': p['points'], 'bassin': p['bassin'], 'valid': p['motif'], 'comp': p['competition']}
                            for p in sorted(e['_parsed'], key=lambda p: (p['date'], p['dist'])) if p['genre'] == base['genre']]
            rec['eau_libre_wa'] = sorted(e.get('ow') or [], key=lambda o: o.get('Date') or '')
            years = sorted({p['date'].year for p in e['_parsed'] if p['bassin'] == '50m'})
            rec['par_annee'] = {}
            for y in range(max(2019, years[0]) if years else 2019, TODAY.year + 1):
                end = date(y, 12, 31) if y < TODAY.year else TODAY
                wb = window_bests(e['_parsed'], end, base['genre'])
                if any(wb[str(d)] for d in DISTS):
                    rec['par_annee'][str(y)] = wb
        out['nageurs'][k] = rec
    date_log = []
    for r in races():
        wa_date, n = verify_date(r, raw)
        try:
            db = datetime.strptime(r['date_base'], '%d/%m/%Y').date()
        except (TypeError, ValueError):
            db = None
        ref = date.fromisoformat(wa_date) if wa_date else db
        if wa_date and db and abs((ref - db).days) > 7:
            date_log.append(dict(course=f"{r['source']}/{r['key']}", label=r['label'], date_base=r['date_base'],
                                 date_wa=ref.strftime('%d/%m/%Y'), nb_nageurs_concordants=n))
        crec = {'source': r['source'], 'genre': r['genre'], 'key': r['key'], 'label': r['label'],
                'date': ref.isoformat() if ref else None, 'date_base': r['date_base'],
                'date_verifiee_wa': bool(wa_date), 'participants': []}
        for nom, rang in r['participants']:
            e = raw.get(f"{r['genre']}|{norm(nom)}")
            p = {'nom': nom, 'rang': rang}
            if e and e.get('status') == 'ok' and ref:
                p.update(window_bests(e['_parsed'], ref - timedelta(days=1), r['genre']))
            crec['participants'].append(p)
        out['courses'][f"{r['source']}|{r['genre']}|{r['key']}"] = crec
    return out, date_log


if __name__ == '__main__':
    out, date_log = run()
    json.dump(out, open(f'{SCR}/historique_bassin_el.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(date_log, open(f'{SCR}/dates_courses_a_corriger.json', 'w'), ensure_ascii=False, indent=1)
    print('nageurs', len(out['nageurs']), 'courses', len(out['courses']))
    print('dates divergentes:', len(date_log))
    for d in date_log:
        print(' ', d)
    nv = [c['key'] for c in out['courses'].values() if not c['date_verifiee_wa']]
    print('courses sans verification WA de la date:', nv)
