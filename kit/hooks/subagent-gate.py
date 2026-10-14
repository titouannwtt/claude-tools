#!/usr/bin/env python3
"""PreToolUse gate for the Agent and Workflow tools (see ~/.claude/CLAUDE.md).

Matrice modèle x effort (validée) :
  haiku  : low, medium, high, xhigh, max  -> allow
  sonnet : medium, high                   -> allow ; low, xhigh, max -> deny
  opus   : low, medium, high              -> allow ; xhigh -> ask ; max -> deny

Agent : refuse un modèle hors haiku/sonnet/opus 5.5, applique la matrice, exige
model + effort pour les agents génériques, refuse un brief de moins de 400 caractères
(fork exempté).
Workflow (ultracode) : demande toujours confirmation, avec un résumé des modèles et efforts.
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
    """claude-sonnet-5-5 -> sonnet ; alias sonnet -> sonnet ; inconnu -> ''."""
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
        problems.append("modèle « %s » interdit (haiku, sonnet ou opus 5.5 uniquement)" % model)
    if effort and effort not in ALLOWED_EFFORTS:
        problems.append("effort « %s » inconnu (low, medium, high, xhigh, max)" % effort)
    if model and effort and family(model) and effort in ALLOWED_EFFORTS:
        verdict = MATRIX[family(model)][effort]
        if verdict == "deny":
            problems.append("%s avec effort « %s » interdit par la matrice de ~/.claude/CLAUDE.md"
                            % (family(model), effort))
        elif verdict == "ask":
            ask_reason = ("%s en effort « %s » : exceptionnel, à valider. Justifie-le en une phrase "
                          "dans le chat avant d'accepter." % (family(model), effort))
    if agent_type in GENERIC_TYPES:
        if not model:
            problems.append("agent générique « %s » sans model explicite" % (agent_type or "défaut"))
        if not effort:
            problems.append("agent générique « %s » sans effort explicite" % (agent_type or "défaut"))
    if len(prompt.strip()) < MIN_BRIEF_CHARS:
        problems.append("brief de %d caractères (minimum %d) : il manque objectif, contexte, "
                        "entrées exactes, interdits, critères d'acceptation, format du rapport, "
                        "condition d'arrêt" % (len(prompt.strip()), MIN_BRIEF_CHARS))
    if problems:
        decide("deny", "subagent-gate : " + " ; ".join(problems)
               + ". Choisis modèle et effort selon le tableau de ~/.claude/CLAUDE.md et relance.")
    if ask_reason:
        decide("ask", "subagent-gate : " + ask_reason)


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
    return ", ".join("%s x%d" % (k, v) for k, v in sorted(counts.items())) or "aucun explicite"


def gate_workflow(tool_input):
    script = read_script(tool_input)
    name = tool_input.get("name")
    if not name:
        match = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", script)
        name = match.group(1) if match else "sans nom"
    calls = len(re.findall(r"\bagent\s*\(", script))
    models = [m.lower() for m in re.findall(r"\bmodel\s*:\s*['\"]([\w.-]+)['\"]", script)]
    efforts = [e.lower() for e in re.findall(r"\beffort\s*:\s*['\"](\w+)['\"]", script)]
    bad = sorted({m for m in models if not family(m) and m != "inherit"})
    bad += sorted({"effort " + e for e in efforts if e not in ALLOWED_EFFORTS})
    if bad:
        decide("deny", "subagent-gate : workflow refusé, valeurs interdites : %s." % ", ".join(bad))
    summary = "workflow « %s »" % name
    if tool_input.get("resumeFromRunId"):
        summary += " (reprise %s)" % tool_input.get("resumeFromRunId")
    if script:
        summary += " ; %d appel(s) agent() dans le script ; modèles : %s ; efforts : %s" % (
            calls, tally(models), tally(efforts))
        if len(models) < calls:
            summary += " ; attention, des agent() n'ont peut-être pas de model explicite (héritent de la session)"
    decide("ask", "Ultracode / Workflow multi-agents : validation requise. " + summary + ".")


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
