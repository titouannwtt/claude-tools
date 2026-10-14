#!/usr/bin/env bash
# Publishes a skill: checks for secrets and personal names, commit, push, then syncs the other machine.
# Usage: tools/publish_skill.sh <skill-name> ["commit message"]
# Local settings (local.env, never versioned): PEER_SSH (ssh arguments of the other machine),
# PEER_PRE (command to run first, e.g. load the SSH agent), PEER_REPO (repo folder on the other machine).
set -euo pipefail

name="${1:-}"
message="${2:-feat(skill): $name}"
if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "usage: tools/publish_skill.sh <skill-name> [message]" >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ ! -f "skills/$name/SKILL.md" ]]; then
  echo "skills/$name/SKILL.md not found" >&2
  exit 2
fi

git add -- "skills/$name"
if [[ -f tools/sync_counts.py ]]; then  # README and banner counters
  python3 tools/sync_counts.py
  git add -- README.md assets/hero.svg 2>/dev/null || true
fi
if git diff --cached --quiet; then
  echo "nothing new to commit for $name"
else
  if ! python3 tools/check_repo.py --staged; then
    echo "check rejected: nothing committed" >&2
    git reset -q -- "skills/$name"
    exit 1
  fi
  git commit -q -m "$message"
fi

git pull -q --rebase
git push -q
echo "pushed: $(git log --oneline -1)"
./install.sh >/dev/null && echo "local links up to date"

env_get() { { grep -E "^$1=" local.env 2>/dev/null || true; } | head -1 | cut -d= -f2-; }
peer_ssh="$(env_get PEER_SSH)"
if [[ -n "$peer_ssh" ]]; then
  pre="$(env_get PEER_PRE)"
  repo="$(env_get PEER_REPO)"
  repo="${repo:-claude-tools}"
  read -r -a ssh_args <<< "$peer_ssh"
  ssh "${ssh_args[@]}" "${pre:+$pre >/dev/null 2>&1; }cd \"$repo\" && git pull -q --ff-only && ./install.sh"
  echo "other machine synced"
else
  echo "PEER_SSH missing from local.env: run 'git pull && ./install.sh' on the other machine"
fi
