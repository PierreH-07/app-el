# Contexte — Application Eau Libre (FFN · Centre de la Performance)

> Document de référence à placer dans les fichiers du projet.  
> À partager avec Claude en début de chat pour reprendre le développement sans perte de contexte.  
> Dernière mise à jour : 08/05/2026

---

## 1. Vue d'ensemble du projet

Application web d'analyse de natation en eau libre, développée pour le Centre de la Performance de la FFN. Hébergée sur **GitHub Pages** (pas de backend, pas de base de données). Tous les fichiers sont statiques.

**URL de production :** `https://pierreh-07.github.io/app-el/`

**Stack technique :**
- HTML / CSS / JS vanilla (pas de framework)
- Thème sombre "marine" (voir palette ci-dessous)
- Données : fichiers JSON externes chargés via `fetch()` depuis la branche `data`
- Hébergement : GitHub Pages (dépôt `pierreh-07/app-el`)

---

## 2. Architecture des fichiers

### Structure des branches

Le dépôt utilise **deux branches distinctes** avec des rôles séparés :

| Branche | Contenu | Rôle |
|---------|---------|------|
| `main` | Fichiers HTML, README, documentation | Code source de l'application |
| `data` | Fichiers JSON de résultats uniquement | Source de vérité des données |

**⚠️ Il n'y a pas de dossier `data/` dans `main`.** Les JSON sont exclusivement dans la branche `data`.

### Branche `main`

```
app-el/  (branche main)
├── index.html                      ← page d'accueil, liens vers toutes les applis
├── Analyse_KO_Eau_libre.html       ← analyse résultats courses KO (3km Sprint)
├── analyse_course_el.html          ← analyse résultats courses 10km
├── Ponton10km.html                 ← ponton startlist 10km (avec météo)
├── ponton_ko_ibiza2026.html        ← ponton startlist KO Ibiza 2026 (modèle)
├── README.md
└── CONTEXTE_PROJET_EL.md
```

### Branche `data`

```
app-el/  (branche data)
├── resultats_10km_el.json          ← SOURCE DE VÉRITÉ courses 10km
└── resultats_ko_el.json            ← SOURCE DE VÉRITÉ courses KO
```

### Règle fondamentale d'architecture

Les fichiers HTML chargent les JSON via `fetch()` **directement depuis la branche `data`** sur GitHub raw. Cela fonctionne sur GitHub Pages et en local avec un serveur HTTP. **Ne fonctionne pas en `file://`.**

```js
// Pattern standard de chargement — pointe vers la branche data
fetch('https://raw.githubusercontent.com/PierreH-07/app-el/data/resultats_10km_el.json')
  .then(r => r.json())
  .then(json => {
    // ... tout le code JS
  })
  .catch(e => {
    document.body.innerHTML = '<p style="color:red;padding:2rem">Erreur chargement : ' + e + '</p>';
  });
```

---

## 3. Les deux fichiers JSON — Sources de vérité

### 3.1 `resultats_ko_el.json`

Structure de premier niveau :
```json
{
  "KO_DATA":  { ... },   // résultats de chaque course KO
  "KO_HF":   { ... },   // historique individuel femmes
  "KO_HH":   { ... },   // historique individuel hommes
  "KO_FLAGS": { ... }   // emojis drapeaux par NOC
}
```

**Convention de nommage des clés dans `KO_DATA` :**
```
{ville}{année2chiffres}_{genre}
Exemples : golfo26_f · ibiza26_h · singapour25_f · starigrad25_h
```

**Structure d'une course dans `KO_DATA` :**
```json
"ibiza26_f": {
  "conditions": "17.3°C · Vent NE 18.2 km/h rafales 42.8 km/h",
  "label": "CdM Ibiza 2026",
  "date": "25/04/2026",
  "genre": "F",
  "type": "CDM",
  "nb_series": 2,
  "nq_par_serie": 10,
  "fastest_serie": 2,
  "stats_series": { "1": { ... } },
  "series": { "1": [...], "2": [...] },
  "placement_demi": [...],
  "demi": [...],
  "placement_finale": [...],
  "finale": [...]
}
```

