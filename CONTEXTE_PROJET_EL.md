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
- Thème "marine" (voir palette ci-dessous)
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

Les fichiers HTML chargent les JSON via `fetch()` **directement depuis la branche `data`** sur GitHub raw. **Ne fonctionne pas en `file://`.**

```js
// Pattern standard de chargement — pointe vers la branche data
fetch('https://raw.githubusercontent.com/PierreH-07/app-el/data/resultats_10km_el.json')
  .then(r => r.json())
  .then(json => { /* ... */ })
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
  { "l": "CdM Ibiza 2026", "d": "2026", "t": "CDM", "r": 4, "n": 48, "rv": 13, "di": 12 }
]
```

**⚠️ Point critique — Correspondance des noms :**
- PDF tronque les prénoms : `BRANDT DE MACEDO L.` → compléter
- Doublons de clés : `DE VALDES Maria` et `de VALDES Maria` peuvent coexister

---

### 3.2 `resultats_10km_el.json`

**Structure réelle de premier niveau :**
```json
{
  "CF":        { ... },   // courses femmes 10km (une clé par course)
  "CH":        { ... },   // courses hommes 10km (une clé par course)
  "DATA_F":    [...],     // liste des nageuses avec profil + historique (pour pontons)
  "DATA_H":    [...],     // liste des nageurs avec profil + historique (pour pontons)
  "NOC_FLAGS": { ... }    // emojis drapeaux par NOC
}
```

#### Structure d'une course dans `CF` / `CH`

Clé = identifiant de course (`CDM_Ibiza25`, `golfo26_h`, `JO_Paris24`…) :

```json
"CDM_Ibiza25": {
  "sheet":      "CDM_Ibiza25",
  "label":      "CdM Ibiza 2025",
  "type":       "CDM",
  "date":       "27/04/2025",
  "conditions": "16.4°C · Vent NNO ...",
  "nb_tours":   6,
  "dists":      [1574, 1666, 1666, 1666, 1666, 1758],
  "dist_cumul": [1574, 3240, 4906, 6572, 8238, 9996],
  "nb":         68,
  "groupes":    [ [...], [...], ... ],
  "nageurs":    [ {...}, ... ]
}
```

**Structure d'un nageur dans `CF`/`CH` :**
```json
{
  "nom":   "FILADELLI Andrea",
  "noc":   "ITA",
  "rang":  1,
  "pos":   [21, 10, 9, 11, 11, 1],
  "ecart": [11.3, 7.6, 13.3, 7.3, 7.4, 0.0],
  "vit":   [1.5107, 1.5058, 1.5023, 1.5041, 1.5063, 1.5198],
  "rv":    null,
  "di":    null
}
```

| Champ | Description |
|-------|-------------|
| `pos` | Position au classement à chaque tour |
| `ecart` | Écart cumulé sur le leader en secondes à chaque tour |
| `vit` | Vitesse cumulative = `dist_cumul[i] / cumul_s[i]` (4 décimales) |
| `rv` | Rang vitesse piscine (1500m) — peut être `null` |
| `di` | Indice EL = `rv − rang` · positif = meilleur en course qu'en piscine |

**Structure d'un groupe dans `groupes[tour]` :**
```json
{"n": 12, "ecart_fin": 7.3, "membres": ["NOM Prenom", "NOM2 Prenom2", ...]}
```

**⚠️ Règle de regroupement (seuil = 3 secondes) :**  
Si l'écart entre le nageur `[i]` et le nageur `[i+1]` dépasse **3 secondes**, on coupe et on ouvre un nouveau groupe. **Ce calcul est fait en Python lors de la génération du JSON, il n'y a aucun seuil dans le JS.** `renderGroupes()` lit `c.groupes[]` directement.

---

#### Structure d'un nageur dans `DATA_F` / `DATA_H`

