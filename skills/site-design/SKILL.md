---
name: site-design
description: Analyze the design of an existing website (palette, typography, spacing, radii, shadows, CSS variables, breakpoints, screenshots at mobile, tablet and desktop widths) to draw inspiration from it, reproduce it or audit it. Use when the user gives a site URL and asks for its style, its colors, its fonts, to copy it in spirit, or to check its responsive rendering.
---

# site-design

A script loads the page in Chromium (Playwright), measures the computed styles of the visible elements, and writes
screenshots and a summary. Zero model tokens for the measurement; you then read `summary.md` and look at the screenshots.

## Commands

Script: `~/.claude/skills/site-design/scripts/site_design.py`. Output: JSON on stdout.

- `analyze "<url>" --out <folder>`: writes `shot-375.png`, `shot-768.png`, `shot-1280.png`, `design.json`, `summary.md`.
- `--widths 375,1440`: other widths (the largest is used for the measurements). `--dark`: captures and measures the largest
  width in dark mode (the measurements then describe the dark theme; run twice to compare).
- `doctor`: checks Playwright and Chromium.

## After the analysis

1. Read `summary.md` (short). Open the screenshots with Read to judge the overall impression: the measurements say
   what, the screenshots say whether it looks good.
2. Report in three blocks: identity (palette, fonts, tone), system (size scale, spacing, radii,
   shadows), responsive (horizontal scrolling, breakpoints). Cite the measured values.
3. To reproduce a style: draw inspiration from the system (scale, rhythm, contrasts), do not copy texts, logos, images
   or licensed fonts.
4. Limits: a background set only on `body` or `html` does not appear in the backgrounds; third-party stylesheets
   (other domain) deliver neither variables nor breakpoints; a site behind a login cannot be analyzed.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | Read `summary.md` and the screenshots. |
| 4 | Page blocked (403, 429) | Rerun **once** with `--use-proxy`; otherwise say so. |
| 5 | Playwright or Chromium missing | See Installation. |
| 7 | Page unreachable | Check the URL and the connection. |
| 2 | Invalid URL | Ask for an http(s) URL. |
| 1 | Unexpected error | Repair the script (see below). |

## Installation

Mac: `python3 -m venv ~/.venvs/site-design && ~/.venvs/site-design/bin/pip install playwright &&
~/.venvs/site-design/bin/playwright install chromium` (if a private pip index gets in the way, add
`--isolated --index-url https://pypi.org/simple`). The script switches to that environment by itself.
VPS: `pip install --user playwright && python3 -m playwright install --with-deps chromium`.

## Proxy

`--use-proxy`: residential proxy from `local.env` (key `IPROYAL_RESIDENTIAL_URL`), only after a block. Limited
budget: a page loads its images, so prefer a single pass. Never display the proxy value.

## Repair

Fix `<claude-tools>/skills/site-design/scripts/site_design.py`, then `python3 -m unittest discover -s tests`
in the skill's folder. Two attempts at most, then report the exact message to the user.
