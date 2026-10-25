---
name: media-download
description: Download the video, or only the audio as MP3, from YouTube (videos, Shorts), Instagram (posts, Reels), TikTok and ina.fr links, or read their metadata and the YouTube thumbnail. Use when the user gives a YouTube, Shorts, Instagram, Reel, TikTok or INA link, or a list of links, and asks to download, extract the audio, keep an MP3 or build an audio bank. For the transcript, use video-transcript.
---

# media-download

A script relies on yt-dlp (download) and ffmpeg (MP3 conversion, mp4 merge). It handles a list of links in one call.
Reserve it for content the user has the right to download (their own, free license, authorized use):
if the doubt is serious, say so rather than executing.

## Commands

Script: `~/.claude/skills/media-download/scripts/media_download.py`. The last stdout line is JSON.

- `doctor`: checks yt-dlp, ffmpeg and the YouTube, Instagram, TikTok and INA extractors. Run it first on a new machine.
- `audio <url> [<url> ...] [--liste FILE] --dossier DIR [--cookies FILE] [--qualite 192]`: for each link, the best audio
  stream converted to MP3 (192 kb/s by default). Writes `DIR/<slug>.mp3` and `DIR/<slug>.json`; every video or
  intermediate file is deleted. `--liste` is a text file with one link per line (`#` comments allowed).
- `video <url> [<url> ...] [--liste FILE] --dossier DIR [--height 1080] [--max-filesize 500M]`: mp4 video, same outputs.
- `info <url>`: title, author, date, duration, platform, available heights, license. Run before a long download.
- `thumbnail <url> --dossier DIR`: largest YouTube thumbnail (maxres, then sd, hq, mq).

`audio` and `video` end with `{"fichiers": [paths], "echecs": [{"lien", "erreur"}], "metadonnees": [...]}`. One failing
link never stops the others. `<slug>.json` holds `fichier`, `titre`, `auteur`, `date` (YYYY-MM-DD or null),
`plateforme` (YouTube, Instagram, TikTok, INA), `lien` (canonical), `duree_s`, `id`. The slug is a short ASCII title
(the id is added on collision). Tell the user where the files are, and report each entry of `echecs`.

## Platforms and login

- YouTube (watch, Shorts, youtu.be) and INA: no account needed.
- Instagram needs a session, TikTok sometimes: pass `--cookies FILE` (Netscape format, exported from a browser by the
  user; a secondary account is advised). A "login required" failure says so in its message. The script never reads
  the browser cookies by itself: do not add `--cookies-from-browser` unless the user asks for it.
- `auteur` can be null (INA gives no channel).

## Exit codes (audio, video)

| Code | Meaning | Action |
|---|---|---|
| 0 | At least one link succeeded | Give the paths, list the failures. |
| 2 | No valid link | Ask for correct links. |
| 5 | Missing dependency (yt-dlp, ffmpeg) or proxy not configured | Install it (`pip install -U yt-dlp`, `brew install ffmpeg`), run `doctor`. |
| 1 | Every link failed | Read `echecs`: login (use `--cookies`), blocked (below), or unexpected (repair). |

`info` and `thumbnail` use the same codes plus 4 (blocked) and 8 (no thumbnail: private or deleted video).

## Blocked (429, 403, "not a bot")

1. Update yt-dlp (`pip install -U yt-dlp`) and rerun. 2. Give `--cookies FILE`. 3. Only once, `--use-proxy`
(residential proxy from `local.env`, key `IPROYAL_RESIDENTIAL_URL`, limited budget of 2 GB): prefer `audio` with
`--max-filesize`, avoid `video`. Never display the proxy value.

## Repair

Fix `<claude-tools>/skills/media-download/scripts/media_download.py`, then run
`python3 -m unittest discover -s tests` in the skill's folder. Two attempts at most, then report the exact message.
