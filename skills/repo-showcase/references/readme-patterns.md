# README patterns

## Principles

- **Five-second test**: banner + one sentence + one visual say what it is, for whom, and why it is different.
- **Visuals carry the message**, the text confirms it. Every image has alt text that states its key message, and
  anything essential in an image is also said in one line of text.
- **Length follows the project**, always on the short side. Indicative budgets: small repository (under about
  20 files) 40 to 80 lines; medium 80 to 150; product or large codebase 120 to 200, the rest in `docs/` or in
  `<details>` blocks. Cut any section that does not serve the chosen audience.
- **Above the fold** (first screen): banner, link row, a two or three line pitch, then the first real visual.
- **Claims are concrete**: measured, with the conditions ("75 % fewer API calls, four bots, live, Oct 2026"), never
  hype words. No hard-coded counts that move (see visuals.md, Live numbers).
- **Consistent**: the README pitch, the GitHub description and the social preview say the same thing.
- Relative links for repository files; anchors in the link row; no em dash.

## Building blocks

- Link row: `<p align="center"><a href="#install"><b>Install</b></a> · <a href="https://..."><b>Website</b></a></p>`.
- Badges: four or five at most, live only (stars, release, license, CI). A badge wall reads as noise.
- Tables for comparisons, catalogs and "what's inside"; Mermaid for a simple flow (renders on GitHub); a custom SVG
  for a polished diagram.
- GitHub alerts (`> [!TIP]`, `> [!NOTE]`): one or two per README.
- `<details><summary>...</summary>` for long but useful material (full options, FAQ).
- Footer: license line, then the author line if the user wants their profile highlighted.

## Patterns by archetype

**Product (web or mobile app)**: banner (framed screenshot or animated hero) · pitch · link row (site, store, demo) ·
screenshot strip, desktop and mobile, or a demo GIF · three to six features (text or an SVG card grid) · how it
works (diagram, optional) · run locally · stack · license · author.

**CLI or developer tool**: animated terminal card showing a real command and its real output · pitch · one-command
install · quick start (three commands) · features · configuration · license.

**Library or API**: banner · pitch · install · minimal working example · API overview table · links to the docs ·
compatibility · license.

**Catalog, data or assets**: banner · what's inside (table with live counts through markers or badges) · how to use
or download (with checksums) · license of each asset family (critical for reuse) · contributing.

**Showcase (portfolio, school or side project)**: banner · what it demonstrates (skills, decisions) · screenshots ·
architecture · what was hard and how it was solved · author.

**Fork**: what differs from upstream (table) and why · link to upstream and credits · sync policy · install.

**Profile README** (`owner/owner`): hero or terminal card (who, focus, status) · one paragraph · flagship projects
table with live star badges · stack · contact and availability. Optional short section in the user's language.

## Metadata (set after the preview is validated)

- Description: one sentence, about 120 characters at most, the same promise as the pitch, in the README language.
- Topics: five to ten, lowercase, hyphenated, the words people search (language, framework, domain).
- Homepage: the site, store page or live demo.
- Social preview: `social --source assets/<banner>.svg`, uploaded by hand in Settings.
- Pin the repository on the profile if it should be seen first.

## Proposal format (workflow step 4)

Present two or three directions, then recommend one:

| Direction | Highlights | For | Length | Visuals |
|---|---|---|---|---|
| A. Product first | the app in use, the outcome for users | users, recruiters | ~90 lines | framed screenshots, demo GIF |
| B. Engineering depth | architecture, measured results, decisions | developers, recruiters | ~130 lines | diagram, benchmark card |
| C. Minimal | one visual, one sentence, install | developers in a hurry | ~40 lines | terminal card |

Each direction states its trade-off in one line (what it leaves out). The recommendation follows from the interview:
audience first, then goal, then length.
