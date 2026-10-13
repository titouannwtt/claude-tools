#!/usr/bin/env python3
"""Transcription de vidéos YouTube.

Voie A (sous-titres existants, sans téléchargement de la vidéo) : `subs`.
Voie B (audio puis transcription locale) : `audio`, et `transcribe` pour un fichier audio déjà présent.
Diagnostic des dépendances : `doctor`.

Dépendances : yt-dlp (obligatoire), ffmpeg (voie B), faster-whisper (transcription locale).
Proxy : uniquement sur demande explicite (`--use-proxy`), valeur lue dans local.env (clé IPROYAL_PROXY_URL).

Sortie : toujours du JSON sur stdout. Codes de sortie :
  0 succès ; 1 erreur inattendue ; 2 entrée invalide ; 3 aucun sous-titre disponible ;
  4 téléchargement bloqué (à réessayer avec --use-proxy) ; 5 dépendance manquante.
Python 3.9 compatible.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID, EXIT_NO_SUBS, EXIT_BLOCKED, EXIT_MISSING = 0, 1, 2, 3, 4, 5
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
BLOCK_MARKERS = ("HTTP Error 429", "HTTP Error 403", "Sign in to confirm", "not a bot",
                 "IpBlocked", "RequestBlocked", "blocked")
TIMEOUT_SECONDS = 900
TIME_RE = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})")
TAG_RE = re.compile(r"<[^>]+>")


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


def load_local_env(explicit=None):
    """Lit local.env (clés KEY=VALUE) : chemin explicite, variable CLAUDE_TOOLS_LOCAL, ou racine du dépôt."""
    candidates = [explicit, os.environ.get("CLAUDE_TOOLS_LOCAL"),
                  str(Path(__file__).resolve().parents[3] / "local.env")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            values = {}
            for line in Path(candidate).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
            return values
    return {}


def resolve_proxy(use_proxy, explicit_env=None):
    if not use_proxy:
        return None
    proxy = load_local_env(explicit_env).get("IPROYAL_PROXY_URL")
    if not proxy:
        raise Failure(EXIT_MISSING, "IPROYAL_PROXY_URL absent de local.env : impossible d'utiliser le proxy")
    return proxy


def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise Failure(EXIT_MISSING, "yt-dlp introuvable : pip install -U yt-dlp")
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
    return output


def _seconds(hours, minutes, seconds, millis):
    total = int(hours) if hours else 0
    return round(total * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0, 3)


def parse_vtt(text):
    """Segments {start, end, text} d'un fichier WebVTT ; les répétitions des sous-titres automatiques sont fusionnées."""
    segments = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = TIME_RE.search(lines[index])
        index += 1
        if not match:
            continue
        start = _seconds(match.group(1), match.group(2), match.group(3), match.group(4))
        end = _seconds(match.group(5), match.group(6), match.group(7), match.group(8))
        chunk = []
        while index < len(lines) and lines[index].strip():
            chunk.append(TAG_RE.sub("", lines[index]).strip())
            index += 1
        content = " ".join(part for part in chunk if part)
        if not content:
            continue
        if segments and content == segments[-1]["text"]:
            segments[-1]["end"] = end
        elif segments and content.startswith(segments[-1]["text"]):
            segments[-1]["text"] = content
            segments[-1]["end"] = end
        else:
            segments.append({"start": start, "end": end, "text": content})
    return segments


