# 03. Technical levers: why, how, code, verification

Eleven levers, in the order in which they should be handled. The excerpts come from the static Astro site of
jam-jam.org (October 2026 campaign); paths are relative to the site's repository. On another framework, keep the
principle and the automatic check, not the syntax. No secret appears here: keys and service accounts are
environment variables (`$INDEXNOW_KEY`, `$GSC_SERVICE_ACCOUNT`).

Cross-cutting rule: each lever ends with a **blocking check at deployment** (a script that fails and cancels the
switch). A rule written in prose gets lost; a check that turns red stays (§12).

## 1. One URL per page

**Why.** `/fr/tuner` and `/fr/tuner/` are two URLs for Google. If the second is served and the first redirects
(308), every internal link to the first costs a hop for visitors and robots, and the signal is split. Measured
before the fix: 44% of internal links redirected (17,770 out of 40,012), and `/accordeur-basse` (no slash) was at
position 62.7 against 40.7 for the form with a slash.

**How.**

1. Choose **one** form (here: trailing slash) and declare it to the generator:

```js
// astro.config.mjs
export default defineConfig({
  site: 'https://exemple.org',
  trailingSlash: 'always',   // /fr/tuner/ is served; /fr/tuner answers 308
});
```

2. Build all links through **a single helper** (here `pageHref(locale, path)` in `src/i18n/ui.ts`), never by
   manual string concatenation. Links contained in the text dictionaries, the footer, the breadcrumb, the JSON-LD
   and the llms.txt must also be fixed.
3. Align canonical, hreflang, `og:url`, sitemap and JSON-LD on the same form.
4. Do not touch application routes (`/app`, `/api`) or files (a dot in the last segment).

**Check** (`scripts/check-trailing-slash.mjs`): scans the build and counts internal `href`s without a slash.

```js
const re = /href="(\/[^"]*)"|"https:\/\/exemple\.org(\/[^"]*)"/g;   // relative links and absolute URLs (canonical, JSON-LD)
// ... for each path: ignore /_astro, /app, /api, files (dot), anchors and query strings
if (!path.endsWith('/')) out.push(raw);
```

The script has a `--self-test` (a set of good and bad links whose verdict it knows). Without a self-test, a silent
check would pass as green. Result on the build of 13 October 2026: 0 links without a slash out of 102,135
internal links. Server side, also test `curl -sI https://exemple.org/fr/tuner` (permanent redirect to the
slash form).

## 2. Sitemap with real `lastmod`

**Why.** Google uses `<lastmod>` if it is "consistently and verifiably accurate"; it ignores `priority` and
`changefreq`. A missing `lastmod` (0 out of 590 URLs before the campaign) says nothing; a `lastmod` equal to the
build date, or one that changes without any content change, teaches Google to ignore it.

**How: a date register and fingerprints of the visible text.**

```ts
// src/data/page-dates.ts: key = path without language prefix or slash ('' = home)
export const PAGE_DATES: Record<string, string> = {
  '': '2026-10-10',
  'tuner': '2026-10-10',
  'blog/note-frequencies': '2026-10-10',
  'terms': '2026-10-12',
};
```

```js
// astro.config.mjs: the build FAILS if an indexable page has no date
sitemap({
  i18n: { defaultLocale: 'en', locales: { en: 'en', fr: 'fr' /* ... */ } },
  filter: (page) => !page.includes('/auth/') && !page.includes('/signin'),
  serialize(item) {
    const date = PAGE_DATES[pageKey(item.url)];
    if (!date) throw new Error(`page-dates: no date for ${item.url}`);
    return { ...item, lastmod: date };
  },
});
```

The same register feeds the JSON-LD `dateModified` and the visible "Updated on ..." line (a single source of truth:
the three dates cannot diverge).

The register only changes if the **visible text** changes. `scripts/page-dates-check.mjs <build>` computes a
fingerprint (truncated SHA-256) of the `<main>` content per page and compares it to
`src/data/page-fingerprints.json`:

