import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "media_download.py"
sys.path.insert(0, str(SCRIPT.parent))
import media_download as md  # noqa: E402

BIG = b"\xff\xd8" + b"x" * 5000


class Thumbs(BaseHTTPRequestHandler):
    """maxres missing (404), sd = placeholder image too small, hq valid."""

    def do_GET(self):
        name = self.path.rsplit("/", 1)[-1]
        if name.startswith("maxres"):
            self.send_response(404)
            self.end_headers()
            return
        body = b"\xff\xd8tiny" if name.startswith("sd") else BIG
        if "empty000000" in self.path:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# Fake yt-dlp: the id is the last path segment of the link, the title comes from FAKE_TITLE.
FAKE_YTDLP = """#!{python}
import json, os, sys
args = sys.argv[1:]
mode = os.environ.get("FAKE_MODE", "ok")
with open(os.environ["FAKE_ARGS"], "a") as handle:
    handle.write(" ".join(args) + "\\n")
if "--version" in args:
    import datetime; print(datetime.date.today().strftime("%Y.%m.%d")); sys.exit(0)
if "--list-extractors" in args:
    print("Ina\\nInstagram\\nTikTok\\nyoutube\\nyoutube:tab"); sys.exit(0)
url = args[-1]
ident = url.rstrip("/").rsplit("/", 1)[-1].split("=")[-1]
if "badlink" in url:
    print("ERROR: [generic] x: Unable to download webpage", file=sys.stderr); sys.exit(1)
if mode == "blocked":
    print("ERROR: [youtube] abc: HTTP Error 429: Too Many Requests", file=sys.stderr); sys.exit(1)
if mode == "login":
    print("ERROR: [Instagram] abc: Instagram sent an empty media response. Check if this post is accessible in "
          "your browser without being logged-in.", file=sys.stderr); sys.exit(1)
extractor = os.environ.get("FAKE_EXTRACTOR", "Youtube")
info = {{"id": ident, "title": os.environ.get("FAKE_TITLE", "Caf\\u00e9 d\\u00e9j\\u00e0 vu!"), "uploader": "Someone",
        "upload_date": "20240131", "duration": 12, "webpage_url": url, "extractor_key": extractor,
        "formats": [{{"height": 720, "vcodec": "avc1"}}, {{"height": 360, "vcodec": "avc1"}},
                    {{"height": None, "vcodec": "none"}}]}}
if "--dump-single-json" in args and "--skip-download" in args:
    print(json.dumps(info)); sys.exit(0)
template = args[args.index("-o") + 1]
ext = "mp3" if "--audio-format" in args else "mp4"
path = template.replace("%(id)s", ident).replace("%(ext)s", ext)
if mode == "noaudio":
    print(json.dumps(info)); sys.exit(0)
open(path, "wb").write(b"data")
# a leftover intermediate video, as yt-dlp leaves one when it extracts audio
open(path.rsplit(".", 1)[0] + ".webm", "wb").write(b"video")
print(json.dumps(info))
"""


