# 05. Multilingual rebuild (10 languages)

This file explains how to rebuild a site so that it is recommended in several languages without
ever publishing a half-translated page. It is based on the campaign run on jam-jam.org (worked
example): English at the root, then fr, es, de, it, pt, nl, pl, ja, ko, with 560 URLs dated the
same day, all present in the 10 languages.

The paths cited are those of the site's repository (Astro, static rendering). On another site,
keep the principle and adapt the names. For the `hreflang` mechanics themselves (tags, sitemap,
reciprocity), see also `03-technical.md`, §5.

## 1. Why add languages, and in what order of priority

Languages do not carry the same weight. Search Console measurement over 90 days (campaign audit,
10 July to 9 October 2026), clicks and impressions per language:

| Language | Clicks | Impressions | Reading |
|---|---|---|---|
| en (root) | 311 | 8 725 | volume, but generic queries with heavy competition |
| fr | 171 | 5 397 | home market |
| es | 118 | 4 002 | strong demand for tuners |
| de | 43 | 1 369 | very specific queries ("guitalele stimmen online") |
| ja | 33 | 314 | few impressions, but a high click rate relative to impressions |
| it | 14 | 695 | |
| pl | 14 | 194 | |
| pt | 12 | 222 | |
| ko | 6 | 188 | |
| nl | 3 | 206 | |

Languages with little competition (ja, pl, nl, ko) rank quickly if the page is good, and each
language has its own query vocabulary: you do not translate a title, you rebuild it (see §5).

Scoping rule: if the brief says "all the site's languages", the list of languages is a deliverable
of phase 0 (see `09-autonomous-procedure.md`), not a decision made along the way.

## 2. Catalogue architecture: one file per language

### What the campaign found

The site had two large `Record<Locale, Dict>` dictionaries: `src/i18n/ui.ts` (interface) and
`src/i18n/seo.ts` (SEO content). Four languages (fr, en, es, de) lived in `seo.ts` (965 KB), and
the six others each had their own file (`seo.it.ts`, `seo.pt.ts`, `seo.nl.ts`, `seo.pl.ts`,
`seo.ja.ts`, `seo.ko.ts`, plus the matching `ui.<langue>.ts` files). This is a design flaw:
two agents translating es and de write to the same file.

### What the campaign added

For new pages and articles, a `src/i18n/geo/` folder with two files per language:

```
src/i18n/geo/
  index.ts          assembles { ...pages.<langue>, ...blog.<langue> } per language
  pages.en.ts  pages.fr.ts  pages.es.ts  ...  pages.ko.ts   (tool pages, glossary, about)
  blog.en.ts   blog.fr.ts   blog.es.ts   ...  blog.ko.ts    (reference articles)
```

The text reader (`useSeoT`) consults these catalogues AFTER `seo*.ts`: a key that already exists
in the old catalogue keeps priority there. Benefits: the 10 translation agents each write to their
own files, never to the same one; adding a language does not require opening a 900 KB file.

### Key naming convention

A key = `<family>.<identifier>.<field>`. Real examples:

| Key | Content |
|---|---|
| `tool.clavier-midi.brief` | "In brief" block of the page |
| `post.note-frequencies.s1h` | title of section 1 of an article |
| `glossary.a440.def` / `.more` / `.example` | definition, elaboration, example of a term |
| `about.publisherForm` | legal form of the publisher (to translate; ja/ko had forgotten it) |
| `install.tool.<slug>.*` | install box specific to the page |

The prefix serves the computed availability (§3): it must group ALL the keys of a page.

### Golden rule

One agent per catalogue file, at all times. If two languages share a file, either split the file
before launching the agents, or serialise their PRs (see §4, the `seo.ts` pitfall).

## 3. Computed availability: never English on a translated page

### The default to avoid

