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

## Nageurs sans temps bassin connus (à renseigner si données disponibles)

Femmes : GKAZGKA Maria (GRE), KARRAS Sophia Olivia (GRE), VIANA Carolina (POR),
HEMMENS Sasha-Lee (RSA), GARCES Sofia (ARG), IMWINKELRIED Romina Sole (ARG),
ANDRE Angelica (POR), LI Xinxuan (CHN), ABAD Ana (ECU), LEE Kyle (AUS — homme).

Hommes : MORENO Joaquin (ARG), CASSINI Franco Ivo (ARG), KIMBER Byron (RSA),
POLSTER Attila (SUI), MORENO GUTIERREZ Raul (MEX), CHRISTODOULOU Angelos (GRE),
SARREIRA Tomas (POR), LIETZEN Jesper (FIN), LEE Kyle (AUS), SIEGEL Will (USA),
LUDVIK David (CZE), MARQUES Duarte (POR), KOVACS-SERES Hunor (HUN).

## JSON data (branche `data`)

- `resultats_10km_nageurs_el.json` : DATA_F / DATA_H avec vitesses EL des nageurs
- `resultats_ko_el.json` : résultats rounds KO
- Le ponton KO fetch les deux en parallèle (Promise.all) pour enrichir les données de vitesse
