#!/usr/bin/env bash
# Idempotent install: links each skill of the repo into ~/.claude/skills and installs the git checks
# (pre-commit: secrets and personal data; commit-msg: no mention of an AI assistant).
# Optional variable: CLAUDE_HOME (default ~/.claude).
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
    echo "link updated: $name"
  elif [[ -e "$target" ]]; then
    echo "skipped (exists and is not a link): $name" >&2
  else
    ln -s "${dir%/}" "$target"
    echo "link created: $name"
  fi
done

if [[ -d "$root/.git" ]]; then
  hook="$root/.git/hooks/pre-commit"
  if [[ ! -e "$hook" ]] || grep -q "claude-tools check_repo" "$hook"; then
    printf '%s\n' '#!/bin/sh' '# claude-tools check_repo' \
      'exec python3 "$(git rev-parse --show-toplevel)/tools/check_repo.py" --staged' > "$hook"
    chmod +x "$hook"
    echo "pre-commit check installed"
  else
    echo "existing pre-commit hook kept (not managed by this repo)" >&2
  fi
  hook="$root/.git/hooks/commit-msg"
  if [[ ! -e "$hook" ]] || grep -q "claude-tools check_repo" "$hook"; then
    printf '%s\n' '#!/bin/sh' '# claude-tools check_repo' \
      'exec python3 "$(git rev-parse --show-toplevel)/tools/check_repo.py" --commit-msg "$1"' > "$hook"
    chmod +x "$hook"
    echo "commit message check installed (no mention of an AI assistant)"
  else
    echo "existing commit-msg hook kept (not managed by this repo)" >&2
  fi
fi
