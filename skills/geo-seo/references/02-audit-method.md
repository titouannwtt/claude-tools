# 02. Auditing an unknown site, read-only

Method for a GEO + SEO audit of a site you do not know. Everything is done without changing anything: public
HTTP requests, reading the repository if one is provided, reading Search Console if access exists. The
deliverable is a quantified `AUDIT.md`, ranked by severity, which feeds the plan (impact/cost) and the
implementation batches.

Worked example: the audit of jam-jam.org of 10 October 2026 (§10), measured on the live release (994 HTML
files), Search Console from 10 July to 9 October 2026, and real requests with AI robot user-agents.

## 1. Principles

- **Read-only.** No writes, no submissions, no circumvention of protections. The script of the skill
  `scripts/geo_audit.py` respects this rule (standard library, JSON on stdout).
- **Measure before judging.** Each finding carries a figure and the command that produced it.
- **From cheapest to most expensive.** Access and redirect checks (minutes) come before reading the content
  (hours) and before off-site actions (days).
- **Separate finding from hypothesis.** Say "measured" or "assumed". An unreadable server log is a finding;
  "AI robots do not come" would be a hypothesis.
- **Audit public exposure first.** See the site as a robot does: raw HTML, without JavaScript, with the robots'
  user-agents.

## 2. The script `geo_audit.py`

Call: `python3 -I <skill>/scripts/geo_audit.py <subcommand> ...` (the `-I` flag prevents loading code from the
current directory). Python 3.8 or later, no dependencies. Exit codes: 0 success, 2 invalid arguments, 4 network
unreachable, 1 unexpected error.

| Subcommand | What it does | Useful JSON fields |
|---|---|---|
| `doctor` | Checks the Python version and network access | `python_ok`, `network` |
| `robots <url> [--path /x/]` | Reads `/robots.txt`, applies "longest rule, Allow on a tie" for each AI robot on the tested paths (by default `/`, `/blog/`, `/app/`), lists the declared sitemaps | `status`, `sitemaps`, `access` (robot, path, allowed), `notes` (sitemap blocked by a Disallow, AI robots blocked, no sitemap declared) |
| `sitemap <url>` | Loads the sitemap or index (two levels, 60,000 URLs maximum), counts the URLs | `urls`, `with_lastmod`, `lastmod_distinct`, `with_hreflang`, `hreflang_values`, `duplicates`, `no_trailing_slash`, `errors` (unreadable sitemaps or invalid XML) |
| `page <url> [--ignore-prefix /app/]` | Analyzes a page (follows redirects and reports them) | `title_len`, `description_len`, `canonical`, `canonical_matches`, `h1`, `visible_words`, `hreflang`, `jsonld` (types, `@id`, `sameAs`, invalid blocks), `internal_links_without_slash`, `has_time_element`, `first_paragraph_words`, `x_robots_tag`, `issues` |
| `bots <url>` | Requests the same page with each AI robot's user-agent (without following redirects) | `results` (status per robot), `refused`, a note if the response size differs by more than half |
| `crawl <url> --max N` | Regularly samples N pages from the sitemap and aggregates problems | `issues_summary`, `issues_examples`, `duplicate_titles`, `pages` |

Limits to know (they prevent false greens):

- `sitemap` does not check the status of each listed URL; `errors` only reports unreadable sitemaps. For
  statuses, see §4.
- `crawl` and `page` follow redirects: a sitemap URL that redirects stays invisible there, except via
  `redirected_from` of `page`. The redirect check is done with `curl` without `-L` (§4).
