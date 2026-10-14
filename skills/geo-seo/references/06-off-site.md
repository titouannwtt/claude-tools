# 06. Off-site: the real ceiling of GEO

A perfectly rebuilt site stays invisible to AI assistants if nobody else talks about it.
This file gives the general method, then applies it point by point with the full example of
Jam Jam (jam-jam.org). The template texts are parameterised: `[NAME]` for the product, `[FUNCTION]` for
what it does, `[FIGURE]` for a verified figure, `[URL]` for an address. Ready-to-copy versions
are in `templates/` (emails, API examples README, JSON-LD).

## 1. Why this is the ceiling

Findings from the research and the campaign audit:

| Finding | Source |
|---|---|
| Language models respond more to brand mentions than to links: a correlation of about 0.66 between brand mentions and visibility in AI overviews, against about 0.22 for backlinks (Ahrefs study of 75,000 brands). Correlation, not causation. | `RECHERCHE.md`, Ahrefs |
| Wikipedia and Reddit are the domains most cited by ChatGPT (Semrush study, 230,000 queries), but the share varies widely from one month to the next. | `RECHERCHE.md`, Semrush |
| YouTube is the mention most correlated with AI visibility (Ahrefs, December 2025). | `RECHERCHE.md` |
| Ranking first on Google does not guarantee being cited by ChatGPT, which relies on its training memory and on its own index partly backed by Bing. | `RECHERCHE.md` |
| At the start of the campaign: three known external mentions (AlternativeTo, SaaSHub, Trustpilot with 1 review), nothing on Wikidata, YouTube, Reddit, public GitHub or the press. The brand had 72 impressions in 90 days. Troublesome namesakes (Jamn, jam.dev, Cookie Jam, jamm). | `AUDIT.md` §3, point 14 |

Consequence: the work on the site (see `09-autonomous-procedure.md`) makes the site CITABLE; the
off-site work makes it CITED. Both are necessary, but only the second is slow (months) and depends
on outside people.

## 2. General method

### 2.1 The seven rules

1. **Entity consistency.** One reference description (exact name, function, platforms, price,
   figures) copied verbatim into each listing: assistants cross-check. In the campaign, the
   AlternativeTo description serves as the reference (SaaSHub reuses it).
2. **Accuracy.** Each figure comes from the table of validated figures (`BRIEF-MARKETING.md` §3.2,
   checked by `scripts/check-marketing-numbers.mjs`); each platform is described as it is (iOS in
   public beta, not "on the App Store"). A wrong off-site text is harder to correct than a text on
   the site.
3. **A human holds the accounts.** The agent prepares texts to paste; it does not create accounts,
   publish anything in the owner's name, or reply on a forum (checkpoint of
   `09-autonomous-procedure.md`).
4. **Disclose**: any mention made by the creator says so ("Disclosure: I make [NAME]").
5. **No fakes**: no fake account, no fake review, no coordinated vote, no paid link.
6. **Measure before pushing**: the panel (`07-measurement.md`) says which sources assistants cite;
   that list is the prospecting list.
7. **Space out**: a spike of identical mentions on the same day looks like spam.

### 2.2 Impact / effort ranking (campaign)

| # | Action | Impact | Effort | When |
|---|---|---|---|---|
| 1 | Update the AlternativeTo listing and add cross-referenced "alternative to" entries | High | 1 h | Right away |
| 2 | Update the SaaSHub listing | Medium | 30 min | Right away |
| 3 | Public GitHub repository of API examples | Medium to high (cited by code AI, `sameAs`) | 2 h | After README review |
| 4 | Three short YouTube videos | High over time (most correlated mention) | 1 to 2 days | After the site batch |
| 5 | Useful replies on Reddit | Medium, slow | 30 min per reply | Ongoing, from a seasoned account |
| 6 | Contacting authors of "best tools" lists | High if the list is cited by AI | 15 min per email | After the first panel measurement |
| 7 | Wikidata | Medium | 1 h | ONLY after an independent source |
| 8 | Product Hunt | Medium | 1 day | Postponed (see §9) |
| 9 | Pages "alternatives to X" | High | 2 days per page | Postponed (see §12) |

