# Repository structure reference

Used with the `structure` command: its `layout.reference` field points to a section of this file. Layouts are
targets to reason with, not templates to impose. Keep what the project already does consistently; propose a change
only when it removes real friction for a first-time reader.

## How to present suggestions

- Every finding is a suggestion. Never delete, move or rename without the user's agreement, one finding at a time or
  as a short list they approve.
- Moves use `git mv` so the history follows the file. Untracking uses `git rm --cached` (the file stays on disk) and
  is paired with a `.gitignore` line.
- Order: quick wins (junk, `.gitignore`), then naming and Markdown, then folder moves (they change links and CI
  paths: update the README links and run the tests afterwards).
- Pushed files stay in the history: a secret or a huge file also needs the history rewrite step, not only a deletion.

## What belongs at the root

- Always: `README.md`, `LICENSE`, `.gitignore`. Optional by audience: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.
- Manifests and tool configs that tools expect there: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`,
  `Dockerfile`, `Makefile`, lockfiles, `tsconfig.json`, `*.config.js`.
- Folders by purpose: `src/` (code), `tests/`, `docs/` (long material), `scripts/` (maintenance), `examples/`,
  `assets/` (README images and SVG), `data/`. Dot folders (`.github/`) are not counted as clutter.
- At most about 12 visible entries: notes, drafts, exports, screenshots and one-off scripts go in a folder or out.

## Reference layouts

### web-app

```
src/            components, pages, styles
public/         static files served as is
tests/          unit and end-to-end tests
assets/         README banner and screenshots, apart from public/ (that one ships with the app)
package.json  vite.config.* | next.config.*  README.md  LICENSE  .gitignore
```

### website

```
content/ | src/pages/    pages and posts
static/ | public/        images, fonts
layouts/                 templates
assets/                  README visuals
astro.config.* | hugo.toml | _config.yml | .eleventy.js
(never commit the generated site: public/, _site/, dist/)
```

### mobile-app

```
src/ | app/ | lib/      code (React Native, Expo, Flutter)
android/  ios/          native projects, only if ejected or native
docs/store/             store screenshots and descriptions
app.json | pubspec.yaml
```

### cli

```
src/<package>/   code, one module per command
tests/
docs/ | examples/   long usage, sample inputs and outputs
assets/          terminal recording (GIF or SVG) for the README
pyproject.toml | Cargo.toml | package.json ("bin") | go.mod + cmd/<name>/main.go
```

### library

```
src/<package>/   public API at the top, internals in _private modules
tests/
docs/ | examples/
CHANGELOG.md     readers upgrade by reading it
```

### backend

```
app/ | src/      routes, services, models, one folder per domain
migrations/      database migrations
tests/
docs/            API description (OpenAPI)
Dockerfile  docker-compose.yml  .env.example (fake values; never .env)
```

### ml

```
notebooks/       numbered, outputs cleared (they bloat diffs and can leak paths)
src/             reusable code
data/            tiny samples only; large data is downloaded, with a script
models/          never weights in git: link to a release or a model hub
reports/figures/ images used in the README
requirements.txt | environment.yml
```

### game

```
Assets/ | scenes/ | src/    content and code (the engine layout wins)
assets/                      README screenshots and a gameplay GIF
project.godot | ProjectSettings/     (binary art: Git LFS or kept out)
```

### catalog

```
<category>/<entry>.md    one file per item, same front matter
data/                    machine-readable index (JSON, CSV)
scripts/                 builds the index and the README tables
README.md                table or list; entry counts come from markers and `counts sync`, never typed
```

### profile

A repository named like the owner: only `README.md` is displayed on the profile. Keep it to `README.md`, `assets/`
(banner, cards) and optionally a workflow that regenerates dynamic cards. No code, no docs, no config noise.

### docs

```
docs/ | content/   Markdown, one topic per file; docs/assets/ for images
mkdocs.yml | book.toml | docusaurus.config.js
```

### config

Dotfiles repositories: one folder per tool (`zsh/`, `git/`, `nvim/`), an `install.sh` that links them, a README that
says what is where and how to restore on a new machine. No secrets, no machine-specific paths: use templates.

## Community health files

| File | Add when | Where GitHub looks |
|---|---|---|
| `CONTRIBUTING.md` | you want outside contributions | `.github/`, then root, then `docs/` |
| `SECURITY.md` | people may report vulnerabilities | same |
| `CODE_OF_CONDUCT.md` | a community forms around the project | same |
| `SUPPORT.md` | users need to know where to ask | same |
| `FUNDING.yml` | you accept sponsorship | `.github/` only |
| issue and pull request templates | you receive many reports | `.github/` |

Precedence is `.github/` first, then the root, then `docs/`. A personal showcase repository usually needs none of
these: ask the audience question before adding any.

## Naming conventions

- One style per level, lowercase `kebab-case` or `snake_case` (`snake_case` for Python, `kebab-case` for web and
  shell). Conventional exceptions: `README.md`, `LICENSE`, `Dockerfile`.
- No spaces, accents or parentheses. No `final`, `new`, `old`, `copy`, `backup`, `tmp`, `v2`, `untitled`: Git is the
  version history. Names say the content: `dashboard-dark.png`, not a default screenshot name.

## .gitignore essentials

- Always: `.DS_Store`, `Thumbs.db`, `.env`, `.env.*` with `!.env.example`, `*.log`, `.idea/`, editor swap files.
- Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.pytest_cache/`, `.mypy_cache/`, `dist/`, `*.egg-info/`.
- Node: `node_modules/`, `dist/`, `build/`, `.next/`, `.nuxt/`, `coverage/`.
- Rust and Java: `target/`. Unity and Godot: the engine template. Share `.vscode/settings.json` only if it helps
  every contributor.

## Comment density

- Healthy range is roughly 5 % to 40 % of source lines. Below: public functions and modules lack explanation. Above:
  often narration or commented-out code.
- Docstrings for the public API (what it does, arguments, errors); comments explain why (a constraint, a trade-off,
  a workaround), never what the next line does. Delete commented-out code: Git keeps it.

## Markdown organization

- The README is short and visual; long material moves to `docs/` and is linked from the README.
- Other notes (`IDEAS.md`, `TODO.md`, `NOTES.md`) belong in `docs/` or in issues; placeholder `.md` files are
  removed or written.
- Monorepos: one README per package describing that package, and a root README that is only the map.
- `CHANGELOG.md` follows "Keep a Changelog": newest first, one section per release, user-facing wording.
