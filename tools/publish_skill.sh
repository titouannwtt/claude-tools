#!/usr/bin/env bash
# Publie un skill : contrôle des secrets et des noms personnels, commit, push, puis synchronise l'autre machine.
# Usage : tools/publish_skill.sh <nom-du-skill> ["message de commit"]
# Réglages locaux (local.env, jamais versionné) : PEER_SSH (arguments ssh de l'autre machine),
# PEER_PRE (commande à lancer avant, ex. charger l'agent SSH), PEER_REPO (dossier du dépôt chez l'autre).
set -euo pipefail

name="${1:-}"
message="${2:-feat(skill): $name}"
if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "usage : tools/publish_skill.sh <nom-du-skill> [message]" >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ ! -f "skills/$name/SKILL.md" ]]; then
  echo "skills/$name/SKILL.md introuvable" >&2
  exit 2
fi

git add -- "skills/$name"
if git diff --cached --quiet; then
  echo "rien de nouveau à commiter pour $name"
else
  if ! python3 tools/check_repo.py --staged; then
    echo "contrôle refusé : rien n'est commité" >&2
    git reset -q -- "skills/$name"
    exit 1
  fi
  git commit -q -m "$message"
fi

git pull -q --rebase
git push -q
echo "poussé : $(git log --oneline -1)"
./install.sh >/dev/null && echo "liens locaux à jour"

env_get() { { grep -E "^$1=" local.env 2>/dev/null || true; } | head -1 | cut -d= -f2-; }
peer_ssh="$(env_get PEER_SSH)"
if [[ -n "$peer_ssh" ]]; then
  pre="$(env_get PEER_PRE)"
  repo="$(env_get PEER_REPO)"
  repo="${repo:-claude-tools}"
  read -r -a ssh_args <<< "$peer_ssh"
  ssh "${ssh_args[@]}" "${pre:+$pre >/dev/null 2>&1; }cd \"$repo\" && git pull -q --ff-only && ./install.sh"
  echo "autre machine synchronisée"
else
  echo "PEER_SSH absent de local.env : lancer 'git pull && ./install.sh' sur l'autre machine"
fi
