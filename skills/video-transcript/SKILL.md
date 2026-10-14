---
name: video-transcript
description: Get the transcript of a YouTube video from its URL, to read it, summarize it or integrate it into a project. Use when the user gives a YouTube link and asks what is said in it, its transcript, its subtitles, or an analysis of its content.
---

# video-transcript

Objective: turn a YouTube video into timestamped text, then understand it from that text.
The script does all the work (zero model tokens). Your role: run it, read the result, repair the script if needed.

## Commands

Script: `~/.claude/skills/video-transcript/scripts/transcript.py`. It always writes JSON to stdout.

1. **Route A, existing subtitles (try first, fast and no video download)**:
   `python3 <script> subs "<url>" --lang fr,en --out <folder>`
2. **Route B, audio then local transcription (if route A found nothing)**:
   `python3 <script> audio "<url>" --lang fr --model small --out <folder>`
3. **Audio file already present**: `python3 <script> transcribe <file> --out <folder>`
4. **Check the dependencies**: `python3 <script> doctor`

## Exit codes and reaction

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | Read the `.txt` (lines `[hh:mm:ss] text`) or the `.json` (segments). |
| 3 | No subtitles | Run route B (`audio`). |
| 4 | Download blocked (429, 403, "not a bot", blocked IP) | 1. Update yt-dlp (`brew upgrade yt-dlp` or `pip install -U yt-dlp`): a 403 often comes from an outdated version. 2. Rerun. 3. If it still blocks, rerun **only once** with `--use-proxy`. Never use the proxy without a block. |
| 5 | Missing dependency | Install what the message indicates (`pip install -U yt-dlp`, `pip install faster-whisper`, ffmpeg). |
| 2 | Invalid URL or file | Ask for the correct URL. |
| 1 | Unexpected error | Read the message, fix the script, rerun (see Repair). |

## Repair

If the script fails without an expected code (1), or if an output is inconsistent:
1. Read the full error message.
2. Fix the script in `<claude-tools>/skills/video-transcript/scripts/transcript.py` (the symbolic link points to it), and run `python3 -m unittest discover -s tests` in the skill's folder.
3. Rerun the command. Two attempts at most, then report the problem to the user with the exact message.

## Installing the dependencies

- yt-dlp and ffmpeg: Homebrew (Mac) or system packages (VPS).
- faster-whisper: on the Mac, in a dedicated environment `~/.venvs/video-transcript` (Homebrew's Python, PEP 668).
  The script switches to that environment by itself. On the VPS, `pip install --user faster-whisper`.
- In both cases, `av` must stay below version 16 (`pip install "av<16"`): recent versions
  remove a parameter that faster-whisper uses.

## Proxy (fallback)

- The IPRoyal proxy is used only with `--use-proxy`, and only after a block (code 4).
- Its address comes from `local.env` at the root of `claude-tools` (key `IPROYAL_RESIDENTIAL_URL`, the residential proxy; ignored by git). Do not use the Web Unblocker: it intercepts TLS and breaks yt-dlp. Limited budget (2 GB): prefer `subs` with the proxy.
- Never display the proxy value, neither in the chat nor in a versioned file.

## After the transcript

Read the `.txt`, then answer the user's question from the text, citing the useful timestamps
(`[00:12:40]`). If the video is long, summarize in sections rather than copying everything.