**Structure d'un nageur dans une série/demi/finale KO :**
```json
{
  "rang": 1,
  "nom": "FABIAN Bettina",
  "noc": "HUN",
  "temps": "18:20.1",
  "temps_s": 1100.1,
  "ecart_s": 0.0,
  "qualifie": true,
  "t1500": 987.39,
  "t800": 517.33,
  "t400": 248.86,
  "rv": 13,
  "di": 12
}
```

**Structure d'un nageur dans `KO_HF` / `KO_HH` :**
```json
"FABIAN Bettina": [
  {
    "l": "CdM Ibiza 2026",
    "d": "2026",
    "t": "CDM",
    "r": 4,
    "n": 48,
    "rv": 13,
    "di": 12
  }
]
```

**⚠️ Point critique — Correspondance des noms :**
Les clés dans `KO_HF`/`KO_HH` doivent correspondre **exactement** au champ `nom` dans le ponton. Problèmes fréquents :
- PDF tronque les prénoms : `BRANDT DE MACEDO L.` → compléter
- Doublons de clés : `DE VALDES Maria` et `de VALDES Maria` peuvent coexister

---

### 3.2 `resultats_10km_el.json`

**Structure réelle de premier niveau (vérifiée mai 2026) :**
```json
{
  "CF":        { ... },   // courses femmes 10km (29 courses en mai 2026)
  "CH":        { ... },   // courses hommes 10km (28 courses en mai 2026)
  "DATA_F":    [...],     // liste des nageuses avec profil + historique
  "DATA_H":    [...],     // liste des nageurs avec profil + historique
  "NOC_FLAGS": { ... }    // emojis drapeaux par NOC
}
```

#### Structure d'une course dans `CF` / `CH`

Clé = identifiant de course (`CDM_GolfoAranci24`, `JO_Paris24`, `golfo26_h`...) :

```json
"golfo26_h": {
  "sheet":      "golfo26_h",
  "label":      "CdM Golfo Aranci 2026",
  "type":       "CDM",
  "date":       "01/05/2026",
  "conditions": "22°C · Vent NE 12 km/h",
  "nb_tours":   6,
  "dists":      [1666, 1667, 1667, 1666, 1667, 1667],
  "dist_cumul": [1666, 3333, 5000, 6666, 8333, 10000],
  "nb":         67,
  "groupes": [
    [ {"n":12, "ecart_fin":0.0, "membres":["NOM Prenom", ...]}, ... ],
    ...
  ],
  "nageurs": [
    {
      "nom":   "FONTAINE Logan",
      "noc":   "FRA",
      "rang":  1,
      "pos":   [3, 2, 1, 1, 1, 1],
      "ecart": [2.1, 0.8, 0.0, 0.0, 0.0, 0.0],
      "vit":   [1.58, 1.61, 1.63, 1.62, 1.60, 1.64],
      "rv":    2,
      "di":    1
    }
  ]
}
```

**Champs nageur dans `CF`/`CH` :**

| Champ | Description |
|-------|-------------|
| `pos` | Position au classement à chaque tour (tableau de `nb_tours` valeurs) |
| `ecart` | Écart cumulé sur le leader en secondes à chaque tour |
| `vit` | Vitesse moyenne en m/s à chaque tour |
| `rv` | Rang vitesse piscine (1500m) — peut être `null` |
| `di` | Indice EL = `rv − rang` · positif = meilleur en course qu'en piscine |

**Champs `groupes[t][i]` :**

| Champ | Description |
|-------|-------------|
| `n` | Nombre de nageurs dans le groupe |
| `ecart_fin` | Écart interne du groupe à la fin du tour (secondes) |
| `membres` | Liste des noms dans le groupe |

#### Structure d'un nageur dans `DATA_F` / `DATA_H`

