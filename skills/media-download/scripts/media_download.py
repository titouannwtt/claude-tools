#!/usr/bin/env python3
"""Media download (YouTube, Instagram, TikTok, INA): audio as MP3, video as MP4, metadata, thumbnail.

Commands:
  audio <url> [<url> ...] [--liste F] --dossier D [--cookies F] [--qualite 192]
        best audio stream converted to MP3; writes D/<slug>.mp3 and D/<slug>.json, no video is kept
  video <url> [<url> ...] [--liste F] --dossier D [--cookies F] [--height 1080]
        mp4 video (maximum requested height); writes D/<slug>.mp4 and D/<slug>.json
  info <url> [--cookies F]               metadata without downloading
  thumbnail <url> [--dossier D]          largest YouTube thumbnail (maxres, sd, hq, mq)
  doctor                                 checks yt-dlp, ffmpeg and the extractors
Common options: --use-proxy (residential proxy from local.env, only after a block), --max-filesize 500M.
Only use it for content you are allowed to download (your own, freely licensed, authorized use).

audio and video: one failing link never stops the others. The last stdout line is JSON:
{"fichiers": [...], "echecs": [{"lien", "erreur"}], "metadonnees": [{"fichier", "titre", "auteur", "date",
"plateforme", "lien", "duree_s", "id"}]}. Other commands print one JSON object.
Codes: 0 at least one success; 1 unexpected error; 2 invalid input (no valid link); 4 blocked (info, thumbnail);
5 missing dependency (yt-dlp, ffmpeg); 8 thumbnail not found.
Cookies: Instagram (and sometimes TikTok) need a session: give a Netscape cookies file with --cookies.
The browser cookies are never read by this script.
Python 3.9 compatible.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import cttools  # noqa: E402

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID, EXIT_BLOCKED, EXIT_MISSING, EXIT_NO_THUMB = 0, 1, 2, 4, 5, 8
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_RE = re.compile(r"^https?://[^\s/]+", re.IGNORECASE)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
BLOCK_MARKERS = ("http error 429", "http error 403", "not a bot", "ipblocked", "requestblocked", "too many requests")
LOGIN_MARKERS = ("login required", "log in", "logged in", "logged-in", "sign in", "empty media response",
                 "requires authentication", "authentication", "rate-limit reached", "use --cookies",
                 "private", "cookies")
THUMB_BASE = os.environ.get("YT_THUMB_BASE", "https://i.ytimg.com/vi")
THUMB_NAMES = ("maxresdefault", "sddefault", "hqdefault", "mqdefault", "default")
TIMEOUT_SECONDS = 3600
PLAYLIST_LIMIT = 20  # a profile or channel link must not download hundreds of items
REQUIRED_EXTRACTORS = ("Ina", "Instagram", "TikTok", "Youtube")
STALE_DAYS = 120
LOGIN_HINT = "login required: give a cookies file (Netscape format) with --cookies FILE (a secondary account is advised)"


class Failure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- pure helpers

def video_id_from_url(value):
    for pattern in (r"youtu\.be/([A-Za-z0-9_-]{11})", r"[?&]v=([A-Za-z0-9_-]{11})",
                    r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})"):
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    if VIDEO_ID_RE.match(value):
        return value
    raise Failure(EXIT_INVALID, "YouTube URL not recognized: %s" % value)


def normalize_url(value):
    """Accept an http(s) link, or a bare 11-character YouTube id (turned into a watch link)."""
    value = value.strip()
    if URL_RE.match(value):
        return value
    if VIDEO_ID_RE.match(value):
        return "https://www.youtube.com/watch?v=%s" % value
    raise Failure(EXIT_INVALID, "not a valid link (http or https expected): %s" % value[:120])


def platform_from_url(url):
    """Platform name from the host of a link; the host itself when unknown."""
    host = (urlparse(url).hostname or "").lower()
    for suffix, name in (("youtube.com", "YouTube"), ("youtu.be", "YouTube"), ("youtube-nocookie.com", "YouTube"),
                         ("instagram.com", "Instagram"), ("tiktok.com", "TikTok"), ("ina.fr", "INA")):
        if host == suffix or host.endswith("." + suffix):
            return name
    return host[4:] if host.startswith("www.") else (host or "unknown")


def platform_from_info(info, url):
    """Platform name from the yt-dlp extractor key, falling back on the link."""
    key = str(info.get("extractor_key") or info.get("ie_key") or "")
    lowered = key.lower()
    for prefix, name in (("youtube", "YouTube"), ("instagram", "Instagram"), ("tiktok", "TikTok"), ("ina", "INA")):
        if lowered == prefix or (lowered.startswith(prefix) and prefix != "ina"):
            return name
    return platform_from_url(url)


def slugify(title, max_len=50):
    """Short ASCII slug from a title (accents removed, words kept whole); empty string if nothing is left."""
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) > max_len:
        cut = text[:max_len]
        text = cut.rsplit("-", 1)[0] if "-" in cut and text[max_len] != "-" else cut
    return text.strip("-")


def safe_id(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "", str(value or ""))


def choose_slug(title, media_id, folder, suffix, platform=""):
    """Slug free in `folder`: the title alone, or title + id on collision (a rerun of the same id overwrites)."""
    base = slugify(title) or slugify(platform) or "media"
    ident = safe_id(media_id) or "x"
    for candidate in (base, "%s-%s" % (base, ident)):
        if not (folder / (candidate + suffix)).exists() and not (folder / (candidate + ".json")).exists():
            return candidate
        if same_id(folder / (candidate + ".json"), media_id):
            return candidate
    counter = 2
    while (folder / ("%s-%s-%d%s" % (base, ident, counter, suffix))).exists():
        counter += 1
    return "%s-%s-%d" % (base, ident, counter)


def same_id(json_path, media_id):
    try:
        return json.loads(json_path.read_text(encoding="utf-8")).get("id") == media_id
    except (OSError, ValueError, AttributeError):
        return False


def clean_error_line(text):
    text = ANSI_RE.sub("", text or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    errors = [line for line in lines if "ERROR" in line]
    return (errors[-1] if errors else (lines[-1] if lines else ""))[:300]


def classify_error(output):
    """(kind, message) from yt-dlp output; kind is 'blocked', 'login' or 'other'."""
    line = clean_error_line(output)
    lowered = (output or "").lower()
    if "not a bot" in lowered:
        return "blocked", ("blocked by the platform (bot check): update yt-dlp, give --cookies FILE, "
                           "or retry once with --use-proxy. %s" % line)
    if any(marker in lowered for marker in LOGIN_MARKERS):
        return "login", "%s (%s)" % (LOGIN_HINT, line)
    if any(marker in lowered for marker in BLOCK_MARKERS):
        return "blocked", "blocked by the platform (429/403): update yt-dlp, or retry once with --use-proxy. %s" % line
    return "other", "yt-dlp failed: %s" % (line or "no message")


def upload_date(info):
    raw = str(info.get("upload_date") or info.get("release_date") or "")
    if re.fullmatch(r"\d{8}", raw):
        return "%s-%s-%s" % (raw[:4], raw[4:6], raw[6:])
    timestamp = info.get("timestamp") or info.get("release_timestamp")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    return None


def build_metadata(info, url, file_path):
    author = next((info[key] for key in ("channel", "uploader", "creator", "uploader_id") if info.get(key)), None)
    return {"fichier": str(file_path), "titre": info.get("title"), "auteur": author, "date": upload_date(info),
            "plateforme": platform_from_info(info, url), "lien": info.get("webpage_url") or url,
            "duree_s": info.get("duration"), "id": info.get("id")}


def build_options(mode, tmp_dir, quality=192, height=1080, cookies=None, proxy=None, max_filesize=None):
    """yt-dlp arguments (without the executable nor the link) for a download into tmp_dir."""
    options = ["--no-warnings", "-q", "--no-progress", "--no-playlist", "--playlist-end", str(PLAYLIST_LIMIT),
               "--dump-single-json", "--no-simulate", "-o", str(Path(tmp_dir) / "%(id)s.%(ext)s")]
    if mode == "audio":
        options += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "%dK" % quality]
    else:
        options += ["-f", format_selector(height), "--merge-output-format", "mp4"]
    if cookies:
        options += ["--cookies", str(cookies)]
    if proxy:
        options += ["--proxy", proxy]
    if max_filesize:
        options += ["--max-filesize", max_filesize]
    return options


def format_selector(height):
    return "bv*[height<=%d]+ba/b[height<=%d]/b" % (height, height)


def read_links(values, list_file):
    """Links given on the command line plus the --liste file (one per line, '#' comments, text around allowed)."""
    items = [(value, value) for value in values]
    if list_file:
        try:
            lines = Path(list_file).read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise Failure(EXIT_INVALID, "cannot read the list %s: %s" % (list_file, error.strerror or error))
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = [token for token in line.split() if URL_RE.match(token)]
            items += [(token, token) for token in tokens] if tokens else [(line, line)]
    seen, unique = set(), []
    for raw, _ in items:
        if raw not in seen:
            seen.add(raw)
            unique.append(raw)
    return unique


# ---------------------------------------------------------------- yt-dlp calls

def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise Failure(EXIT_MISSING, "yt-dlp not found: brew install yt-dlp, or pip install -U yt-dlp")
    return [sys.executable, "-m", "yt_dlp"]


def require_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise Failure(EXIT_MISSING, "ffmpeg not found: brew install ffmpeg (or apt install ffmpeg)")


def resolve_proxy(use_proxy, local_env=None):
    if not use_proxy:
        return None
    proxy = cttools.configured_proxy(local_env)
    if not proxy:
        raise Failure(EXIT_MISSING, "IPROYAL_RESIDENTIAL_URL missing from local.env: cannot use the proxy")
    return proxy


def check_cookies(path):
    if path and not Path(path).is_file():
        raise Failure(EXIT_INVALID, "cookies file not found: %s" % path)


def run_ytdlp(args):
    try:
        result = subprocess.run(ytdlp_command() + args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return 1, "", "ERROR: timed out (%d s)" % TIMEOUT_SECONDS
    return result.returncode, result.stdout or "", result.stderr or ""


def parse_info(stdout):
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


class LinkFailure(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
        self.message = message


def fetch_one(mode, url, folder, args, proxy):
    """Download one link into a temporary subfolder, then move the result(s) to `folder`. Returns metadata list."""
    suffix = ".mp3" if mode == "audio" else ".mp4"
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tmp-", dir=str(folder)))
    try:
        options = build_options(mode, tmp_dir, getattr(args, "qualite", 192), getattr(args, "height", 1080),
                                args.cookies, proxy, args.max_filesize)
        code, stdout, stderr = run_ytdlp(options + [url])
        info = parse_info(stdout)
        if code != 0 or info is None:
            kind, message = classify_error(stderr + stdout if code != 0 else stderr or "no metadata returned")
            raise LinkFailure(kind, message)
        entries = [e for e in (info.get("entries") or []) if e] if info.get("entries") is not None else [info]
        if not entries:
            raise LinkFailure("other", "nothing to download at this link")
        produced = sorted(p for p in tmp_dir.iterdir() if p.suffix == suffix)
        results = []
        for entry in entries:
            entry.setdefault("extractor_key", info.get("extractor_key"))
            source = tmp_dir / ("%s%s" % (entry.get("id"), suffix))
            if not source.is_file():
                source = produced[0] if len(entries) == 1 and len(produced) == 1 else source
            if not source.is_file() or source.stat().st_size == 0:
                raise LinkFailure("other", "no %s file produced (size limit exceeded, or conversion failed)"
                                  % suffix[1:])
            platform = platform_from_info(entry, url)
            slug = choose_slug(entry.get("title"), entry.get("id"), folder, suffix, platform)
            target = folder / (slug + suffix)
            shutil.move(str(source), str(target))
            meta = build_metadata(entry, entry.get("webpage_url") or url, target)
            (folder / (slug + ".json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
            results.append(meta)
        return results
    finally:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)


# ---------------------------------------------------------------- commands

def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def cmd_batch(args):
    mode = args.command
    empty = {"fichiers": [], "echecs": [], "metadonnees": []}
    try:
        links = read_links(args.urls, args.liste)
        if not links:
            raise Failure(EXIT_INVALID, "no link given (arguments or --liste)")
        check_cookies(args.cookies)
        ytdlp_command()
        require_ffmpeg()
        proxy = resolve_proxy(args.use_proxy, args.local_env)
        folder = Path(args.dossier).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
    except Failure as failure:
        empty["erreur"] = failure.message
        emit(empty)
        return failure.code
    kinds = []
    for raw in links:
        try:
            url = normalize_url(raw)
        except Failure as failure:
            empty["echecs"].append({"lien": raw, "erreur": failure.message})
            kinds.append("invalid")
            continue
        try:
            for meta in fetch_one(mode, url, folder, args, proxy):
                empty["fichiers"].append(meta["fichier"])
                empty["metadonnees"].append(meta)
                print("ok: %s" % meta["fichier"], file=sys.stderr)
        except LinkFailure as failure:
            empty["echecs"].append({"lien": url, "erreur": failure.message})
            kinds.append(failure.kind)
            print("failed: %s: %s" % (url, failure.message), file=sys.stderr)
        except Exception as error:  # noqa: BLE001
            empty["echecs"].append({"lien": url, "erreur": "unexpected error: %s" % error})
            kinds.append("other")
    emit(empty)
    if empty["fichiers"]:
        return EXIT_OK
    return EXIT_INVALID if kinds and all(kind == "invalid" for kind in kinds) else EXIT_UNEXPECTED


def cmd_info(args):
    check_cookies(args.cookies)
    proxy = resolve_proxy(args.use_proxy, args.local_env)
    url = normalize_url(args.urls[0]) if args.urls else None
    if not url:
        raise Failure(EXIT_INVALID, "no link given")
    options = ["--no-warnings", "-q", "--no-playlist", "--playlist-end", "1", "--dump-single-json", "--skip-download"]
    if args.cookies:
        options += ["--cookies", args.cookies]
    if proxy:
        options += ["--proxy", proxy]
    code, stdout, stderr = run_ytdlp(options + [url])
    data = parse_info(stdout)
    if code != 0 or data is None:
        kind, message = classify_error(stderr)
        raise Failure(EXIT_BLOCKED if kind == "blocked" else EXIT_UNEXPECTED, message)
    if data.get("entries"):
        data = next((e for e in data["entries"] if e), data)
    heights = sorted({f["height"] for f in data.get("formats", []) if f.get("height") and f.get("vcodec") != "none"})
    meta = build_metadata(data, url, "")
    meta.pop("fichier")
    meta.update({"upload_date": data.get("upload_date"), "heights": heights,
                 "has_subtitles": bool(data.get("subtitles")), "license": data.get("license")})
    return meta


def cmd_thumbnail(args):
    video_id = video_id_from_url(args.urls[0] if args.urls else "")
    proxy = resolve_proxy(args.use_proxy, args.local_env)
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    out_dir = Path(args.dossier)
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


def version_age_days(version):
    match = re.match(r"^(\d{4})\.(\d{2})\.(\d{2})", version or "")
    if not match:
        return None
    released = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - released).days


def cmd_doctor(args):
    report = {"yt_dlp": None, "ffmpeg": shutil.which("ffmpeg"), "extractors": {}, "problems": []}
    try:
        command = ytdlp_command()
    except Failure as failure:
        report["problems"].append(failure.message)
        command = None
    if command:
        version = subprocess.run(command + ["--version"], capture_output=True, text=True).stdout.strip()
        report["yt_dlp"] = version
        age = version_age_days(version)
        if age is not None and age > STALE_DAYS:
            report["problems"].append("yt-dlp is %d days old: update it (pip install -U yt-dlp)" % age)
        listing = subprocess.run(command + ["--list-extractors"], capture_output=True, text=True).stdout.split("\n")
        names = {line.strip().split(":")[0].split(" ")[0].lower() for line in listing}
        for extractor in REQUIRED_EXTRACTORS:
            report["extractors"][extractor] = extractor.lower() in names
            if extractor.lower() not in names:
                report["problems"].append("extractor %s missing: update yt-dlp" % extractor)
    if not report["ffmpeg"]:
        report["problems"].append("ffmpeg not found: install it (needed for MP3 conversion and mp4 merge)")
    report["ok"] = not report["problems"]
    missing = not report["yt_dlp"] or not report["ffmpeg"] or not all(report["extractors"].values())
    return report, (EXIT_MISSING if missing else EXIT_OK)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("audio", "video", "info", "thumbnail", "doctor"):
        item = sub.add_parser(name)
        if name == "doctor":
            continue
        item.add_argument("urls", nargs="*", help="links (YouTube, Instagram, TikTok, ina.fr)")
        item.add_argument("--dossier", "--out", dest="dossier", default="./media-download",
                          help="output folder (default ./media-download)")
        item.add_argument("--cookies", default=None, help="cookies file, Netscape format (Instagram, TikTok)")
        item.add_argument("--use-proxy", action="store_true", help="proxy from local.env (fallback after a block)")
        item.add_argument("--max-filesize", default=None, help="e.g. 500M")
        item.add_argument("--local-env", default=None)
        if name in ("audio", "video"):
            item.add_argument("--liste", default=None, help="text file with one link per line")
        if name == "audio":
            item.add_argument("--qualite", type=int, default=192, help="MP3 bitrate in kb/s (default 192)")
        if name == "video":
            item.add_argument("--height", type=int, default=1080)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command in ("audio", "video"):
        return cmd_batch(args)
    handler = {"info": cmd_info, "thumbnail": cmd_thumbnail, "doctor": cmd_doctor}[args.command]
    try:
        result = handler(args)
    except Failure as failure:
        emit({"error": failure.message})
        return failure.code
    except Exception as error:  # noqa: BLE001
        emit({"error": "unexpected error: %s" % error})
        return EXIT_UNEXPECTED
    code = EXIT_OK
    if isinstance(result, tuple):
        result, code = result
    emit(result)
    return code


if __name__ == "__main__":
    sys.exit(main())
