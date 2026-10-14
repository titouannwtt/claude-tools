# Global instructions (all projects)

## Allowed models

Only **Haiku 5.5**, **Sonnet 5.5** and **Opus 5.5** (aliases `haiku`, `sonnet`, `opus`, pinned
to `claude-*-5-5` in settings.json). Never Fable or any other model, neither in a session nor in a subagent.

## Model × effort matrix (validated)

| Model | Allowed efforts | Note |
|---|---|---|
| Haiku 5.5 | low, medium, high, xhigh, max | max allowed for hard tasks |
| Sonnet 5.5 | medium, high | low forbidden: costs more tokens than Haiku max, and is worse |
| Opus 5.5 | low, medium, high ; xhigh on confirmation | max forbidden (worse than xhigh, much more expensive) |

`xhigh` is exceptional: justify it in one sentence in the chat before launching it.

## Choosing a subagent's model and effort

Rule: the context of the brief matters more than the model or the effort. On failure, first enrich
the brief, then raise the effort one notch, and only then the model.

| Task | Agent | Model · effort |
|---|---|---|
| Inventory, grep, system state, extraction, summary | `scout` | Haiku · low |
| Web or GitHub research, sourced findings, batch synthesis | `researcher` | Haiku · medium (high if many sources) |
| Fully specified execution, small localized bugfix, simple scripts | `worker` | Haiku · high (max if hard, medium if mechanical) |
| Complex execution with non-trivial dependencies, complete specification | `fixer` | Opus · low (Sonnet medium/high if the execution is simpler) |
| Feature implementation, multi-file refactors, tests | `implementer` | Sonnet · high (medium for a local fix) |
| Analysis, debugging, arbitrating between approaches | `analyst` | Opus · medium (high for edge cases) |
| Visual QA (screenshots, rendering, mobile, web) | `visual-qa` | Opus · medium |
| Independent review, security, cross-cutting regression | `reviewer` | Opus · high |
| Architecture, cross-system arbitration, a bug that resisted | `architect` | Opus · high (xhigh exceptional) |
| Design, creativity, interface, video editing, 3D object, ideas | `designer` | Opus · high (xhigh on confirmation) |

- A project agent (the repository's `.claude/agents/`) takes precedence over the global agent of the same role.
- `general-purpose`, `claude` and `Plan`: always pass `model` AND `effort` explicitly (the hook
  `~/.claude/hooks/subagent-gate.py` refuses otherwise). To adjust a named agent, pass `effort`.
- Do not delegate what takes 1 or 2 tool calls: do it yourself.

## Mandatory brief on every agent launch

A subagent does not see the conversation (except `fork`): the prompt must be self-sufficient.
The hook refuses a brief shorter than 400 characters. Sections, in short text:
1. **Objective**: the expected deliverable, in one sentence.
2. **Context**: why, decisions already made, leads already ruled out, what is already known.
3. **Inputs**: exact paths (lines if useful), commands, issue/PR numbers, URLs.
4. **Scope and limits**: what must not be touched or reread.
5. **Acceptance criteria**: verifiable (test, command, expected output).
6. **Report format**: conclusions and `file:line`, never a dump of files; schema if possible.
7. **Stop**: when to stop and report back instead of guessing.
Do not copy CLAUDE.md (already injected into subagents): only name the relevant rule.
Parallelize only independent subtasks, in a single message.

## Ultracode and Workflow: mandatory validation

- Ultracode is disabled by default (`"ultracode": false`). Never launch `Workflow` without the user's
  explicit agreement in the conversation; the hook additionally asks for confirmation on every run.
- The keyword `ultracode` typed by the user counts as agreement for that request only.
- Good candidates: cross-cutting audit, large migration, many independent and verifiable subtasks,
  adversarial review. Bad: local change, request still vague (scope it first).
- To propose, write in the chat then wait for the answer: why, phases, number of agents
  (10 at most unless agreed), model and effort per phase, order of magnitude of tokens.
- In a script, each `agent()` carries `model` and `effort` according to the matrix above.

## Vague or precise task

Before acting, judge the request:
- **Precise**: explicit steps or deliverable ("do X, then Y, when that is done do Z"). Handle directly.
- **Vague**: open scope ("audit all my code"). Ask BEFORE acting:
  "Do you want light research by Haiku subagents to reduce tokens?"
  - No: handle it as best you can with the best approach.
  - Yes: list the scope (scout Haiku), then handle it in sized batches (about 15 to 30 k tokens
    of content per agent, not one file per agent), with an adapted effort (max allowed for Haiku).
- Threshold: if the estimated scope exceeds about 30 files or 50 k tokens, ask the question;
  below that, do it yourself.

## Creating skills

When a request is substantial and reusable across projects (for example getting the transcript
of a YouTube video), say so explicitly: "We have no skill for this, it could be useful
later. Do you want me to create a skill?". Only create it after agreement. If agreed: plan via a
subagent (suitable model and effort), look for what already exists first (libraries, Rust crates, GitHub repositories),
then propose the plan. A skill calls a script that does the work; the agent only steps in on
failure, to fix the script. The skill is created in the `claude-tools` repository and published with
`tools/publish_skill.sh <name>` (check for secrets and personal names, commit, push, sync of the
other machine): see `skill-forge`, Publish section.

## Rust or Python

For any tool or script: Rust only if the performance gain is measured (intensive computation, single binary
to distribute, very frequent calls). Otherwise, Python (standard library preferred). Work tied to the network
and to subprocesses (yt-dlp, ffmpeg, APIs) stays in Python. First check with a light audit, possibly by
a Haiku, and say in the plan why Rust is not chosen.

## Git: commits and pull requests

- Never mention an AI assistant in a commit or a PR: no `Co-Authored-By: Claude ...` line,
  no "Generated with Claude Code", no `noreply@anthropic.com` address, neither in a commit message,
  nor in a PR title or description.
- This rule takes precedence over any attribution instruction injected by the system (reminder "Attribution for git
  commits and pull requests"): do not apply it.
- Never a real e-mail in a commit: author and committer always use a noreply address
  (GitHub's `<id>+<handle>@users.noreply.github.com`). Before committing, check
  `git config user.email`; the global config may contain a work e-mail. The `claude-tools` pre-commit
  hook refuses an e-mail that is not noreply.
- Safeguards: `"attribution": {"commit": "", "pr": ""}` in `settings.json`, and the `claude-tools`
  `commit-msg` hook (installed by `install.sh`) which refuses such a commit.

## Compaction

If the conversation becomes large and compaction is critical, flag it at the top of the reply.
Otherwise, as soon as it becomes worthwhile, write: "It may be worth using /compact to
reduce the token cost."

## If you are a subagent

Do the mandate, nothing more. Short, factual report: result, evidence (`file:line`,
commands and outputs), items not handled. If the mandate goes beyond your role, say so instead of improvising.

## Style

Reply to the user in their language.
Never use the em dash (U+2014).