```json
{
  "bib":         5,
  "nom":         "FONTAINE Logan",
  "noc":         "FRA",
  "annee":       1999,
  "t400":        "3:46.2",
  "t800":        "7:55.1",
  "t1500":       "14:52.3",
  "v400":        1.7671,
  "v1500":       1.6812,
  "experience":  18,
  "respiration": "Gauche",
  "courses": [
    {
      "sheet":          "CdM_Ibiza26",
      "label":          "CdM Ibiza 2026",
      "type":           "CDM",
      "date":           "24/04/2026",
      "format":         "10km",
      "nb_nageurs":     48,
      "nb_tours":       6,
      "rang":           3,
      "rv":             2,
      "di":             -1,
      "dists":          [1666, 1667, 1667, 1666, 1667, 1667],
      "dist_cumul":     [1666, 3333, 5000, 6666, 8333, 10000],
      "positions_tour": [4, 3, 3, 3, 3, 3],
      "vitesses_tour":  [1.58, 1.61, 1.63, 1.62, 1.60, 1.64]
    }
  ],
  "strategie": {
    "top5":  [ {"pct":20, "pos_moy":2.1, "nb_moy":18, "vz_norm":0.72, "n_courses":5}, ... ],
    "hors5": [ {"pct":20, "pos_moy":7.4, "nb_moy":22, "vz_norm":0.61, "n_courses":3}, ... ]
  }
}
```

**Champs strategie `top5`/`hors5` :**

| Champ | Description |
|-------|-------------|
| `pct` | Point de la course en % (20, 40, 60, 80, 100) |
| `pos_moy` | Position moyenne du nageur dans le peloton |
| `nb_moy` | Taille moyenne du peloton à ce point |
| `vz_norm` | Vitesse normalisée du peloton (0=lent, 1=rapide) |
| `n_courses` | Nombre de courses ayant servi au calcul |

---

## 4. Les fichiers d'analyse

### 4.1 `Analyse_KO_Eau_libre.html`

Outil d'analyse des courses KO (3km Sprint). Charge `resultats_ko_el.json` depuis la branche `data`.

**Variables JS après le fetch :**
```js
var DATA  = json.KO_DATA;
var HF    = json.KO_HF;
var HH    = json.KO_HH;
var FLAGS = json.KO_FLAGS;
```

---

### 4.2 `analyse_course_el.html` (583 lignes)

Outil d'analyse des courses 10km. Charge `resultats_10km_el.json` depuis la branche `data`.

**Variables JS après le fetch :**
```js
const CF = json.CF;
const CH = json.CH || {};
```

**Fonction de routage genre :**
```js
function courses(){ return G==='f' ? CF : CH; }
```

**Fonctions JS principales :**

| Fonction | Ligne | Rôle |
|----------|-------|------|
| `setGender(g)` | 168 | Bascule F/H, reconstruit le sélecteur |
| `buildCourseSelector()` | 178 | Peuple le `<select>` depuis `CF` ou `CH` |
| `renderGroupes(c)` | 248 | Affiche les groupes par tour (SVG) |
| `renderIndice(c)` | 350 | Affiche le nuage rang-vitesse + tableau indice EL |
| `renderPositions(c)` | 408 | Affiche l'évolution des positions tour/tour |
| `renderFocus(c)` | 475 | Fiche détaillée d'un nageur |

**Ce que chaque vue lit dans le JSON :**

- **Groupes** : `c.groupes[t][i].n`, `.ecart_fin`, `.membres` — **les groupes sont pré-calculés dans le JSON, aucun seuil dans le JS**
- **Indice EL** : `ng.rv` (rang vitesse piscine) et `ng.di` (indice EL) dans `c.nageurs[]`
- **Positions** : `ng.pos[]` (position à chaque tour) dans `c.nageurs[]`
- **Focus** : `ng.vit[]` (vitesses), `ng.ecart[]` (écarts), `ng.rang`, `ng.noc`

---

### 4.3 `Ponton10km.html` (1176 lignes)

Ponton pour les courses 10km. Charge `resultats_10km_el.json` depuis la branche `data`.

