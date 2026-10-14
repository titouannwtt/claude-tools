---
name: youtube-download
description: Télécharger une vidéo, une piste audio ou la miniature d'une vidéo YouTube à partir de son URL, ou en lire les métadonnées (titre, durée, qualités disponibles). Utiliser quand l'utilisateur donne un lien YouTube et demande de le télécharger, d'extraire l'audio ou de récupérer la miniature. Pour la transcription, utiliser video-transcript.
---

# youtube-download

Un script s'appuie sur yt-dlp (vidéo, audio) et sur les images publiques de YouTube (miniature).
À réserver aux contenus que l'utilisateur a le droit de télécharger (les siens, licence libre, usage autorisé) :
si le doute est sérieux, le dire plutôt que d'exécuter.

## Commandes

Script : `~/.claude/skills/youtube-download/scripts/yt_download.py`. Sortie : JSON sur stdout.

- `info "<url>"` : titre, chaîne, durée, hauteurs disponibles. À lancer avant un téléchargement long.
- `thumbnail "<url>" --out <dossier>` : miniature la plus grande disponible (maxres, puis sd, hq, mq).
- `video "<url>" --height 1080 --out <dossier>` : mp4 à la hauteur maximale demandée.
- `audio "<url>" --format mp3 --out <dossier>` : piste audio (`mp3`, `m4a`, `opus`, `wav`).
- Toujours ajouter `--max-filesize 500M` (ou moins) sur `video` : sans lui, une vidéo longue en 4K pèse des Go.

Sans dossier `--out`, les fichiers vont dans `./yt-download`. Dire à l'utilisateur où est le fichier.

## Codes de sortie

| Code | Sens | Action |
|---|---|---|
| 0 | Succès | Donner le chemin du fichier. |
| 4 | Bloqué (429, 403, « not a bot ») | 1. Mettre yt-dlp à jour (`brew upgrade yt-dlp` ou `pip install -U yt-dlp`). 2. Relancer. 3. Si ça bloque encore, **une seule fois** avec `--use-proxy`, de préférence pour `thumbnail` ou `info` (léger). |
| 5 | Dépendance manquante | Installer yt-dlp (et ffmpeg pour le mp4 fusionné et l'audio). |
| 8 | Aucune miniature | Vidéo privée ou supprimée : le dire. |
| 2 | URL invalide | Demander l'URL correcte. |
| 1 | Erreur inattendue | Réparer le script (voir ci-dessous). |

## Proxy

`--use-proxy` utilise le proxy résidentiel de `local.env` (clé `IPROYAL_RESIDENTIAL_URL`). Budget limité (2 Go) :
éviter `video` par ce canal, ne l'utiliser qu'après un blocage réel, avec `--height` bas et `--max-filesize`.
Ne jamais afficher la valeur du proxy.

## Réparation

Corriger `~/dev/claude-tools/skills/youtube-download/scripts/yt_download.py`, puis lancer
`python3 -m unittest discover -s tests` dans le dossier du skill. Deux tentatives au plus, puis remonter le message exact.
