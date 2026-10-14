# 04. Content patterns: what was applied, with before and after

This file describes the templates and editorial rules of the jam-jam.org campaign (October 2026), with real
before/after excerpts taken from the site's git history (batches A to F, merge requests 60 to 74). Batch mapping:
A technical (60), B existing pages (64), C new pages (63), D reference articles (62), E translations (65 to 73),
finishing (74).

Frame to keep in mind: Google writes (guide of 15 May 2026) that **unique and useful** content weighs more than any
other instruction, and that "chunking", rewriting for AIs or fabricating mentions is pointless for it. The patterns
below serve the reader first; their effect on the other assistants is **probable, not demonstrated** (`01` §2).
No result of the campaign is measured to date.

## 1. The "In short" block (40 to 60-word answer at the top of the page)

**Rule.** Right after the hero (H1, hook, screenshot) and before the introduction paragraph, a paragraph of 40 to 60
words that answers the page's question, with the essential figures, followed by 3 to 5 facts specific to the page.
The block is rendered by the template from dedicated keys (`tool.<page>.brief`, `tool.<page>.fact1` to `fact5`) and
a localized heading (`toolref.briefHeading`: "En bref" (French), "In short" (English), "Kurz gesagt" (German)...).
A generic block repeated from one page to another is not published: each block carries its own data (tunings,
frequencies, particularities taken from the code).

Before (first text of the tuner page: a promotional introduction paragraph, which stays, reworked, under the block):

> The Jam Jam online tuner listens to your instrument through your microphone and tells you, in real time,
> which note you are playing and whether you are sharp or flat. Twenty instruments come with their own
> presets [...] No download, no account, no ads: open the page and tune. The tuner is one screen of Jam Jam,
> the app that finds your songs' chords [...]

After (block added above, 51 words):

> To tune a guitar online, open the Jam Jam tuner, allow the microphone and pluck each open string: E2 (82.41 Hz),
> A2, D3, G3, B3, then E4 (329.63 Hz). The needle turns green within ±5 cents of the target. Eight guitar tunings
> are built in, and 20 more instruments have their own presets.

