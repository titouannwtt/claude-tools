---
name: skill-forge
description: Decide whether to create a skill for a reusable request (tool, script, download, transcription, analysis), then design it, research it and build it after agreement. Use when a request is substantial and reusable across projects, or when the user asks to create or improve a skill.
---

# skill-forge

Objective: accumulate reusable skills, one by one, without creating any wrongly. A skill is not justified for a one-off
task; it is for a capability that will be useful in other projects.

## 1. Check what exists

List `~/.claude/skills/` and `skills/` of the `claude-tools` repository. If a skill covers the request, use it and stop there.

## 2. Propose, do not create

If nothing covers the request, write:
"We have no skill for this. It looks useful for later. Do you want me to create it?"
Wait for the answer. Without agreement, create nothing.

## 3. Plan (after agreement)

Present a short plan, to be validated before any implementation:
- **Name** (kebab-case, generic, no personal name or hard-coded path).
- **Scope**: what the skill does, and what it does not do.
- **Inputs and outputs**: arguments, output format (text, JSON).
- **Script**: language, justification (see section 4), planned tests.
- **Research**: sources to explore (GitHub repositories, crates.io, PyPI, official documentation).
- **Configuration**: local values (paths, identifiers) in `local.env`, ignored by git.

## 4. Choose the language

Rust feasibility checklist, to fill in before writing the script:
1. Is the work compute-bound (heavy loops, parsing large volumes)? Yes/no.
2. Does a single dependency-free binary need to be distributed? Yes/no.
3. Will the script be called very often (dozens of times a day)? Yes/no.

- At least one "yes" and a measured or estimated gain: Rust.
- Otherwise, or if the work is tied to the network and to subprocesses (yt-dlp, ffmpeg, APIs): Python (standard library
  preferred). Say in the plan why Rust is not chosen.
- Rule validated by the user: Rust only if the gain is measured, Python otherwise.

## 5. Research (subagent)

Launch a `researcher` (Haiku 5.5, medium ; high if many sources) with a complete brief: question, sources,
criteria (license, maintenance, installation, limits), report format as a table with URL and date accessed.
Recommend nothing without this table.

## 6. Build

- Short `SKILL.md`: when to use it, which command to run, what to do on error.
- The script does the work (deterministic, JSON output, exit codes, a `doctor` subcommand that checks the dependencies).
- Unit tests in `tests/` (run with `python3 -m unittest`).
- Repair: if the script fails, the agent reads the error, fixes the script, reruns. Two attempts at most,
  then it reports back to the user. The script must never ask a model to do the work in its place.

## 7. Publish

The skill is created in `skills/<name>/` of the `claude-tools` repository (its local clone; `readlink ~/.claude/skills/skill-forge` gives the location).
Once the tests are green, run from the repository root:

`tools/publish_skill.sh <name> ["commit message"]`

Before publishing, add the skill to the repository's showcase (in English): one row in the "Skills" table of
`README.md` (name linked to `skills/<name>`, role, dependencies, claude.ai compatibility) and a card in
`assets/skills.svg` (icon, name, tagline; enlarge the grid if it is full). The banner and README counters are
updated by the script (`tools/sync_counts.py`), which also flags a skill missing from the showcase.

The script chains the following, with no other intervention:
0. counter update (`tools/sync_counts.py`);
1. check for secrets, e-mails, IPs, personal paths and the forbidden terms of `local.env`
   (`tools/check_repo.py --staged`); on a finding, nothing is committed, fix then rerun;
2. commit and push to `main`;
3. `git pull` and `./install.sh` on the other machine (`PEER_SSH` setting of `local.env`), which creates the link in
   `~/.claude/skills/`. Without `PEER_SSH`, it prints the command to run by hand.

Never bypass the check (`--no-verify`) nor commit a `local.env` file.

## Safeguards

- No personal name, handle or personal path in a versioned file. Local values go in `local.env`.
- No committed secret. Proxy or API credentials stay in `local.env`.