A missing translation key is served as a fallback, so in English, in the middle of a German page.
For Google, it is a "de" page whose content is English: low quality, risk of the page being seen
as a duplicate of the English version. For an AI assistant, it is a passage that does not match
the language of the question, so it is not cited. For the visitor, it is an impression of a
sloppy site.

### The principle

A page is PUBLISHED in a language only if ALL its keys exist in that language's catalogue. English
is the reference: the required keys of a page are all the English keys that start with its prefix.
Availability is not maintained by hand in a register (the campaign did so at first, then removed
the register): it is computed at each build.

Campaign code (`src/data/geo-locales.ts`, abridged):

```ts
const PAGE_PREFIXES: Record<string, string> = {
  'clavier-midi': 'tool.clavier-midi.',
  'glossaire': 'glossary.',
  'a-propos': 'about.',
  'blog/note-frequencies': 'post.note-frequencies.',
  // ...
};

function requiredKeys(prefix: string): string[] {
  // Keys `install.<prefix>…` (install box specific to the page) count too.
  return Object.keys(geo.en).filter((k) => k.startsWith(prefix) || k.startsWith(`install.${prefix}`));
}

/** Missing keys of a page in one language (empty = page complete). */
export function geoMissingKeys(path: string, locale: Locale): string[] {
  const prefix = PAGE_PREFIXES[path];
  if (!prefix) return [];
  return requiredKeys(prefix).filter((k) => !(k in geo[locale]));
}

export const GEO_PAGE_LOCALES: Record<string, readonly Locale[]> = Object.fromEntries(
  Object.keys(PAGE_PREFIXES).map((path) => [path, LOCALES.filter((l) => geoMissingKeys(path, l).length === 0)]),
);
```

### Who consumes this list

Everything that offers or generates another language goes through a single function
(`localesForPath`):

1. the `getStaticPaths` of the routes: a missing language is not built, so there is no page, no
   URL, no announced 404;
2. the `hreflang` tags (never an alternate pointing to a page that does not exist);
3. the language selector in the footer;
4. the automatic redirect of the root page to the browser's language;
5. the sitemap, the generated `llms.txt` (the "localised versions" block) and the internal linking
   (footer, blog index filtered by available language).

The campaign's code comment explains why there is a single function: a legal page announced nine
translations, six of which had never been generated; the selector led to a 404 and the automatic
redirect sent the visitor there without a click, including on the privacy policy. General rule:
never two language lists for the same page.

### Effects to know

A complete translation makes the page appear at the next build, without touching any list. Three
keys forgotten out of 361 remove it from that language, silently. An English key added afterwards
makes the page disappear for all the other languages until they have the key.

A safeguard is needed, because the omission is silent: a build report showing, per page, the number
of published languages and the missing keys, and a deployment check that fails if that number drops
or if the target (10 languages) is not reached. In the campaign, the list of 560 URLs in `ETAT.md`
("all present in the 10 languages") served as the final verification.

## 4. Translation workflow with sub-agents

```
1. French and English source content written and reviewed (batches B, C, D of 09-autonomous-procedure.md), then FROZEN
2. Exact list of keys to translate (key file)
3. One agent per language, one branch and one PR per language, one catalogue file per agent
4. Blocking checks in each PR
5. Review by a second agent on a sample (es, de, ja in the campaign)
6. Merge one language after another, then build, visual QA, deployment
```

Nine separate PRs in the campaign: #65 Japanese, #66 Polish, #67 Spanish, #68 Portuguese (pt-BR), #69 German, #70 Dutch, #71 Italian, #72 Korean, #73 labels of the reference tables in the 10 languages. Volume per language: 408 SEO keys (81 replaced, 327 added, drawn from a list drafted
before the launch), the home page meta, 361 keys of `pages.<langue>.ts` and 263 keys of
`blog.<langue>.ts`, that is roughly 1 000 keys.

### The brief of a translation agent

