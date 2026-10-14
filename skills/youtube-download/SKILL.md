---
name: youtube-download
description: Download a video, an audio track or the thumbnail of a YouTube video from its URL, or read its metadata (title, duration, available qualities). Use when the user gives a YouTube link and asks to download it, extract the audio or get the thumbnail. For the transcript, use video-transcript.
---

# youtube-download

A script relies on yt-dlp (video, audio) and on YouTube's public images (thumbnail).
Reserve it for content the user has the right to download (their own, free license, authorized use):
if the doubt is serious, say so rather than executing.

## Commands

Script: `~/.claude/skills/youtube-download/scripts/yt_download.py`. Output: JSON on stdout.

- `info "<url>"`: title, channel, duration, available heights. Run before a long download.
- `thumbnail "<url>" --out <folder>`: largest available thumbnail (maxres, then sd, hq, mq).
- `video "<url>" --height 1080 --out <folder>`: mp4 at the maximum requested height.
- `audio "<url>" --format mp3 --out <folder>`: audio track (`mp3`, `m4a`, `opus`, `wav`).
- Always add `--max-filesize 500M` (or less) on `video`: without it, a long 4K video weighs several GB.

Without an `--out` folder, files go to `./yt-download`. Tell the user where the file is.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | Give the file path. |
| 4 | Blocked (429, 403, "not a bot") | 1. Update yt-dlp (`brew upgrade yt-dlp` or `pip install -U yt-dlp`). 2. Rerun. 3. If it still blocks, **only once** with `--use-proxy`, preferably for `thumbnail` or `info` (light). |
| 5 | Missing dependency | Install yt-dlp (and ffmpeg for the merged mp4 and the audio). |
| 8 | No thumbnail | Private or deleted video: say so. |
| 2 | Invalid URL | Ask for the correct URL. |
| 1 | Unexpected error | Repair the script (see below). |

## Proxy

`--use-proxy` uses the residential proxy from `local.env` (key `IPROYAL_RESIDENTIAL_URL`). Limited budget (2 GB):
avoid `video` through this channel, only use it after a real block, with a low `--height` and `--max-filesize`.
Never display the proxy value.

## Repair

Fix `<claude-tools>/skills/youtube-download/scripts/yt_download.py`, then run
`python3 -m unittest discover -s tests` in the skill's folder. Two attempts at most, then report the exact message.
