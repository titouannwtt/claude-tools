#!/usr/bin/env python3
"""YouTube download: metadata, video, audio, thumbnail.

Commands:
  info <url>                              title, duration, channel, most useful formats (no download)
  video <url> [--height 1080] [--out D]   mp4 video (requested maximum height)
  audio <url> [--format mp3] [--out D]    audio track only
  thumbnail <url> [--out D]               largest thumbnail available (maxres, sd, hq, mq)
Common options: --use-proxy (residential proxy from local.env, only after a block), --max-filesize 500M.
Only use it for content you are allowed to download (your own, freely licensed, authorized use).

Output: JSON on stdout. Codes: 0 success; 1 unexpected error; 2 invalid input; 4 blocked (retry once
with --use-proxy); 5 missing dependency; 8 thumbnail not found.
Python 3.9 compatible.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import cttools  # noqa: E402

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID, EXIT_BLOCKED, EXIT_MISSING, EXIT_NO_THUMB = 0, 1, 2, 4, 5, 8
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
BLOCK_MARKERS = ("HTTP Error 429", "HTTP Error 403", "Sign in to confirm", "not a bot", "IpBlocked", "RequestBlocked")
THUMB_BASE = os.environ.get("YT_THUMB_BASE", "https://i.ytimg.com/vi")
THUMB_NAMES = ("maxresdefault", "sddefault", "hqdefault", "mqdefault", "default")
TIMEOUT_SECONDS = 3600


class Failure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def video_id_from_url(value):
    for pattern in (r"youtu\.be/([A-Za-z0-9_-]{11})", r"[?&]v=([A-Za-z0-9_-]{11})",
                    r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})"):
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    if VIDEO_ID_RE.match(value):
        return value
    raise Failure(EXIT_INVALID, "YouTube URL not recognized: %s" % value)


def resolve_proxy(use_proxy, local_env=None):
    if not use_proxy:
        return None
    proxy = cttools.configured_proxy(local_env)
    if not proxy:
        raise Failure(EXIT_MISSING, "IPROYAL_RESIDENTIAL_URL missing from local.env: cannot use the proxy")
    return proxy


def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise Failure(EXIT_MISSING, "yt-dlp not found: brew install yt-dlp, or pip install -U yt-dlp")
    return [sys.executable, "-m", "yt_dlp"]


def run_ytdlp(args, proxy=None):
    command = ytdlp_command() + ["--no-warnings", "--no-playlist"]
    if proxy:
        command += ["--proxy", proxy]
    try:
        result = subprocess.run(command + args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise Failure(EXIT_UNEXPECTED, "yt-dlp: timed out (%d s)" % TIMEOUT_SECONDS)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        if any(marker in output for marker in BLOCK_MARKERS):
            first = next((line for line in output.splitlines() if "ERROR" in line), output.strip()[:200])
            raise Failure(EXIT_BLOCKED, "download blocked: %s" % first.strip())
        raise Failure(EXIT_UNEXPECTED, "yt-dlp failed: %s" % output.strip()[-400:])
    return result.stdout or ""


def format_selector(height):
    return "bv*[height<=%d]+ba/b[height<=%d]/b" % (height, height)


def cmd_info(args):
    proxy = resolve_proxy(args.use_proxy, args.local_env)
    out = run_ytdlp(["--dump-single-json", "--skip-download", args.url], proxy)
    data = json.loads(out)
    heights = sorted({f["height"] for f in data.get("formats", []) if f.get("height") and f.get("vcodec") != "none"})
    return {"id": data.get("id"), "title": data.get("title"), "channel": data.get("channel"),
            "duration_s": data.get("duration"), "upload_date": data.get("upload_date"),
            "heights": heights, "has_subtitles": bool(data.get("subtitles")),
            "license": data.get("license")}


def download(args, extra):
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    proxy = resolve_proxy(args.use_proxy, args.local_env)
    command = ["-o", str(out_dir / "%(title).80s [%(id)s].%(ext)s"), "--print", "after_move:filepath"]
    if args.max_filesize:
        command += ["--max-filesize", args.max_filesize]
    out = run_ytdlp(command + extra + [args.url], proxy)
    files = [line.strip() for line in out.splitlines() if line.strip() and Path(line.strip()).exists()]
    if not files:
        raise Failure(EXIT_UNEXPECTED, "yt-dlp produced no file (maximum size exceeded?)")
    path = Path(files[-1])
    return {"file": str(path), "bytes": path.stat().st_size}


def cmd_video(args):
    return download(args, ["-f", format_selector(args.height), "--merge-output-format", "mp4"])


def cmd_audio(args):
    return download(args, ["-x", "--audio-format", args.format])


def cmd_thumbnail(args):
    video_id = video_id_from_url(args.url)
    proxy = resolve_proxy(args.use_proxy, args.local_env)
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in THUMB_NAMES:
        url = "%s/%s/%s.jpg" % (THUMB_BASE, video_id, name)
        try:
            with opener.open(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
                body = r.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue  # size not available for this video: try the next one
            raise Failure(EXIT_BLOCKED if error.code in (403, 429) else EXIT_UNEXPECTED, "thumbnail: HTTP %d" % error.code)
        except (urllib.error.URLError, OSError) as error:
            raise Failure(EXIT_UNEXPECTED, "thumbnail: network unreachable (%s)" % getattr(error, "reason", error))
        if len(body) < 1500:  # gray placeholder image returned in place of a missing size
            continue
        path = out_dir / ("%s_%s.jpg" % (video_id, name))
        path.write_bytes(body)
        return {"file": str(path), "size_name": name, "bytes": len(body)}
    raise Failure(EXIT_NO_THUMB, "no thumbnail found for %s" % video_id)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("info", cmd_info), ("video", cmd_video), ("audio", cmd_audio),
                          ("thumbnail", cmd_thumbnail)):
        item = sub.add_parser(name)
        item.add_argument("url")
        item.add_argument("--out", default="./yt-download")
        item.add_argument("--use-proxy", action="store_true", help="proxy from local.env (fallback after a block)")
        item.add_argument("--max-filesize", default=None, help="e.g. 500M (de facto required with the proxy)")
        item.add_argument("--local-env", default=None)
        item.set_defaults(handler=handler)
        if name == "video":
            item.add_argument("--height", type=int, default=1080)
        if name == "audio":
            item.add_argument("--format", default="mp3", choices=["mp3", "m4a", "opus", "wav"])
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command != "info" and args.command != "thumbnail":
            video_id_from_url(args.url)
        result = args.handler(args)
    except Failure as failure:
        print(json.dumps({"error": failure.message}, ensure_ascii=False))
        return failure.code
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"error": "unexpected error: %s" % error}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