**Variables JS après le fetch :**
```js
var NOC_FLAGS = json.NOC_FLAGS;
var DATA_F    = json.DATA_F;
var DATA_H    = json.DATA_H;
```

**Fonction de routage genre :**
```js
const data = () => G==='f' ? DATA_F : DATA_H;
```

**Fonctions JS principales :**

| Fonction | Ligne | Rôle |
|----------|-------|------|
| `renderHist()` | 346 | Histogramme vitesses piscine (SVG) |
| `tap(bib)` | 452 | Clic sur un nageur, ouvre le panel |
| `renderProfil(ng)` | 612 | Fiche profil : temps piscine, stats EL |
| `renderCoursesList(ng)` | 662 | Liste des courses du nageur |
| `selectCourse(sheet)` | 697 | Sélectionne une course pour le détail |
| `renderCourseDetail(ng, sheet)` | 705 | Graphique positions + vitesses par tour |
| `renderStrategie(ng)` | 499 | Graphique ovales stratégie cigare |
| `switchGender(g)` | 824 | Bascule F/H |

**Ce que `renderCourseDetail` lit :**
```js
// Cherche la course dans ng.courses[] par son sheet
const c = ng.courses.find(x => x.sheet === sheet);
// Lit directement :
c.positions_tour   // ⚠️ crash si absent (pas de vérification null)
c.vitesses_tour
c.dists
c.nb_nageurs
c.nb_tours
c.rang
```

**Ce que `renderStrategie` lit :**
```js
const strat = ng.strategie;
// Lit : strat.top5[], strat.hors5[]
// Chaque entrée : {pct, pos_moy, nb_moy, vz_norm, n_courses}
```

---

## 5. Les fichiers pontons KO

### `ponton_ko_ibiza2026.html`

Modèle de ponton pour les courses KO. Charge `resultats_ko_el.json`.

**Pour créer un nouveau ponton KO :**
1. Dupliquer ce fichier
2. Renommer : `ponton_ko_{ville}{annee}.html`
3. Mettre à jour `CONFIG`, `STARTLIST_F`, `STARTLIST_H`, `METEO_F`, `METEO_H`
4. Vérifier la correspondance des noms avec les clés du JSON

---

## 6. Palette de couleurs commune

Tous les fichiers utilisent le même thème "marine" :

```css
--bg:       #f4f7fb;
--blue:     #003087;
--red:      #C8102E;
--gold:     #b8860b;
--green:    #1a7a3c;
--border:   #c8d8ea;
--txt:      #1a2a4a;
--txt-dim:  #5a7a9e;
```

---

## 7. Workflow de mise à jour

### Après une course KO

1. Ouvrir `resultats_ko_el.json` (branche `data`)
2. Ajouter la course dans `KO_DATA`
3. Ajouter les entrées dans `KO_HF` ou `KO_HH`
4. `git push` sur la branche `data` → GitHub Pages se met à jour en 1-2 min

### Après une course 10km

1. Ouvrir `resultats_10km_el.json` (branche `data`)
2. Ajouter la course dans `CF` (femmes) ou `CH` (hommes) avec :
   - `nageurs[]` avec `pos`, `ecart`, `vit`, `rv`, `di`
   - `groupes[][]` avec `n`, `ecart_fin`, `membres` (calculé par le script Python)
3. Ajouter les courses dans `DATA_F` ou `DATA_H` (chaque nageur) avec :
   - `positions_tour[]`, `vitesses_tour[]`
4. Recalculer `strategie.top5` et `strategie.hors5` pour les nageurs concernés
5. `git push` sur la branche `data`

### Test en local

```bash
# Option 1 — VS Code Live Server
# Clic droit sur index.html → Open with Live Server

# Option 2 — Python
python3 -m http.server 8000
# puis ouvrir http://localhost:8000
```

**⚠️ Le fetch pointe vers GitHub raw, pas localhost.** En local, modifier temporairement l'URL du fetch pour pointer vers `data/resultats_10km_el.json` si un fichier local est disponible.

---