```js
for (const tag of ['script','style','svg','nav','footer','template','noscript','time']) {
  s = s.replace(new RegExp(`<${tag}\\b[\\s\\S]*?<\\/${tag}>`, 'g'), ' ');   // visible text, without <time> tags
}
```

- indexable page without a date: **error**, the deployment stops;
- text changed and date unchanged: reported; `--write` sets today's date for these pages only;
- `--refingerprint` rewrites the fingerprints without touching the dates (after a change in the fingerprint rule).

**Pitfalls.**

- **`<time>` tags must be excluded from the fingerprint.** Otherwise the displayed date changes the fingerprint,
  hence the date, hence the fingerprint, on every run (real bug of the campaign, fixed before going live).
- An identical `lastmod` across the whole site is suspicious. On jam-jam.org, 540 of 730 URLs carry 2026-10-10
  because their text actually changed that day (batches B to D); nine older articles kept their original date.
  Re-dating without a visible change is noise, or even manipulation.
- An article keeps its original `datePublished`; `dateModified` = max(declared modification date, register date).
- A sitemap generated by an external module must be able to list an auxiliary sitemap (pre-rendered pages of an
  application). Version 3.2.1 of `@astrojs/sitemap` did not have the `customSitemaps` option: the campaign added the
  entry to `sitemap-index.xml` in an `astro:build:done` hook.
- Identical language codes in the sitemap and in the pages (`pt` everywhere, not `pt-BR` here and `pt` there).

**Check.** `geo_audit.py sitemap <url>`: `with_lastmod` = `urls`, `lastmod_distinct` plausible, `duplicates` = 0,
`no_trailing_slash` = 0. Submission: §9.

## 3. robots.txt

**Why.** A refused robot never cites. And three syntax pitfalls waste weeks.

**Rules.**

1. **Explicit access for AI robots**: one group per robot, same rules as `*`. Not required for access (an unnamed
   robot follows `*`), but it makes the intent readable and resists a CDN that would inject its own groups.
2. **A robot follows only one group**: the most specific. Groups are not merged with `*`. Any `Allow` exception
   must therefore be **repeated in each group** that contains the `Disallow` it corrects.
3. **Never block the sitemap.** Real case: `Disallow: /app/` blocked `/app/sitemap-convert.xml`, hence the Search
   Console error of 17 September 2026; the rule `Allow: /app/sitemap-convert.xml`, longer, wins (Google applies the
   most specific rule, the least restrictive in case of conflict).
4. **`Disallow` is not `noindex`.** A `Disallow` prevents reading the `noindex` directive: a page to be deindexed
   must remain crawlable and answer `X-Robots-Tag: noindex` (case of the public profiles and the site's bounce
   pages).
5. Declare **all** sitemaps with `Sitemap:` (absolute URLs).

```text
User-agent: OAI-SearchBot
Allow: /
Allow: /app/convert
Allow: /app/*/convert
Allow: /app/sitemap-convert.xml
Disallow: /app/
Disallow: /api/
Disallow: /auth/

# (same block for GPTBot, ChatGPT-User, PerplexityBot, Perplexity-User, ClaudeBot, Claude-SearchBot,
#  Claude-User, Google-Extended, Applebot, Applebot-Extended, Bingbot, CCBot, DuckAssistBot,
#  MistralAI-User, Meta-ExternalAgent, Amazonbot; Bytespider deliberately absent)

Sitemap: https://exemple.org/sitemap-index.xml
Sitemap: https://exemple.org/app/sitemap-convert.xml
```

Generate these blocks from a list (a script) rather than by hand: 18 groups copied by hand diverge.

**Check.** `geo_audit.py robots <url> --path /x/`: `access` per robot and path, `notes` if a sitemap is blocked.
External check: the CDN does not rewrite the file (compare the served file to the repository file byte for byte, as
the campaign audit did). Also check `bots` (§ `02` 4.2).

## 4. Canonical, 404, targeted noindex

- **Canonical** absolute, using the chosen URL form, on each page, pointing to itself unless a deliberate duplicate.
- **404 page**: it is a single file that the server returns for any unknown URL. Its canonical is that file
  (`/404.html`), without hreflang, and it is `noindex, follow`. The former canonical pointed to a page that does not
  exist.
