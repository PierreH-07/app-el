# app-el — Contexte Claude Code

## Architecture

- **Branche `main`** : fichiers HTML servis par GitHub Pages
- **Branche `data`** : fichiers JSON (résultats de courses EL, mis à jour après chaque épreuve)
- **Branche de travail** : `claude/analyze-course-html-PCRZd`

## Fichiers HTML principaux

| Fichier | Contenu |
|---|---|
| `Ponton10km.html` | Ponton course 10 km (World Cup Stop 4, Sétubal 2026) |
| `ponton_ko_setubal2026.html` | Ponton course KO (World Cup Stop 4, Sétubal 2026) |
| `ponton_ko_ibiza2026.html` | Ponton course KO (Stop précédent, Ibiza) |
| `Analyse_KO_Eau_libre.html` | Analyse tactique courses KO |
| `analyse_course_el.html` | Analyse course 10 km |
| `index.html` | Page d'accueil |

## Mise à jour des temps bassin (pool times)

### Où mettre à jour

Les temps bassin sont codés en dur dans les tableaux `STARTLIST_F` et `STARTLIST_H` de chaque fichier ponton :

- **`Ponton10km.html`** → `STARTLIST_F` (≈ ligne 284) et `STARTLIST_H` (≈ ligne 334)
- **`ponton_ko_setubal2026.html`** → `STARTLIST_F` (≈ ligne 240) et `STARTLIST_H` (≈ ligne 288)

### Format d'une entrée avec temps bassin

```javascript
{bib:N, nom:'NOM Prenom', noc:'XXX', annee:YYYY,
 t400:'M:SS.s', t800:'M:SS.s', t1500:'MM:SS.s',
 v400:X.XXXX, v800:X.XXXX, v1500:X.XXXX},
```

### Calcul des vitesses (m/s)

```
v400  = 400  / (min*60 + sec)
v800  = 800  / (min*60 + sec)
v1500 = 1500 / (min*60 + sec)
```

Arrondir à 4 décimales. Notation française : virgule → point décimal (03:51,4 → 3:51.4).

### Entrée sans temps bassin (stub)

```javascript
{bib:N, nom:'NOM Prenom', noc:'XXX', annee:YYYY},
```

### Numéros de dossard (bib)

- Femmes 10 km : 101–148
- Hommes 10 km : 1–55
- KO : dossards propres à chaque édition (cf. PDF start list officiel)

`buildStartlist` utilise `e.bib` s'il est défini, sinon l'index du tableau.

### Deux endroits à mettre à jour

1. **JSON (branche `data`)** — source primaire, 438 H + 69 F
   - Fichier : `resultats_10km_nageurs_el.json` (champs `t400`, `t800`, `t1500`, `v400`, `v800`, `v1500`)
   - Méthode : worktree sur `origin/data`, modifier le JSON, pousser sur `data`

2. **HTML STARTLIST (branche feature)** — fallback si JSON a null
   - `Ponton10km.html` STARTLIST_F / STARTLIST_H
   - `ponton_ko_setubal2026.html` STARTLIST_F / STARTLIST_H

`buildStartlist` prend le JSON en priorité — si v1500 est null dans le JSON, il utilise l'entrée STARTLIST HTML.

### Déploiement après modification

```bash
# 1. Mettre à jour le JSON (branche data)
git worktree add /tmp/data-branch origin/data
# ... modifier resultats_10km_nageurs_el.json ...
cd /tmp/data-branch && git add . && git commit -m "..." && git push origin HEAD:data
git worktree remove /tmp/data-branch --force

# 2. Mettre à jour les HTML STARTLIST (branche feature → main)
git add Ponton10km.html ponton_ko_setubal2026.html
git commit -m "Update pool times: ..."
git push origin claude/analyze-course-html-PCRZd

# 3. Merger sur main pour le site
git checkout main && git merge claude/analyze-course-html-PCRZd --no-edit
git push origin main
git checkout claude/analyze-course-html-PCRZd
```

## Nageurs des STARTLIST sans temps bassin (contrôle World Aquatics du 29/09/2026)

Aucun 400/800/1500 NL en bassin 50m trouvé sur World Aquatics dans les 24 derniers mois :

Femmes : ABAD Ana (ECU), KARRAS Sophia Olivia (GRE).

Hommes : CASSINI Franco Ivo (ARG), MARQUES Duarte (POR), KIMBER Byron (RSA).

## Contrôle des temps bassin via World Aquatics (`outils/worldaquatics/`)

