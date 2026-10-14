#!/usr/bin/env bash
# Installs the base settings: agents, routing hook and global CLAUDE.md.
# Never merges settings.json: the fragment to copy into it is printed at the end.
# An existing, different file is backed up as .bak before being replaced (agents, hook).
# The global CLAUDE.md is only copied if it does not exist; otherwise it is dropped next to it as .claude-tools.new.
# Usage: kit/install_kit.sh        (CLAUDE_HOME to change ~/.claude)
set -euo pipefail
kit="$(cd "$(dirname "$0")" && pwd)"
home="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$home/agents" "$home/hooks"

put() {  # put <source> <destination>
  if [[ -f "$2" ]] && ! cmp -s "$1" "$2"; then
    cp "$2" "$2.bak"
    echo "backup: $2.bak"
  fi
  cp "$1" "$2"
  echo "installed: $2"
}

for f in "$kit"/agents/*.md; do put "$f" "$home/agents/$(basename "$f")"; done
put "$kit/hooks/subagent-gate.py" "$home/hooks/subagent-gate.py"

if [[ -f "$home/CLAUDE.md" ]]; then
  cp "$kit/CLAUDE.md" "$home/CLAUDE.md.claude-tools.new"
  echo "existing CLAUDE.md kept; base version written to: $home/CLAUDE.md.claude-tools.new"
else
  cp "$kit/CLAUDE.md" "$home/CLAUDE.md"
  echo "installed: $home/CLAUDE.md"
fi

echo
echo "To do by hand: copy the content of $kit/settings.snippet.json into $home/settings.json"
echo "(merge the \"hooks.PreToolUse\" and \"env\" keys with the existing ones, without overwriting your other hooks)."