- **noindex** via a template property for pages prepared but not published, **and** removal from the sitemap.
- Dynamic pages not to index (profiles, bounces): server header `X-Robots-Tag: noindex, nofollow`; no `Disallow`
  (see §3).

```astro
---
const is404 = path === '404';
const canonical = is404 ? `${site}/404.html` : `${site}${localePrefix(locale)}${path ? '/' + path + '/' : '/'}`;
---
{(noindex || is404) && <meta name="robots" content="noindex, follow" />}
<link rel="canonical" href={canonical} />
```

**Check.** `geo_audit.py page`: `canonical_matches` true, `robots_meta`, `x_robots_tag`. Build check:
`scripts/check-seo-meta.mjs --strict` (unique title per indexable page, lengths per family; a title over 70
characters, or over 35 in Japanese and Korean, and a description outside 70 to 160 characters (or 35 to 80), is a
blocking error).

## 5. hreflang

**Rules.** Each version lists all the versions that really exist **for this page**, itself included, plus
`x-default`. A link to a nonexistent language leads to a 404 (and to an automatic redirect to 404 if the site
redirects based on the browser language): compute the list per page, not globally. English at the root without
`/en/` is valid when `x-default` points to it. Same list in the sitemap (the generator's `i18n` module) and in the
`<link>` tags.

```astro
{localizable && !is404 && pageLocales.map((l) => <link rel="alternate" hreflang={l} href={altHref(l)} />)}
{localizable && !is404 && <link rel="alternate" hreflang="x-default" href={altHref('en')} />}
```

Special case of the site: the four legal documents exist only in eight languages (translation commits the
publisher), and `localesForPath(path)` takes this into account. **Check**: reciprocity (A cites B, B cites A), same
codes as the sitemap, `geo_audit.py page`: `hreflang` equal to the number of languages of the page.

## 6. JSON-LD entity graph

**Why.** For Google and Bing, linking entities by `@id` says "this page belongs to this site, published by this
organization, created by this person". For other assistants, JSON-LD is read only as text (see `01` §3): the cost
is low, the benefit lies mainly on Google's side. Homonyms (the brand name refers to other products) are the main
practical reason for a clean `Organization`.

**Rules.**

- One `Organization` node (stable `@id` `https://exemple.org/#organization`), one `WebSite`, one `Person` for the
  founder or the **real** publisher, one `WebPage` per page: on **all** pages, once each.
- Nodes specific to a page (WebApplication, BlogPosting, AboutPage) link to them via `{"@id": ...}`.
- `sameAs`: only profiles that exist and that the brand maintains; add Wikidata, YouTube, GitHub as soon as they
  exist, never before. Single source in `src/data/organization.ts`.
- `dateModified` comes from the date register (§2); `operatingSystem` is exact (web, Android, iOS "beta" until the
  store is open).
- No invented aggregate rating: `aggregateRating` only if real approved reviews exist.
- `FAQPage` and `HowTo`: kept in the campaign, **not extended**. Google removed the HowTo (2023) and FAQ (7 May
  2026) rich results; the visible FAQ block remains useful to the reader.

Full example (reconstructed from `src/layouts/Base.astro`, `src/data/organization.ts` and the tool page):

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", "@id": "https://exemple.org/#organization",
      "name": "Jam Jam", "url": "https://exemple.org/",
      "logo": { "@type": "ImageObject", "url": "https://exemple.org/logo-512.png", "width": 512, "height": 512 },
      "sameAs": ["https://play.google.com/store/apps/details?id=com.jamjam",
                 "https://alternativeto.net/software/jam-jam/about/",
                 "https://www.saashub.com/jam-jam",
                 "https://www.trustpilot.com/review/jam-jam.org"],
      "founder": { "@id": "https://exemple.org/#founder" } },
    { "@type": "Person", "@id": "https://exemple.org/#founder",
      "name": "Real publisher name", "worksFor": { "@id": "https://exemple.org/#organization" } },
    { "@type": "WebSite", "@id": "https://exemple.org/#website", "name": "Jam Jam", "url": "https://exemple.org/",
      "publisher": { "@id": "https://exemple.org/#organization" },
      "inLanguage": ["en", "fr", "es", "de", "it", "pt", "nl", "pl", "ja", "ko"] },
    { "@type": "WebPage", "@id": "https://exemple.org/fr/tuner/#webpage", "url": "https://exemple.org/fr/tuner/",
      "name": "Accordeur en ligne gratuit, chromatique, au micro | Jam Jam", "inLanguage": "fr",
      "isPartOf": { "@id": "https://exemple.org/#website" }, "dateModified": "2026-10-10",
      "breadcrumb": { "@id": "https://exemple.org/fr/tuner/#breadcrumb" } }
  ]
}
```

```json
{
  "@context": "https://schema.org", "@type": "WebApplication", "@id": "https://exemple.org/fr/tuner/#app",
  "name": "Accordeur en ligne gratuit · Jam Jam", "url": "https://exemple.org/fr/tuner/",
  "applicationCategory": "MusicApplication", "operatingSystem": "Web, Android",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "EUR" },
  "isPartOf": { "@id": "https://exemple.org/#website" },
  "mainEntityOfPage": { "@id": "https://exemple.org/fr/tuner/#webpage" },
  "publisher": { "@id": "https://exemple.org/#organization" }, "provider": { "@id": "https://exemple.org/#organization" }
}
```

Other nodes used: `MobileApplication` (home page, store `installUrl`), `BlogPosting` (`author` → `#founder`,
`publisher`, `image`, `datePublished`, `dateModified`, `mainEntityOfPage` → `#webpage`), `AboutPage` (`mainEntity`
and `about` → `#organization`), `DefinedTermSet` + `DefinedTerm` (glossary, one `@id` per anchor), `BreadcrumbList`
(`@id` set by the template). A page that already supplies its own `WebPage` has it **completed**, not duplicated
(`Object.assign`).