```json
{
  "bib":           1,
  "nom":           "FILADELLI Andrea",
  "noc":           "ITA",
  "annee":         1999,
  "experience":    12,
  "t400":          248.86,
  "t800":          517.33,
  "t1500":         987.39,
  "v400":          null,
  "v800":          null,
  "v1500":         1.521,
  "respiration":   "bilatérale",
  "resultats_cdm": { ... },
  "resultats_chm": { ... },
  "courses": [
    {
      "sheet":          "CDM_Ibiza25",
      "label":          "CdM Ibiza 2025",
      "type":           "CDM",
      "format":         "10km",
      "manche":         "Finale",
      "nb_nageurs":     68,
      "date":           "27/04/2025",
      "dists":          [1574, 1666, ...],
      "dist_cumul":     [1574, 3240, ...],
      "nb_tours":       6,
      "rang":           1,
      "rv":             null,
      "di":             null,
      "positions_tour": [21, 10, 9, 11, 11, 1],
      "vitesses_tour":  [1.5107, 1.5058, ...]
    }
  ],
  "strategie": {
    "top5":  [ {"pct":20, "pos_moy":3.2, "nb_moy":65.0, "vz_norm":1.512, "n_courses":5}, ... ],
    "hors5": [ ... ]
  }
}
```

**⚠️ Règle de synchronisation critique :**  
`positions_tour` dans `DATA_H/F` est une **copie exacte** de `pos[]` du même nageur dans `CH/CF` pour la même course. Idem pour `vitesses_tour` = `vit[]`. Ces deux paires doivent toujours être synchronisées.

**Champs `t400`/`t800`/`t1500` :** temps en **secondes numériques** (pas de chaîne `"3:46.2"`).  
`v400`/`v800` peuvent être `null` si non disponibles.

**Champs `strategie.top5` / `strategie.hors5` — valeurs exactes attendues par le JS :**

| Champ | Description |
|-------|-------------|
| `pct` | Jalon de la course en % — valeurs exactes : **20, 40, 60, 80, 100** |
| `pos_moy` | Position moyenne du nageur dans le peloton à ce jalon |
| `nb_moy` | Taille moyenne du peloton (= `nb_nageurs` des courses du groupe) |
| `vz_norm` | Vitesse moyenne du peloton à ce jalon (m/s) |
| `n_courses` | Nombre de courses ayant servi au calcul |

Règles :
- `top5` = courses où `rang <= 5`, `hors5` = courses où `rang > 5`
- **Jalons : 20, 40, 60, 80, 100%** — définis dans le JS par `const JALONS=[20,40,60,80,100]`
- Le JS cherche chaque jalon par `rowData.find(r => r.pct === pct)` — si `pct` ne correspond pas exactement, l'ovale s'affiche vide
- Le JS lit `strategie` directement depuis le JSON — **aucun calcul côté client**

**Valeur de `strategie` quand vide :**  
`strategie = null` (pas `{}` ni `[]`). Le garde-fou JS `if (!strat || ...)` intercepte correctement `null`.  
Ne jamais mettre `{"top5": [], "hors5": []}` — cela passerait le garde-fou et afficherait un graphique vide.

**La stratégie cigare n'existe que dans `Ponton10km.html`** (`renderStrategie` ligne 499). Elle est absente de `analyse_course_el.html`.

---

## 4. Sources de données et calcul des champs

### Sources

| Donnée | Source |
|--------|--------|
| Temps par tour | Excel : `Donnees_EL_Hommes.xlsx` / `Donnees_EL_Femmes.xlsx` — feuille = clé de la course |
| Métadonnées (label, date, conditions) | Saisie manuelle depuis les PDFs officiels World Aquatics |
| `rv` et `di` | Saisie manuelle — classement mondial World Aquatics au moment de la course |

**Rôle de Claude vs Claude Code :**
- **Claude** lit les Excel et PDFs (extraction des données brutes)
- **Claude Code** écrit le JSON (calcul et insertion)

### Formules de calcul depuis les temps bruts

```
cumul_s[i]  = somme des temps de tour 1 à i (en secondes)
ecart[i]    = round(cumul_s[i] - min(cumuls_valides[i]), 1)
vit[i]      = round(dist_cumul[i] / cumul_s[i], 4)
pos[i]      = rang du nageur parmi tous les cumuls valides au tour i
```