### 2.3 Keeping the log

A table (date, platform, URL of the mention, text published, status, assistants that cite it in the
next panel run). The URL of each profile created is added to the `sameAs` of the JSON-LD (see
`templates/json-ld-graph.json`), only once the profile exists and is maintained by the project. To
avoid: hidden text, mass pages, fake reviews or accounts, a self-promotional Wikipedia article, the
Google Indexing API outside its official use (see `01-research-verdicts.md`).

## 3. AlternativeTo (existing listing)

Why: an alternatives site heavily cited by assistants for "which app for X" questions. The listing
already existed in the campaign; the job is to make it accurate and to link it to other listings.

### Fields and template text

- **Name**: `[NAME]`
- **Tagline** (100 characters maximum). Real example:
  `Free chord songbook, AI chord detection, tuner and MIDI-ready online piano. Web and Android.`
  Template: `[FUNCTION 1], [FUNCTION 2] and [FUNCTION 3]. [PLATFORMS].`
- **Description** (reference text, in English):

```
[NAME] is [CATEGORY IN ONE SENTENCE]: [MAIN BENEFIT].

What you can do for free:
- [FUNCTION 1]: [detail verified with [FIGURE]].
- [FUNCTION 2]: [verified detail].
- [FUNCTION 3]: [verified detail].

Platforms: [web / Android / iOS beta...]. Available in [N] languages.

Free to use. [Paid offer in one sentence: what it unlocks, what it does not change.]
Made by [PUBLISHER, country].
```

Real example: "Jam Jam is a songbook for musicians: find the chords of a song, adapt it to your
instrument and keep it ready to play [...] Free to use. An optional Premium subscription raises the weekly
limits and removes ads on mobile. There are no ads on the website."

- **Platforms**: tick only what is published. For Jam Jam: Online, Android. iPhone only at the App
  Store release (a TestFlight beta is not an "available" platform).
- **License**: Freemium. **Category**: Audio & Music.
- **Tags**: those that already exist on the site (chord-detection, guitar-tuner, virtual-piano,
  midi-keyboard, songbook, metronome, offline, no-registration-required, web-based, api...).
- **Features**: tick only what is true on the target platform ("no ads" applies to the site, not to
  the mobile app).

### "Alternative to": by real function

On the listing of each comparable software, use "Suggest an alternative" pointing to `[NAME]`, with a
factual sentence, without disparagement. Principle: one line per software whose function really
overlaps a function of the product.

| Software | Shared function | Justification to paste |
|---|---|---|
| Chordify | chord detection from audio | `Detects chords from the mic, a browser tab or an audio file, then saves them to an editable songbook.` |
| Chord ai | live chord detection | `Real-time chord detection (168 chords) that runs on the phone, offline.` |
| GuitarTuna | tuner | `Free chromatic tuner, 21 instruments and 79 tunings, in the browser or on Android.` |
| Ultimate Guitar | chord songbook, transposition | `Personal chord and lyrics songbook with transpose, capo and PDF export.` |
| Virtual Piano | online piano | `Online piano with 142 sounds that accepts a real USB MIDI keyboard in Chrome or Edge.` |

The campaign's full list had 11 software. Sentence template: `[precise FUNCTION] with [verified FIGURE], [platform].`

DO NOT list: software whose overlap is too weak, or whose function the product does not promise (the
campaign dropped a track-separation tool although the function was not yet published, a tablature
reader with too little overlap, a chord-chart accompanist whose web and mobile parity had not been
verified).

## 4. SaaSHub

Same logic as AlternativeTo: listing already submitted (3 August in the campaign), to be completed.

- **Tagline**: short version of the reference text (`Chord songbook, AI chord detection,
  21-instrument tuner and MIDI online piano`).
