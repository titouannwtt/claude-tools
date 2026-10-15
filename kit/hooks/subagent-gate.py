#!/usr/bin/env python3
"""PreToolUse gate for the Agent and Workflow tools (see ~/.claude/CLAUDE.md).

Model x effort matrix (validated):
  haiku  : low, medium, high, xhigh, max  -> allow
  sonnet : medium, high                   -> allow ; low, xhigh, max -> deny
  opus   : low, medium, high              -> allow ; xhigh -> ask ; max -> deny

Agent: rejects a model other than haiku/sonnet/opus 5.5, applies the matrix, requires
model + effort for generic agents, rejects a brief shorter than 400 characters
(fork exempt).
Workflow (ultracode): rejects forbidden models or efforts, then asks for confirmation with a summary;
SUBAGENT_GATE_WORKFLOW=allow (settings.json "env") approves valid workflows without asking.
Set SUBAGENT_GATE_OFF=1 to bypass. Python 3.9 compatible.
"""
import json
import os
import re
import sys

MATRIX = {
    "haiku": {"low": "allow", "medium": "allow", "high": "allow", "xhigh": "allow", "max": "allow"},
    "sonnet": {"low": "deny", "medium": "allow", "high": "allow", "xhigh": "deny", "max": "deny"},
    "opus": {"low": "allow", "medium": "allow", "high": "allow", "xhigh": "ask", "max": "deny"},
}
ALLOWED_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
GENERIC_TYPES = {"", "general-purpose", "claude", "plan"}
MIN_BRIEF_CHARS = 400


def decide(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def norm(value):
    return str(value or "").strip().lower()


def family(model):
    """claude-sonnet-5-5 -> sonnet ; alias sonnet -> sonnet ; unknown -> ''."""
    for name in MATRIX:
        if model == name or model == "claude-%s-5-5" % name:
            return name
    return ""


def gate_agent(tool_input):
    agent_type = norm(tool_input.get("subagent_type"))
    if agent_type == "fork":
        return
    model = norm(tool_input.get("model"))
    effort = norm(tool_input.get("effort"))
    prompt = str(tool_input.get("prompt") or "")
    problems = []
    ask_reason = None

    if model and not family(model):
        problems.append("model \"%s\" not allowed (haiku, sonnet or opus 5.5 only)" % model)
    if effort and effort not in ALLOWED_EFFORTS:
        problems.append("unknown effort \"%s\" (low, medium, high, xhigh, max)" % effort)
    if model and effort and family(model) and effort in ALLOWED_EFFORTS:
        verdict = MATRIX[family(model)][effort]
        if verdict == "deny":
            problems.append("%s with effort \"%s\" is forbidden by the matrix in ~/.claude/CLAUDE.md"
                            % (family(model), effort))
        elif verdict == "ask":
            ask_reason = ("%s with effort \"%s\": exceptional, needs approval. Justify it in one sentence "
                          "in the chat before accepting." % (family(model), effort))
    if agent_type in GENERIC_TYPES:
        if not model:
            problems.append("generic agent \"%s\" without an explicit model" % (agent_type or "default"))
        if not effort:
            problems.append("generic agent \"%s\" without an explicit effort" % (agent_type or "default"))
    if len(prompt.strip()) < MIN_BRIEF_CHARS:
        problems.append("brief of %d characters (minimum %d): missing objective, context, "
                        "exact inputs, prohibitions, acceptance criteria, report format, "
                        "stop condition" % (len(prompt.strip()), MIN_BRIEF_CHARS))
    if problems:
        decide("deny", "subagent-gate: " + "; ".join(problems)
               + ". Pick model and effort from the table in ~/.claude/CLAUDE.md and retry.")
    if ask_reason:
        decide("ask", "subagent-gate: " + ask_reason)


def read_script(tool_input):
    script = str(tool_input.get("script") or "")
    path = tool_input.get("scriptPath")
    if not script and path:
        try:
            with open(os.path.expanduser(str(path)), encoding="utf-8") as handle:
                script = handle.read()
        except OSError:
            pass
    return script


def tally(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return ", ".join("%s x%d" % (k, v) for k, v in sorted(counts.items())) or "none explicit"


def call_pairs(script):
    """(model, effort) of each agent() call of a workflow script; '' when the call does not set it."""
    pairs = []
    for chunk in re.split(r"\bagent\s*\(", script)[1:]:
        model = re.search(r"\bmodel\s*:\s*['\"]([\w.-]+)['\"]", chunk)
        effort = re.search(r"\beffort\s*:\s*['\"](\w+)['\"]", chunk)
        pairs.append((model.group(1).lower() if model else "", effort.group(1).lower() if effort else ""))
    return pairs


def verdict_of(model, effort):
    """Matrix verdict for one agent() call, or '' if the pair is incomplete or unknown."""
    if family(model) and effort in ALLOWED_EFFORTS:
        return MATRIX[family(model)][effort]
    return ""


def gate_workflow(tool_input):
    script = read_script(tool_input)
    name = tool_input.get("name")
    if not name:
        match = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", script)
        name = match.group(1) if match else "unnamed"
    calls = len(re.findall(r"\bagent\s*\(", script))
    models = [m.lower() for m in re.findall(r"\bmodel\s*:\s*['\"]([\w.-]+)['\"]", script)]
    efforts = [e.lower() for e in re.findall(r"\beffort\s*:\s*['\"](\w+)['\"]", script)]
    bad = sorted({m for m in models if not family(m) and m != "inherit"})
    bad += sorted({"effort " + e for e in efforts if e not in ALLOWED_EFFORTS})
    pairs = call_pairs(script)
    bad += sorted({"%s %s" % (m, e) for m, e in pairs if verdict_of(m, e) == "deny"})
    if bad:
        decide("deny", "subagent-gate: workflow rejected, forbidden values: %s." % ", ".join(bad))
    summary = "workflow \"%s\"" % name
    if tool_input.get("resumeFromRunId"):
        summary += " (resume %s)" % tool_input.get("resumeFromRunId")
    if script:
        summary += "; %d agent() call(s) in the script; models: %s; efforts: %s" % (
            calls, tally(models), tally(efforts))
        if len(models) < calls:
            summary += "; warning, some agent() calls may have no explicit model (they inherit the session one)"
    explicit = bool(pairs) and all(m and e for m, e in pairs)
    confirm = [m + " " + e for m, e in pairs if verdict_of(m, e) == "ask"]
    if os.environ.get("SUBAGENT_GATE_WORKFLOW", "").strip().lower() == "allow":
        if explicit and not confirm:
            decide("allow", "subagent-gate: workflow approved (SUBAGENT_GATE_WORKFLOW=allow). " + summary + ".")
        summary += "; asked anyway: %s" % (", ".join(confirm) + " needs confirmation" if confirm else
                                           "every agent() call needs an explicit model and effort")
    decide("ask", "Ultracode / multi-agent Workflow: approval required. " + summary + ".")


def main():
    if os.environ.get("SUBAGENT_GATE_OFF") == "1":
        return
    try:
        data = json.loads(sys.stdin.read(), strict=False)
    except ValueError:
        return
    tool_input = data.get("tool_input") or {}
    tool = data.get("tool_name")
    if tool == "Agent":
        gate_agent(tool_input)
    elif tool == "Workflow":
        gate_workflow(tool_input)


if __name__ == "__main__":
    main()
