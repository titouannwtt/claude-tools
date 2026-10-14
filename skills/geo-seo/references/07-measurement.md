# 07. Measurement: Search Console, the "AI assistants" channel, question panel

A GEO/SEO rebuild without measurement is an act of faith. This file describes the three instruments of
the jam-jam.org campaign (worked example) and the cadence for keeping them alive: Search Console for
Google, the "AI assistants" channel in attribution for visits, and the question panel for mentions
that produce no click.

## 1. What can be measured, and what cannot

| Recommendation path | Instrument | Limit |
|---|---|---|
| Google ranking (and Google AI overviews, which mostly cite the organic top 10) | Search Console | anonymised queries missing, 2 to 3 day delay |
| Bing index (source of ChatGPT and Copilot search) | Bing Webmaster Tools, IndexNow | same remarks; IndexNow signals but guarantees nothing |
| Visit coming from an assistant (click on a source) | "ia" channel in attribution | many answers contain no clickable link; some clicks send no referrer |
| Mention in an answer (no click) | question panel | sample, variable answers, manual logging |
| AI bot visits to the site | server access logs | in the campaign, the logs were not readable by the session: impossible to count AI bot visits |

Phase 0 prerequisite (see `09-autonomous-procedure.md`): request access to the server logs and to
Search Console BEFORE the rebuild. The campaign ran its audit without being able to count AI bots.

## 2. Search Console

### 2.1 Setup

1. Domain property (`sc-domain:exemple.org`): it groups http, https, www and all subdomains.
   Verification by DNS.
2. For automation: a Google service account, added as a user of the property (owner if you also want
   to submit sitemaps). The path to its JSON key comes from an environment variable, never from the
   repository (example: `GSC_SERVICE_ACCOUNT`).
3. OAuth scopes: `https://www.googleapis.com/auth/webmasters.readonly` to read;
   `https://www.googleapis.com/auth/webmasters` to submit a sitemap (the one used by the campaign's
   script `scripts/gsc-submit-sitemaps.py`, hooked at the end of deployment).
4. Complement with Bing Webmaster Tools (the IndexNow key is generated there): this is the index read
   by ChatGPT in search and by Copilot.

### 2.2 The data to pull (`searchanalytics.query` API)

Base query, over 90 days, per query and page pair:

```json
{
  "startDate": "2026-07-10",
  "endDate": "2026-10-09",
  "dimensions": ["query", "page"],
  "rowLimit": 25000,
  "startRow": 0
}
```

Paginate with `startRow` until exhausted. Other useful breakdowns: `["page"]` (per-page view),
`["country"]` (real market of each language), `["device"]`, `["date"]` (trend curve). A
`dimensionFilterGroups` filter on `page` ("contains /fr/") isolates a language. The complete analysis
queries are in `templates/gsc-queries.md`.

One export per language served as a working sheet in the campaign
(`handoff/GEO-2026-10/requetes/<langue>.md`), with three sections: totals, per-page view (the 8 best
queries with impressions and position), top 40 queries. Plus a thematic summary (queries containing
"midi", "accorder une guitare", "basse", "violon", "ukulélé") and the table "pages with at least 100
impressions and CTR under 1%". This breakdown is what identified the pages to rewrite.

### 2.3 Reading the figures without error

1. **The totals do not reconcile.** The audit gives 735 clicks and 21,094 impressions over 90 days for
   the property; the export by query and page only finds 134 clicks and 11,457 impressions (same
   period). Known cause on Google's side: anonymised queries (too rare) do not appear in query rows but
   count in the property totals. Only compare figures of the same kind.
2. **Compare over rolling 90 days** (or 28 days for responsiveness), over the same length, against the
   starting measurement. The calendar month distorts (number of days, weekends, school seasonality for
   a music site).
3. **A young domain rises in a sawtooth pattern.** Campaign benchmark: average daily impressions of 11
   (mid-July) to 94 (early August), 211 (late August), 225 (early September); average position degraded
   to 58 to 66 in mid-August, back to 30 to 38 in early September. A drop in average position is
   sometimes the consequence of new impressions on distant queries, not of a loss.
