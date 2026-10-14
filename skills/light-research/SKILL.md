---
name: light-research
description: Light research over a large scope (auditing a whole repository, rereading many documents) at reduced token cost, by splitting the work into batches read by Haiku subagents. Use when a request is vague ("audit all the code", "read all the documents") and the scope exceeds about 30 files or 50,000 estimated tokens.
---

# light-research

Objective: reduce the token cost of a vague task over a large scope. The splitting is done
by a deterministic script (zero model tokens). Haiku subagents read the batches. Opus writes the synthesis,
on the findings only, never on the sources.

## Procedure

1. **Judge the prompt.** Precise (explicit steps and deliverable): do not use this skill. Vague (open scope):
   continue.
2. **Ask before acting.** Write: "Do you want light research by Haiku subagents to reduce tokens?"
   - No: handle the request as best you can, without batches.
   - Yes: continue.
3. **Measure the scope.** Run
   `python3 ~/.claude/skills/light-research/scripts/plan_batches.py <folder> --budget 25000`.
   The JSON gives the number of files, the estimated tokens and the batches. If the scope is under 30 files and 50,000 tokens,
   do it yourself: do not launch subagents.
4. **Specify the question.** One sentence: what you are looking for in each batch (bugs, debt, inconsistencies, security...).
   Without a precise question, the findings will be vague.
5. **Launch the batches.** One `researcher` subagent (Haiku 5.5, medium) per batch, all in **a single message**
   (at most 10 at a time). Each brief contains: objective, exact list of the batch's files, question, output file
   (`<scratchpad>/lot-<id>.json`), output schema, stop condition. See the template below.
6. **Synthesize.** One `analyst` subagent (Opus 5.5, medium) reads only the findings files, deduplicates them,
   ranks them by severity and returns the report. It rereads the sources only to confirm a doubtful finding, backed by `file:line`.
7. **Deliver the result**: report, number of batches, estimated tokens, failed batches.

## Per-batch brief template

```
Objective: read the files of batch <id> and answer: <question>.
Context: <one sentence about the project and what is already known>.
Inputs: files (exact paths): <list>. Read nothing else.
Scope and limits: no modification; do not reread files outside the batch.
Acceptance criteria: each finding cites file:line and evidence (excerpt of 1 to 3 lines).
Format: write a JSON to <output path>: [{"file": "...", "line": n, "severity": "blocking|major|minor", "finding": "...", "evidence": "..."}] ; empty list if nothing.
Stop: if a file is unreadable or binary, note it in the JSON and move on to the next one.
```

## Safeguards

- Never launch the batches in series: parallelism (one message, several calls) is what saves time.
- A failed batch does not stop the others: flag it in the final report.
- The script ignores dependency folders and binaries, but not secrets: never include `.env`
  or `*credentials*` in a scope, check the list before launching.
