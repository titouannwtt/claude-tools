# Requêtes d'analyse Search Console

Gabarit d'analyse pour la phase 2 (audit) et pour le suivi mensuel (voir `../07-mesure.md`, §2). Tout
passe par l'API `searchanalytics.query` en lecture seule. Aucune clé n'est écrite dans les fichiers : le
chemin de la clé du compte de service vient de la variable d'environnement `GSC_SERVICE_ACCOUNT`.

## 0. Accès (une fois)

1. Ajouter l'adresse du compte de service comme utilisateur de la propriété `sc-domain:[DOMAINE]`
   (Search Console, Paramètres, Utilisateurs et autorisations).
2. Portée : `https://www.googleapis.com/auth/webmasters.readonly`.
3. Variables d'environnement : `GSC_SERVICE_ACCOUNT` (chemin du fichier de clé, hors dépôt),
   `GSC_SITE` (par exemple `sc-domain:[DOMAINE]`).

```python
# gsc.py : fonction de lecture paginée. Dépendances : google-auth, requests, pandas.
import os, requests, pandas as pd
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITE = os.environ["GSC_SITE"]

def _token():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GSC_SERVICE_ACCOUNT"], scopes=SCOPES)
    creds.refresh(Request())
    return creds.token

def query(start, end, dimensions, filters=None, page_size=25000):
    """Toutes les lignes de searchanalytics.query (pagination par startRow)."""
    url = "https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % requests.utils.quote(SITE, safe="")
    headers = {"Authorization": "Bearer " + _token()}
    rows, start_row = [], 0
    while True:
        body = {"startDate": start, "endDate": end, "dimensions": dimensions,
                "rowLimit": page_size, "startRow": start_row}
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        r = requests.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        batch = r.json().get("rows", [])
        rows += batch
        if len(batch) < page_size:
            break
        start_row += page_size
    out = pd.DataFrame([{**{d: k for d, k in zip(dimensions, r["keys"])},
                         "clicks": r["clicks"], "impressions": r["impressions"],
                         "ctr": r["ctr"], "position": r["position"]} for r in rows])
    return out

# Exemple : 90 jours (le dernier jour disponible a 2 à 3 jours de retard)
# df = query("2026-07-10", "2026-10-09", ["query", "page"])
# df.to_csv("gsc-90j.csv", index=False)
```

Le script de soumission de sitemaps de la campagne (`scripts/gsc-submit-sitemaps.py`) utilise la portée
`webmasters` (écriture); pour l'analyse, utiliser la portée en lecture seule.

## 1. Totaux et découpages de base

| Besoin | Dimensions | Filtre |
|---|---|---|
| Totaux de la propriété | aucune (ou `["date"]` pour la courbe) | |
| Vue par page | `["page"]` | |
| Marché réel de chaque langue | `["country"]` | `page` contient `/fr/` |
| Mobile contre ordinateur | `["device"]` | |
| Requête + page (analyses ci-dessous) | `["query","page"]` | |

Note : le total de la propriété est supérieur à la somme des lignes `query+page` (requêtes anonymisées
absentes des lignes). Comparez toujours des chiffres de même nature.

Filtre par langue (exemple : pages françaises) :

```python
fr = query(start, end, ["query", "page"],
           filters=[{"dimension": "page", "operator": "contains", "expression": "/fr/"}])
```

Pour la langue racine (sans préfixe), filtrer par exclusion : `operator: "notContains"` pour chaque préfixe
de langue, ou calculer la langue dans pandas depuis l'URL.

```python
LANGS = ["fr","es","de","it","pt","nl","pl","ja","ko"]
def lang_of(url):
    path = url.split("://",1)[-1].split("/",1)[-1]
    first = path.split("/",1)[0]
    return first if first in LANGS else "en"
df["lang"] = df["page"].map(lang_of)
```

## 2. Positions 5 à 20 : les gains rapides

