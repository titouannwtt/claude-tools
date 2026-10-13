# claude-tools

Configuration partagée de Claude Code : CLAUDE.md global, agents, hooks, skills.
Dépôt privé. Installation sur Mac et VPS via `install.sh` (à venir).

Règles :
- aucun nom, pseudo ou chemin personnel en dur ; la configuration locale vit dans `local.env` (ignoré par git) ;
- aucun secret commité ;
- Rust par défaut pour les outils, si le gain de performance le justifie.

## Installation

`./install.sh` lie chaque skill dans `~/.claude/skills/` et installe le contrôle avant commit. Il est idempotent.

## Réglages locaux

`local.env` (ignoré par git, droits 600) contient ce qui ne doit jamais être versionné :
`FORBIDDEN_TERMS` (termes à bloquer avant commit, séparés par des virgules), `PEER_SSH`, `PEER_PRE`, `PEER_REPO`
(synchronisation de l'autre machine), `IPROYAL_RESIDENTIAL_URL` (proxy de repli).

## Publier un skill

`tools/publish_skill.sh <nom>` : contrôle, commit, push, puis synchronisation de l'autre machine.