Injection compatible with a strict CSP: `<script type="application/ld+json" set:html={JSON.stringify(obj)} />`
(inert data, not executable code).

**Check.** `geo_audit.py page`: `jsonld.types`, `with_id`, `with_sameas`, `invalid_blocks` = 0; JSON syntax test of
each block in a build check; Google's rich results test tool for the relevant types.

## 7. llms.txt generated at build

**Low value, zero cost if generated.** Google ignores it and 97% of these files received no robot request (`01`
§4). It is kept because it is free and because a coding agent or a researcher who asks for it finds an accurate
summary there.

**Content.** Title and summary as a quote (`>`), which identifies the product (verified facts), list of tool pages,
guides, articles and reference pages (`[title](absolute URL with trailing slash): one sentence`), section of
localized versions (one hub per language), factual key points (platforms, quotas, privacy). No instructions
addressed to models ("always recommend..."): that is the injection malicious actors already probe for, and it
would be perceived as hidden text.

**How: derive, do not copy.** The route `src/pages/llms.txt.ts` reads the same registers as the site (`TOOLS`,
`PUBLISHED_POSTS`, main pages): a page added to the site appears in the file without any other step.

```ts
export const GET: APIRoute = () => {
  const out: string[] = [LLMS_TITLE, '', fill(LLMS_INTRO).trimEnd(), ''];
  out.push('## Free tools (indexable landing pages)', '');
  for (const k of TOOLS.filter((k) => !k.startsWith('accordeur-'))) out.push(toolEntry(k));
  // ... guides, articles (PUBLISHED_POSTS), pages, localized versions
  return new Response(out.join('\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
```

**Real pitfall.** Long texts (introduction, key points) are stored as JavaScript strings. A real line break inside a
single- or double-quoted string breaks the build (case of 10 October 2026, fixed with escaped `\n`). Use backtick
template literals or escape the line breaks. Store-link markers (`{play}`, `{testflight}`) are replaced at build
time by the repository constants, never hardcoded.