Short, identical for each language: (1) the file to write and the prohibition on touching any
other; (2) the keys and the English source (the French source helps with solfège); (3) the
localisation rules of the language (§5); (4) the real queries of the language taken from Search
Console (see `07-measurement.md`) to build titles and descriptions: "accordatore online, accordatore
violoncello, metronomo online" in it, "stemapparaat online, viool stemmen online" in nl,
"afinador online, cifra" in pt; (5) the length thresholds; (6) the checks to run, with exit code 0
required; (7) the prohibition on modifying the shared registers (`geo-locales.ts`, `page-dates.ts`).

### Blocking checks

| Check | What it catches | Where |
|---|---|---|
| Key parity | missing or unknown key, empty or non-text value | `scripts/i18n-assemble.mjs --verifier`, `geoMissingKeys` |
| Markers | `{n}` renamed or lost (would display "{nombre}"), double braces `{{…}}` | `i18n-assemble.mjs` |
| Batch duplicates | same key, two different texts | `i18n-assemble.mjs` |
| Untranslated | string identical to English: flagged, not rejected (proper noun, chord symbol) | `nonTraduites()` |
| Table labels | a missing language makes `astro build` fail (control loop at module import) | `src/data/tool-reference-labels.ts` |
| Em dash | the U+2014 character, all languages | `scripts/check-em-dash.mjs` |
| Titles and descriptions | length depending on the script, unique titles | `scripts/check-seo-meta.mjs --strict` |
| Numbers | a published figure that diverges from the code | `scripts/check-marketing-numbers.mjs` |
| Trailing slash | internal link without `/` in a translated text | `scripts/check-trailing-slash.mjs` |
| Legal texts | structural parity (§9) | `scripts/check-legal-parity.mjs` |

The label check deserves copying: the site has no type checking at build time, so the module checks
by itself, at import, that every row has all the languages.

Thresholds of `check-seo-meta`: title as a warning beyond 60 Latin characters (30 in ja/ko), as an
error beyond 70 (35); description from 70 to 160 Latin characters (35 to 80 in ja/ko). French and
German easily exceed 160: to be written into the brief.

### Sample review

A second agent, read-only, receives 30 to 50 keys drawn at random and checks meaning, the app's
terminology, notation, figures and tone, then returns a list of corrections. An automatic check does
not read Polish: the quality of meaning remains a human review or a second agent.

### Orchestration pitfalls

1. **Two languages in the same file.** The es (#67) and de (#69) PRs both modify `seo.ts`: merge
   them one after the other, rebasing.
2. **Shared registers.** `page-dates.ts` and `page-fingerprints.json` are regenerated by
   `page-dates-check.mjs --write`: only the coordinator regenerates them, on the final build.
3. **Source modified during translation.** An English key changed after the launch makes the 8 PRs
   incomplete at once (the computed availability removes the page). Freeze the source before batch E.
4. **Pre-existing descriptions out of range.** Several PRs had to shorten existing descriptions that
   `check-seo-meta --strict` flagged: to be anticipated in the brief.

## 5. Terminology and notation pitfalls

### General rule

The terminology comes from the product's interface, not from the translator. The campaign had to
align: "de: Liederbuch everywhere (app term)", "pl: AI (app term)", "ja/ko: Premium as the name of
the offer". A site that says "carnet de chansons" in the app and "recueil" on the SEO pages
confuses the user who clicks. Useful deliverable: a glossary per language extracted from the app's
catalogue, provided to the agent.

### Note notation

| Language | Notation in texts | Remark |
|---|---|---|
| fr | solfège: Do, Ré, Mi, Fa, Sol, La, Si | the table also shows the letter in parentheses |
| es | solfège: Do, Re, Mi, Fa, Sol, La, Si | no accent on Re |
| it | solfège: Do, Re, Mi, Fa, Sol, La, Si | |
| pt | solfège: Dó, Ré, Mi, Fá, Sol, Lá, Si | accents specific to Portuguese |
| en, nl, ja, ko | letters C D E F G A B | ja and ko: letters for tuner users (campaign choice) |
| de, pl | letters, with the H/B pitfall below | |

The campaign's code handles solfège through a `SOLFEGE` table (fr, es, it, pt) and a function that
replaces each letter of a template (`E A D G` becomes `Mi La Ré Sol` in French): the template stays
unique, the notation is applied at output. Never have a translator retype the notes: tunings come
from data generated from the product's code (`src/data/tool-reference.json`, produced by
`scripts/build-tool-reference.mjs`), and the labels file carries only names.

