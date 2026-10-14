---
name: web-fetch
description: Fetch the content of a URL (HTML page, text, JSON) when direct access is blocked or unstable, with automatic fallback to a residential proxy. Use when WebFetch fails (403, 429, 503, timeout), or to save a page's text to a file without going through the model.
---

# web-fetch

A script fetches the page: direct attempt, then the residential proxy only if direct access is blocked.
Your role: run it, read the JSON, decide what follows. The script bypasses neither a login nor a subscription.

## Command

`python3 ~/.claude/skills/web-fetch/scripts/fetch_url.py "<url>" [--text] [--out file]`

- `--text`: readable text of the page (without script or style); without it, raw HTML.
- `--out`: writes the body to a file; the JSON then contains only the path (useful for a large page).
- `--no-proxy`: never a proxy. `--force-proxy`: directly through the proxy (rare, see budget).
- JSON output: `url`, `status`, `via` (`direct` or `proxy`), `content_type`, `bytes`, `text` or `file`.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | Read `text` or `file`. If `via` is `proxy`, tell the user. |
| 4 | Blocked, even with the proxy or no proxy configured | Say that the site refuses access. Do not insist; offer the driven browser (skill `mac-control`) if the user agrees. |
| 6 | HTTP error other than a block (404, 500...) | Check the URL; the proxy would not change anything. |
| 7 | Network unreachable | Check the connection or the domain name. |
| 2 | Invalid URL | Ask for an http(s) URL. |
| 1 | Unexpected error | Repair the script (see below). |

## Proxy

Address in `local.env` at the root of `claude-tools` (key `IPROYAL_RESIDENTIAL_URL`, ignored by git). Limited budget
(2 GB): do not download large files through this channel. Never display the proxy value.

## Repair

Fix `<claude-tools>/skills/web-fetch/scripts/fetch_url.py`, then run `python3 -m unittest discover -s tests`
in the skill's folder. Two attempts at most, then report the exact message to the user.
