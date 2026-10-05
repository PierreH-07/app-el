# Récupération des temps bassin sur World Aquatics (WA)

Ce document décrit comment les scripts de `outils/worldaquatics/` récupèrent les résultats
bassin (et eau libre) sur World Aquatics, les filtrent, puis les appliquent à la base EL.

## 1. Source des données

Les scripts n'utilisent pas le site web directement. Ils interrogent l'API publique qui alimente
worldaquatics.com, avec des en-têtes de navigateur (`origin`/`referer` = worldaquatics.com) :

| Appel | Rôle |
|---|---|
| `GET https://api.worldaquatics.com/fina/athletes?name=…&nationality=…&page=…&pageSize=50` | recherche d'un athlète par nom |
| `GET https://api.worldaquatics.com/fina/athletes/{id}/results` | tous les résultats de l'athlète |

Aucune clé d'API n'est nécessaire. Chaque requête est retentée jusqu'à 4 fois (2 fois pour les résultats en passe 2), avec une pause croissante.
Une pause aléatoire de 0,3 à 0,9 s sépare deux nageurs.

Résultats conservés :
- **Bassin** (`SportCode = SW`) : 200, 400, 800 et 1500 NL, hors relais. Pour chaque résultat :
  épreuve, date, temps, points WA, compétition, ville, pays, phase, rang.
- **Eau libre** (`SportCode = OW`) : épreuve, date, temps, rang, compétition, ville.
  Ces résultats servent à vérifier les dates des courses (§ 5).

## 2. Liste des nageurs à rechercher

`wa_collect.py` construit la liste unique (genre + nom normalisé) à partir de :
- `resultats_10km_nageurs_el.json` (DATA_F / DATA_H), branche `data` ;
- `resultats_ko_el.json` (DATA_F / DATA_H), branche `data` ;
- les `STARTLIST_F` / `STARTLIST_H` de `Ponton10km.html`, `ponton_ko_setubal2026.html` et
  `ponton_ko_ibiza2026.html`.

Normalisation des noms : accents supprimés, tirets, apostrophes et points remplacés par des espaces,
majuscules. Le nom de famille correspond à la partie en MAJUSCULES, le prénom au reste
(`MARTINEZ GUILLEN Angela` → `MARTINEZ GUILLEN` / `Angela`).

## 3. Identification du nageur sur WA

### Passe 1 — `wa_collect.py`
- Recherche par nom de famille. Si aucun résultat : recherche « prénom nom ».
- Candidat retenu = même genre, nom compatible, et meilleur score :
  nom identique +2, prénom identique +3 (premier prénom +2, initiale +0,5, prénom différent = rejeté),
  nation identique +2, année de naissance identique +2 (différente −3).
- Égalité de score en tête → statut `ambigu`, aucun candidat retenu.
- Sortie : `wa_raw.json`, sauvegardé tous les 10 nageurs. Le script reprend là où il s'est arrêté.

### Passe 2 — `wa_pass2.py` (reprend tous les nageurs)
- Plusieurs requêtes : « prénom nom », nom, chaque mot du nom de 3 lettres ou plus,
  « 1er prénom + 1er mot du nom ». Filtre par nation (sauf NAB/AIN), 3 pages de 50 au maximum.
- Comparaison du nom **par mots entiers** (au moins un mot en commun). Le prénom doit correspondre
  au début ou à l'initiale ; les prénoms composés sont tolérés (« Pen-Han » = « Pen Han »).
- Score : nom identique +2, prénom identique +2, discipline OW +1, nation identique +3 (différente −3),
  année de naissance identique +3 (différente −4).
- **Fusion des doublons WA** : si les meilleurs candidats désignent une seule personne
  (même date de naissance et même nation), tous ses profils WA sont fusionnés, y compris les profils
  sans date de naissance de même nation. Leurs résultats sont réunis et dédoublonnés.
  Identifiants fusionnés : `athlete.ids_fusionnes`.
- Plusieurs personnes possibles → `ambigu`. Aucun candidat → `introuvable`.

État de la base au 29/09/2026 (`historique_bassin_el.json`) : 702 nageurs identifiés,
68 introuvables, 3 ambigus.

## 4. Validation du bassin (50 m uniquement) — `wa_pool.py`

L'API ne renseigne pas le bassin. Il est déduit de deux façons :
1. **Étiquette** dans le nom de compétition : `(25m)` → exclu ; `(50m)` → candidat 50 m.
2. **Points WA** : base implicite = temps × (points / 1000)^(1/3).
   - Bases de référence par (genre, distance, année, bassin) = médiane des bases implicites des
     résultats étiquetés (au moins 3 résultats). Si l'année manque : année ±1, puis ±2.
   - Résultat classé 50 m si sa base est à 0,5 % ou moins de la référence 50 m et plus proche
     d'elle que de la référence 25 m.
   - Étiqueté `(50m)` mais classé autrement par les points → `conflit`, signalé et non retenu.
   - Pas de points, ou pas de référence 50 m → `non_verifie`, non retenu.

