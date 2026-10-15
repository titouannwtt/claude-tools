# Visuals

Each repository gets its own visuals, designed for its message by the `designer` agent. What follows is fixed:
the constraints of GitHub rendering, the rules that keep visuals true over time, and the brief template.

## Formats

- **SVG** for banners, cards, terminals and diagrams, committed in `assets/`: sharp at any width, animatable,
  diffable. Under 200 KB is the target, 1 MB the limit.
- **PNG** for screenshots (`shoot`), in `assets/screenshots/`, under 1.5 MB each (`--scale 1` or fewer pages if
  larger).
- **GIF** for a short demo (`demo`, 5 MB warning). Check the WebP variant renders with `preview` before using it.
- Never embed a screenshot as base64 inside an SVG: commit the PNG and lay it out in the README.

## GitHub constraints

- An SVG shown through `<img>` runs no script, loads no external resource (fonts, images, even relative files) and
  gets no hover or click. `preview` blocks scripts and external references.
- Fonts are the viewer's: use system stacks (`-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
  sans-serif`; mono `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`) and leave 10 to 15 % slack around
  text, because widths vary between systems.
- Width: design at 1280 px wide with a `viewBox`, display with `width="100%"`. On a phone it shrinks to about
  360 px, a factor of 3.5: the key message needs at least 40 px type at 1280, secondary text 24 px; smaller text is
  decoration and must be repeated in the README. Always check the 390 px render.
- Themes: a self-contained card with its own rounded background works on light and dark GitHub. For theme-specific
  variants, use `<picture>` with `<source media="(prefers-color-scheme: dark)" srcset="...">`. A media query inside
  the SVG follows the system setting, not the GitHub theme: do not rely on it for contrast.
- Contrast of text against its background: at least 4.5:1.

## Animation

- SMIL (`<animate>`, `<animateTransform>`) and CSS `@keyframes` both play inside `<img>` on github.com.
- The static state must be complete: with no animation (static renderer, social preview, reduced motion), every
  piece of information is visible. One-shot reveals use `fill="freeze"` and end on the full content.
- Wrap CSS loops in `@media (prefers-reduced-motion: no-preference)`. Keep SMIL to one-shot reveals.
- Subtle and short: intro under 3 to 4 seconds; loops limited to a blinking cursor, a pulse, a gentle float, dots
  moving along a path. Never hide key information behind a long sequence.

## Live numbers

A number written in a visual or the README is only allowed if:

1. it is a **live badge** (shields.io: stars, release, downloads, last commit, or `counts badge --kind files` for
   the number of entries of a folder);
2. it is a **synced counter**: `<tspan data-count="name">57</tspan>` in an SVG, `<!-- count:name -->57<!-- /count -->`
   in Markdown, defined in `.showcase.json` and rewritten by `counts sync` (and by the GitHub Action from
   `counts install-action` when it changes often);
3. it is a **dated measurement** whose context is stated ("measured with four bots, Oct 2026").

Otherwise reword without the number ("a growing catalog of VSTs"). `counts lint` flags the rest: the README and root
Markdown files (not dated ones such as CHANGELOG), `assets/**/*.svg` and every local SVG the README displays, wherever
it lives; its output lists the linted files.

Counters (`glob`, `dirs`) count the files **tracked by git** (`git ls-files`; untracked files are ignored), and
`lines`/`json` fall back to `HEAD` when the file is not on disk. So the Action installed by `counts install-action`
checks out a blobless, shallow, sparse tree (`.showcase.json`, the script, the files holding markers, the files read
by `lines`/`json`) and stays cheap on a repository of several gigabytes; it needs `.showcase.json` to exist first, and
every file with markers must be listed in `files` (default: root `*.md`, `assets/**/*.svg`). Outside a git
repository the counters walk the filesystem. Patterns: `*` and `?` stay inside a folder, `**/` matches zero or more
folders, `[...]` is a class.

Display (`format` in `.showcase.json`, per counter): `round` (round down to a multiple), `suffix`, and `sep`, a
thousands separator applied last: `{"round": 10, "suffix": "+", "sep": ","}` shows 3358 as `3,350+`, `{"sep": ","}`
shows it as `3,358`.

## Mascot

- Use the image the user designated (link or path) and state its rights. Fan art of a brand gets a disclaimer line
  in the README footer.
- Inside an SVG, an external or relative image does not load: redraw the mascot in SVG (pixel art becomes `rect`
  elements) or embed it as a small data URI (size counts toward the limit).
- One mascot, one pose per visual, doing something that explains the project (routing tasks, reading files).

## Vocabulary that works

Terminal card (window, typed commands, real output, blinking cursor) for CLIs and profiles; hero with the mascot
acting the concept; flow diagram with dots moving along paths; card grid (icon, name, tagline) for skills or
features; catalog cards with synced counts; framed screenshots side by side (desktop and phone, `shoot --frame`);
before and after.

## Designer brief template

Pass these sections, filled, to the `designer` agent (one visual per brief, or a set with one message each):

1. Objective: the visual, its file path, its single message in one sentence.
2. Project facts: what it does, for whom, the chosen direction (from the proposals), real names, commands and
   outputs to show (never invented figures).
3. Style: palette and fonts (from `site-design` or the owner's `style_sources`), mascot file and rights if any.
4. Constraints: this file's GitHub constraints, Animation and Live numbers sections, named, not copied.
5. Deliverables: SVG at 1280 px wide, height, size target, alt text proposal.
6. Acceptance: `preview` renders at 880 and 390 px, light and dark, legible on mobile, no blocking SVG lint,
   `counts lint` clean.
7. Stop: if a fact needed for the visual is unknown, report instead of inventing it.