class PureTest(unittest.TestCase):
    def test_slugify_ascii_and_short(self):
        self.assertEqual(md.slugify("Café déjà vu!"), "cafe-deja-vu")
        self.assertEqual(md.slugify("日本語"), "")
        slug = md.slugify("word " * 40)
        self.assertLessEqual(len(slug), 50)
        self.assertFalse(slug.endswith("-"))

    def test_choose_slug_collision_adds_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(md.choose_slug("Same title", "aaa", folder, ".mp3"), "same-title")
            (folder / "same-title.mp3").write_bytes(b"x")
            (folder / "same-title.json").write_text(json.dumps({"id": "aaa"}), encoding="utf-8")
            self.assertEqual(md.choose_slug("Same title", "aaa", folder, ".mp3"), "same-title")  # same id: overwrite
            self.assertEqual(md.choose_slug("Same title", "bbb", folder, ".mp3"), "same-title-bbb")

    def test_choose_slug_empty_title_uses_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(md.choose_slug("日本語", "id1", Path(tmp), ".mp3", "TikTok"), "tiktok")

    def test_platform_from_url(self):
        cases = {"https://www.youtube.com/shorts/abcdefghijk": "YouTube", "https://youtu.be/abcdefghijk": "YouTube",
                 "https://m.youtube.com/watch?v=abcdefghijk": "YouTube",
                 "https://www.instagram.com/reel/Cxyz/": "Instagram", "https://vm.tiktok.com/ZM123/": "TikTok",
                 "https://www.tiktok.com/@a/video/1": "TikTok", "https://www.ina.fr/video/I1": "INA",
                 "https://example.org/a": "example.org"}
        for url, expected in cases.items():
            self.assertEqual(md.platform_from_url(url), expected, url)

    def test_platform_from_info(self):
        self.assertEqual(md.platform_from_info({"extractor_key": "Ina"}, "https://x.test/a"), "INA")
        self.assertEqual(md.platform_from_info({"extractor_key": "Youtube"}, "https://x.test/a"), "YouTube")
        self.assertEqual(md.platform_from_info({"extractor_key": "TikTokVM"}, "https://x.test/a"), "TikTok")
        self.assertEqual(md.platform_from_info({"extractor_key": "InstagramIOS"}, "https://x.test/a"), "Instagram")
        self.assertEqual(md.platform_from_info({}, "https://www.tiktok.com/@a/video/1"), "TikTok")

    def test_normalize_url(self):
        self.assertEqual(md.normalize_url("dQw4w9WgXcQ"), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(md.normalize_url(" https://a.test/x "), "https://a.test/x")
        with self.assertRaises(md.Failure) as raised:
            md.normalize_url("not a link")
        self.assertEqual(raised.exception.code, md.EXIT_INVALID)

    def test_build_options_audio(self):
        options = md.build_options("audio", "/tmp/t", quality=128, cookies="/c.txt", max_filesize="50M")
        joined = " ".join(options)
        self.assertIn("-x --audio-format mp3 --audio-quality 128K", joined)
        self.assertIn("--cookies /c.txt", joined)
        self.assertIn("--max-filesize 50M", joined)
        self.assertIn("--dump-single-json --no-simulate", joined)
        self.assertNotIn("--cookies-from-browser", joined)
        self.assertNotIn("--proxy", joined)

    def test_build_options_video(self):
        joined = " ".join(md.build_options("video", "/tmp/t", height=720, proxy="http://p"))
        self.assertIn("height<=720", joined)
        self.assertIn("--merge-output-format mp4", joined)
        self.assertIn("--proxy http://p", joined)
        self.assertNotIn("--audio-format", joined)

    def test_classify_error(self):
        kind, message = md.classify_error("ERROR: [Instagram] x: rate-limit reached or login required")
        self.assertEqual(kind, "login")
        self.assertIn("--cookies", message)
        kind, message = md.classify_error("ERROR: [Instagram] x: Instagram sent an empty media response")
        self.assertEqual(kind, "login")
        self.assertEqual(md.classify_error("ERROR: [youtube] x: HTTP Error 429: Too Many Requests")[0], "blocked")
        kind, message = md.classify_error("ERROR: [youtube] x: Sign in to confirm you're not a bot. Use --cookies")
        self.assertEqual(kind, "blocked")
        self.assertEqual(md.classify_error("ERROR: [Ina] x: Unable to extract")[0], "other")

    def test_build_metadata(self):
        info = {"id": "abc", "title": "T", "channel": "Chan", "uploader": "U", "upload_date": "20240131",
                "duration": 61, "extractor_key": "Youtube", "webpage_url": "https://www.youtube.com/watch?v=abc"}
        meta = md.build_metadata(info, "https://youtu.be/abc", "/d/t.mp3")
        self.assertEqual(meta, {"fichier": "/d/t.mp3", "titre": "T", "auteur": "Chan", "date": "2024-01-31",
                                "plateforme": "YouTube", "lien": "https://www.youtube.com/watch?v=abc",
                                "duree_s": 61, "id": "abc"})

    def test_upload_date_fallbacks(self):
        self.assertEqual(md.upload_date({"timestamp": 1706659200}), "2024-01-31")
        self.assertIsNone(md.upload_date({}))

    def test_read_links_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.txt"
            path.write_text("# comment\n\nhttps://a.test/1\nTitle - https://b.test/2 notes\nhttps://a.test/1\nplain\n",
                            encoding="utf-8")
            self.assertEqual(md.read_links(["https://c.test/3"], str(path)),
                             ["https://c.test/3", "https://a.test/1", "https://b.test/2", "plain"])

    def test_version_age(self):
        self.assertGreater(md.version_age_days("2020.01.01"), 1000)
        self.assertIsNone(md.version_age_days("weird"))


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Thumbs)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "o"
        bindir = self.dir / "bin"
        bindir.mkdir()
        fake = bindir / "yt-dlp"
        fake.write_text(FAKE_YTDLP.format(python=sys.executable), encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        ffmpeg = bindir / "ffmpeg"
        ffmpeg.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        ffmpeg.chmod(ffmpeg.stat().st_mode | stat.S_IEXEC)
        self.bindir = str(bindir)
        (self.dir / "empty.env").write_text("", encoding="utf-8")  # isolates from the machine's real local.env

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, path=None, **env):
        base = {"PATH": path or (self.bindir + ":/usr/bin:/bin"), "YT_THUMB_BASE": self.base + "/vi",
                "FAKE_ARGS": str(self.dir / "args.txt"), "CLAUDE_TOOLS_LOCAL": str(self.dir / "empty.env")}
        base.update(env)
        result = subprocess.run([sys.executable, str(SCRIPT)] + list(args), capture_output=True, text=True, env=base)
        last = result.stdout.strip().splitlines()[-1]
        return result.returncode, json.loads(last)

    def passed(self):
        return (self.dir / "args.txt").read_text()

    def test_thumbnail_skips_missing_or_fake_sizes(self):
        code, data = self.run_cli("thumbnail", "dQw4w9WgXcQ", "--dossier", str(self.out))
        self.assertEqual((code, data["size_name"]), (0, "hqdefault"))
        self.assertTrue(Path(data["file"]).exists())

    def test_thumbnail_not_found(self):
        code, _ = self.run_cli("thumbnail", "empty000000", "--dossier", str(self.out))
        self.assertEqual(code, 8)

    def test_audio_writes_mp3_and_json_and_removes_video(self):
        code, data = self.run_cli("audio", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "--dossier", str(self.out))
        self.assertEqual(code, 0)
        self.assertEqual(data["echecs"], [])
        mp3 = self.out / "cafe-deja-vu.mp3"
        self.assertEqual(data["fichiers"], [str(mp3)])
        self.assertTrue(mp3.exists())
        meta = json.loads((self.out / "cafe-deja-vu.json").read_text(encoding="utf-8"))
        self.assertEqual(meta, data["metadonnees"][0])
        self.assertEqual(meta["plateforme"], "YouTube")
        self.assertEqual((meta["titre"], meta["auteur"], meta["date"], meta["id"], meta["duree_s"]),
                         ("Café déjà vu!", "Someone", "2024-01-31", "dQw4w9WgXcQ", 12))
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["cafe-deja-vu.json", "cafe-deja-vu.mp3"])
        self.assertIn("--audio-format mp3 --audio-quality 192K", self.passed())

    def test_quality_option(self):
        self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), "--qualite", "128")
        self.assertIn("--audio-quality 128K", self.passed())

    def test_collision_adds_id_and_list_file(self):
        listing = self.dir / "liens.txt"
        listing.write_text("# voix\nhttps://www.tiktok.com/@a/video/111\nhttps://www.tiktok.com/@a/video/222\n",
                           encoding="utf-8")
        code, data = self.run_cli("audio", "--liste", str(listing), "--dossier", str(self.out), FAKE_EXTRACTOR="TikTok")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(Path(f).name for f in data["fichiers"]), ["cafe-deja-vu-222.mp3", "cafe-deja-vu.mp3"])
        self.assertEqual({m["plateforme"] for m in data["metadonnees"]}, {"TikTok"})

    def test_one_failure_does_not_stop_the_others(self):
        code, data = self.run_cli("audio", "https://a.test/badlink", "https://a.test/good", "not a link",
                                  "--dossier", str(self.out))
        self.assertEqual(code, 0)
        self.assertEqual(len(data["fichiers"]), 1)
        self.assertEqual(sorted(e["lien"] for e in data["echecs"]), ["https://a.test/badlink", "not a link"])

    def test_all_invalid_returns_2(self):
        code, data = self.run_cli("audio", "nope", "also nope", "--dossier", str(self.out))
        self.assertEqual(code, 2)
        self.assertEqual((data["fichiers"], len(data["echecs"])), ([], 2))

    def test_no_link_returns_2(self):
        code, data = self.run_cli("audio", "--dossier", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("erreur", data)

    def test_all_downloads_fail_returns_1(self):
        code, data = self.run_cli("audio", "https://a.test/badlink", "--dossier", str(self.out))
        self.assertEqual((code, data["fichiers"]), (1, []))
        self.assertEqual(list(self.out.iterdir()), [])  # temporary folder removed

    def test_login_required_suggests_cookies(self):
        code, data = self.run_cli("audio", "https://www.instagram.com/reel/Cxyz/", "--dossier", str(self.out),
                                  FAKE_MODE="login")
        self.assertEqual(code, 1)
        self.assertIn("--cookies", data["echecs"][0]["erreur"])

    def test_blocked_message(self):
        code, data = self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), FAKE_MODE="blocked")
        self.assertEqual(code, 1)
        self.assertIn("429", data["echecs"][0]["erreur"])

    def test_missing_audio_file_is_a_failure(self):
        code, data = self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), FAKE_MODE="noaudio")
        self.assertEqual(code, 1)
        self.assertIn("no mp3 file", data["echecs"][0]["erreur"])

    def test_cookies_file_passed_and_checked(self):
        cookies = self.dir / "c.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        code, _ = self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), "--cookies", str(cookies))
        self.assertEqual(code, 0)
        self.assertIn("--cookies %s" % cookies, self.passed())
        self.assertNotIn("from-browser", self.passed())
        code, _ = self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), "--cookies", str(self.dir / "no"))
        self.assertEqual(code, 2)

    def test_missing_ffmpeg_returns_5(self):
        only_ytdlp = self.dir / "only"
        only_ytdlp.mkdir()
        (only_ytdlp / "yt-dlp").symlink_to(Path(self.bindir) / "yt-dlp")
        code, data = self.run_cli("audio", "dQw4w9WgXcQ", "--dossier", str(self.out), path=str(only_ytdlp))
        self.assertEqual(code, 5)
        self.assertIn("ffmpeg", data["erreur"])

    def test_video_requests_height_and_returns_mp4(self):
        code, data = self.run_cli("video", "dQw4w9WgXcQ", "--height", "720", "--dossier", str(self.out))
        self.assertEqual(code, 0)
        self.assertEqual([Path(f).suffix for f in data["fichiers"]], [".mp4"])
        self.assertIn("height<=720", self.passed())
        self.assertNotIn("--proxy", self.passed())
        self.assertTrue((self.out / "cafe-deja-vu.json").exists())

    def test_proxy_without_configuration_returns_5(self):
        code, data = self.run_cli("video", "dQw4w9WgXcQ", "--use-proxy", "--dossier", str(self.out))
        self.assertEqual(code, 5)
        self.assertIn("IPROYAL_RESIDENTIAL_URL", data["erreur"])

    def test_info_lists_heights(self):
        code, data = self.run_cli("info", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual((code, data["heights"], data["plateforme"]), (0, [360, 720], "YouTube"))

    def test_info_blocked_returns_4(self):
        code, _ = self.run_cli("info", "dQw4w9WgXcQ", FAKE_MODE="blocked")
        self.assertEqual(code, 4)

    def test_doctor_ok(self):
        code, data = self.run_cli("doctor")
        self.assertEqual(code, 0)
        self.assertEqual((data["ok"], data["problems"]), (True, []))
        self.assertTrue(all(data["extractors"].values()))

    def test_doctor_without_ytdlp_returns_5(self):
        code, data = self.run_cli("doctor", path=self.dir.as_posix() + "/none")
        self.assertEqual(code, 5)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