Requêtes proches de la première page ou du haut de la seconde, avec du volume : réécrire le titre et la
description (voir `../07-mesure.md`, §2.4), enrichir la section qui répond.

```python
q = df[(df.position >= 5) & (df.position <= 20) & (df.impressions >= 30)]
q = q.sort_values("impressions", ascending=False)
print(q[["query","page","impressions","clicks","ctr","position"]].head(50).to_string(index=False))
```

Seuils d'impressions à adapter : 30 pour un petit site (sur 90 jours), 100 ou plus pour un grand. Exemple
de la campagne : `accordeur basse en ligne`, 679 impressions, position 9,0, 6 clics.

## 3. CTR faible à position correcte

Pages ou requêtes qui apparaissent mais ne reçoivent pas de clics : le titre ou la description ne donne
pas envie, ou la requête n'est pas servie par l'intention de la page.

```python
# Courbe de CTR attendue calculée sur VOS données, par tranche de position
bins = [0,3,7,10,20,50,1000]
df["tranche"] = pd.cut(df.position, bins=bins)
courbe = df.groupby("tranche", observed=True).apply(
    lambda g: pd.Series({"impr": g.impressions.sum(), "clics": g.clicks.sum(),
                         "ctr": g.clicks.sum() / max(g.impressions.sum(), 1)}))
print(courbe)

# Lignes sous la courbe : CTR inférieur à la moitié de la médiane de leur tranche, avec du volume
med = df.groupby("tranche", observed=True).ctr.median()
df["ctr_attendu"] = df.tranche.map(med).astype(float)
bas = df[(df.impressions >= 50) & (df.ctr < 0.5 * df.ctr_attendu) & (df.position <= 20)]
print(bas.sort_values("impressions", ascending=False).head(40)[["query","page","impressions","clicks","ctr","position"]])
```

Ne comparez pas la marque au reste : retirer d'abord les requêtes de marque.

```python
MARQUE = ["[nom de marque]", "[nom de domaine]", "[variante]"]
df["marque"] = df["query"].str.lower().apply(lambda s: any(m in s for m in MARQUE))
hors_marque = df[~df.marque]
```

Pages à au moins 100 impressions et CTR sous 1 % (tableau de la campagne) :

```python
pages = df.groupby("page").agg(impressions=("impressions","sum"), clicks=("clicks","sum"),
                               position=("position","mean"))
pages["ctr"] = pages.clicks / pages.impressions
print(pages[(pages.impressions >= 100) & (pages.ctr < 0.01)].sort_values("impressions", ascending=False))
```

## 4. Pages sans clic

Pages indexées qui reçoivent des impressions mais zéro clic, et pages du sitemap qui ne reçoivent AUCUNE
impression (non indexées, mal classées ou sans demande).

```python
par_page = df.groupby("page").agg(impressions=("impressions","sum"), clicks=("clicks","sum"))
sans_clic = par_page[(par_page.impressions >= 20) & (par_page.clicks == 0)]
print(sans_clic.sort_values("impressions", ascending=False).head(40))

# Pages du sitemap absentes de GSC : comparer à la liste des URL du sitemap
import re, urllib.request
sm = urllib.request.urlopen("https://[DOMAINE]/sitemap-0.xml").read().decode()
urls = set(re.findall(r"<loc>([^<]+)</loc>", sm))
vues = set(df.page)
print(len(urls - vues), "URL du sitemap sans aucune impression sur la période")
```

Les pages sans impression se traitent par ordre : (1) est-elle indexée (outil d'inspection d'URL) ? (2) a-t-elle
un lien interne ? (3) répond-elle à une requête qui existe ? Ne pas ajouter de contenu avant d'avoir
répondu à ces trois questions.

## 5. Requêtes sans page : les pages à créer

Requêtes avec des impressions pour lesquelles aucune page du site n'est faite : la page qui apparaît est
l'accueil, un article voisin, ou une page d'une autre langue.