Observed pitfall: the Portuguese cavaquinho was written with a tuning different from the product's.
Campaign fix: "cavaquinho D5 A4 B4 E4 everywhere" (aligned with the app's tuning file, in the 10
languages and in `llms.txt`). Lesson: a numeric value on a translated page must come from a single
source, never from manual entry per language.

### The H/B pitfall in German and Polish

In German and Polish, B means B-flat and H means B natural. A text that writes "B" for B natural
(English usage) is wrong for a German or Polish reader. The campaign found that the product cannot
display this notation (English letters or solfège only). Rules adopted:

1. a content page may EXPLAIN the difference, but must never promise that the tool displays it;
2. open a product ticket;
3. when the product implements it, recapture the de and pl images (they showed B3 and B5);
4. in the meantime, the branch `geo/notation-hb` (H = B natural, B = B-flat in the tunings, scales,
   capo, article blocks, de and pl texts) is ready but NOT deployed at the time of the campaign,
   pending a product decision.

### Numbers, symbols, punctuation

| Topic | Rule |
|---|---|
| Decimal comma | de, fr, es, it, pt, nl, pl write "82,41 Hz"; en, ja, ko write "82.41 Hz". Generated tables must follow the language (the campaign left "decimal comma in nl" to be settled on the product side) |
| Thousands separator | varies (non-breaking space, point, comma): set one rule per language and test it in the tables |
| Brand and offer | "Premium", "Jam Jam" are not translated; check in ja/ko (fixed in finishing) |
| Arrow and button | `&nbsp;→` after the label: without a non-breaking space, the arrow falls alone on a line in German or Dutch (fixed in 2.34.2) |
| Sharp, flat | ♯ and ♭: the visual spaces around them come from the fallback font, the text itself is clean (known issue) |
| Em dash | forbidden in all languages (automatic check); the en dash "–" remains valid for ranges |
| Quotation marks | specific to each language (« » in fr, "" in en, 「」 in ja); do not keep those of the source |

### Query vocabulary per language

Do not translate "tuner" word for word. The words users type (taken from the panel questions and
the campaign's Search Console queries):

| Language | Tuner | Real example |
|---|---|---|
| fr | accordeur | accordeur basse en ligne |
| es | afinador | afinador de bajo online |
| de | Stimmgerät, stimmen | guitalele stimmen online |
| it | accordatore | accordatore violoncello online |
| pt | afinador | afinador de violão online |
| nl | stemapparaat, stemmen | viool stemmen online |
| pl | tuner | tuner gitarowy online |
| ja | チューナー, チューニング | バイオリン チューニング サイト |
| ko | 튜너, 조율 | 온라인 기타 튜너 |

Procedure: for each language, extract from Search Console the top 8 queries per page
(`handoff/GEO-2026-10/requetes/<langue>.md` in the campaign), then write the title around the
dominant query. Example page: `/fr/accordeur-basse/` had 679 impressions on "accordeur basse en
ligne" at position 9.0 for 6 clicks; the title was rewritten for that query.

## 6. hreflang and x-default

### Rules applied on the site

1. Every page offered per language carries a `<link rel="alternate" hreflang="xx">` for each language
   ACTUALLY published for that page (hence coming from `localesForPath`), plus a `hreflang="x-default"`.
2. `x-default` points to English (site root). No `/en/`: English at the root with x-default is valid;
   only reciprocity needs to be checked (each page cites all the others and itself).
3. The codes are those of the language alone (`pt`, not `pt-BR`), consistent everywhere. The audit
   found that the sitemap of the conversion pages used `pt-BR` while the rest of the site used `pt`:
   an inconsistency listed among the possible causes of the Search Console error on that sitemap.
4. A page that exists only in English (authentication return page, 404) has no alternate.
5. The `html lang` attribute is correct on each page (checked by the campaign inventory).
6. Each canonical URL has a trailing slash and is the only form linked (see `08-pitfalls-and-incidents.md`).

Campaign measurement (audit): 932 pages with 11 alternates (10 languages and x-default).

### The automatic redirect to the visitor's language

The site redirects the English root page to the browser's language, once per session (flag in
`sessionStorage`), preferring first the explicit choice saved by the application, then
`navigator.language`, then an IP geolocation by a service of the site itself (no third party).
Three precautions:

