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

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "yt_download.py"
sys.path.insert(0, str(SCRIPT.parent))
import yt_download as yd  # noqa: E402

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


FAKE_YTDLP = """#!{python}
import os, sys
args = sys.argv[1:]
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "blocked":
    print("ERROR: [youtube] abc: HTTP Error 429: Too Many Requests", file=sys.stderr); sys.exit(1)
if "--dump-single-json" in args:
    print('{{"id":"dQw4w9WgXcQ","title":"T","formats":[{{"height":720,"vcodec":"avc1"}},{{"height":360,"vcodec":"avc1"}},{{"height":null,"vcodec":"none"}}]}}'); sys.exit(0)
template = args[args.index("-o") + 1]
path = template.replace("%(title).80s", "Title").replace("%(id)s", "dQw4w9WgXcQ").replace("%(ext)s", "mp4")
open(path, "wb").write(b"data")
open(os.environ["FAKE_ARGS"], "w").write(" ".join(args))
print(path)
"""


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
        bindir = self.dir / "bin"
        bindir.mkdir()
        fake = bindir / "yt-dlp"
        fake.write_text(FAKE_YTDLP.format(python=sys.executable), encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.bindir = str(bindir)
        (self.dir / "empty.env").write_text("", encoding="utf-8")  # isolates from the machine's real local.env

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, **env):
        base = {"PATH": self.bindir + ":/usr/bin:/bin", "YT_THUMB_BASE": self.base + "/vi",
                "FAKE_ARGS": str(self.dir / "args.txt"), "CLAUDE_TOOLS_LOCAL": str(self.dir / "empty.env")}
        base.update(env)
        result = subprocess.run([sys.executable, str(SCRIPT)] + list(args), capture_output=True, text=True, env=base)
        return result.returncode, json.loads(result.stdout)

    def test_thumbnail_skips_missing_or_fake_sizes(self):
        code, data = self.run_cli("thumbnail", "dQw4w9WgXcQ", "--out", str(self.dir / "o"))
        self.assertEqual((code, data["size_name"]), (0, "hqdefault"))
        self.assertTrue(Path(data["file"]).exists())

    def test_thumbnail_not_found(self):
        code, _ = self.run_cli("thumbnail", "empty000000", "--out", str(self.dir / "o"))
        self.assertEqual(code, 8)

    def test_invalid_url(self):
        code, _ = self.run_cli("video", "https://exemple.example/x")
        self.assertEqual(code, 2)

    def test_video_requests_height_and_returns_file(self):
        code, data = self.run_cli("video", "dQw4w9WgXcQ", "--height", "720", "--out", str(self.dir / "o"))
        self.assertEqual(code, 0)
        self.assertTrue(data["file"].endswith("Title [dQw4w9WgXcQ].mp4"))
        passed = (self.dir / "args.txt").read_text()
        self.assertIn("height<=720", passed)
        self.assertNotIn("--proxy", passed)

    def test_audio_extracted_as_mp3(self):
        code, _ = self.run_cli("audio", "dQw4w9WgXcQ", "--out", str(self.dir / "o"))
        self.assertEqual(code, 0)
        self.assertIn("--audio-format mp3", (self.dir / "args.txt").read_text())

    def test_block_returns_4(self):
        code, data = self.run_cli("video", "dQw4w9WgXcQ", "--out", str(self.dir / "o"), FAKE_MODE="blocked")
        self.assertEqual(code, 4)
        self.assertIn("429", data["error"])

    def test_proxy_without_configuration_returns_5(self):
        code, data = self.run_cli("video", "dQw4w9WgXcQ", "--use-proxy", "--out", str(self.dir / "o"))
        self.assertEqual(code, 5)
        self.assertIn("IPROYAL_RESIDENTIAL_URL", data["error"])

    def test_info_lists_heights(self):
        code, data = self.run_cli("info", "dQw4w9WgXcQ")
        self.assertEqual((code, data["heights"]), (0, [360, 720]))

    def test_format_selector(self):
        self.assertIn("height<=480", yd.format_selector(480))


if __name__ == "__main__":
    unittest.main()
