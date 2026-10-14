# Search Console analysis queries

Analysis template for phase 2 (audit) and for monthly tracking (see `../07-measurement.md`, §2). Everything goes through
the `searchanalytics.query` API, read-only. No key is written in the files: the path to the service account key comes
from the `GSC_SERVICE_ACCOUNT` environment variable.

## 0. Access (once)

1. Add the service account's address as a user of the property `sc-domain:[DOMAIN]` (Search Console, Settings, Users
   and permissions).
2. Scope: `https://www.googleapis.com/auth/webmasters.readonly`.
3. Environment variables: `GSC_SERVICE_ACCOUNT` (path to the key file, outside the repository), `GSC_SITE` (for
   example `sc-domain:[DOMAIN]`).

```python
# gsc.py: paginated read function. Dependencies: google-auth, requests, pandas.
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
    """All rows of searchanalytics.query (paginated by startRow)."""
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

# Example: 90 days (the latest available day is 2 to 3 days late)
# df = query("2026-07-10", "2026-10-09", ["query", "page"])
# df.to_csv("gsc-90j.csv", index=False)
```

The campaign's sitemap submission script (`scripts/gsc-submit-sitemaps.py`) uses the `webmasters` scope (write); for
analysis, use the read-only scope.

## 1. Totals and basic breakdowns

| Need | Dimensions | Filter |
|---|---|---|
| Property totals | none (or `["date"]` for the trend) | |
| Per-page view | `["page"]` | |
| Real market of each language | `["country"]` | `page` contains `/fr/` |
| Mobile vs desktop | `["device"]` | |
| Query + page (analyses below) | `["query","page"]` | |

Note: the property total is higher than the sum of the `query+page` rows (anonymized queries are absent from the
rows). Always compare figures of the same kind.

Filter by language (example: French pages):

```python
fr = query(start, end, ["query", "page"],
           filters=[{"dimension": "page", "operator": "contains", "expression": "/fr/"}])
```

For the root language (no prefix), filter by exclusion: `operator: "notContains"` for each language prefix, or compute
the language in pandas from the URL.

```python
LANGS = ["fr","es","de","it","pt","nl","pl","ja","ko"]
def lang_of(url):
    path = url.split("://",1)[-1].split("/",1)[-1]
    first = path.split("/",1)[0]
    return first if first in LANGS else "en"
df["lang"] = df["page"].map(lang_of)
```

## 2. Positions 5 to 20: quick wins

Queries close to the first page or at the top of the second, with volume: rewrite the title and description (see
`../07-measurement.md`, §2.4), enrich the section that answers.

```python
q = df[(df.position >= 5) & (df.position <= 20) & (df.impressions >= 30)]
q = q.sort_values("impressions", ascending=False)
print(q[["query","page","impressions","clicks","ctr","position"]].head(50).to_string(index=False))
```

Impression thresholds to adapt: 30 for a small site (over 90 days), 100 or more for a large one. Campaign example:
`accordeur basse en ligne`, 679 impressions, position 9.0, 6 clicks.

## 3. Low CTR at a decent position

Pages or queries that appear but get no clicks: the title or description does not make people want to click, or the
query is not served by the page's intent.

```python
# Expected CTR curve computed on YOUR data, per position bracket
bins = [0,3,7,10,20,50,1000]
df["tranche"] = pd.cut(df.position, bins=bins)
courbe = df.groupby("tranche", observed=True).apply(
    lambda g: pd.Series({"impr": g.impressions.sum(), "clics": g.clicks.sum(),
                         "ctr": g.clicks.sum() / max(g.impressions.sum(), 1)}))
print(courbe)

# Rows below the curve: CTR under half the median of their bracket, with volume
med = df.groupby("tranche", observed=True).ctr.median()
df["ctr_attendu"] = df.tranche.map(med).astype(float)
bas = df[(df.impressions >= 50) & (df.ctr < 0.5 * df.ctr_attendu) & (df.position <= 20)]
print(bas.sort_values("impressions", ascending=False).head(40)[["query","page","impressions","clicks","ctr","position"]])
```

Do not compare the brand with the rest: remove the brand queries first.

```python
MARQUE = ["[brand name]", "[domain name]", "[variant]"]
df["marque"] = df["query"].str.lower().apply(lambda s: any(m in s for m in MARQUE))
hors_marque = df[~df.marque]
```