Other real examples: violin ("To tune a violin online, allow the microphone, pick Violin and start with A4 at
440 Hz. Then tune D4 (293.66 Hz), G3 (196 Hz) and E5 (659.26 Hz)... Jam Jam offers one violin tuning: standard."),
bass ("E1 (41.20 Hz), A1 (55 Hz), D2 (73.42 Hz) and G2 (98 Hz) ... 5-string bass (low B at 30.87 Hz)") and MIDI
keyboard ("plug it in over USB, open the keyboard in Chrome or Edge and allow MIDI access... the sustain pedal
(CC64) works").

Writing model: one sentence in the infinitive-verb form answering the question, numerical values with their unit,
the honest limit ("one violin tuning only") and nothing promotional. The brand name appears because the answer
describes the tool.

Strict reading: if a language lacks the key, the block is **not displayed** (no fallback to English);
`05-multilingual.md` describes the blocking check of the keys.

## 2. Verifiable figures

Every published number meets three conditions: it comes from the code or from a cited source, it is dated or
datable, and the reader can reproduce it. Campaign figures (recounted from the application): 21 instruments and 79
tunings, needle accuracy ±5 cents, 168 chords (14 qualities across 12 keys), 142 sounds of which 19 free, 48 drum
kits, 26 instruments with chord diagrams, 16 scales, 10 languages.

Mechanism: a table of allowed figures in a brand brief, and a check that **recounts the catalogs from the
application's data** then fails if a published figure diverges, or if an outdated figure reappears
(`scripts/check-marketing-numbers.mjs`). A check that only enumerates what is expected never sees a deletion; hence
the explicit link between text and constant for the sensitive lines (quotas, prices).

Limitation found on 14 October 2026: the home page's JSON-LD `featureList` (`src/layouts/Base.astro`) still
publishes "9 instruments, 20 tunings" and "17 sounds free", whereas the brief says 21 instruments, 79 tunings and 19
free sounds. The check script does not cover this file: **structured data is published content and must be included
in the figures check.**

## 3. Tables generated from the source code

Never a hand-written data table: it diverges at the first product change.

`scripts/build-tool-reference.mjs` bundles a small probe (esbuild) that imports the application's domain modules
(tuning catalog, scales, piano voicings, capo instruments, chord diagrams), runs it, and writes
`src/data/tool-reference.json` (79 instrument tunings with frequencies recalculated from the MIDI number:
`440 × 2^((midi − 69) / 12)`, rounded to two decimals).

```bash
node scripts/build-tool-reference.mjs          # writes the JSON
node scripts/build-tool-reference.mjs --check  # fails if the file is no longer up to date
```

The components `ToolReference.astro` (tool and tuner pages) and the blog blocks (`NoteFrequencyTable`, `CapoChart`,
`CircleOfFifths`...) read this JSON or compute at build time. Example: the table of note frequencies (108 notes,
octaves 0 to 8) is produced by the formula, not typed in. The frequency calculator of the same article (reference
440, 432 or 442 Hz) displays an initial value **in the HTML** (readable without JavaScript) and is updated by an
external script compatible with the CSP. Column labels are in the 10 languages, with a blocking check.

## 4. "How to" section in steps

For a task-type need: 4 to 6 numbered steps, each with a short heading and an explanatory sentence, specific to the
page. On tuner pages, a section "How to tune a/an <instrument>" with its own steps (violin: "Vérifie d'abord le
chevalet : il doit être droit, perpendiculaire à la table"), a table of frequencies per tuning (generated, §3), and
a section "what sets this tuner apart" (bass: detection lowered to 30 Hz because the low E is at 41 Hz). The `HowTo`
JSON-LD matches the same keys as the visible text, with no possible divergence. Google no longer shows this rich
result (2023): the value is for the reader and for passage extraction.

## 5. FAQ

- 3 to 5 real questions per page (those of real queries: "Does it handle drop D and half-step down?",
  "Why do other tuners show the wrong octave on my low E?").
- Each answer starts with the answer ("Yes.", or a figure), stands alone and fits in one to three sentences.
- The visible text is the source; the `FAQPage` JSON-LD derives from it (same keys). On jam-jam.org: 720 pages and
  2,710 questions before the campaign, kept.
- **Why include one despite Google.** FAQ rich results have been restricted since August 2023 and have not appeared
  at all since 7 May 2026. But a standalone question/answer pair is a unit that is easy to extract for other engines,
  and it answers a real hesitation of the reader. Do not extend the markup, do not inflate the FAQ: no invented
  question to place a keyword.

## 6. Visible and honest update date, real author

- Line "Updated on 10 October 2026 by <publisher>, publisher of <brand>" (EN; key `toolref.updated`, localized, date
  formatted per language). It reads **the same register** as `dateModified` and `<lastmod>` (`03` §2) and appears
  only if the page has a date.
- The date changes only if the visible text changes (fingerprints). In the campaign, 44 keys were re-dated to
  10 October because their text had really changed; nine older articles kept their original date.
- Author: the identifiable legal publisher, declared in a single place (`src/i18n/publisher.ts`, also the single
  source for the legal notices). `BlogPosting.author` points to the `Person` node of the graph; never an invented
  name, never "team" without a person behind it.
- An About page (§9) makes this identity verifiable.

## 7. Titles and descriptions rewritten for real queries

**Method.**

1. Extract from Search Console, per language (not translated from English), the queries per page over 90 days, and
   the pages with 100 impressions or more and a CTR below 1% (`02` §4.8). The campaign's summary file lists for
   example `/fr/accordeur-basse/`: 1,180 impressions, 11 clicks, position 11.7 (the query "accordeur basse en ligne"
   accounts for 679 impressions); `/fr/accordeur-violon/`: 594 impressions, 0 clicks, position 19.6; `/metronome/`:
   571 impressions, 1 click, position 75.7.
2. Put the exact query at the head of the title, state the benefit (e.g. "free"), keep the intent specific to the
   page.
3. Respect the thresholds: title at most 60 Latin characters (30 in Japanese and Korean), never more than 70;
   description between 70 and 160 characters (35 to 80 in CJK); unique titles (`check-seo-meta.mjs --strict`).
4. Put the precise fact at the start of the description (frequencies, range, tolerance) rather than a slogan.
5. Fix any wrong figure along the way.

Before → after, real (English):

| Page | Title before | Title after | Reason |
|---|---|---|---|
| tuner | Free Online Guitar Tuner: chromatic tuner by mic | Online Tuner: free chromatic tuner by mic | The page serves 21 instruments; "guitar" alone over-promised |
| clavier | Free Online MIDI Keyboard | Online Piano Keyboard, free, with MIDI support | The MIDI intent is carried by the new page clavier-midi; the page goes back to being an online piano page |
| accordeur-basse | Free Online Bass Tuner: 4-string, drop D, by mic | Bass Tuner Online: free 4 and 5-string, by mic | Word order of the queries ("bass tuner online") and 5 strings added |
| metronome | Free Online Metronome (description "40 to 240 BPM") | Online Metronome: free, 30-300 BPM, tap tempo | Range corrected from the code |
| accords | AI Chords: find, name and read any chord, free | Chord Finder Online: name any chord, free | Real query "chord finder" rather than "AI chords" |
| gammes | Scales on an Online Keyboard: see any scale, free | Piano Scales Online: see 16 scales and modes | Exact figure and query "piano scales" |

Before → after, real (French):

| Page | Title before | Title after |
|---|---|---|
| tuner | Accordeur chromatique en ligne, gratuit | Accordeur en ligne gratuit, chromatique, au micro |
| accordeur-violon | Accordeur violon en ligne. Sol Ré La Mi au micro | Accordeur violon en ligne gratuit, au micro |
| accordeur-basse | Accordeur de basse en ligne gratuit, au micro | Accordeur basse en ligne gratuit, au micro |
| transposer | Transposer une chanson + calculateur de capo | Transposer des accords en ligne + calcul du capo |
| accords | Trouve un accord par IA, gratuit | Trouver un accord en ligne, gratuit, par IA |

Description before → after (violin, fr): "Accorde ton violon gratuitement en ligne : Mi5 La4 Ré4 Sol3 en quintes
justes, une justesse à ±5 centièmes..." becomes "Accordeur de violon en ligne gratuit : Sol3 196 Hz, Ré4, La4 440 Hz
et Mi5 659 Hz, aiguille juste à ±5 centièmes..." : frequencies first, strings ordered from low to high.

Honesty about these changes: for the French violin page, the original title already began with the query; the
expected gain is modest and **not measured**. The tracking criterion adopted is a CTR above 3% on niche queries at
4 to 8 weeks.

## 8. Pages created for needs with no page

Principle: one page per **intent** and per measured real need, never one page per keyword variant (Google's guide
classes this practice as "scaled content abuse"). Common template: H1 = the need, "In short" block, steps, verified
differences, FAQ, call to action to the tool.

| Page | Need and targeted queries | Why it did not exist |
|---|---|---|
| `/clavier-midi` | "midi keyboard online" (136 impressions), "online midi keyboard" (81), average position 23.8 on the piano page; "clavier midi en ligne" in French | The query landed on a generic piano page. Own content: compatible browsers (Web MIDI: Chrome and Edge, not Safari or Firefox), troubleshooting, latency, mobile app |
| `/apprendre-piano` | "learn piano online free", "apprendre le piano gratuit" | Real piano-learning feature, without an overview page; verified in the code before being written |
| `/karaoke` | karaoke creation, synchronized lyrics | Feature without a page; no song lyrics displayed; audio deletion no later than 72 h after processing, verified |
| `/importer-chanson` | importing chords from a link, a PDF, a photo | Core flow without a page; privacy described exactly (photo: server-side recognition on the web, on-device on mobile); import sites are never named |
| `/glossaire` | music theory definitions | Citable reference content, 21 terms each linked to the tool that shows it (reduced from 40 planned to 20 in depth) |
| `/a-propos` | who publishes the product, principles, profiles | Entity page: the publisher was public only in the legal notices |

Pages dropped or merged after plan review: `/progressions-accords` (no matching web tool; replaced by an article),
`tune-your-bass`, `tune-your-violin`, `tune-your-ukulele` (merged into the tuner pages that already ranked, §10),
`midi-keyboard-browser` (absorbed by `/clavier-midi`: one URL per intent), `beginner-guitar-chords` (same intent as
an article from another workstream). "Alternatives to X" pages: postponed, because comparative advertising requires
a prior legal protocol.

## 9. Glossary, About, citable reference articles

**Glossary** (`DefinedTermSet`): each term has a translated anchor (`#capo`, `#cent`), a direct definition in one or
two sentences, an explanation, an example and a link to the tool. The JSON-LD carries one `DefinedTerm` per anchor
(one `@id` per anchor), linked to the page via `mainEntity`. Real example: "A capo is a clamp placed on the neck
that shortens every string and raises the instrument by as many semitones as frets."

**About** (`AboutPage` → `Organization`): who publishes (legal identity, address, host, taken from the single source
of the legal notices), what the product does (one entry per need covered), **verifiable** principles (free tools
without an account, microphone analyzed on the device, audio file deleted after processing, no advertising on the
web, figures recounted from the code), platforms and languages, links to contact, legal notices and privacy. Each
principle cites a checkable fact; nothing superlative.

**Reference articles** (6): written to be cited, with the answer in the first sentence, self-contained sections, a
table, FAQ, link to the tool.

| Article | Answer at the top | Generated block | Linked tool |
|---|---|---|---|
| `note-frequencies` | "Middle C is 261.63 Hz, A0 27.50 Hz, C8 4,186.01 Hz" with the formula | Table of 108 notes, 440/432/442 Hz calculator, note names (English, solfège, German) | tuner |
| `capo-chart` | "A G shape played at capo 2 gives an A" | Table of shapes × frets 1 to 7, capo by key | transposer |
| `circle-of-fifths` | keys and key signatures | Circle of fifths, order of accidentals | gammes |
| `read-guitar-tabs` | symbols and rhythm | Symbols, chords, rhythm | tablature |
| `find-song-bpm` | tap-tempo method | Tempo calculation, terms and styles | metronome |
| `common-chord-progressions` | progressions by scale degree | Major and minor progression tables, diatonic chords | (mobile app, referenced) |

Substantive precautions: on `note-frequencies`, the "432 Hz" myth is addressed with facts ("no serious study
attributes any particular effect"); German H/B notation is explained without promising that the tool displays it
(it does not), and the gap was escalated as a product ticket.

## 10. Merging and enriching thin pages

- **Merge rather than create**: for tune-your-bass/violin/ukulele, the content was added to the tuner pages that
  already ranked (a "How to tune" section, a table drawn from the code, FAQ). A new URL would have put two pages in
  competition for the same intent.
- **Enrich without padding**: `piano-chords` (231 words before) and `tune-your-harp` (254) received a rewritten
  description ("Piano chords explained: major, minor, seventh, sus and ninth formulas in semitones..."), formulas in
  semitones, a table and 3 FAQ questions. Measured after (same inventory script, 13 October build): 453 and 437
  words. No word threshold imposed, since Google knows of no ideal length.
- Still to do: 46 article pages remain under 300 words across all languages (including, in English, tune-your-
  charango, find-song-chords, tune-your-guitar, tune-your-oud, play-piano-online, mp3-to-lyrics). Enrich them only if
  a real query justifies it.

## 11. Accuracy rules (to apply before writing a line)

1. **Every published fact matches the real code or product.** Check in the code, never in a specification, a brief or
   another text on the site: documents "sometimes describe as still to be done work that has already shipped".
2. **State the platform** (web, Android, iOS in beta) and never promise a missing feature (example: the site explains
   German H notation without claiming the tool displays it; a progression composer exists only on mobile).
3. **Fix errors found** during writing. Real campaign cases: "Vingt instruments" became 21; "pentatoniques" (plural)
   became "pentatonique mineure et blues" (the code knows only one); metronome 40-240 became 30-300 BPM; cavaquinho
   tuning D5 A4 B4 E4 harmonized everywhere; bass: 4 strings (standard, Drop D, half step down) and 5 strings with low
   B, not 6 strings; ukulele: re-entrant standard, Low G, baritone; violin: a single tuning; photo import not reserved
   to mobile; karaoke audio deleted no later than 72 h.
4. **Figures only those from the brief**, recounted by script (§2).
5. **No protected excerpts**: generic progressions or public-domain titles.
6. **No emoji, no em dash** in published text (automatic check); the form of address (tu or vous) set by the brand
   brief.
7. **Check the rendering**: an HTML comment cut by an angle-bracket tag was displayed as plain text under each article
   (all languages) before being replaced. Re-read the built HTML, not just the source.

## 12. What not to do

- **Hidden text** for AIs, instructions addressed to models in the pages or in llms.txt: treated as cloaking; Google
  specifies that its anti-spam rules apply to generative answers.
- **Mass-produced content** without its own value, one page per query variant: "scaled content abuse" policy.
- **Invented aggregate ratings** (`aggregateRating` without real, approved reviews), fake reviews, fake forum accounts.
- **Tampered dates**: re-dating without a visible change, displaying the build date, setting a future date.
- **Identical "In short" blocks** from page to page, FAQs with invented questions, hand-written tables.
- **Platform or price promises** that do not match actual behavior.
- **"Alternatives to X" pages** without legal validation (comparative advertising).
- **Self-promotional encyclopedic article**: notability criterion not met, risk of deletion.

## 13. Recommended work order for a new site

1. Technical and sitemap (`03`), otherwise the content will be neither crawled nor dated.
2. Accuracy: inventory of figures, generated reference table, figures check.
3. Existing pages already ranking in positions 5 to 20: In short block, titles and descriptions, FAQ, date.
4. Pages for measured needs without a page, then citable reference articles.
5. Localized translations per language (`05-multilingual.md`), only complete pages.
6. External mentions (`06-off-site.md`), then measurement (`07-measurement.md`).