Un nageur est considéré **DNF** si son temps est absent ou nul pour un tour avant le dernier.

### Variantes de colonnes Excel — hommes

| Champ | Variantes connues |
|-------|-----------------|
| Nom | `Nom` ou `Nom_complet` |
| NOC | `Nation` ou `NOC` |
| Temps de tour | `Tour1` … `TourN` |
| Distances | `Distance_tour1` … `Distance_tourN` |
| À ignorer | `Distance_tour5.1` (doublon parasite) |

Certaines feuilles ont **5 tours** (courses 5km ou parcours court), d'autres **6 ou 7**. Toujours lire `nb_tours` depuis la feuille, ne pas supposer.

---

## 5. Les fichiers d'analyse

### 5.1 `Analyse_KO_Eau_libre.html`

Outil d'analyse des courses KO (3km Sprint). Charge `resultats_ko_el.json` depuis la branche `data`.

**Variables JS après le fetch :**
```js
var DATA  = json.KO_DATA;
var HF    = json.KO_HF;
var HH    = json.KO_HH;
var FLAGS = json.KO_FLAGS;
```

---

### 5.2 `analyse_course_el.html` (583 lignes)

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

- **Groupes** : `c.groupes[t][i].n`, `.ecart_fin`, `.membres` — groupes pré-calculés en Python
- **Indice EL** : `ng.rv` et `ng.di` dans `c.nageurs[]`
- **Positions** : `ng.pos[]` dans `c.nageurs[]`
- **Focus** : `ng.vit[]`, `ng.ecart[]`, `ng.rang`, `ng.noc`

**Note :** ce fichier n'a pas de vue stratégie cigare — uniquement dans `Ponton10km.html`.

---

### 5.3 `Ponton10km.html` (1176 lignes)

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

**⚠️ `renderCourseDetail` ligne 720 — crash si `positions_tour` absent :**
```js
const nb = c.positions_tour.length;  // TypeError si null/undefined
```
Fix à appliquer :
```js
if (!c.positions_tour || !c.positions_tour.length) {
  document.getElementById('fiche-content').innerHTML =
    '<div class="fiche"><div class="empty-r">Positions par tour non disponibles.</div></div>';
  return;
}
```

---

## 6. Les fichiers pontons KO

### `ponton_ko_ibiza2026.html`

Modèle de ponton pour les courses KO. Charge `resultats_ko_el.json`.

**Pour créer un nouveau ponton KO :**
1. Dupliquer ce fichier
2. Renommer : `ponton_ko_{ville}{annee}.html`
3. Mettre à jour `CONFIG`, `STARTLIST_F`, `STARTLIST_H`, `METEO_F`, `METEO_H`
4. Vérifier la correspondance des noms avec les clés du JSON

---

## 7. Palette de couleurs commune

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

## 8. Workflow de mise à jour

### Après une course KO

1. Ouvrir `resultats_ko_el.json` (branche `data`)
2. Ajouter la course dans `KO_DATA`
3. Ajouter les entrées dans `KO_HF` ou `KO_HH`
4. `git push` sur la branche `data`

### Checklist — ajouter une course 10km

1. **Ajouter l'entrée dans `CH` ou `CF`** avec :
   - `groupes[][]` calculés (seuil 3s entre nageurs consécutifs)
   - `nageurs[]` avec `pos`, `ecart`, `vit`, `rv`, `di`
2. **Mettre à jour `DATA_H` ou `DATA_F`** pour chaque nageur de la course :
   - Ajouter ou mettre à jour son entrée avec `positions_tour`, `vitesses_tour`, `rang`, `nb_nageurs`
   - `positions_tour` doit être identique à `pos[]` de l'entrée `CH`/`CF`
3. **Recalculer `strategie`** pour tous les nageurs impactés (jalons 20, 40, 60, 80, 100%)
4. **Valider le JSON :**
   ```bash
   python3 -c "import json; json.load(open('resultats_10km_el.json')); print('OK')"
   ```
