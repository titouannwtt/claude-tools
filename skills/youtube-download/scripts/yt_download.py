#!/usr/bin/env python3
"""Téléchargement YouTube : métadonnées, vidéo, audio, miniature.

Commandes :
  info <url>                              titre, durée, chaîne, formats les plus utiles (sans téléchargement)
  video <url> [--height 1080] [--out D]   vidéo mp4 (hauteur maximale demandée)
  audio <url> [--format mp3] [--out D]    piste audio seule
  thumbnail <url> [--out D]               miniature la plus grande disponible (maxres, sd, hq, mq)
Options communes : --use-proxy (proxy résidentiel de local.env, seulement après un blocage), --max-filesize 500M.
À n'utiliser que pour des contenus que l'on a le droit de télécharger (les siens, sous licence libre, usage autorisé).

Sortie : JSON sur stdout. Codes : 0 succès ; 1 erreur inattendue ; 2 entrée invalide ; 4 bloqué (réessayer une
fois avec --use-proxy) ; 5 dépendance manquante ; 8 miniature introuvable.
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
    raise Failure(EXIT_INVALID, "URL YouTube non reconnue : %s" % value)


def resolve_proxy(use_proxy, local_env=None):
    if not use_proxy:
        return None
    proxy = cttools.configured_proxy(local_env)
    if not proxy:
        raise Failure(EXIT_MISSING, "IPROYAL_RESIDENTIAL_URL absent de local.env : impossible d'utiliser le proxy")
    return proxy


def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise Failure(EXIT_MISSING, "yt-dlp introuvable : brew install yt-dlp, ou pip install -U yt-dlp")
    return [sys.executable, "-m", "yt_dlp"]


def run_ytdlp(args, proxy=None):
    command = ytdlp_command() + ["--no-warnings", "--no-playlist"]
    if proxy:
        command += ["--proxy", proxy]
    try:
        result = subprocess.run(command + args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise Failure(EXIT_UNEXPECTED, "yt-dlp : délai dépassé (%d s)" % TIMEOUT_SECONDS)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        if any(marker in output for marker in BLOCK_MARKERS):
            first = next((line for line in output.splitlines() if "ERROR" in line), output.strip()[:200])
            raise Failure(EXIT_BLOCKED, "téléchargement bloqué : %s" % first.strip())
        raise Failure(EXIT_UNEXPECTED, "yt-dlp a échoué : %s" % output.strip()[-400:])
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
        raise Failure(EXIT_UNEXPECTED, "yt-dlp n'a produit aucun fichier (taille maximale dépassée ?)")
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
                continue  # taille absente pour cette vidéo : essayer la suivante
            raise Failure(EXIT_BLOCKED if error.code in (403, 429) else EXIT_UNEXPECTED, "miniature : HTTP %d" % error.code)
        except (urllib.error.URLError, OSError) as error:
            raise Failure(EXIT_UNEXPECTED, "miniature : réseau injoignable (%s)" % getattr(error, "reason", error))
        if len(body) < 1500:  # image de remplacement grise renvoyée à la place d'une taille absente
            continue
        path = out_dir / ("%s_%s.jpg" % (video_id, name))
        path.write_bytes(body)
        return {"file": str(path), "size_name": name, "bytes": len(body)}
    raise Failure(EXIT_NO_THUMB, "aucune miniature trouvée pour %s" % video_id)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("info", cmd_info), ("video", cmd_video), ("audio", cmd_audio),
                          ("thumbnail", cmd_thumbnail)):
        item = sub.add_parser(name)
        item.add_argument("url")
        item.add_argument("--out", default="./yt-download")
        item.add_argument("--use-proxy", action="store_true", help="proxy de local.env (repli après blocage)")
        item.add_argument("--max-filesize", default=None, help="ex. 500M (obligatoire de fait avec le proxy)")
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
        print(json.dumps({"error": "erreur inattendue : %s" % error}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
