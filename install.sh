#!/usr/bin/env bash
# Installation idempotente : lie chaque skill du dépôt dans ~/.claude/skills et installe les contrôles git
# (pre-commit : secrets et données personnelles ; commit-msg : aucune mention d'assistant IA).
# Variable optionnelle : CLAUDE_HOME (défaut ~/.claude).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="${CLAUDE_HOME:-$HOME/.claude}/skills"
mkdir -p "$dest"

for dir in "$root"/skills/*/; do
  [[ -d "$dir" ]] || continue
  name="$(basename "$dir")"
  target="$dest/$name"
  if [[ -L "$target" ]]; then
    ln -sfn "${dir%/}" "$target"
    echo "lien mis à jour : $name"
  elif [[ -e "$target" ]]; then
    echo "ignoré (existe et n'est pas un lien) : $name" >&2
  else
    ln -s "${dir%/}" "$target"
    echo "lien créé : $name"
  fi
done

if [[ -d "$root/.git" ]]; then
  hook="$root/.git/hooks/pre-commit"
  if [[ ! -e "$hook" ]] || grep -q "claude-tools check_repo" "$hook"; then
    printf '%s\n' '#!/bin/sh' '# claude-tools check_repo' \
      'exec python3 "$(git rev-parse --show-toplevel)/tools/check_repo.py" --staged' > "$hook"
    chmod +x "$hook"
    echo "contrôle avant commit installé"
  else
    echo "hook pre-commit existant conservé (non géré par ce dépôt)" >&2
  fi
  hook="$root/.git/hooks/commit-msg"
  if [[ ! -e "$hook" ]] || grep -q "claude-tools check_repo" "$hook"; then
    printf '%s\n' '#!/bin/sh' '# claude-tools check_repo' \
      'exec python3 "$(git rev-parse --show-toplevel)/tools/check_repo.py" --commit-msg "$1"' > "$hook"
    chmod +x "$hook"
    echo "contrôle du message de commit installé (aucune mention d'assistant IA)"
  else
    echo "hook commit-msg existant conservé (non géré par ce dépôt)" >&2
  fi
fi