Règles appliquées :
- Fenêtre : 24 mois avant la date du contrôle.
- Un temps WA remplace celui de la base **uniquement s'il est meilleur** (ou si la base est vide).
- Bassin 50m uniquement, `(25m)` exclu. Quand le nom de compétition n'indique pas le bassin,
  il est validé par les points WA : base implicite = temps × (points/1000)^(1/3), comparée aux
  bases de référence 50m/25m de l'année (médianes des résultats étiquetés), tolérance 0,5 %.
- Rapprochement nageur ↔ WA : nom par mots entiers + prénom + nation + année ; les profils WA
  en double (même date de naissance et nation) sont fusionnés.

Enchaînement (variables d'environnement : `WA_WORK` dossier de travail, `WA_DATA` copie de la
branche `data`, `WA_APP` racine du dépôt, `WA_TODAY` date du contrôle, `WA_OUT` sortie) :
1. `wa_collect.py` puis `wa_pass2.py` → `wa_raw.json` (résultats WA bruts par nageur)
2. `dedup.py` (optionnel) → fusion des doublons de noms dans toute la base
3. `wa_report.py` → JSON + HTML mis à jour, `historique_bassin_el.json`, Excel avant/après et historiques

### Stratégie du ponton (`outils/worldaquatics/strategie.py`)

`strategie` de chaque fiche (DATA_F/DATA_H) = `compute(fiche['courses'])` :
- courses retenues : `format == '10km'` (5 km inclus), `positions_tour` et `rang` renseignés.
  **Toute course 10 km ajoutée à une fiche doit porter `format: '10km'`**, sinon elle est ignorée.
- `top5` = courses avec rang ≤ 5, `hors5` = rang > 5.
- jalon pct (20/40/60/80/100) = tour dont `dist_cumul` est le plus proche de pct % de la distance totale.
- par jalon : courses sans position à ce tour écartées ; `pos_moy` = moyenne des positions,
  `nb_moy` = moyenne de `nb_nageurs`, `n_courses` = nb de courses.
- `vz_norm` = moyenne sur les courses de (vitesse **du tour** du nageur / vitesse **médiane du peloton**
  sur ce tour) : 1,00 = vitesse du peloton, 1,03 = 3 % plus rapide. Calcul : `compute(courses, build_ref(courses_json, 'CF'|'CH'))`.
- Le ponton colore les ovales de −6 % (bleu clair) à +6 % (marine) (`VZ_MIN`/`VZ_MAX` dans `renderStrategie`).
- aucune course retenue → `null` ; un groupe sans course → `[]`.
- Recalculer après toute modification des courses d'une fiche. Positions : règle validée sur
  470/476 stratégies d'origine.

**⚠️ Stockage de `vit` hétérogène dans `resultats_10km_courses_el.json`** : vitesse **cumulée**
(dist_cumul / temps cumulé) pour les courses hommes, sauf `golfo26_h` ; vitesse **du tour**
(dists / temps du tour) pour toutes les courses femmes et `golfo26_h`. `strategie.storage_type()`
le détecte (écarts recalculés cohérents ⇒ cumulé). Vérifier le type avant toute analyse de `vit`.

**⚠️ ChM_Singapour25_5K et CHM_Singapour25_10K (F)** : `pos` et `ecart` incohérents à partir du
tour 3 (ex. la gagnante JOHNSON 14e à 1235 s) ; `vit` (vitesse du tour) semble correcte.

Les fiches fusionnées portent un champ `alias` (variantes d'orthographe rencontrées dans les
PDF) : s'en servir pour rattacher les résultats des prochaines courses à la bonne fiche.

## JSON data (branche `data`)

- `resultats_10km_nageurs_el.json` : DATA_F / DATA_H avec vitesses EL des nageurs
- `resultats_ko_el.json` : résultats rounds KO
- `historique_bassin_el.json` : historique des temps bassin WA (lecture machine)
  - `nageurs[genre|NOM NORMALISE]` : identité WA, `perfs` (tous les 200→1500 NL avec bassin
    retenu et motif de validation), `par_annee[AAAA]` (meilleurs 400/800/1500 + VC sur les
    24 mois finissant au 31/12), `eau_libre_wa` (résultats OW WA)
  - `courses[source|genre|cle]` : date (vérifiée via WA), et pour chaque participant les
    meilleurs 400/800/1500 + VC sur les 24 mois précédant la course
- Le ponton KO fetch les deux en parallèle (Promise.all) pour enrichir les données de vitesse
