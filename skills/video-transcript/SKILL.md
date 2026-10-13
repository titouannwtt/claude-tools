---
name: video-transcript
description: Obtenir la transcription d'une vidéo YouTube à partir de son URL, pour la lire, la résumer ou l'intégrer à un projet. Utiliser quand l'utilisateur donne un lien YouTube et demande ce qui y est dit, sa transcription, ses sous-titres, ou une analyse de son contenu.
---

# video-transcript

Objectif : transformer une vidéo YouTube en texte horodaté, puis la comprendre à partir de ce texte.
Le script fait tout le travail (zéro token de modèle). Ton rôle : lancer, lire le résultat, réparer le script si besoin.

## Commandes

Script : `~/.claude/skills/video-transcript/scripts/transcript.py`. Il écrit toujours du JSON sur stdout.

1. **Voie A, sous-titres existants (à essayer en premier, rapide et sans téléchargement vidéo)** :
   `python3 <script> subs "<url>" --lang fr,en --out <dossier>`
2. **Voie B, audio puis transcription locale (si la voie A n'a rien trouvé)** :
   `python3 <script> audio "<url>" --lang fr --model small --out <dossier>`
3. **Fichier audio déjà présent** : `python3 <script> transcribe <fichier> --out <dossier>`
4. **Vérifier les dépendances** : `python3 <script> doctor`

## Codes de sortie et réaction

| Code | Sens | Action |
|---|---|---|
| 0 | Succès | Lire le `.txt` (lignes `[hh:mm:ss] texte`) ou le `.json` (segments). |
| 3 | Aucun sous-titre | Lancer la voie B (`audio`). |
| 4 | Téléchargement bloqué (429, 403, « not a bot », IP bloquée) | Relancer **une seule fois** avec `--use-proxy`. Ne jamais utiliser le proxy sans ce blocage. |
| 5 | Dépendance manquante | Installer ce qui est indiqué dans le message (`pip install -U yt-dlp`, `pip install faster-whisper`, ffmpeg). |
| 2 | URL ou fichier invalide | Demander l'URL correcte. |
| 1 | Erreur inattendue | Lire le message, corriger le script, relancer (voir Réparation). |

## Réparation

Si le script échoue sans code attendu (1), ou si une sortie est incohérente :
1. Lire le message d'erreur complet.
2. Corriger le script dans `~/dev/claude-tools/skills/video-transcript/scripts/transcript.py` (le lien symbolique pointe dessus), et lancer `python3 -m unittest discover -s tests` dans le dossier du skill.
3. Relancer la commande. Deux tentatives au plus, puis remonter le problème à l'utilisateur avec le message exact.

## Proxy (repli)

- Le proxy IPRoyal n'est utilisé qu'avec `--use-proxy`, et seulement après un blocage (code 4).
- Son adresse vient de `local.env` à la racine de `claude-tools` (clé `IPROYAL_PROXY_URL`, ignoré par git).
- Ne jamais afficher la valeur du proxy, ni dans le chat, ni dans un fichier versionné.

## Après la transcription

Lire le `.txt`, puis répondre à la question de l'utilisateur à partir du texte, en citant les horodatages utiles
(`[00:12:40]`). Si la vidéo est longue, résumer par tranches plutôt que de tout recopier.