def fmt_timestamp(seconds):
    whole = int(seconds)
    return "%02d:%02d:%02d" % (whole // 3600, (whole % 3600) // 60, whole % 60)


def write_outputs(out_dir, video_id, language, segments, method):
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "%s.%s" % (video_id, language or "und")
    txt_path = out_dir / (stem + ".txt")
    json_path = out_dir / (stem + ".json")
    txt_path.write_text("".join("[%s] %s\n" % (fmt_timestamp(s["start"]), s["text"]) for s in segments),
                        encoding="utf-8")
    json_path.write_text(json.dumps({"video_id": video_id, "language": language, "method": method,
                                     "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(txt_path), str(json_path)


def pick_subtitle_file(out_dir, video_id, languages):
    candidates = sorted(out_dir.glob("%s.*.vtt" % video_id))
    for wanted in languages:
        for candidate in candidates:
            lang = candidate.name[len(video_id) + 1:-len(".vtt")]
            if lang == wanted or lang.startswith(wanted + "-"):
                return candidate, lang
    return None, None


def fetch_subs(url, languages, out_dir, proxy=None):
    video_id = video_id_from_url(url)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_ytdlp(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", ",".join(languages),
               "--sub-format", "vtt", "-o", str(out_dir / "%(id)s.%(ext)s"),
               "https://www.youtube.com/watch?v=" + video_id], proxy)
    subtitle, lang = pick_subtitle_file(out_dir, video_id, languages)
    if subtitle is None:
        raise Failure(EXIT_NO_SUBS, "aucun sous-titre pour %s dans %s : utiliser la commande audio"
                      % (video_id, ",".join(languages)))
    segments = parse_vtt(subtitle.read_text(encoding="utf-8", errors="replace"))
    txt, js = write_outputs(out_dir, video_id, lang, segments, "subs")
    return {"video_id": video_id, "method": "subs", "language": lang, "segments": len(segments),
            "txt": txt, "json": js}


def fetch_audio(url, out_dir, proxy=None):
    video_id = video_id_from_url(url)
    if not shutil.which("ffmpeg"):
        raise Failure(EXIT_MISSING, "ffmpeg introuvable : requis pour la voie audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_ytdlp(["-x", "--audio-format", "mp3", "-o", str(out_dir / "%(id)s.%(ext)s"),
               "https://www.youtube.com/watch?v=" + video_id], proxy)
    audio = out_dir / (video_id + ".mp3")
    if not audio.is_file():
        raise Failure(EXIT_UNEXPECTED, "audio introuvable après téléchargement : %s" % audio)
    return audio


def transcribe_file(path, model_name, language):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise Failure(EXIT_MISSING, "faster-whisper absent : pip install faster-whisper")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    raw, info = model.transcribe(str(path), language=language or None, vad_filter=True)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
                for s in raw if s.text.strip()]
    return segments, info.language


def doctor():
    try:
        ytdlp_command()
        ytdlp = True
    except Failure:
        ytdlp = False
    try:
        import faster_whisper  # noqa: F401
        whisper = True
    except ImportError:
        whisper = False
    return {"ytdlp": ytdlp, "ffmpeg": bool(shutil.which("ffmpeg")), "faster_whisper": whisper,
            "proxy_configured": bool(load_local_env().get("IPROYAL_PROXY_URL"))}


def dispatch(args):
    if args.cmd == "doctor":
        return doctor()
    out_dir = Path(args.out).expanduser().resolve()
    if args.cmd == "subs":
        proxy = resolve_proxy(args.use_proxy)
        languages = [lang.strip() for lang in args.lang.split(",") if lang.strip()]
        return fetch_subs(args.url, languages, out_dir, proxy)
    if args.cmd == "audio":
        proxy = resolve_proxy(args.use_proxy)
        video_id = video_id_from_url(args.url)
        audio = fetch_audio(args.url, out_dir, proxy)
        segments, language = transcribe_file(audio, args.model, args.lang)
        txt, js = write_outputs(out_dir, video_id, language, segments, "audio")
        return {"video_id": video_id, "method": "audio", "language": language, "segments": len(segments),
                "txt": txt, "json": js}
    if args.cmd == "transcribe":
        path = Path(args.file).expanduser().resolve()
        if not path.is_file():
            raise Failure(EXIT_INVALID, "fichier audio introuvable : %s" % path)
        segments, language = transcribe_file(path, args.model, args.lang)
        txt, js = write_outputs(out_dir, path.stem, language, segments, "local")
        return {"source": path.name, "method": "local", "language": language, "segments": len(segments),
                "txt": txt, "json": js}
    raise Failure(EXIT_INVALID, "commande inconnue : %s" % args.cmd)


def build_parser():
    parser = argparse.ArgumentParser(description="Transcription de vidéos YouTube (sortie JSON).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="vérifie les dépendances")
    for name in ("subs", "audio"):
        item = sub.add_parser(name)
        item.add_argument("url")
        item.add_argument("--out", default="transcripts")
        item.add_argument("--use-proxy", action="store_true", help="proxy IPRoyal depuis local.env (repli)")
        if name == "subs":
            item.add_argument("--lang", default="fr,en", help="langues par ordre de préférence")
        else:
            item.add_argument("--lang", default=None, help="langue de l'audio (ex. fr) ; vide = détection")
            item.add_argument("--model", default="small", help="modèle faster-whisper (tiny, base, small, medium)")
    item = sub.add_parser("transcribe")
    item.add_argument("file")
    item.add_argument("--out", default="transcripts")
    item.add_argument("--lang", default=None)
    item.add_argument("--model", default="small")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    except Failure as failure:
        print(json.dumps({"ok": False, "code": failure.code, "error": failure.message}, ensure_ascii=False, indent=2))
        return failure.code


if __name__ == "__main__":
    sys.exit(main())
