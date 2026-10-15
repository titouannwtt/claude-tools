---
name: repo-showcase
description: Turn a basic GitHub repository into a publish-ready showcase. Interviews the user (purpose, audience, goal, length, mascot, links), audits secrets and personal data in the files and the whole git history, removes AI co-authorship mentions, audits the file structure, then builds a short, very visual README (custom animated SVG banner, screenshots, live counters) and checks the GitHub rendering before pushing. Use when the user wants a repository to look professional, to highlight their profile, to prepare it for going public, or to check it holds no personal data.
---

# repo-showcase

Goal: a visitor understands the project in five seconds, from the visuals alone, and nothing private leaks.
Short and visual beats long: if it is long nobody reads it; if it is short and visual, people at least look at the
images, and if the images are clear the project is understood at a glance.

Script: `S=~/.claude/skills/repo-showcase/scripts/showcase.py` (`python3 $S <command>`, JSON on stdout).
Run `python3 $S doctor` once per machine: it says what is possible (history rewrite, screenshots, faces, demo).

## Hard rules

- Never change a repository's visibility. For a private repository, the last message says: going public is the
  user's last step (`ready` prints the command for them).
- Never print or store a raw secret: talk about findings with their preview and fingerprint only.
- Normal push and `gh repo edit` (description, topics, homepage) only after the user validated the preview.
- History rewrite and force push: only after an explicit yes, asked separately each time. Never delete or move a
  file without agreement.
- Remove every AI co-authorship mention (commits, files, pull requests, releases). A project that is *about* AI
  keeps its product mentions.
- Commits: `git config user.email` must be a noreply address; no AI attribution in messages.
- No hard-coded number that changes often in a visual or the README, unless it is live (badge), synced
  (`counts`), or a dated measurement.

## Workflow

1. **Facts** (no questions yet): `inventory <repo>` and `structure <repo>`. If the user gave only a URL,
   `gh repo clone` it into a work folder first. Read `hints`, `project_type`, `run_hints`, `style_sources`.
2. **Safety first**: `security <repo>` (files + full history) and `attribution <repo>`. Report by severity and
   category, then ask how to handle each category with AskUserQuestion, using the options of
   [references/security-remediation.md](references/security-remediation.md). Fix the working tree first.
   History: `fix-plan` (fetches the remote and refuses if it holds work the local refs lack; dry run on a
   temporary mirror, must report `remaining: 0`), show the summary, ask, then `fix-apply --confirm` (bundle and
   git directory archive first), ask again, then run the printed `--force-with-lease` push (existing remote refs only).
   A secret that was ever pushed is rotated, rewrite or not. False positive: `allow <repo> <fingerprint>`.
   Pull requests and releases: `fix-prs <repo>` (dry run), then `--confirm`.
3. **Interview**: [references/interview.md](references/interview.md). Two batches of at most four questions,
   pre-filled from the inventory; never ask what the facts already answer. Mascot chosen: ask for the image
   (link or path) and its rights.
4. **Proposals**: two or three README directions from [references/readme-patterns.md](references/readme-patterns.md),
   each with what it highlights, for whom, its length and its visuals; recommend one. The user picks.
5. **Build**:
   - Visuals are custom for each repository: brief the `designer` agent with the template and constraints of
     [references/visuals.md](references/visuals.md) (one message per visual, palette from the product site via
     `site-design` or from the owner's `style_sources`).
   - Screenshots: `shoot <url> --out assets/screenshots` (live site, or `--serve "<run hint>"` for a local app);
     `demo` for a short GIF when interaction is the point. Check every capture for personal data.
   - README: follow the chosen pattern; counters through markers and `counts sync`; `counts lint` must pass.
     Offer `counts install-action` when a count changes often (it counts tracked files, so it also suits very large
     repositories).
   - Structure: present the `structure` findings as suggestions (see
     [references/structure.md](references/structure.md)); apply only the accepted ones, with `git mv`.
6. **Verify**: `preview <repo>` (static checks + renders at 880 and 390 px, light and dark). Open
   `readme-fold-*.png` and the mobile render with Read. For a flagship repository, add a `visual-qa` agent.
7. **Publish**: show the user the fold render and the list of changes; after validation commit, push, set the
   description, topics and homepage with `gh repo edit`. Then `ready <repo>` must exit 0. Offer
   `social <repo> --source assets/<banner>.svg` (uploaded by hand in Settings) and pinning on the profile.
   Private repository: end with the `final_step` sentence.

## Commands

| Command | Use |
|---|---|
| `doctor` | dependencies and `ready_for` |
| `inventory <repo>` / `structure <repo>` | facts, layout audit |
| `security <repo>` / `attribution <repo>` | findings; full redacted report in `.git/repo-showcase/` |
| `allow <repo> <fp>...` | accept false positives |
| `fix-plan` / `fix-apply --confirm [--push]` / `fix-prs [--confirm]` | history and remote cleanup |
| `counts sync\|lint\|badge\|install-action <repo>` | live numbers |
| `shoot`, `demo`, `preview`, `social` | captures and rendering |
| `ready <repo>` | final gate, prints `final_step` |

Run `python3 $S <command> -h` for the options.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | OK | Continue. |
| 4 | Findings or failed checks | Handle them with the user, rerun. |
| 5 | Dependency missing | `doctor` gives the install command; continue without that step if optional. |
| 6 | Safety refusal | Read `error` (dirty tree, `--confirm` missing, git < 2.36, refs changed). |
| 7 | GitHub or network | Check `gh auth status` and the URL. |
| 3 / 2 | Not a repository / bad arguments | Fix the call. |
| 1 | Unexpected error | Repair the script (below). |

## Repair

Fix the module in `<claude-tools>/skills/repo-showcase/scripts/`, then
`python3 -m unittest discover -s tests -q` in the skill's folder. Two attempts at most, then report the exact
message to the user.