1. the script is a simple `<script>`, externalised by the build, to pass a strict CSP (the build
   values go through `data-*` attributes on `<html>`);
2. the redirect targets ONLY the languages available for this page (otherwise it sends the visitor
   to a 404);
3. robots do not execute this JavaScript: they always see English at the root and discover the other
   languages through hreflang and sitemap. Do not redirect robots server-side according to language:
   Google recommends avoiding any automatic redirect based on the perceived language.

## 7. Interface screenshots by language

### The QA lesson

The final visual QA found translated pages showing screenshots of the interface in French: a Spanish
page with a French screen is an inconsistency that the visitor and an assistant reading the images
will notice. Rule: **never a French screenshot on a Spanish page**. A screenshot belongs to one
language; if the language does not have its own, the fallback is English, never French, unless a
documented exception applies.

### The site's mechanism

The screenshots are files `src/assets/screenshots/web/<langue>/<nom>.webp`. A single function
selects them:

```ts
// src/lib/web-shots.ts (abridged)
const variants = import.meta.glob<ImageMetadata>('../assets/screenshots/web/*/*.webp', { eager: true, import: 'default' });

export function webShot(name: string, locale: string): ImageMetadata {
  const img = variants[`../assets/screenshots/web/${locale}/${name}.webp`]
    ?? variants[`../assets/screenshots/web/en/${name}.webp`]
    ?? legacy[name];            // old French screenshot, only 3 names
  if (!img) throw new Error(`web-shots : capture inconnue « ${name} »`);
  return img;
}
```

Fallback order: page language, then English, then legacy screenshot. Three screenshots remain in
French and outdated (`melodie-tablature`, `diagrammes-piano`, `carnet-voix`) because they show songs
from the owner's personal account: they have not been redone (privacy), which is a deliberate
exception noted in `ETAT.md`.

### Producing the screenshots

Versioned scripts in `scripts/captures-web/` (`capture.mjs`, `lib.mjs`, `compare-layout.mjs`).
Principles to reuse:

1. **Same viewport for all languages** (1280 x 1100, scale factor 2, i.e. 2560 x 2200), light
   theme, WebP output at quality 88; otherwise the layouts cannot be compared.
2. **Forced language** through the application's local storage before loading (`jamLang`), with the
   browser context's `locale` aligned.
3. **Disable settings synchronisation** (profile read and write requests) so that the server account's
   language does not overwrite the forced language and no write reaches the demo account.
4. **Find the buttons by their translated label**, built from the application's catalogues (the script
   looks up all the translations in the language of the keys whose French text is given), not from
   position selectors.
5. **Fake audio input** for the tuner and detection (WAV file looped by the browser).
6. **Demo account** of a store, never a personal account; credentials in environment variables,
   never in the code.

Campaign result: the 6 screens (tuner, keyboard, detection, metronome, scale lock, chord detection)
recaptured in the current interface, in 10 languages (version 2.34.4).