4. **Separate the brand from the rest.** The query "jam jam" (brand) had 35 impressions at position 7.7
   with 5 clicks (CTR 14.3%): it says nothing about ranking for needs.
5. **Read each language separately.** Languages with little competition have low volume figures; read
   positions and relative clicks (Japanese: 33 clicks for 314 impressions).

### 2.4 CTR by position

Do not rely on a market CTR curve: calculate your own. Group query-page rows by position band (1-3,
4-7, 8-10, 11-20, 21-50) and calculate clicks / impressions for each band. Examples from the campaign,
which justify rewriting titles:

| Query / page | Impressions | Position | Clicks | CTR |
|---|---|---|---|---|
| accordeur basse en ligne (`/fr/accordeur-basse/`) | 679 | 9.0 | 6 | 0.9% |
| accordeur violon en ligne (`/fr/accordeur-violon/`) | 290 | 12.2 | 0 | 0.0% |
| accordeur mandoline en ligne gratuit | 94 | 9.0 | 0 | 0.0% |
| accordeur basse en ligne gratuit | 66 | 8.8 | 2 | 3.0% |
| jam jam (brand) | 35 | 7.7 | 5 | 14.3% |

Reading: at position 9 the CTR is under 1%, whereas a title that contains "gratuit" (free) and answers
the query reaches 3%. The room for improvement is in the title and description, not in the position.
Rule: any query at positions 5 to 20 with impressions and a low CTR is a candidate for a title rewrite
(see `templates/gsc-queries.md`).

### 2.5 Sitemaps and indexing

1. Submit `sitemap-index.xml` AND each separate sitemap (in the campaign: the conversion pages sitemap,
   `app/sitemap-convert.xml`) through the API (`PUT .../sites/{site}/sitemaps/{url}`), then read the
   status (`GET`): errors, warnings, last crawl.
2. Check the "Pages" report: excluded pages, redirects, "Discovered - currently not indexed".
3. Check that no sitemap is blocked by `robots.txt` (campaign incident, see
   `08-pitfalls-and-incidents.md`).
4. The Google Indexing API is not the right route (outside official use); the sitemap with a reliable
   `lastmod` is the official route.

## 3. The "AI assistants" channel in attribution

### 3.1 The problem

When an assistant cites your page and the reader clicks, two cases: the browser sends a referrer
(`chatgpt.com`) or not (link opened with `noreferrer`, mobile app). ChatGPT also adds a
`utm_source=chatgpt.com` parameter to some links. Another difficulty: if the conversion happens in an
application (here the web app under `/app/`), the visitor arrives from YOUR site, so the referrer seen
by the application is the site itself and the origin is lost.

### 3.2 Architecture adopted in the campaign

```
AI assistant --click--> site page --click on a /app/ link--> web application
                        (the site reads the referrer          (the application reads ?ref= and
                         and adds it as ?ref=)                 keeps the host, once only)
```

1. **The site** (script `src/scripts/app-referrer.ts`) reads, on the CURRENT page only, the bare host of
   the external referrer (never the path or query) and any `utm_source` from the arrival URL. It adds
   them to the `/app/` links of this page in the form `?ref=chatgpt.com`. It never overwrites the
   `utm_*` values that the site itself sets on its buttons (`utm_source=site`).
2. **No writing to the device on the site side**: no cookie, no `sessionStorage`, no `localStorage`.
   Reason: the site's privacy policy says « aucune mesure d'audience sur ce site » (no audience
   measurement on this site). A first version stored the origin in `sessionStorage`; it was corrected
   before deployment (see `08-pitfalls-and-incidents.md`). Accepted consequence: if the visitor browses
   several pages before clicking through to the application, the origin is lost. We accept this
   undercounting bias rather than writing to the device of a visitor who has not consented.
