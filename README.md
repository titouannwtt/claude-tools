# claude-tools

Configuration partagée de Claude Code : CLAUDE.md global, agents, hooks, skills.
Dépôt privé. Installation sur Mac et VPS via `install.sh`.

Règles :
- aucun nom, pseudo ou chemin personnel en dur ; la configuration locale vit dans `local.env` (ignoré par git) ;
- aucun secret commité ;
- Python par défaut pour les outils ; Rust seulement si le gain de performance est mesuré.

## Skills

| Skill | Rôle | Dépendances |
|---|---|---|
| `light-research` | découpage d'un grand périmètre en lots pour sous-agents Haiku | aucune |
| `skill-forge` | création et publication d'un nouveau skill | aucune |
| `video-transcript` | transcription d'une vidéo YouTube (sous-titres, sinon audio + Whisper local) | yt-dlp, ffmpeg, faster-whisper |
| `youtube-download` | vidéo, audio, miniature et métadonnées YouTube | yt-dlp, ffmpeg |
| `web-fetch` | page web avec repli sur proxy résidentiel si l'accès est bloqué | aucune |
| `site-design` | palette, typographie, espacements et captures responsives d'un site | playwright, Chromium |
| `mac-control` | pilotage du Mac via cua-driver, avec garde-fous pour les démarches | cua-driver (Mac) |
| `geo-seo` | référencement d'un site pour Google et les assistants IA | voir le skill |

Chaque skill appelle un script testé (`python3 -m unittest discover -s tests` dans son dossier) ; `lib/` contient les
fonctions communes (lecture de `local.env`, proxy).

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