Motifs de validation conservés (`valid`) : `etiquette (50m)`, `points WA coherents 50m`, etc.
Bilan actuel des perfs : 23 749 en 50 m, 5 898 en 25 m, 151 non vérifiées.

## 5. Application à la base

### `wa_process.py` — temps du jour (fiches + STARTLIST)
- Fenêtre : **24 mois avant la date du contrôle** (`WA_TODAY`).
- Pour 400, 800 et 1500 : meilleur temps WA en 50 m validé dans la fenêtre.
- Il **remplace** le temps de la base **seulement s'il est meilleur** (de plus de 0,004 s), ou si la
  base est vide. La vitesse est recalculée : `v = distance / secondes`, arrondie à 4 décimales.
- Nettoyages techniques : temps invalides mis à null, formats normalisés, vitesses incohérentes
  recalculées.
- Année de naissance ajoutée si elle manque. Différence d'année ou de nation base/WA → signalée,
  non modifiée.

### `wa_history.py` — historique (`historique_bassin_el.json`)
- `nageurs` : identité WA, toutes les perfs 200→1500 NL avec le bassin retenu, résultats eau libre WA,
  et `par_annee` (meilleurs 400/800/1500 sur les 24 mois finissant au 31/12, ou à la date du jour
  pour l'année en cours).
- `courses` : pour chaque course 10 km et KO, meilleurs 400/800/1500 de chaque participant sur les
  **24 mois finissant la veille de la course**.
- **Vitesse critique** : `VC = 1100 / (t1500 − t400)` (m/s), seulement si le 400 et le 1500 existent.
- **Date des courses** vérifiée par les résultats eau libre WA des participants (même année, même
  ville, même épreuve 10 km / 5 km / KO). La date WA n'est retenue que si 3 nageurs ou plus concordent.
  Elle est corrigée dans la base si l'écart dépasse 7 jours. Actuellement, 62 courses sur 71 ont une
  date vérifiée.

### `wa_report.py` — sorties
Écrit dans `WA_OUT` (par défaut `staging/`) :
- JSON mis à jour (`resultats_10km_nageurs_el.json`, `resultats_ko_el.json`,
  `resultats_10km_courses_el.json`, `historique_bassin_el.json`) et HTML ponton mis à jour ;
- `controle_WA_avant_apres.xlsx` : synthèse, temps modifiés, années ajoutées, corrections
  techniques, dates corrigées, points à vérifier ;
- `historique_bassin_Femmes.xlsx` / `historique_bassin_Hommes.xlsx` : par course, par année, toutes
  les perfs WA.

Ces fichiers sont ensuite copiés à la main sur la branche `data` (JSON) et sur la branche de travail
(HTML) : voir `CLAUDE.md`, section « Déploiement ».

### `dedup.py` (optionnel)
Fusionne dans toute la base les fiches qui correspondent au même athlète WA sous plusieurs
orthographes. Les variantes sont gardées dans le champ `alias`. Option `--dry` : rapport seulement.

## 6. Enchaînement

```bash
export WA_WORK=/chemin/travail        # dossier de travail (wa_raw.json, staging/)
export WA_DATA=/chemin/copie_branche_data
export WA_APP=/chemin/app-el          # racine du dépôt (HTML ponton)
export WA_TODAY=2026-09-29            # date du contrôle
export WA_OUT=$WA_WORK/staging

python3 wa_collect.py    # passe 1 -> wa_raw.json
python3 wa_pass2.py      # passe 2 -> wa_raw.json
python3 dedup.py --dry   # optionnel : contrôle des doublons
python3 wa_report.py     # -> staging/ (JSON, HTML, Excel)
```

Dépendances Python : `requests`, `openpyxl`.

## 7. Limites connues

- Seuls les résultats publiés par WA sont couverts. Une compétition nationale absente de WA
  est invisible.
- Nageurs introuvables ou ambigus : aucun temps WA appliqué. Ils figurent dans « A verifier » de
  l'Excel.
- Le bassin validé par les points dépend des tables de points de l'année : une perf à la limite de
  la tolérance de 0,5 % peut être écartée à tort (`non_verifie`).
- La docstring de `wa_process.py` mentionne un `wa_apply.py` qui n'existe pas dans le dépôt :
  c'est `wa_report.py` qui écrit les sorties.