### Defects found by the QA of translated screenshots

| Defect | Cause | Status |
|---|---|---|
| `diagrammes-piano` image on the ja home page in French | old screenshot without a variant | to redo |
| "Social" section of the ja home page in English | missing keys in the home catalogue | to translate |
| Metronome page image = Keyboard screen | wrong image name attached | to fix |
| "AppleReviewer" name visible on the new screenshots | review account used for the screenshots | to rename or hide |
| de and pl images with B3 and B5 | H/B notation not displayable (§5) | after product decision |

Recommendation (not made by the campaign): make the inventory fail when a non-English page resolves a
screenshot through fallback, and localise the image `alt` attributes (planned for plan v2).

## 8. Language leak check

There are two leaks: French in a translated page (the source content) and English in a translated
page (the missing key). Computed availability (§3) removes the second for the campaign's pages; the
other layers:

| Layer | Tool | What it sees |
|---|---|---|
| 1. Catalogue parity | `geoMissingKeys`, `i18n-assemble.mjs` | missing key |
| 2. Build inventory | `scripts/geo-inventory.py` | column `fr_words_on_non_fr`: count of French function words on non-French pages; `html_lang`; hreflang; `has_table` |
| 3. Build walkthrough | built-in QA on the final build | 732 pages at 400 and 1280 px: 0 overflow, 0 raw key displayed (a key like `tool.x.y` visible), 0 broken image |
| 4. Visual review | screenshots at 5 widths, light and dark, on a sample per language | foreign text, foreign image, broken words |

The campaign's inventory measured French words on non-French pages ("no French leak measured") but
not English on non-English pages, the most likely leak: extend the method with English function words
(the, and, with, your, for) on the text of `<main>`. Run the inventory with `python3 -I` (the build
folder is not reliable), see `08-pitfalls-and-incidents.md`, A4.

Real residues from the campaign (`ETAT.md`): "Social" section of the ja home page in English, a few
screenshots in French. Found by the visual QA, not by an automatic check: keep the visual pass even
when all the checks are green.

## 9. Legal texts by language: parity

### Principle

Legal documents do not follow the site's language list. On jam-jam.org they exist in 8 languages (en,
fr, es, de, it, pt, nl, pl), not in ja or ko: translating a legal document is a legal act, not an
editorial adaptation, and the repository imposes a legal protocol before touching it. For ja and ko,
the footer links to the English version (`legalHref`) and no legal page is generated under their
prefix: an unvalidated translation, or an English page under a Japanese URL, would be worse than the
explicit link. French is authoritative; the other versions are translations and say so.

### The check `scripts/check-legal-parity.mjs`

The risk is the clause missing in a language (skipped paragraph, one fewer bullet in the list of GDPR
rights, lost contact link). The script compares each language to French:

1. **Structure**: same number of blocks, same sequence of types (title, paragraph, list), same list
   sizes;
2. **Links**: same sequence of `href`;
3. **Policy marker**: `<!-- policy-version: … -->` exactly once per language;
4. **Figures**: same numbers in the same place (durations, caps); update dates out of scope.

It has a `--self-test` that injects a defect and proves that it turns red. Acknowledged limit: it
counts blocks, it does not read Polish; a watered-down clause remains invisible, this half is a human
review.

### Working rules

1. A legal change is a single batch that touches ALL the legal languages and passes parity (campaign:
   privacy policy updated in 8 languages in a single PR, version 2.34.3, dated 11 October 2026).
2. Read the repository's legal protocol before modifying; substantive questions (provenance of the
   original site, automatic separation of tracks) go to the owner.
3. The legal form of the publisher on the "About" page (`about.publisherForm`) is a content key:
   ja and ko had forgotten it.
4. If the legal scope is smaller than the site's language list, write it in phase 0: "ja and ko outside
   the legal scope, fallback to English".