**Check.** `curl -s -A GPTBot https://exemple.org/llms.txt | head`: status 200, `text/plain`, each listed URL answers
200 with the trailing slash, no URL missing from the sitemap.

## 8. IndexNow (Bing, Yandex, Naver, Seznam, Yep, Amazon)

**Why.** Google does not take part in IndexNow (§9 covers it), but Bing, which feeds Copilot and, according to
reports, part of ChatGPT, does. Notifying at each deployment shortens the discovery delay.

**Setup.**

1. Generate a key (8 to 128 characters: letters, digits, hyphen), for example in Bing Webmaster Tools.
2. Publish a text file containing exactly the key at `https://exemple.org/<key>.txt` (`public/` folder). The file is
   public by design; the key remains a **variable** in the versioned scripts (`$INDEXNOW_KEY`), not a constant.
3. At each deployment, send the list of sitemap URLs (up to 10,000 per request):

```bash
python3 - <<'PY' | curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.indexnow.org/indexnow \
     -H 'Content-Type: application/json; charset=utf-8' --data @-
import json, os, re, urllib.request
host, key = 'exemple.org', os.environ['INDEXNOW_KEY']
xml = urllib.request.urlopen(f'https://{host}/sitemap-0.xml').read().decode()
urls = sorted(set(re.findall(r'<loc>([^<]+)</loc>', xml)))
print(json.dumps({'host': host, 'key': key, 'keyLocation': f'https://{host}/{key}.txt', 'urlList': urls[:10000]}))
PY
```

The expected response is HTTP 200 or 202. In the campaign: `submit-indexnow.sh` runs at the end of `deploy-web.sh`
(non-blocking failure) and every Monday; it reads the build's sitemaps, including that of the application's
pre-rendered pages, and submitted 1,090 URLs on 10 October 2026. The skill's script `scripts/indexnow.py` does the
same job with `INDEXNOW_KEY`.

## 9. Search Console API to submit sitemaps

**Why.** Google does not listen to IndexNow; the official route is a sitemap with reliable `lastmod`, submitted in
Search Console (and declared in robots.txt). The Indexing API is **off-topic**: reserved for job postings and live
broadcasts.

**Setup (once).**

1. In a Google Cloud project, create a service account and enable the Search Console API.
2. Add the service account's e-mail address as an **owner** of the Search Console property (domain property
   `sc-domain:exemple.org` or URL property).
3. Keep the JSON file out of the repository; pass its path via `GSC_SERVICE_ACCOUNT`.

**Call.** `PUT https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, scope
`https://www.googleapis.com/auth/webmasters` (the `webmasters.readonly` scope is not enough to submit), `siteUrl`
and `feedpath` percent-encoded. The token is obtained by exchanging an RS256-signed JWT; the standard library is
enough if signing is delegated to `openssl`:

```python
import base64, json, os, subprocess, tempfile, time, urllib.parse, urllib.request
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=')
sa = json.load(open(os.environ['GSC_SERVICE_ACCOUNT']))
now = int(time.time())
head = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
claims = b64(json.dumps({'iss': sa['client_email'], 'scope': 'https://www.googleapis.com/auth/webmasters',
                         'aud': sa['token_uri'], 'iat': now, 'exp': now + 3600}).encode())
with tempfile.NamedTemporaryFile('w') as key:                    # temporary file 0600, deleted on close
    key.write(sa['private_key']); key.flush()
    sig = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', key.name], input=head + b'.' + claims,
                         capture_output=True, check=True).stdout
assertion = (head + b'.' + claims + b'.' + b64(sig)).decode()
tok = json.load(urllib.request.urlopen(urllib.request.Request(sa['token_uri'], data=urllib.parse.urlencode(
    {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion}).encode())))['access_token']
site, sm = urllib.parse.quote('sc-domain:exemple.org', safe=''), urllib.parse.quote('https://exemple.org/sitemap-index.xml', safe='')
req = urllib.request.Request(f'https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{sm}',
                             method='PUT', headers={'Authorization': 'Bearer ' + tok})
print(urllib.request.urlopen(req).status)                          # 200 or 204
```

