# claude-tools

Configuration partagée de Claude Code : CLAUDE.md global, agents, hooks, skills.
Dépôt privé. Installation sur Mac et VPS via `install.sh` (à venir).

Règles :
- aucun nom, pseudo ou chemin personnel en dur ; la configuration locale vit dans `local.env` (ignoré par git) ;
- aucun secret commité ;
- Python par défaut pour les outils ; Rust seulement si le gain de performance est mesuré.

## Installation

`./install.sh` lie chaque skill dans `~/.claude/skills/` et installe le contrôle avant commit. Il est idempotent.

## Socle de réglages (dossier `kit/`)

Agents (Haiku, Sonnet, Opus avec leur effort), hook de routage `subagent-gate.py` (matrice modèle × effort, brief
minimal, validation de `Workflow`) et `CLAUDE.md` global générique. `kit/install_kit.sh` les installe dans
`~/.claude` : fichiers existants sauvegardés en `.bak`, `CLAUDE.md` existant jamais écrasé (la version du socle est
déposée en `.claude-tools.new`). `settings.json` n'est pas modifié : reporter à la main `kit/settings.snippet.json`.

## Réglages locaux

`local.env` (ignoré par git, droits 600) contient ce qui ne doit jamais être versionné :
`FORBIDDEN_TERMS` (termes à bloquer avant commit, séparés par des virgules), `PEER_SSH`, `PEER_PRE`, `PEER_REPO`
(synchronisation de l'autre machine), `IPROYAL_RESIDENTIAL_URL` (proxy de repli).

## Publier un skill

`tools/publish_skill.sh <nom>` : contrôle, commit, push, puis synchronisation de l'autre machine.