- **Description**: identical to the AlternativeTo one (entity consistency).
- **Categories**: Music, Music Education, Audio Tools, Developer Tools (for the API).
- **Pricing**: Freemium. **Platforms**: Web, Android.
- **Alternatives**: validate SaaSHub's suggestion by category and add the software from the
  AlternativeTo list.
- **Form questions** (model answers):
  - What makes [NAME] different? Example: `The songbook, the chord detection and the practice tools share the same data: a detected song lands in your songbook, and the keyboard can follow its key.`
  - Is there a free offer? Example: `Yes. The web tools need no account. A free account has weekly limits (for example 10 imports per week); Premium raises them.`

## 5. Public GitHub repository of API examples

### Why

Code assistants (ChatGPT, Claude Code, Cursor, Copilot) read GitHub. A public repository of runnable
examples answers questions like "is there an API for [FUNCTION]" (the panel asked three per
language), provides a high-authority page that cites the product, adds one more profile to `sameAs`
(Wikidata P1324 later), and costs little: two hours, since the examples already exist in the
documentation.

### License: MIT

MIT for the examples (copyable into proprietary code). Apache-2.0 if the publisher wants a patent
clause. The license covers the examples, NOT the API or the service, which the README says in its
last section, pointing to the terms of use.

### Recommended structure

```
[nom]-api-examples/
  README.md
  LICENSE
  .env.example              # [NOM]_API_KEY=cle_exemple_xxxxxxxx  (NEVER a real key)
  samples/
    public-domain-song.pdf  # public-domain content, created for the repository
  curl/       01-list-formats.sh ... 06-usage.sh
  javascript/ package.json, list-formats.mjs, convert-file.mjs, convert-url.mjs, follow-events.mjs
  python/     requirements.txt, list_formats.py, convert_file.py, convert_url.py, usage.py
  mcp/        claude_desktop_config.json
```

Real name in the campaign: `jam-jam-api-examples`. GitHub description:
`Examples for the [NAME] REST API: [FUNCTION] ...`. Topics: `music`, `chords`, `chordpro`, `musicxml`,
`midi`, `pdf`, `rest-api`, `openapi`, `songbook`. Website field: the site's developer page.

### Repository rules

1. No real key, no protected lyrics or titles in the examples: replace any song URL taken from the
   developer page with a neutral URL.