## 8. Bugs connus et diagnostic (mai 2026)

### 8.1 Hommes non fonctionnels dans `analyse_course_el.html` et `Ponton10km.html`

**Diagnostic complet effectué le 08/05/2026.**

La branche `data` contient bien 28 courses dans `CH` et 28 nageurs dans `DATA_H`, mais **le script Python de génération n'a traité complètement que `golfo26_h`**. Pour les 27 autres courses hommes :

| Problème | Portée | Symptôme visible |
|----------|--------|-----------------|
| `CH[x].groupes` vide `[]` | 27/28 courses | Onglet Groupes : SVG blanc |
| `CH[x].nageurs[i].rv` = null | 27/28 courses | Onglet Indice EL : "Données non disponibles" |
| `CH[x].nageurs[i].di` = null | 27/28 courses | Indice EL absent |
| `DATA_H[i].courses[c].positions_tour` absent | 27/28 courses + 5 sheets inconnus | **Crash JS** dans `renderCourseDetail` |
| `DATA_H[i].strategie` vide | 100% nageurs H | Onglet Stratégie : "Pas assez de données" |
| `DATA_F[i].strategie` vide | 100% nageurs F | Idem côté femmes |
| `CH['CdM_Ibiza26']` absent | 1 course | Course manquante dans le sélecteur H |

**Sheets présents dans `DATA_H` mais absents de `CH`** (à régulariser) :
`golfo25_h`, `ibiza25_h`, `ibiza26_h`, `meet4_25_h`, `singapour25_h`, `starigrad25_h`

**Cause racine :** le script Python de génération du JSON n'a pas exécuté les étapes suivantes pour les courses hommes historiques :
- calcul des groupes par tour (seuil à vérifier dans le script Python)
- croisement avec les données piscine (`rv`, `di`)
- calcul des `positions_tour` / `vitesses_tour` dans `DATA_H`
- calcul de `strategie.top5` / `strategie.hors5`

### 8.2 Crash JS dans `renderCourseDetail` (Ponton10km)

```js
// Ligne 720 — pas de vérification null
const nb = c.positions_tour.length;  // ← TypeError si positions_tour absent
```

**Fix à appliquer :**
```js
if (!c.positions_tour || !c.positions_tour.length) {
  document.getElementById('fiche-content').innerHTML =
    '<div class="fiche"><div class="empty-r">Positions par tour non disponibles.</div></div>';
  return;
}
```

### 8.3 Autres points de vigilance

- **Noms tronqués dans les PDF** : toujours compléter les prénoms avant insertion dans le JSON.
- **Correspondance des noms** : la moindre différence (espace, tiret, majuscule) entre le nom dans la startlist du ponton et la clé dans `DATA_F`/`DATA_H` empêche l'affichage de l'historique.
- **fetch() en `file://`** : impossible. Toujours tester avec un serveur local.
- **Groupes calculés côté Python, pas JS** : `renderGroupes` lit `c.groupes[]` directement, aucun seuil dans le HTML. Le seuil de séparation des groupes est dans le script Python.

---

## 9. Backlog / Évolutions prévues

### Correctifs prioritaires
- [ ] Régénérer `resultats_10km_el.json` : remplir `CH.groupes`, `rv`/`di`, `positions_tour`, `vitesses_tour` et `strategie` pour les 27 courses hommes manquantes
- [ ] Ajouter `CH['CdM_Ibiza26']`
- [ ] Ajouter guard null dans `renderCourseDetail` (ligne 720)
- [ ] Régulariser les 6 sheets `_h` présents dans `DATA_H` mais absents de `CH`

### Applis analyse
- [ ] Couplage avec résultats officiels pour afficher les positions de tous les nageurs aux points de passage

### Pontons
- [ ] Automatiser la récupération de la météo via l'API Open-Meteo au chargement

### Maintenance JSON
- [ ] Script Python pour extraire automatiquement les résultats depuis les PDF World Aquatics
- [ ] Script Python : vérifier et documenter le seuil de regroupement utilisé pour `groupes[]`