- `first_paragraph_words` measures the first paragraph of at least twelve words. It is not an "answer block"
  detector: the block is judged by reading (40 to 60 words answering the page's question, §8).
- `bots` sends robot user-agents from the auditor's IP address. A firewall that also checks the origin IP address
  (ranges published by the publishers) may respond differently to real robots: a 200 result is encouraging, not
  definitive; a 403 is already a defect to fix.
- `crawl` reads `/sitemap-index.xml` then `/sitemap.xml` at the root; for another location, use
  `sitemap <url>` then `page` on a sample.

## 3. Audit order

| Step | Question | Tool |
|---|---|---|
| 1 | Which indexable pages, by family and by language? | Sitemap, repository, `geo-inventory.py` (§4.1) |
| 2 | Do robots (human, Google, Bing, AI) receive the pages? | `bots`, `robots`, curl |
| 3 | One URL per page? | curl without following, `page` |
| 4 | Is the sitemap reliable and declared? | `sitemap`, `robots` |
| 5 | Titles, descriptions, canonical, hreflang | `crawl`, `page` |
| 6 | Structured data, entity | `page` (`jsonld`), reading the JSON-LD |
| 7 | Is the text in the raw HTML? | curl, `page` (`visible_words`) |
| 8 | Content: thinness, answer at the top, facts, dates, author | `crawl`, reading |
| 9 | Search Console: queries, positions 5 to 20, CTR | API or interface |
| 10 | Needs without a page | Search Console + inventory |
| 11 | Off-site presence, homonyms | Manual searches |
| 12 | Report by severity | `AUDIT.md` |

## 4. The checks, with commands

### 4.1 Inventory of indexable pages

If the repository is available, the inventory is done on the **build**, not on the sources (what the robot
receives is what counts). An inventory script produces one CSV line per page: family, language, title and
description (and their lengths), H1, canonical, robots, hreflang, JSON-LD types, dates, word count, internal
links. In the campaign, it is `scripts/geo-inventory.py` in the site's repository (model to reuse).

Without a repository, from the sitemap:

```bash
curl -s https://exemple.org/sitemap-index.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//'     # sitemaps
curl -s https://exemple.org/sitemap-0.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//' > urls.txt
wc -l urls.txt
awk -F/ '{l=$4; if (l ~ /^(fr|es|de|it|pt|nl|pl|ja|ko)$/) c[l]++; else c["en"]++} END{for(k in c) print c[k], k}' urls.txt   # per language
```

Then sort by family (home, tools, products, blog, legal, misc.) and note the `noindex` pages (`robots` meta or
`X-Robots-Tag` header). A site with prefixed languages (`/fr/`) and a default language at the root is valid.

### 4.2 Access and rendering without JavaScript

```bash
UA_BASE='Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; %s/1.0)'
for bot in GPTBot OAI-SearchBot ChatGPT-User ClaudeBot Claude-SearchBot Claude-User PerplexityBot \
           Perplexity-User Googlebot bingbot Applebot Amazonbot meta-externalagent MistralAI-User DuckAssistBot CCBot; do
  printf '%-18s ' "$bot"
  curl -s -o /dev/null -w '%{http_code} %{size_download}\n' -A "$(printf "$UA_BASE" "$bot")" https://exemple.org/page/
done
```

Reading: everything must return 200 (or a clean redirect to the canonical URL) with a size close to a browser's.
A 403 or 429 for a single robot, very different content, or a challenge page ("Verify you are human") indicates
a firewall or CDN to adjust. `geo_audit.py bots <url>` does the same thing in JSON.

Rendering without JavaScript:

```bash
curl -s https://exemple.org/page/ -o page.html
grep -c '<h1' page.html                                    # exactly one H1 in the raw HTML
python3 -I -c "import re,sys;h=open('page.html').read();h=re.sub(r'<(script|style|svg|nav|footer)\b.*?</\1>','',h,flags=re.S);print(len(re.findall(r'\w+',re.sub(r'<[^>]+>',' ',h))))"
```

A word count close to zero, or a lone `<div id="root"></div>`, means the content is built client-side: invisible
to OpenAI, Anthropic and Perplexity (see `00` §2). The routes of an application (SPA) may stay out of search if
each need has a static equivalent; say so in the report.

### 4.3 One URL per page (trailing slash, redirects)

This is the most profitable check of the campaign audit. Two steps.

1. **Status of the sitemap URLs without following redirects** (sample or full list):

```bash
while read -r u; do
  printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$u")" "$u"
done < <(shuf -n 300 urls.txt) | awk '{c[$1]++} END{for(k in c) print c[k], k}' | sort -rn
```

Any sitemap URL that returns anything other than 200 is a defect (the sitemap must only list canonical,
indexable URLs returning 200).

2. **Share of internal links that redirect.** Extract the internal `href`s from a few dozen pages, deduplicate,
   test without following:

```bash
curl -s https://exemple.org/page/ | grep -o 'href="/[^"#?]*"' | sed 's/href="//;s/"$//' | sort -u |
while read -r p; do printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "https://exemple.org$p")" "$p"; done |
awk '{c[$1]++} END{for(k in c) print c[k], k}'
```

`geo_audit.py page` gives `internal_links_without_slash` per page. On a site whose pages live at `/x/`, a `/x`
link costs a redirect (308 or 301) for every visitor and blurs the canonical signal.

### 4.4 robots.txt

```bash
curl -s https://exemple.org/robots.txt
python3 -I <skill>/scripts/geo_audit.py robots https://exemple.org --path / --path /blog/ --path /app/
```

To check:

- no `Disallow` on pages to be indexed; a `Disallow` does not remove a page from an index and prevents reading a
  `noindex` (see `03` §3-4);
- sitemaps are declared with `Sitemap:` using absolute URLs;
- a sitemap is not located in a forbidden folder (jam-jam.org case: `/app/sitemap-convert.xml` under
  `Disallow: /app/`);
- a named group (`User-agent: GPTBot`) does not inherit the rules of the `*` group: if it exists, it must repeat
  them, including the `Allow` exceptions;
- AI robots are not blocked by accident (the command's `notes`);
- do not audit with `urllib.robotparser`: it applies the first rule in file order and ignores wildcards (see
  `01` §5).

### 4.5 Sitemap

```bash
python3 -I <skill>/scripts/geo_audit.py sitemap https://exemple.org/sitemap-index.xml
```

Indicators: number of URLs, `with_lastmod` (target: all), `lastmod_distinct` (a single date everywhere is
suspicious, unless everything really changed the same day), `with_hreflang`, `hreflang_values` (same codes as in
the pages: `pt` versus `pt-BR` is a real discrepancy), `duplicates`, `no_trailing_slash`. Also check that each
auxiliary sitemap (pre-rendered pages of an application, for example) is declared in the index **and** in
robots.txt, and answers 200 to robots.

### 4.6 Canonical, titles, descriptions, duplicates

```bash
python3 -I <skill>/scripts/geo_audit.py crawl https://exemple.org --max 60
```

`issues_summary` aggregates: long title (over 65 characters), long description (over 160), missing canonical,
number of H1 different from one, thin content (under 300 visible words), links without slash, absence of
structured data, `noindex`. `duplicate_titles` lists identical titles. For an exhaustive check on the build, use
a dedicated script (model: `check-seo-meta.mjs`, `03` §4): thresholds per family, lengths in Latin characters and
shorter for Japanese and Korean (pixel and character width). Separately check the canonical of the 404 page (it
must be the 404 file itself) and the absence of canonicals pointing to a URL that redirects.

### 4.7 Structured data

`geo_audit.py page` returns `jsonld.types`, the number of nodes with `@id` and with `sameAs`, and the invalid
blocks. To read in addition, by hand, on three pages (home, a tool, an article):

- `Organization`: `sameAs` pointing to **real** profiles, `logo` at 512 px, stable `@id`;
- `WebSite` and `WebPage` linked by `@id`, honest `dateModified`;
- `BlogPosting`: real `author`, `datePublished` and `dateModified`;
- appropriate types (`WebApplication`, `MobileApplication`, `SoftwareApplication`) with an exact
  `operatingSystem`;
- consistency between the markup and the visible text (prices, platforms).

### 4.8 Search Console

See `07-measurement.md` for setup and the API. For the audit, three extractions over 90 days:

1. **Queries in positions 5 to 20** with at least a few dozen impressions: these are the quick wins.
2. **Pages with near-zero CTR**: at least 100 impressions and under 1% clicks, to compare with the site's average
   CTR (3.48% on jam-jam.org).
3. **Queries without a dedicated page**: group by theme, spot those whose displayed page is a generic page (case
   of "midi keyboard online" shown on the piano page).

Typical request body (`searchanalytics.query` API, read-only scope):

```json
{"startDate": "2026-07-10", "endDate": "2026-10-09", "dimensions": ["page", "query"], "rowLimit": 25000}
```

Warning: the per-query export omits anonymized queries. On jam-jam.org, the query file totals 134 clicks and
11,457 impressions while the property shows 735 clicks and 21,094 impressions; the gap is probably due to this
anonymization (unverified hypothesis). Use the property totals for orders of magnitude, and the per-query export
to decide on titles.

### 4.9 Thin content, answer at the top, author, dates

- Visible words per page (`visible_words`), distribution by family; flag pages under 300 words, but judge on
  value: a short, complete page is worth more than a padded one (Google: no ideal length).
- First paragraph: promotional, or an answer? Does the page answer the question of its H1 within the first lines?
- Figures: are there any, are they verifiable and dated?
- Author: a real name (identifiable person or publisher), or a generic brand name on every page?
- Update date visible and in the JSON-LD; do not confuse `datePublished` and `dateModified`.
- Languages: leftover foreign text on a translated page (count words in another language).

### 4.10 Off-site presence

Manual searches, no account needed: brand name on Google and Bing, results for the query "brand + category",
presence of a knowledge panel, mentions in directories, videos, public repositories, forums, press, reviews. Note
the **homonyms** (does the name refer to other products?) and the brand's search volume in Search Console. Mentions
are the ceiling of the site alone (`06-off-site.md`).

### 4.11 Access logs

If the server is readable, this is the only direct measure of robot visits:

```bash
grep -E 'GPTBot|OAI-SearchBot|ChatGPT-User|ClaudeBot|Claude-User|Claude-SearchBot|PerplexityBot|Perplexity-User|bingbot|Googlebot' access.log |
  awk '{print $NF}' | sort | uniq -c | sort -rn | head
```

If the logs are not accessible (campaign case), write it as a limit of the audit and propose opening this access or
using the CDN's robot analysis.

## 5. Severity grid

| Severity | Definition | Examples from the audit |
|---|---|---|
| Critical | Prevents indexing, splits signals or breaks a sitemap | Internal links redirecting, sitemap blocked by robots.txt, AI robots refused |
| High | Deprives Google of information or blurs the entity | No `lastmod`, `Organization` without `sameAs`, no real author |
| Medium | Loss of clicks or citability | Descriptions too long, zero CTR on positions 8 to 13, no answer at the top, thin pages |
| Low | Hygiene | Isolated duplicate titles, 404 canonical, outdated text on platforms |
| Ceiling | Limit off the site | Few external mentions, brand little searched |

For each finding: severity, measure, probable cause, proposed fix, effort (low, medium, high).

## 6. Reporting: the format of `AUDIT.md`

1. Scope and method (date, build or environment measured, tools, access limits).
2. Inventory of indexable pages: table by family with the number of pages, then by language.
3. What is done well (useful: it is not "fixed").
4. What is done badly, by severity, with figures.
5. Key Search Console measures.
6. Recommendations ranked by impact/cost, which feed the plan.

After review by two outside perspectives (AI marketing, the site's business), produce a plan v2: the trade-offs
(pages to create, merge, remove, postpone) take precedence over the initial version.

## 7. Worked example: jam-jam.org, 10 October 2026

### 7.1 Inventory (972 indexable pages)

| Family | Pages | Detail |
|---|---|---|
| Home | 10 | one per language |
| Tools | 130 | 13 tools × 10 languages |
| Tuners by instrument | 180 | 18 instruments × 10 languages |
| Blog | 160 | index + 15 articles × 10 languages |
| Conversion (`/app/convert`, pre-rendered) | 380 | about 37 conversions × 10 languages |
| Misc. | 70 | premium, developers, changelog, contact, feedback... |
| Legal | 42 | 8 languages (legal choice: no Japanese or Korean) |

English at the root, nine other prefixed languages. `noindex`: login, bounce page, SPA `/app/*`, profiles `/u/*`
(server header).

### 7.2 What was good

- Static site: all the text is in the HTML.
- 10 complete languages with hreflang and `x-default` (932 pages with 11 alternatives), `html lang` correct
  everywhere.
- robots.txt open to 13 AI robots, not rewritten by the CDN (byte-identical), all receive 200 on the public pages;
  the SPA remains protected by design.
- Rich JSON-LD: FAQPage (720 pages, 2,710 questions), WebApplication, HowTo, BreadcrumbList, BlogPosting.
- IndexNow on every deployment and every Monday (591 URLs accepted); rich llms.txt.
- Rare-instrument pages that rank (bass tuner in French at position 9, guitalele 8, mandolin, violin, cello 9 to 13).
- Discipline of published figures (marketing brief and automatic check).

### 7.3 What was bad, by severity

| # | Severity | Finding | Measure |
|---|---|---|---|
| 1 | Critical | Internal links served as 308 redirects | 17,770 links out of 40,012 (44%) to `/fr/tuner` instead of `/fr/tuner/`; `/accordeur-basse` position 62.7 versus `/accordeur-basse/` position 40.7; `/fr/clavier` in "Redirect error" since July |
| 2 | Critical | No `lastmod` | 0 out of 590 URLs in the sitemap |
| 3 | Critical | Conversion sitemap not declared, blocked by robots.txt, in error in Search Console since 17 September | `Disallow: /app/` covered the file; hreflang `pt-BR` versus `pt` elsewhere |
| 4 | High | `Organization` without `sameAs`, logo on only 10 pages, no `@id` | 490 pages concerned |
| 5 | High | No real author (brand on 150 pages), no About page, no update date outside the blog | Publisher public only in the legal notices |
| 6 | High | Needs without a page | "midi keyboard online" in position 13 without a dedicated page; learn piano, karaoke, song import, chord progressions, glossary; no citable reference content |
| 7 | Medium | Descriptions too long, duplicate titles, wrong 404 canonical | 547 pages over 160 characters; 12 duplicate titles |
| 8 | Medium | Access logs unreadable for the session | Impossible to count AI robot visits |
| 9 | Medium | No answer at the top of tool pages, few figures | First paragraph promotional |
| 10 | Medium | Near-zero CTR on positions 8 to 13 | Violin online tuner: 297 impressions, 0 clicks; online mandolin tuner: 176, 0; afinador cromático: 181, 0; `/transposer`: 448 impressions, 1 click; `/accords`: 851, CTR 0.7% |
| 11 | Medium | Thin blog | 61 article pages under 300 words (piano-chords 231, tune-your-harp 254) |
| 12 | Medium | Use outside the official scope of the Indexing API | 412 tool URLs submitted |
| 13 | Low | Outdated platforms in the data and llms.txt | "Android, Web" whereas the iOS beta exists |
| 14 | Ceiling | Generic queries out of reach | Metronome in position 70 to 82 |
| 15 | Ceiling | Off-site | Three known external mentions; nothing on Wikidata, YouTube, Reddit, public GitHub, press; the brand gets 72 impressions over 90 days; homonyms |

Key Search Console measures over 90 days: 735 clicks, 21,094 impressions, CTR 3.48%, average position 26.6.
Clicks and impressions by language: English root 311 and 8,725, French 171 and 5,397, Spanish 118 and 4,002,
German 43 and 1,369, Japanese 33 and 314, Italian 14 and 695, Polish 14 and 194, Portuguese 12 and 222, Korean
6 and 188, Dutch 3 and 206.

### 7.4 What to take from the example

- The first three defects (redirects, `lastmod`, blocked sitemap) are purely technical, cheap to fix, and came
  before any content writing.
- Queries at an average position (5 to 20) with zero clicks were handled first: a title and description rewritten
  for the exact query (see `04`).
- Needs without a page were measured on real queries, not imagined (see `04`).
- The off-site ceiling was documented and prepared (`06-off-site.md`), not executed by the auditor.
- After correction (live build of 13 October): 0 internal links without a slash out of 102,135 measured links,
  `lastmod` on the 730 URLs of the main sitemap, but 46 article pages still under 300 words (same script): only the
  two thinnest articles had been enriched, by plan choice ("enrich without padding").