Méthode A (à la main, rapide) : repérer les requêtes dont la page classée n'est PAS une page de besoin.

```python
BESOIN = r"/(tuner|clavier|detection|metronome|accords|gammes|transposer|tablature)/"  # à adapter
pas_besoin = hors_marque[~hors_marque.page.str.contains(BESOIN, regex=True)]
cand = pas_besoin[pas_besoin.impressions >= 20].sort_values("impressions", ascending=False)
print(cand.head(60)[["query","page","impressions","position"]])
```

Méthode B (avec l'inventaire du build, `geo-inventory.csv`) : requêtes dont aucun mot significatif ne figure
dans un titre ou un h1 du site.

```python
inv = pd.read_csv("geo-inventory.csv")
corpus = (inv["title"].fillna("") + " " + inv["h1"].fillna("")).str.lower().tolist()
STOP = {"en","ligne","gratuit","online","free","de","la","le","les","du","des","a","the","for","and"}
def sans_page(q):
    mots = [m for m in q.lower().split() if m not in STOP and len(m) > 2]
    return bool(mots) and not any(all(m in c for m in mots) for c in corpus)
cand = hors_marque[(hors_marque.impressions >= 20)].copy()
cand["sans_page"] = cand["query"].map(sans_page)
print(cand[cand.sans_page].sort_values("impressions", ascending=False).head(60)[["query","page","impressions","position"]])
```

Résultats à lire avec jugement : une requête sans page n'est pas toujours un besoin à servir. Critères de
la campagne pour créer une page : une intention distincte (une URL par intention), du volume, une
fonction réelle du produit (vérifiée dans le code), une page qui serait supérieure à ce qui se classe. Par
exemple, `midi keyboard online` (position 13, sans page dédiée) a donné la page de clavier MIDI; une page
d'outil inexistant sur le web a été refusée.

## 6. Fiche par langue

Produire pour chaque langue un fichier `requetes/<langue>.md` avec :

1. Totaux (clics, impressions, nombre de lignes requête x page).
2. Par page : impressions, clics, position moyenne et les 8 meilleures requêtes avec impressions et
   position.
3. Top 40 des requêtes (requête, page, impressions, clics, CTR, position).
4. Synthèse thématique (requêtes contenant un mot clé du domaine) et tableau « pages à au moins 100
   impressions et CTR sous 1 % ».

```python
def fiche(df, lang):
    d = df[df.lang == lang]
    print("Clics", d.clicks.sum(), "Impressions", d.impressions.sum(), "Lignes", len(d))
    top = (d.groupby("page").apply(lambda g: g.sort_values("impressions", ascending=False).head(8))
            .reset_index(drop=True))
    return top
```

La fiche de la langue est l'entrée du traducteur pour construire titres et descriptions (voir
`../05-multilingue.md`, §5).

## 7. Sitemaps et inspection

```python
# Lire l'état des sitemaps (erreurs, avertissements, dernier passage)
site = requests.utils.quote(SITE, safe="")
r = requests.get("https://www.googleapis.com/webmasters/v3/sites/%s/sitemaps" % site,
                 headers={"Authorization": "Bearer " + _token()}, timeout=30)
for s in r.json().get("sitemap", []):
    print(s["path"], "erreurs", s.get("errors"), "avertissements", s.get("warnings"), "dernier passage", s.get("lastDownloaded"))
```

L'inspection d'URL individuelle (indexée ou non, canonique choisie par Google) existe dans l'API
`urlInspection`; elle est limitée en volume quotidien : à réserver aux pages prioritaires.

## 8. Rythme

| Fréquence | Requêtes à lancer |
|---|---|
| Hebdomadaire | totaux 28 jours, erreurs de sitemap |
| Mensuelle | §2 (positions 5 à 20), §3 (CTR faible), §4 (pages sans clic), fiches par langue |
| Trimestrielle | §5 (requêtes sans page), revue de la liste des besoins du panel |