Pages with at least 100 impressions and CTR under 1% (campaign table):

```python
pages = df.groupby("page").agg(impressions=("impressions","sum"), clicks=("clicks","sum"),
                               position=("position","mean"))
pages["ctr"] = pages.clicks / pages.impressions
print(pages[(pages.impressions >= 100) & (pages.ctr < 0.01)].sort_values("impressions", ascending=False))
```

## 4. Pages without clicks

Indexed pages that receive impressions but zero clicks, and sitemap pages that receive NO impressions (not indexed,
poorly ranked or with no demand).

```python
par_page = df.groupby("page").agg(impressions=("impressions","sum"), clicks=("clicks","sum"))
sans_clic = par_page[(par_page.impressions >= 20) & (par_page.clicks == 0)]
print(sans_clic.sort_values("impressions", ascending=False).head(40))

# Sitemap pages absent from GSC: compare with the list of sitemap URLs
import re, urllib.request
sm = urllib.request.urlopen("https://[DOMAIN]/sitemap-0.xml").read().decode()
urls = set(re.findall(r"<loc>([^<]+)</loc>", sm))
vues = set(df.page)
print(len(urls - vues), "sitemap URLs with no impressions in the period")
```

Pages with no impressions are handled in order: (1) is it indexed (URL inspection tool)? (2) does it have an internal
link? (3) does it answer a query that exists? Do not add content before answering these three questions.

## 5. Queries without a page: pages to create

Queries with impressions for which no page of the site exists: the page that appears is the home page, a neighboring
article, or a page in another language.

Method A (manual, quick): spot the queries whose ranking page is NOT a need page.

```python
BESOIN = r"/(tuner|clavier|detection|metronome|accords|gammes|transposer|tablature)/"  # to adapt
pas_besoin = hors_marque[~hors_marque.page.str.contains(BESOIN, regex=True)]
cand = pas_besoin[pas_besoin.impressions >= 20].sort_values("impressions", ascending=False)
print(cand.head(60)[["query","page","impressions","position"]])
```

Method B (with the build inventory, `geo-inventory.csv`): queries for which no significant word appears in any title or
h1 of the site.

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

Read the results with judgment: a query without a page is not always a need to serve. Campaign criteria to create a
page: a distinct intent (one URL per intent), volume, a real product function (verified in the code), a page that
would be better than what ranks. For example, `midi keyboard online` (position 13, no dedicated page) led to the MIDI
keyboard page; a tool page for a tool that does not exist on the web was refused.

## 6. Sheet per language

For each language, produce a file `requetes/<langue>.md` with:

1. Totals (clicks, impressions, number of query x page rows).
2. Per page: impressions, clicks, average position and the top 8 queries with impressions and position.
3. Top 40 queries (query, page, impressions, clicks, CTR, position).
4. Thematic summary (queries containing a keyword of the domain) and a table "pages with at least 100 impressions and
   CTR under 1%".

```python
def fiche(df, lang):
    d = df[df.lang == lang]
    print("Clicks", d.clicks.sum(), "Impressions", d.impressions.sum(), "Rows", len(d))
    top = (d.groupby("page").apply(lambda g: g.sort_values("impressions", ascending=False).head(8))
            .reset_index(drop=True))
    return top
```

The language sheet is the translator's input to build titles and descriptions (see `../05-multilingual.md`, §5).

## 7. Sitemaps and inspection

```python
# Read the sitemap status (errors, warnings, last pass)
site = requests.utils.quote(SITE, safe="")
r = requests.get("https://www.googleapis.com/webmasters/v3/sites/%s/sitemaps" % site,
                 headers={"Authorization": "Bearer " + _token()}, timeout=30)
for s in r.json().get("sitemap", []):
    print(s["path"], "errors", s.get("errors"), "warnings", s.get("warnings"), "last pass", s.get("lastDownloaded"))
```

Individual URL inspection (indexed or not, canonical chosen by Google) exists in the `urlInspection` API; it is limited
in daily volume: reserve it for priority pages.

## 8. Rhythm

| Frequency | Queries to run |
|---|---|
| Weekly | 28-day totals, sitemap errors |
| Monthly | §2 (positions 5 to 20), §3 (low CTR), §4 (pages without clicks), sheets per language |
| Quarterly | §5 (queries without a page), review of the panel's list of needs |