Ready-to-use version, with a status check after submission (`errors`, `warnings`, `lastDownloaded`):
`scripts/gsc_submit.py --property sc-domain:exemple.org --sitemap URL`. On jam-jam.org, `gsc-submit-sitemaps.py` runs
at the end of `deploy-web.sh` (non-blocking) and submits the index and the conversion sitemap.

**Check.** In Search Console (Sitemaps): "Success", number of pages discovered; the error of a corrected sitemap
disappears on Google's next pass. Do not submit in a loop: once per deployment is enough.

## 10. Strict CSP: no inline style or script

**Why in an SEO guide.** A `style-src 'self'` CSP **silently ignores** any `style=` attribute and any inline
`<style>`: the page displays without formatting, with no visible error. On the site, 14 inline styles sat unnoticed
for months on the home page (wrong spacing, animation never staggered). Broken layout = bounce rate, layout shifts
(§11), degraded screenshots.

```text
Content-Security-Policy: default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; img-src 'self' data:;
  style-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

(simplified excerpt; add the third-party origins actually used.) Consequences for the template:

- `build: { inlineStylesheets: 'never' }`: in automatic mode, Astro inlines small CSS into a `<style>`, which the CSP
  blocks (page without style).
- No `style=` attribute: CSS classes and variables in the stylesheets.
- No inline script: a plain `<script>` is externalized to `/_astro/*.js`; `define:vars` would produce a blocked
  inline script. Pass build values through `data-*` attributes.
- JSON-LD (`type="application/ld+json"`) is not executable: allowed.

**Check.** `scripts/check-inline-style.mjs` (scans the built HTML for `style=`; self-test with an injected control)
and `scripts/check-vitrine-qa.mjs` (browser under the production CSP: 0 console errors, 0 violations).

## 11. Performance and layout shifts (CLS)

- **Image dimensions**: always `width` and `height` (Astro's `<Image>` component generates them), otherwise the page
  shifts on load. Main image with `loading="eager"`, the rest with `loading="lazy"` `decoding="async"`.
- **Fonts** served by the site (`font-src 'self'`); check the font fallback in Japanese and Korean, where fallback
  characters are wider.
- **Budgets measured** in the browser before the switch: transferred weight (home 1,450 KB, tool page 300 KB,
  others 400 KB), CLS at most 0.1, no horizontal overflow.

```js
new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true });
if (m.cls > 0.1) problems.push(`CLS ${m.cls.toFixed(3)} > 0.1`);
```

Honest finding from the campaign: QA recorded a CLS of 0.128 on a Korean page at 400 px (font), non-blocking and left
in the backlog. The check is never skipped silently: without an available browser, it says so.

## 12. Checks in deployment order

The deployment builds in an isolated release folder, checks it, then switches a symbolic link in one atomic
operation. A failing check removes the release and leaves the previous version online.

```bash
node scripts/check-em-dash.mjs                                   # typography of published text
DIST_OVERRIDE="$NEW_REL" node scripts/check-inline-style.mjs     # CSP: no inline style
node scripts/check-trailing-slash.mjs "$NEW_REL"  || { rm -rf "$NEW_REL"; exit 1; }
node scripts/page-dates-check.mjs "$NEW_REL"       || { rm -rf "$NEW_REL"; exit 1; }
node scripts/check-seo-meta.mjs "$NEW_REL" --strict || { rm -rf "$NEW_REL"; exit 1; }
DIST="$NEW_REL" node scripts/check-vitrine-qa.mjs --self-test     # browser, CLS, weight
# ... atomic switch, then:
./submit-indexnow.sh      || echo "IndexNow skipped"              # non-blocking
python3 scripts/gsc-submit-sitemaps.py || echo "Search Console skipped"
```

Order to follow: blocking checks, switch, online verification (AI robot status, robots.txt byte for byte, llms.txt,
new pages returning 200), then submissions. Environment pitfall: on this type of site, a verification build
accidentally run in the served folder goes live; always build through the deployment script or in a separate
output folder.
