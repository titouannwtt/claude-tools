# Interview

Goal: learn where the user wants the repository to go, with as few questions as possible. Ask in the user's
language. Use AskUserQuestion (at most four questions per call, two to four options each, the recommended option
first with "(Recommended)"). Pre-fill from `inventory`: a question whose answer the facts give is not asked, it is
stated ("Web app detected: I will capture screenshots").

## What the facts already answer

| Fact from `inventory` / `structure` | Consequence, no question needed |
|---|---|
| `project_type` web-app, website, mobile-app | screenshots recommended; capture plan from `run_hints` |
| `project_type` cli, library | animated terminal or code card recommended |
| `project_type` catalog | contents table with live counts recommended |
| `project_type` profile | profile pattern (see readme-patterns.md) |
| `github.homepageUrl` set, or a site in package.json | that link goes in the link row |
| releases exist | install section points to the latest release |
| no LICENSE | ask in batch 2 only if the goal involves reuse |
| `style_sources` found | propose visual consistency with the owner's other repositories |

## Batch 1: intent

1. **What is this repository for?** A tool or product people use · A library or API for developers · A showcase of
   skills (portfolio, school or side project) · A resource (catalog, data, assets, docs)
2. **Who must understand it first?** (multiSelect) Recruiters and clients · Developers who will use it · Non-technical
   end users · Contributors
3. **Why share it?** Get hired or find clients · Gain users and stars · Attract contributions · Support a product
   (site, app, API)
4. **How long should the README be?** Very short and visual (Recommended) · Short, plus an install tutorial · Full
   documentation (short README, details in `docs/`)

## Batch 2: look and content

1. **Visual style?** Product screenshots in the spotlight (default for apps) · Animated terminal or code card
   (default for CLIs and libraries) · Graphic banner, sober · A mascot
2. **Sections?** (multiSelect; offer the four most relevant for the type, the user can add others) Install ·
   Quick start or example · Screenshots or demo · Architecture diagram · Features · Benchmarks or comparison ·
   Roadmap · Contributing · FAQ
3. **Links to highlight?** (multiSelect) Website or live demo · Documentation · Store or download · Your profile
   (GitHub, LinkedIn, personal site)
4. **Language?** English (Recommended for reach) · Bilingual: English plus a short summary in your language · Your
   language only

## Conditional follow-ups

- **Mascot**: "Where is the mascot? A link or a path to the image (SVG preferred, otherwise a transparent PNG of at
  least 512 px)". Then its rights: own creation · licensed (which license) · fan art of a brand (add a disclaimer
  line, as claude-tools does: "Not affiliated with X; the mascot is a fan illustration"). No image and no source:
  propose a sober banner instead, or an original mascot drawn by the designer agent, only if the user asks.
- **Screenshots**: live URL or local run (`run_hints`), which pages or screens matter, whether a login is needed.
  Never put credentials in the repository; prefer a public demo or seeded local data. Every capture is checked for
  personal data (names, e-mails, avatars, private documents) before it is committed.
- **Brand**: existing site: run `site-design analyze <url>` for the palette and fonts. None: reuse the owner's
  `style_sources` so the profile looks consistent.
- **Author highlight**: put the user's profile forward? A one-line footer ("Built by ..." with profile links), and
  an availability line only if the user wants it on their profile.
- **Live numbers**: if the inventory or the draft shows counts that change (files, entries, plugins), ask whether a
  GitHub Action may update them on every push (`counts install-action`), or whether badges are enough.

## After the answers

Summarize the choices in three lines, then go to the proposals (readme-patterns.md). Do not re-ask a decided point.