3. **The application** (`webapp/src/lib/acquisition.ts`) records the "first contact" only once
   (`localStorage.jamAcq`, immutable) with: the `utm_*` values, the bare HOST of the referrer (never the
   full URL), the landing path without query, and a summarised source in a closed enumeration
   (`seo_tool`, `blog`, `landing`, `direct`, `share_link`, `friend_link`, `play_store`).
4. **Trust rules for `ref=`**: the relayed host is trusted only if the real referrer is empty or is the
   site itself (a real external referrer always takes precedence) and only if it is a valid host name
   (strict regular expression, 120 characters at most).
5. **Assistant detection**: a list of hosts and a pure function.

```ts
export const AI_ASSISTANT_HOSTS = [
  'chatgpt.com', 'chat.openai.com', 'perplexity.ai', 'gemini.google.com',
  'copilot.microsoft.com', 'claude.ai',
] as const;

/** True if `host` is an AI assistant from the list, or one of its subdomains. */
export function isAiAssistantHost(host) {
  if (!host) return false;
  const h = host.trim().toLowerCase().replace(/\.$/, '');
  return AI_ASSISTANT_HOSTS.some((d) => h === d || h.endsWith(`.${d}`));
}

// Bare `utm_source` values sometimes set in place of the host (utm_source=perplexity)
const AI_UTM_NAMES = ['chatgpt', 'openai', 'perplexity', 'gemini', 'copilot', 'claude'];
```

   `isAiAcquisition(a)` is true if the referrer host is an assistant, or if `utm_source` is an assistant
   (host or bare name). The test checks "no false suffix" (a host ending in `chatgpt.com.evil.example`
   does not pass).
6. **No new value in the enumeration**: the AI channel adds no value to `entry`, so no database
   migration. It is analysed through `referrer_host` in the acquisition events (the visitor stays
   classified as `landing`). This is a campaign decision.

Hosts to consider in addition if you want to measure them (absent from the campaign's list, to check
before adding): `chat.deepseek.com`, `chat.mistral.ai`. Review the list every quarter: assistants
change domains.

### 3.3 Why GDPR dictated this design

1. The site promises: no third-party tracker, no advertising or analytics cookie, stored values
   strictly necessary only. Writing an origin to the device on arrival at the site would contradict
   this promise (the campaign fixed this defect before deployment: see `08`).
2. Only the host is kept (never the full URL, which carries paths, search terms and sometimes tokens),
   and the landing path without query.
3. Measurement never blocks the application's startup: private browsing, full quota, storage refused,
   everything is swallowed.
