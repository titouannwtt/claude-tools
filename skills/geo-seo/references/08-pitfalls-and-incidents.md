# 08. Pitfalls and incidents of the campaign

Each entry follows the same outline: **Symptom**, **Cause**, **Fix**, **Guardrail** (what prevents the
return). The entries come from the audit, the plan, `ETAT.md` and the Git history of the jam-jam.org
campaign (October 2026). When the exact detail could not be re-read in the documents, the entry says so.

## The mechanical guardrails created or used

A rule that no machine checks ends up forgotten. Table of the checks, with their creation date (the
campaign created those of 2026-10-10; the others already existed and were used):

| Script | Role | Created | Blocking at deployment |
|---|---|---|---|
| `scripts/check-trailing-slash.mjs` | 0 internal link without a trailing slash to an HTML page (excludes `/app`, `/api`, `/_astro`, files) | campaign, batch A | yes |
| `scripts/check-seo-meta.mjs` | titles and descriptions: lengths depending on the script, unique titles; `--strict` fails on the slightest error | campaign, batch A | yes (`--strict`, since #74) |
| `scripts/page-dates-check.mjs` (+ `page-dates-init.mjs`) | sitemap `lastmod` and `dateModified` change only if the visible text changes (fingerprint of `<main>`); a page without a date fails the build | campaign, batch A | yes |
| `scripts/geo-inventory.py` | CSV inventory of each page: title, description, h1, canonical, hreflang, JSON-LD types, French words on non-French pages, dates, links | campaign, batch A | no (measurement before deployment) |
| `scripts/gsc-submit-sitemaps.py` | submits the sitemaps to Search Console through the API and shows errors and warnings | campaign, batch G | no (failure tolerated) |
| `src/data/geo-locales.ts` | computed availability of pages per language | campaign | by construction |
| import guard of `src/data/tool-reference-labels.ts` | a missing language in a table label breaks `astro build` | campaign, #73 | yes (the build fails) |
| `scripts/build-tool-reference.mjs` | generates `tool-reference.json` from the application's code (tunings, scales, chords) | campaign, batch B | no (generation) |
| `scripts/check-em-dash.mjs` | no em dash in published texts (dictionaries, pages, `llms.ts`); `--self-test` | existing | yes |
| `scripts/check-inline-style.mjs` | strict CSP (`style-src 'self'`): no `style=` attribute in the published site (the browser would ignore it silently) | existing | yes |
| `scripts/check-marketing-numbers.mjs` | recounts the catalogues from the application's data and compares with the published figures; also fails on known stale figures | existing | yes |
| `scripts/check-legal-parity.mjs` | structural parity, links, policy marker and figures between legal languages | existing | yes |
| `scripts/i18n-assemble.mjs` | validates a translated batch (keys, markers, double braces, dash) before turning it into a module | existing | yes |
| `scripts/check-vitrine-qa.mjs` | control pages at 390 and 1440 px under the production CSP: console, horizontal overflow, weight, CLS, animations | existing | yes |
| `scripts/check-developers-endpoints.mjs` | the developer page lists all the paths of the OpenAPI contract (tolerant of the absence of the neighbouring repository) | existing | yes |

All the checks have a `--self-test` mode that injects a control case and proves that the check turns
red (a check that cannot fail protects nothing). The `deploy-web.sh` deployment script builds in a
timestamped release folder, runs these checks on the build, and switches the site over only if they
pass (a failed build leaves the previous version online).

---

## A. Build, deployment, Git

### A1. Commit pushed to `main` with a broken build

- **Symptom**: one minute after a batch commit (`d950961`, new pages in the footer and `llms.txt`), a
  second commit (`62374d0`) fixes "build broken by d950961".
- **Cause**: in `src/i18n/llms.ts`, two JavaScript strings in quotes contained a real line break (a
  sentence cut as "at the latest 72 hours after upload / if it was never processed") instead of `\n`.
  The file no longer compiled. The commit was pushed without building the site.
- **Fix**: line breaks escaped in the strings (`62374d0`).
- **Guardrail**: ALWAYS chain `npm run build && git push` (the `&&` forbids the push if the build fails).
  Production was not touched because deployment goes through `deploy-web.sh`, which first builds in a
  separate release: `main` broken is not a broken site, but the next coordinator inherits a red branch.
  Add to the brief of each agent: "build before pushing, require exit code 0".

### A2. Bare build that goes to production

- **Symptom** (project history, which motivated the script): an isolated `npm run build` redeployed the
  showcase site, destroying the embedded application under `/app/` (bug of 12 July 2026).
- **Cause**: the application (SPA) is copied into `public/app/` BEFORE the showcase build; a build on its
  own reuses the last state present.
- **Fix and guardrail**: a single publication path, `deploy-web.sh`, which builds the application, copies
  it, builds the showcase site in `releases/<timestamp>/`, runs the checks, then switches atomically. Rule
  written in the project documentation: never a manual build or copy to production.

### A3. Hook that forbids `git stash`

- **Symptom**: an agent wants to set its changes aside to rebuild a clean state and is refused `git stash`
  (or `git checkout`/`git restore` on a directory) by a project hook.
- **Cause**: the working tree is shared with other sessions (agents, human). A `stash` or a directory
  `checkout` would also carry away the other sessions' uncommitted work, sometimes irrecoverably.
- **Fix**: work in a dedicated worktree, commit only its own files, revert explicitly named files, check
  `git status` before any commit.
- **Guardrail**: the `block-dir-revert.py` hook (refuses directory operations) plus the rule written in the
  repository's agent instructions. In the brief: "never stash". The detail of the campaign's precise
  incident was not re-read here; the rule and the hook are, however, verified.

### A4. `python -I` that hides modules

- **Symptom**: a Python script run with `-I` fails with `ModuleNotFoundError` for a module that is
  installed (or, conversely, works on one machine and not another).
- **Cause**: `-I` (isolated mode) ignores the `PYTHON*` environment variables and the user's package
  directory, so packages installed with `pip --user` disappear. The mode is intended for reading an
  untrusted folder (`geo-inventory.py` requires `python3 -I`, because the build folder is not trusted
  code), but it breaks a script that needs `requests` or `cryptography` installed outside the system.
- **Fix**: reserve `-I` for scripts that read untrusted data and use only the standard library; for the
  others (sitemap submission), use a virtual environment whose interpreter is called explicitly. Never run
  an interpreter inside the data folder.
- **Guardrail**: put the exact command (with or without `-I`) in the script's header, as
  `geo-inventory.py` does. The exact sequence of the incident could not be re-read in the documents.

### A5. WAF rule rewritten while losing its fields

- **Symptom**: after a firewall rule was updated by script, the rule lost some fields (commit `0eeee3d`,
  "Keep the WAF rule fields when updating it").
- **Cause**: the update API (PATCH) requires the full definition of the rule, including unchanged fields.
- **Fix**: rebuild the body from the rule as read (without `id`, `version`, `last_updated`), change only the
  expression, re-read and compare all fields after writing.
- **Guardrail**: `--dry-run` mode, re-reading and an assertion after writing.

---

## B. Technical: indexing, sitemap, robots

### B1. Half of the internal links through a 308 redirect

- **Symptom**: 44% of the internal links (17,770 out of 40,012) pointed to `/fr/tuner` instead of
  `/fr/tuner/`; Google indexed both forms and split the signal (`/accordeur-basse` at position 62.7 against
  `/accordeur-basse/` at position 40.7); `/fr/clavier` showed "Redirect error" in GSC.
- **Cause**: the server redirects addresses without a slash to addresses with a slash, but the components,
  dictionaries, footer, breadcrumb and JSON-LD linked the form without a slash.
- **Fix**: `trailingSlash: 'always'`, a single helper for building localised URLs (`pageHref`), correction
  of all components and dictionaries: 0 links without a slash across 308 pages.
- **Guardrail**: `check-trailing-slash.mjs` blocking at deployment, with its justified exclusions.

### B2. Sitemap without `lastmod`

- **Symptom**: none of the 590 URLs in the sitemap had a `lastmod`.
- **Cause**: the generator did not know which page had changed.
- **Fix**: registry `src/data/page-dates.ts` (one date per page key); `lastmod` and `dateModified` are drawn
  from it, never from the build date.
- **Guardrail**: `page-dates-check.mjs` (see B3); never put the build date in `lastmod`: Google stops
  trusting a field that changes everywhere at every deployment.

### B3. Unstable date fingerprint because of `<time>` tags

- **Symptom**: at each re-dating of a page, the text fingerprint changed, so the page seemed "modified"
  again at the next check, endlessly (commit `f5efe83`).
- **Cause**: the fingerprint hashed the visible text of `<main>`, which included the `<time>` tag carrying
  the "Updated on..." date (« Mis à jour le... »). Writing the new date changed the fingerprint.
- **Fix**: exclude `<time>` from the fingerprint (along with `script`, `style`, `svg`, `nav`, `footer`,
  `template`, `noscript`); a `--refingerprint` option that rewrites the fingerprints without touching the
  dates after a change of the fingerprint rule; 44 keys re-dated on 2026-10-10 because their text had really
  changed, 9 old articles keeping their original date.
- **Guardrail**: `page-dates-check.mjs --strict` reports a changed text without a changed date; `--write`
  re-dates only the keys whose text has changed. Rule: never a changed date without a changed text (a fraud
  signal for search engines).

### B4. `robots.txt` blocking the conversions sitemap

- **Symptom**: Search Console error on `app/sitemap-convert.xml` since 17 September.
- **Cause**: the file lives under `/app/`, which `Disallow: /app/` forbids; Google could not read it. The
  sitemap also used `pt-BR` while the rest of the site uses `pt`.
- **Fix**: `Allow: /app/sitemap-convert.xml` in EVERY `User-agent` block (the longest rule wins), plus the
  `Allow` lines for the conversion pages before the general `Disallow`.
- **Guardrail**: after each change to `robots.txt`, re-read the sitemap status through the API and test the
  sitemap URL with the Googlebot user-agent. A `Disallow` on a path that contains a sitemap or a page to
  index is a classic; list in `robots.txt`, in a dated comment, WHY each rule exists (the campaign's file
  does so).
- **Neighbouring pitfall**: do not put a `Disallow` on a URL you want to de-index; a `Disallow` prevents the
  robot from reading the `noindex` header. It is the `X-Robots-Tag: noindex` header that de-indexes, provided
  the robot is allowed to fetch the page.

### B5. Undeclared sitemap

- **Symptom**: the sitemap of the 380 conversion pages appeared neither in `sitemap-index.xml` nor in
  `robots.txt`.
- **Cause**: generated by another module (the SPA, pre-rendered), forgotten by the site's generator.
- **Fix**: declared in the index and by a `Sitemap:` line of `robots.txt`; submitted through the API.
- **Guardrail**: `gsc-submit-sitemaps.py` lists the sitemaps to submit; `submit-indexnow.sh` also reads the
  conversions sitemap; add any new sitemap to both.

### B6. Server anti-bot filter: 403 on the sitemap

- **Symptom**: `/app/sitemap-convert.xml` answered 403 to AI robots, while the conversion pages answered 200
  to them (observed after deployment with AI-robot user-agents).
- **Cause**: a server anti-cloning rule (Caddy) on `/app/*` refuses robots, and the sitemap fell within its
  scope.
- **Fix**: exception in the security configuration (`deploy/security.caddy`), placed BEFORE the anti-cloning
  filter of `/app/*`, which stays active elsewhere; the sitemap answers 200 to all robots.
- **Guardrail**: online check with AI-robot user-agents after EACH deployment (see
  `09-autonomous-procedure.md`, phase 6), not only with a browser; a security rule must list its exceptions
  for indexing resources.

### B7. Other technical defects of the initial audit

| Defect | Fix |
|---|---|
| 547 descriptions beyond 160 characters, 12 duplicate titles (Feedback x6, Contact, Kontakt, Aviso legal), wrong canonical on `/404.html` | rewrite + `check-seo-meta.mjs`; thresholds per script (Latin, ja/ko) |
| `Organization` without `sameAs` (490 pages), logo on only 10, no `@id`, no real author | entity graph linked by `@id` on all pages (`src/data/organization.ts`) |
| `llms.txt` written by hand, drifting (said "Android, Web", ignored the iOS beta and the conversion) | generated at build time from the page registries; only the prose stays in `src/i18n/llms.ts` |
| Google Indexing API used for 412 URLs | abandoned: reserved for job postings and live broadcasts |
| Access logs unreadable for the session | request access in phase 0 |

---

## C. Accuracy and legal

### C1. The site text contradicts the code

- **Symptom**: the audit by a domain expert and the re-reading against the code found false claims: "Vingt
  instruments" (twenty instruments) when the catalogue has 21; "pentatoniques" (pentatonic scales, plural)
  when the code has only the minor pentatonic and the blues; the H/B notation promised while the tool does
  not display it; a 6-string bass when only 4 and 5 strings exist; a non-existent ukulele in D tuning; photo
  import described as "mobile only" when the web does it server-side; chord progressions described as a web
  tool when the generator is mobile only; metronome 30 to 300 BPM; capo for 9 instruments; retention period
  of audio files (deletion "at the latest 72 h"; karaoke alignment done on the server and not on the device).
- **Cause**: texts written from documents (brief, old pages) that had drifted from the code. Every check must
  be done in the code, not in the specification.
- **Fix**: batch B (accuracy corrections) and corrections of `llms.txt` and of the karaoke article; tables of
  tunings, scales and chords GENERATED from the application's code (`build-tool-reference.mjs`).
- **Guardrail**: `check-marketing-numbers.mjs` recounts the catalogues from the data and turns red if a
  published figure diverges, if a stale figure reappears, or if a constant has disappeared from the code.
  Method rule: "every claim about a function is checked in the code before being written, and the platform
  is stated". Limit: the check only enumerates what is declared to it and does not see an undeclared deletion.
- **Discrepancy noted while writing this file**: the prose of `llms.ts` still announces a metronome of 40 to
  240 BPM, whereas the pages say 30 to 300 (to check against the application's code). Texts that duplicate a
  fact (here `llms.txt`) are the most exposed; put them under the same check.

### C2. Privacy policy not aligned with actual behaviour

- **Symptom**: the campaign revealed that the server automatically separated voice from instrumental (legal
  question Q72), without the privacy policy describing it; and the source of the installation (name of the
  original site) was not specified (Q71). A sentence "only case where audio is kept" became false.
- **Cause**: a server service added without an update to the legal text.
- **Fix**: policy updated in the 8 legal languages in a single batch, dated 11 October 2026 (site 2.34.3);
  retention of separated tracks specified afterwards (#84); marketing brief to be updated (still open on the
  legal basis and copyright of derived copies).
- **Guardrail**: `check-legal-parity.mjs` (same structure, same figures in the 8 languages); legal decision
  escalated to the owner, not settled by the agent; rule: any new data flow or service must update the policy
  BEFORE going live.

### C3. Measurement script writing to `sessionStorage`

- **Symptom**: the first version of the provenance relay (batch F1) kept the referrer host in `sessionStorage`
  on the site side, whereas the site's policy promises "no audience measurement on this site".
- **Cause**: a pragmatic implementation without re-reading the promise made to the visitor.
- **Fix**: the next commit removes all writing ("no writing to the device on the site side, referrer relay
  limited to the current page"). The site relays `ref=` in the links of the current page, and the application
  records the provenance through its existing mechanism.
- **Guardrail**: re-read the privacy policy before any code that reads or writes an identifier, a storage or
  a referrer; review by a second agent with the policy as input. See `07-measurement.md`, §3.

### C4. Published figures drifting outside the site

- **Symptom**: outdated off-site texts (« all-in-one », « compagnon » (companion), « composer » (compose),
  emoji, prices not current); the Google Play listing and the directory listings said something different from
  the site.
- **Fix**: off-site folder rewritten with the figures from the brief; 38 Google Play listings updated with the
  exact figures.
- **Guardrail**: a single table of validated figures; any value that changes is modified everywhere (behaviour
  and every published occurrence), then we check that the old one has disappeared.

---

## D. Interface and visual QA

### D1. Outdated screenshots of the interface, in French

- **Symptom**: translated pages showing screenshots of the application in an old interface and in French; the
  metronome page image showed the Keyboard screen; the name of a review account visible; a section of a home
  page left in English.
- **Cause**: screenshots taken once in French; no variant per language; no check on the image served.
- **Fix**: 6 screens recaptured in 10 languages in the current interface (2.34.4), `webShot(name, locale)`
  function with English fallback, versioned scripts in `scripts/captures-web/`; three screenshots remain in
  French (they show the owner's personal account).
- **Guardrail**: visual pass on the final build per language; recommendation not implemented by the campaign:
  make the inventory fail when a non-English page serves a fallback screenshot. See `05-multilingual.md`, §7.

### D2. Stretched cards, tables without a scroll cue

- **Symptom**: in the built-in visual QA, reference tables wider than the screen scrolled horizontally with no
  indication; and grid cards in the same row looked stretched to the height of the tallest one.
- **Cause**: containers with `overflow-x: auto` without a visual cue; grid cards left at default alignment. The
  detail of the card fix could not be re-read in the documents.
- **Fix** (version 2.34.2): a scroll shadow that appears at the edge hiding columns and disappears at the end
  (`local` and `scroll` backgrounds layered) on the three families of scrolling tables; rounded corners on the
  container and not on the table.
- **Guardrail**: QA at 400 px at least (the defect shows in narrow widths); any wide table sits in a scrolling
  container WITH a cue.

### D3. Layout defects seen by the final QA

| Defect | Cause | Fix |
|---|---|---|
| "Corde 1" (string 1) headers of the tuning tables to correct | label composed of two template expressions in the cell (exact cause of the defect not re-read) | built as a single string `${T.string} ${i + 1}` |
| Double labels of the circle of fifths ("C♯/D♭") too wide on one line in the SVG | two names in a single `<text>` | one `<tspan>` per name, offset by plus or minus 0.55 em |
| Button arrow falling alone on a line | ordinary space before `→` | `&nbsp;→` |
| "Developers" label still in English in 6 languages | untranslated key | translated into it, pt, nl, pl, ja, ko |
| CLS of 0.128 at 400 px on `/ko/accords-mp3/` | Korean font | noted, not blocking (check threshold: 0.1) |
| Visual gaps around ♯ and ♭ | fallback font | clean text, known residue |

Measurements of the final build: 732 pages at 400 and 1280 px, 0 overflow, 0 raw key, 0 broken image; 10
pages x 5 widths x 2 themes reviewed.

### D4. HTML comment displayed under each article

- **Symptom**: under each blog article, in all 10 languages, a text fragment appeared in plain view (commit
  `02d2193`).
- **Cause**: an HTML comment in the template contained an angle-bracket tag (`<slug>` in
  `install.post.<slug>.body`). The template read it as a tag, which cut the comment and made its end visible.
- **Fix**: Astro comment `{/* ... */}` (never sent to the browser), with the name `install.post.SLUG.body`
  without angle brackets.
- **Guardrail**: in a template, never write angle brackets in an HTML comment; prefer the template engine's
  comment. Detectable by a build check that looks for fragments like ".body -->" in the visible text, or by the
  visual pass.

---

## E. Agent orchestration

### E1. An agent too limited for a design brief

- **Symptom**: an agent of the "mechanical execution" class (low effort) refuses or fails a brief that calls
  for design judgement (writing a content plan, settling trade-offs).
- **Probable cause**: the model routing reserves low effort for fully specified tasks. The detail of the incident
  could not be re-read here.
- **Fix**: re-run on an implementation agent (medium effort); architecture and cross-system trade-offs at high
  effort.
- **Guardrail**: choose the agent according to the nature of the brief (see `09-autonomous-procedure.md`,
  routing); if an agent reports that it "cannot", do not insist with the same agent, change class.

### E2. Usage limits reached in the middle of the campaign

- **Symptom**: the work stopped before the end because of usage limits.
- **Probable cause**: many agents launched in parallel (8 translation agents, reviewers, QA) and reads of large
  files. The exact detail was not re-read in the documents.
- **Fix**: resume from `ETAT.md` (the current truth of progress) and from the branch history; relaunch in batches.
- **Guardrail**: keep `ETAT.md` up to date at EACH completed batch (done, remainders, decisions, open questions,
  deployment, URL), one branch and one PR per batch, short briefs with a short deliverable; spread out the heavy
  agents; do not relaunch a phase already recorded.

### E3. Additions made mid-course lost or ignored

- **Symptom**: an instruction added in the middle of a brief is not taken into account by the agent.
- **Guardrail**: record each addition in `ETAT.md` and cite it in the next brief; relaunch a new batch beyond
  2 to 3 additions.

### E4. Two agents on the same file

- **Symptom**: catalogues overwritten or merge conflicts (es and de share `seo.ts`).
- **Guardrail**: one agent per catalogue file; shared registers (`page-dates.ts`, `page-fingerprints.json`)
  regenerated by the coordinator only; never two agents on the translation files of the same folder.

---

## F. Content and SEO

### F1. Generic "In brief" block repeated

- **Symptom (avoided)**: an identical answer block on 130 pages.
- **Decision (plan v2)**: each block carries data SPECIFIC to the page (tunings, frequencies, particularities
  drawn from the code); a generic block repeated is not published (risk of mass content without its own value).

### F2. Pages for needs without a web function

- **Symptom (avoided)**: a "chord progressions" page promising a tool that exists only on mobile.
- **Decision**: removed as a tool page, replaced by a generic article by degrees with a call to the mobile
  application. Rule: one page per intent, not two pages for the same query (`midi-keyboard-browser` absorbed
  into `/clavier-midi`, `beginner-guitar-chords` removed).

### F3. Overestimated structured data

- **Finding**: ChatGPT and Perplexity read JSON-LD as plain text; the enriched FAQ results are reserved for
  official and health sites. Decision: FAQPage and HowTo kept but not extended. The entity graph (Organization
  + WebSite + WebPage, `sameAs`) mainly serves Google and Bing.

### F4. Dates and author

- **Defect**: no update date outside the blog, author "Jam Jam" on 150 pages, publisher only in the legal notices.
- **Fix**: visible "Updated on" (« Mis à jour le »), publisher and founder named (`Person`), "About" page,
  `dateModified` aligned. Rule: visible date = sitemap date = JSON-LD date, and it moves only if the visible text
  changes.

---

## G. The ten rules to keep

1. Build before pushing: `build && push`.
2. A single production path, checks that block the switch-over.
3. Every check has a `--self-test`.
4. Check every claim in the code, not in a specification; generate the tables from the code.
5. A single function decides the languages of a page.
6. `robots.txt`, sitemap, server anti-bot filter: test them together, with robot user-agents.
7. Never a date that moves without a text that moves.
8. Measurement obeys the privacy policy, not the other way round.
9. A visual QA on the final build, at 400 px at least, in each language.
10. `ETAT.md` up to date at each batch, one file per agent, one PR per batch.
