#!/usr/bin/env bash
# Installe le socle de réglages : agents, hook de routage et CLAUDE.md global.
# Ne fusionne jamais settings.json : le fragment à y reporter est affiché à la fin.
# Un fichier existant et différent est sauvegardé en .bak avant d'être remplacé (agents, hook).
# Le CLAUDE.md global n'est copié que s'il n'existe pas ; sinon il est déposé à côté en .claude-tools.new.
# Usage : kit/install_kit.sh        (CLAUDE_HOME pour changer ~/.claude)
set -euo pipefail
kit="$(cd "$(dirname "$0")" && pwd)"
home="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$home/agents" "$home/hooks"

put() {  # put <source> <destination>
  if [[ -f "$2" ]] && ! cmp -s "$1" "$2"; then
    cp "$2" "$2.bak"
    echo "sauvegarde : $2.bak"
  fi
  cp "$1" "$2"
  echo "installé : $2"
}

for f in "$kit"/agents/*.md; do put "$f" "$home/agents/$(basename "$f")"; done
put "$kit/hooks/subagent-gate.py" "$home/hooks/subagent-gate.py"

if [[ -f "$home/CLAUDE.md" ]]; then
  cp "$kit/CLAUDE.md" "$home/CLAUDE.md.claude-tools.new"
  echo "CLAUDE.md existant conservé ; version du socle déposée : $home/CLAUDE.md.claude-tools.new"
else
  cp "$kit/CLAUDE.md" "$home/CLAUDE.md"
  echo "installé : $home/CLAUDE.md"
fi

echo
echo "À faire à la main : reporter dans $home/settings.json le contenu de $kit/settings.snippet.json"
echo "(fusionner les clés « hooks.PreToolUse » et « env » avec l'existant, sans écraser vos autres hooks)."