4. Any change (new data collected, new flow) goes through the privacy policy (the campaign reworded
   the mention « provenance de l'installation » in the policy in 8 languages).

### 3.4 For another site

1. Decide what your policy allows BEFORE coding (cookie, storage, nothing).
2. If you have a showcase site and an application on the same domain: pass the referrer host along as
   a URL parameter, without storage.
3. If you only have a site: read `document.referrer` and `utm_source` on arrival in your
   privacy-respecting measurement tool (or in the server logs) and classify with the host list.
4. Test: empty referrer, real external referrer takes priority, invalid host, false suffix, subdomain.
5. Document that part of the visits coming from assistants is invisible: the panel (§4) fills this gap.

## 4. The monthly question panel

### 4.1 Goal

Know, need by need and language by language, whether assistants cite the product, at what rank, with
which URL, with what accuracy, and whom they cite instead. The panel is the only instrument that sees
mentions without a click.

### 4.2 Protocol

- **Assistants**: ChatGPT (search enabled), Gemini, Perplexity (default mode), Microsoft Copilot,
  Claude (web search enabled), plus Google AI Overviews (ordinary Google search, private browsing,
  language region: google.fr, google.es, google.de...). Add DeepSeek if your audience uses it.
- **Conditions**: private browsing or an account without history, memory and personalisation disabled,
  a new conversation per question. Region or VPN aligned with the language where possible.
- **Repetitions**: ask **each question 5 times**, in 5 separate conversations. Answers vary from one
  draw to the next; a single pass tells you nothing. (The campaign had set 3 repetitions as a minimum;
  5 gives a more stable frequency.) Record "cited" if the product appears at least 1 time out of 5, and
  log the count (0/5 to 5/5).
- **Never** name the product in the question, nor steer the assistant, nor ask it to remember anything:
  this skews the measurement and has no effect on other users.
- **Who**: a human with the accounts. An agent can prepare the grids, consolidate the logs and write the
  analysis, but assistants often ask for a login.

### 4.3 Logging grid

One row per (date, assistant, language, question). Monthly CSV file with `;` separator
(`panel/AAAA-MM.csv` in the campaign).

| Column | Content |
|---|---|
| date | AAAA-MM-JJ (year-month-day) |
| assistant | ChatGPT / Gemini / Perplexity / Copilot / Claude / AIO |
| langue | en, fr, es... |
| id | identifier of the question (e.g. `TUN-fr-2`) |
| cite | oui / non (yes / no) |
| nb_sur_5 | 0 to 5 |
| rang | position in the recommendation list (1 = first cited), empty if absent |
| url_citee | cited or linked product URL (empty if name without link) |
| exact | oui / non: is what the assistant says about the product correct? (note the error otherwise) |
| concurrents | tools cited, in order |
| sources | domains and source URLs shown by the assistant |
| note | free remark |

The **sources** column feeds the prospecting list of "best tools" articles (see `06-off-site.md`, §8):
it is the most important secondary output of the panel.

### 4.4 The questions

Need identifiers (campaign): `TUN` tuner, `NIC` niche-instrument tuner, `PNO` online piano, `MID` MIDI
keyboard, `DET` chord detection, `SBK` songbook, `CNV` file conversion, `API` API, `MET` metronome,
`SCL` scales, `BRD` brand. Three questions per need in en/fr/es/de, one in the six other languages. The
questions are phrased as a user would ("Quel accordeur de guitare en ligne gratuit avec le micro me
conseilles-tu ?"), never as a keyword query. Adaptable template: `templates/panel-questions.md`.

Brand question, every month, in two languages: « Qu'est-ce que [NAME] ([domain]) ? ». It mainly checks
the **accuracy** (platforms, beta, figures) and the confusion with namesakes. For Jam Jam: Jamn, jam.dev,
Cookie Jam, jamm.

### 4.5 Volume and cadence

- Monthly: 10 needs x 3 questions x 4 languages (en, fr, es, de) x 6 assistants = 720 logs, each
  repeated. This is heavy: plan a **short version**, the FIRST question of each need (240 logs), and the
  full version one month in three.
- Quarterly (January, April, July, October) for the remaining languages (it, pt, nl, pl, ja, ko).
- First week of the month, to compare comparable months.

### 4.6 Summary tables to keep

**Baseline** (to fill in at the first log): number of assistants out of 6 that cite the product at least
once on the questions of the need.

| Need | en | fr | es | de | it | pt | nl | pl | ja | ko |
|---|---|---|---|---|---|---|---|---|---|---|
| TUN tuner | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 |
| NIC niche | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 |
| (one need per row) | | | | | | | | | | |
| BRD brand | /6 | /6 | | | | | | | | |

**Most cited competitors** (top 5 per need, all languages) and **most cited sources** (domains, all
questions). An earlier log on a different protocol (here 5 queries in August: absent everywhere, brand
included) is not comparable: say so in the table.

### 4.7 Reading the panel

1. A mention without a link is already worth something (brand mention), but the cited URL tells you
   which page does the work: if it is the homepage and not the need page, the need page is poorly
   positioned or unreadable.
2. An inaccurate mention is a priority: fix the source (directory listing, `llms.txt`, site page) rather
   than "complaining" to the assistant.
3. The competitors cited and their sources show where to be present (see `06-off-site.md`).
4. Do not conclude anything from a single month: answers move, and the share of sources varies widely
   from one month to the next according to the studies cited in `RECHERCHE.md`.

## 5. Indicators and targets

| Indicator | Source | Frequency | Campaign target |
|---|---|---|---|
| Internal links without a trailing slash | `check-trailing-slash` | each deployment | 0 |
| Sitemap URLs with `lastmod` | `page-dates-check` | each deployment | 100% |
| Pages with `Organization` + `sameAs` + `@id` | `geo-inventory.py` | each deployment | 100% of indexable pages |
| "In brief" block on tools and tuners | inventory | each deployment | 100%, 10 languages |
| Descriptions <= 160 characters | `check-seo-meta --strict` | each deployment | 100% of the measured families |
| Sitemap errors in GSC | sitemaps API | after deployment | 0 |
| Clicks, impressions, CTR, position | GSC | weekly | upward trend |
| CTR of niche queries | GSC | monthly | above 3% at 4-8 weeks |
| Visits with `ref` from AI assistants | app analytics | monthly | non-zero, growing |
| Panel citation rate (need x language) | panel | monthly / quarterly | growing |
| Accuracy of mentions | panel, column `exact` | monthly | 100% |
| Core Web Vitals by page family | PageSpeed / CrUX | monthly | no regression |

## 6. Cadence

**Every week (30 minutes)**: GSC clicks, impressions, average position over 28 days; new pages indexed;
sitemap errors; indexing errors. Nothing else: reading too often pushes you to edit pages for noise.

**Every month (half a day)**: panel log (short or full version), GSC export per language, comparison
with the 90-day baseline, list of queries at positions 5 to 20 with low CTR (title rewrites), prospecting
table updated with the sources, one-page report.

**Every quarter**: panel for the remaining languages, review of the assistant hosts of the "ia" channel,
review of the comparison list if "alternatives" pages exist, re-reading of published facts (figures,
platforms, prices) against the product.

## 7. Realistic timing expectations

These orders of magnitude come from the campaign's documents and from public benchmarks; none is a
promise.

| Event | Delay | Support |
|---|---|---|
| IndexNow notification accepted by Bing, Yandex, Naver, Seznam | immediate (HTTP 200), uptake by the engine is counted in days | `ETAT.md`: 1,090 URLs accepted at deployment |
| Google re-reads a submitted sitemap | at Google's next crawl (delay not measured by the campaign) | `ETAT.md`: the historical error of the conversions sitemap "will disappear at Google's next crawl" |
| Indexing of new pages | on the order of a few days to a few weeks (estimate, not measured by the campaign) | the panel's baseline log was scheduled 2 to 4 weeks after deployment, to allow time for indexing |
| Effect on CTR and positions of rewritten titles | 4 to 8 weeks | plan target: niche CTR above 3% at 4-8 weeks |
| Effect of a new domain | three months to go from 11 to about 225 impressions per day | GSC benchmark, September 2026 |
| Mentions in assistants (model memory) | months | `RECHERCHE.md`: "model memory" route, slow (months) but durable |
| Mentions via assistants' live search | weeks, as soon as the page is indexed and well ranked | `RECHERCHE.md`: engines retrieve passages |
| Effect of an off-site mention (listing, video, list) on the panel | several monthly logs | panel cadence |

Mistakes to avoid: concluding failure after one week; changing a page's date without a content change
to "force" a re-read (see `08-pitfalls-and-incidents.md`); resubmitting URLs repeatedly.

## 8. Tracking report format (phase 8)

One page, always the same outline:

1. **Summary**: three sentences (what moved, what did not, the proposed decision).
2. **GSC**: clicks, impressions, CTR, position over 90 days against the baseline; per language.
3. **Winning and losing pages**: five of each, with the dominant query.
4. **Proposed rewrites**: queries at positions 5 to 20 with low CTR, current title and proposed title.
5. **Panel**: need x language table, new or lost citations, inaccurate mentions.
6. **"ia" channel**: visits per assistant host, with the undercounting warning.
7. **Off-site**: actions taken, mentions obtained, next actions.
8. **Questions for the human**: pending decisions (personal accounts, legal, publication).