5. `git push` sur la branche `data`

### Avant un nouveau ponton

1. Extraire la startlist du PDF officiel World Aquatics
2. Vérifier la correspondance exacte des noms avec `DATA_F`/`DATA_H` (⚠️ prénoms tronqués !)
3. Mettre à jour `CONFIG`, `STARTLIST_F/H` dans le fichier ponton
4. Récupérer la météo sur Open-Meteo et remplir `METEO_F/H`
5. Tester en local avec Live Server
6. `git push` sur `main`

**Source météo recommandée :** Open-Meteo (gratuit, sans clé API)
```
https://api.open-meteo.com/v1/forecast?latitude=41.00&longitude=9.63
  &hourly=temperature_2m,windspeed_10m,windgusts_10m,winddirection_10m
  &timezone=Europe/Rome&forecast_days=1
```

### Test en local

```bash
python3 -m http.server 8000
# puis ouvrir http://localhost:8000
```

**⚠️ Le fetch pointe vers GitHub raw**, pas localhost. En local, modifier temporairement l'URL du fetch pour pointer vers un fichier local.

---

## 9. Bugs connus et diagnostic (mai 2026)

### 9.1 Hommes non fonctionnels dans `analyse_course_el.html` et `Ponton10km.html`

**Diagnostic complet effectué le 08/05/2026.**

La branche `data` contient bien 28 courses dans `CH` et des nageurs dans `DATA_H`, mais **le script Python de génération n'a traité complètement que `golfo26_h`**. Pour les 27 autres courses hommes :

| Problème | Portée | Symptôme visible |
|----------|--------|-----------------|
| `CH[x].groupes` vide `[]` | 27/28 courses | Onglet Groupes : SVG blanc |
| `CH[x].nageurs[i].rv` = null | 27/28 courses | Onglet Indice EL : "Données non disponibles" |
| `CH[x].nageurs[i].di` = null | 27/28 courses | Indice EL absent |
| `DATA_H[i].courses[c].positions_tour` absent | 27/28 courses | **Crash JS** dans `renderCourseDetail` |
| `DATA_H[i].strategie` = null | 100% nageurs H | Onglet Stratégie : "Pas assez de données" |
| `DATA_F[i].strategie` = null | 100% nageurs F | Idem côté femmes |
| `CH['CdM_Ibiza26']` absent | 1 course | Course manquante dans le sélecteur H |

**Sheets présents dans `DATA_H` mais absents de `CH`** (à régulariser) :
`golfo25_h`, `ibiza25_h`, `ibiza26_h`, `meet4_25_h`, `singapour25_h`, `starigrad25_h`

### 9.2 Autres points de vigilance

- **Noms tronqués dans les PDF** : compléter les prénoms avant insertion dans le JSON.
- **Correspondance des noms** : moindre différence (espace, tiret, majuscule) → historique absent dans le ponton.
- **fetch() en `file://`** : impossible. Toujours tester avec un serveur local.
- **Groupes calculés côté Python** : le seuil de 3s est dans le script Python, pas dans le JS.

---

## 10. Backlog / Évolutions prévues

### Correctifs prioritaires
- [ ] Régénérer `resultats_10km_el.json` : remplir `CH.groupes`, `rv`/`di`, `positions_tour`, `vitesses_tour` et `strategie` pour les 27 courses hommes manquantes
- [ ] Ajouter `CH['CdM_Ibiza26']`
- [ ] Ajouter guard null dans `renderCourseDetail` ligne 720
- [ ] Régulariser les 6 sheets `_h` présents dans `DATA_H` mais absents de `CH`

### Applis analyse
- [ ] Couplage avec résultats officiels pour afficher les positions de tous les nageurs aux points de passage

### Pontons
- [ ] Automatiser la récupération de la météo via l'API Open-Meteo au chargement

### Maintenance JSON
- [ ] Script Python : documenter et vérifier le seuil de regroupement (confirmé à 3s)
- [ ] Script Python pour extraire automatiquement les résultats depuis les PDF World Aquatics