2. Format identifiers taken from `GET /formats` and checked against the OpenAPI contract before
   publication (a stale identifier makes the first reader's example fail).
3. Zero dependencies where possible (Node 20 with native `fetch`; Python with `requests`).
4. Each example runs as-is after copying `.env.example` to `.env`.
5. A section on errors (`application/problem+json`, RFC 9457), file retention, quotas and rights
   ("only convert what you have the right to use").
6. An MCP section if the product exposes one: client configuration, list of tools.

Full README skeleton: `templates/readme-api-examples.md`.

### To check before publication

That the MCP package cited is really published in the package registry, that the legal page addresses
are exact, and that a format identifier given as an example is still valid. Once the repository is
online: add it to `sameAs`, to the developer page and to Wikidata (P1324, qualified "API examples").

## 6. Short YouTube videos

### Why and how

YouTube is the mention most correlated with AI visibility. Three videos of 45 to 75 seconds, one per
major need, are worth more than an ambitious channel never fed.

Format: 16:9 with a 9:16 version for Shorts from the same recording, a REAL screenshot of the site,
voice or burned-in subtitles, no protected music (play it yourself or use the product's sounds). The
channel is created by the owner, named like the brand, with a link to the site in the header, then
added to `sameAs`.

### Integration on the site

Clickable facade video: static thumbnail and a `youtube-nocookie.com` link loaded on click, to respect
a strict CSP and GDPR (nothing is requested from YouTube before the click). Placed under the "In brief"
block of the relevant page, with a `VideoObject` JSON-LD (`name`, `description`, `thumbnailUrl`,
`uploadDate`, `duration`, `embedUrl`). One video per page language: fr on fr pages, en on the root and
the other languages (subtitles translated later). The campaign then delivered a batch "Official
YouTube: consent, privacy and CSP" (PR #75), a sign that the integration touches the privacy policy
and the security header: treat it as a separate batch.

### Full example: video 1, tuner

Target page: `/tuner/` and its localised version. French title: « Accordeur guitare en ligne gratuit (micro,
Drop D, basse, ukulélé) ». English title: « Free online guitar tuner with your mic (Drop D, bass,
ukulele) ».

| Shot | Duration | Image | Voice (fr) | Voice (en) |
|---|---|---|---|---|
| 1 | 0 to 4 s | close-up of an out-of-tune guitar, then the screen | « Accorder ta guitare sans installer d'appli. » | "Tune your guitar without installing an app." |
| 2 | 4 to 12 s | opening the site, microphone permission | « Ouvre l'accordeur dans ton navigateur et autorise le micro. Le son reste sur ton appareil. » | "Open the tuner in your browser and allow the mic. The sound stays on your device." |
| 3 | 12 to 30 s | low E string played, needle centring | « Joue une corde : l'aiguille te dit si c'est trop haut ou trop bas, à plus ou moins 5 cents. » | "Play a string: the needle shows if it is sharp or flat, within plus or minus 5 cents." |
| 4 | 30 to 42 s | tuning menu: Drop D, DADGAD | « Change d'accordage en un geste. » | "Switch tunings in one tap." |
| 5 | 42 to 55 s | instrument menu | « 21 instruments et 79 accordages : basse, ukulélé, violon, oud, sitar... » | "21 instruments and 79 tunings." |
| 6 | 55 to 62 s | logo and address | « Gratuit, sans compte : jam-jam.org/tuner » | "Free, no account: jam-jam.org/tuner" |

YouTube description: one promise sentence with the figures, the links (tool page, flagship instrument
page, app), then timestamped chapters (`00:00 Accorder sans appli`, `00:04 Ouvrir
l'accordeur et autoriser le micro`, `00:12 Lire l'aiguille (±5 cents)`...).

### The campaign's other two videos

| Video | Target page | Angle | Precaution |
|---|---|---|---|
| 2. MIDI keyboard | `/clavier-midi/` | USB keyboard plugged into Chrome or Edge, hot-plugging, velocity, sustain | check every sentence against the code before filming (is the chord name displayed on the web?) |
| 3. Chord detection | `/detection/` | microphone, tab audio, audio file, key and tempo, sending to the songbook | no protected song on screen |

## 7. Reddit

Reddit is one of the two domains most cited by ChatGPT in the Semrush study (with Wikipedia), so a
useful, lasting answer counts there. It is also where self-promotion is punished most. Non-negotiable rules:

1. **Disclose, every time**: "Disclosure: I make [NAME]".
2. **Answer the question first, completely.** The link is only an optional support; the answer must
   stand without it.
3. **No fake accounts, no coordinated votes, never the same link pasted in series.**
4. **Follow the subreddit's rules**; when in doubt, do not include a link.
5. **Seasoned account**: age, useful contributions, a ratio of about 9 non-promotional contributions
   for 1 mention of the product (the project's historical strategy).
6. Never link a protected song or a site you do not name publicly.
7. A response template is a framework, never a text to paste. The project's old templates let people
   believe in a third-party user ("I use [NAME]"): ban this wording.

### Five situations where answering is useful (framework)

Adapt the list to your field: one situation = a recurring question + a complete answer + a product
mention as support.

| # | Question type | Subreddits | Useful answer |
|---|---|---|---|
| 1 | Free tuner for a rare instrument | r/oud, r/mandolin, r/banjo, r/bouzouki, r/Cello | give the standard tuning and string frequencies, then the tool link with the specific instrument; disclose |
| 2 | Using a MIDI keyboard without music software | r/piano, r/midi, r/synthesizers | explain Web MIDI (Chrome and Edge, not Safari or Firefox), then the tool as an example |
| 3 | Finding a song's chords by ear | r/guitar, r/musictheory | method (bass first, degrees I-IV-V-vi), then detection to check; disclose |
| 4 | App to organise chord charts and a setlist | r/guitar, r/ukulele, r/WorshipLeaders | criteria (transposition, capo, PDF export, offline), the product among other options cited honestly |
| 5 | Transposing a chart for a capo or another key | r/guitar, r/singing | explain the half-step calculation, a generic example, then the tool |

Answer template: (1) the answer in 3 to 6 lines, (2) the step-by-step or the useful table, (3) a
sentence "Disclosure: I make [NAME], it has a free [FUNCTION] if you want to check it: [URL]", (4) an
invitation to critical feedback.

## 8. "Best tools" lists cited by AI

### Why

When an assistant answers "les meilleurs accordeurs en ligne gratuits", it relies on a few list
articles. Being listed there is worth more than ten directories. The method starts by knowing WHICH
articles are cited.

### Method

1. Ask the panel questions (see `07-measurement.md`, `templates/panel-questions.md`) to Perplexity,
   ChatGPT (search enabled), Copilot and Google AI Overviews. Record **the cited source URLs**, not
   only the tools named.
2. Keep the editorial pages (blogs, media, teacher sites); drop competitors' pages and forums.
3. Supplement with Google queries in each target language: `"best free online [TOOL]"`,
   `"meilleur [TOOL] en ligne gratuit"`, `intitle:"best" "[TOOL]" 2026`, then Bing (source of ChatGPT
   and Copilot).
4. Log in a table: URL, update date, author, contact (contact page or public email), tools cited,
   assistants that cite it.
5. Prioritise: cited by several assistants, then updated within the last year, then the language in
   which the product is strong (for Jam Jam: fr, es, de, pl, ja).
6. **One email per article, one follow-up at most, not before 3 weeks.** Offer nothing in exchange for
   a link (no paid link, no quid pro quo).

### Email template

Full text in fr and en, with follow-up and checklist: `templates/email-outreach.md`. Structure: a
subject that names the article; a precise sentence on what the article brings (never a generic
compliment); a sentence on the function that matches ITS section, with a verified figure; a direct
link to the tool page (never the homepage); a polite exit ("je comprends si ça ne correspond pas à
votre ligne"); an invitation to critical feedback. Personalise the first sentence of each message.

## 9. Product Hunt (postponed)

Owner's decision (15 July 2026): postpone until the iOS release on the App Store. General
justification, not documented by the campaign: a launch cannot be replayed, so it is done once all the
target platforms are available and the text is up to date. The project's historical copy was out of
date (wording banned by the marketing brief, emoji, prices not current): it must be rewritten before
launch from the reference description (§3). General rule: do not launch on Product Hunt until the
product is available where visitors will go to install it.

## 10. Wikidata

**Warning**: create the item ONLY AFTER at least one published independent source (press article,
specialist blog, editorial list that cites the product). The AlternativeTo and SaaSHub listings and
the official site are not enough: an item without a third-party source risks deletion for
insufficient notability, which leaves a negative trace. Created from the owner's personal account,
with the conflict of interest declared on its user page.

Label: the product name, in each language. Short description per language ("music app with chord
songbook, chord detection and tuner" in English).

| Property | Value (example) | Note |
|---|---|---|
| P31 instance of | mobile application; web application | item identifiers to check at entry |
| P178 developer | publisher name | no person item without its own notability: omit rather than create |
| P856 official website | `https://[domaine]/` | |
| P400 platform | Android; web browser | iOS only at App Store release |
| P136 genre | music software | identifier to look up |
| P407 language of work or name | the published languages | |
| P275 license | proprietary software | |
| P3418 Google Play app ID | `[PACKAGE ID]` | |
| P1324 source code repository | examples repository | only if it exists |
| P2397 YouTube channel ID | channel identifier | when it exists |
| Reference (P854) | URL of the independent source | on P31 and P856 at least |

Then: add the Wikidata URL to the `sameAs` of the `Organization`.

## 11. Directory badges

Many directories offer a badge ("Featured on...", "Verified on...") to place on the site in exchange
for a listing. The campaign placed none; the rules below follow from the site's constraints (strict
CSP, policy of "no third-party script by default", performance budgets measured at deployment).

### Possible benefits

A listing and an inbound link (of very variable value), light social proof if the directory is known
to your audience, sometimes a listing conditional on placing the badge.

### Risks

Each badge is an outbound link (mass link exchange is targeted by search engines' anti-spam rules);
many are placed with an external `<script>`, forbidden by a strict CSP and by a policy that promises
no third parties; a third-party image or script adds an external request and a CLS risk (the
campaign's deployment checks CLS and weight); a badge loaded from the directory reveals the visitor's
IP and page to it; a low-quality or paid-for-links directory weakens the brand.

### Rules if you place one

1. **Local image**: copy the badge into the site's assets, never load it from the directory.
2. **No script**, never a third-party `<iframe>`.
3. Explicit `width` and `height` (no CLS), `loading="lazy"`.
4. Outbound link with `rel="noopener"`, and `nofollow`/`sponsored` if the directory is paid or
   requires it to stay compliant.
5. A single place (foot of the "About" page or of a "They talk about us" page), not in the template
   of every page.
6. Localised alt text, and the directory profile is added to `sameAs` only if the project maintains it.

### When not to do it

If the badge requires third-party JavaScript; if the directory charges for the link or is not read by
your audience; if the site's performance is being corrected; if the listing does not exist yet or is
inaccurate (fix the listing first).

## 12. Pages "alternatives to X"

### Why make them

Queries like "alternative to [COMPETITOR]", "[COMPETITOR] alternative", "free [COMPETITOR]
alternative" are comparison intents that assistants serve with pages of this type. The campaign site
had none although the need exists (potential judged high).

### Why wait: the risk of comparative advertising

The campaign postponed these pages: **comparative advertising** is governed by articles L122-1 et seq.
of the French Consumer Code and by Directive 2006/114/EC (art. 4). It is lawful if it concerns goods
meeting the same needs, objectively compares essential, relevant, verifiable and representative
features (including price), is not misleading, does not disparage, does not create confusion and does
not unduly take advantage of a brand's reputation. Consequences adopted:

- each row of the table is **verifiable**: a public source with a link and a visible **date checked**;
- the brand is named in text only, never a third party's logo or graphic identity;
- no disparaging adjective and no "better than": facts, including what the competitor does and the
  product does not (otherwise the comparison is not representative);
- quarterly review, row removed if it is no longer verifiable; article L122-5 requires proving the
  accuracy of claims promptly, so archive each source (dated capture);
- validation by the repository's legal protocol BEFORE any writing.

This is a human checkpoint: launch or not, and in which languages (suggestion: fr and en first).

### Three targets suggested in the campaign (real functional overlap and search volume)

| Target | Comparable function | What the page must honestly say |
|---|---|---|
| Chordify | chord detection from audio | the product detects from the microphone, a tab (web) or a file, with results in an editable songbook; the other starts from online song libraries, not the product |
| GuitarTuna | tuner | the product runs in the browser with no installation, 21 instruments, 79 tunings; the other offers games and lessons, and a published iOS app |
| Ultimate Guitar (personal songbook) | chord songbook, transposition, capo, PDF export | the other has a catalogue of sheet music; the product is a personal songbook |

Page outline (once authorised): direct answer at the top, feature table with sources and date checked,
what each does better, for whom, link to the tool, FAQ, simple `WebPage` JSON-LD (no `Review` nor
invented aggregate rating).

## 13. Follow-up

After each action, note the date. At the next panel run (see `07-measurement.md`), check three things:
is the product cited more often, with which URL, and do the sources cited by assistants now include
your listings? Timelines are in months (see `07-measurement.md`, §7). Tracking mentions is the loop
that feeds the prospecting list of §8.
