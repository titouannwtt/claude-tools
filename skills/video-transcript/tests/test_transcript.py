import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "transcript.py"
sys.path.insert(0, str(SCRIPT.parent))
import transcript as tr  # noqa: E402

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Bonjour</c>

00:00:03.000 --> 00:00:05.000
Bonjour
le monde

00:00:05.000 --> 00:00:07.000
Bonjour le monde

00:01:00.500 --> 01:02:03.250
Fin de la vidéo
"""

FAKE_YTDLP = """#!{python}
import os, sys
args = sys.argv[1:]
mode = os.environ.get("FAKE_MODE", "subs")
if mode == "blocked":
    print("ERROR: [youtube] abc: HTTP Error 429: Too Many Requests", file=sys.stderr)
    sys.exit(1)
if "--write-subs" in args:
    if mode == "nosubs":
        sys.exit(0)
    template = args[args.index("-o") + 1]
    vid = args[-1].split("v=")[-1]
    path = template.replace("%(id)s", vid).replace("%(ext)s", "fr.vtt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(os.environ["FAKE_VTT"])
    sys.exit(0)
sys.exit(3)
"""


class ParsingTest(unittest.TestCase):
    def test_id_from_url_formats(self):
        vid = "dQw4w9WgXcQ"
        for url in ("https://www.youtube.com/watch?v=%s&t=10" % vid, "https://youtu.be/%s" % vid,
                    "https://www.youtube.com/shorts/%s" % vid, vid):
            self.assertEqual(tr.video_id_from_url(url), vid)

    def test_invalid_url(self):
        with self.assertRaises(tr.Failure) as ctx:
            tr.video_id_from_url("https://example.com/not-a-video")
        self.assertEqual(ctx.exception.code, tr.EXIT_INVALID)

    def test_vtt_merges_repeats_and_tags(self):
        segments = tr.parse_vtt(VTT)
        self.assertEqual([s["text"] for s in segments], ["Bonjour le monde", "Fin de la vidéo"])
        self.assertEqual(segments[0]["start"], 1.0)
        self.assertEqual(segments[0]["end"], 7.0)
        self.assertEqual(segments[1]["start"], 60.5)
        self.assertEqual(segments[1]["end"], 3723.25)

    def test_readable_timestamp(self):
        self.assertEqual(tr.fmt_timestamp(3723.9), "01:02:03")
        self.assertEqual(tr.fmt_timestamp(61), "00:01:01")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        fake = self.dir / "bin"
        fake.mkdir()
        exe = fake / "yt-dlp"
        exe.write_text(FAKE_YTDLP.format(python=sys.executable), encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=str(fake) + os.pathsep + os.environ["PATH"], FAKE_VTT=VTT,
                        CLAUDE_TOOLS_LOCAL=str(self.dir / "absent.env"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, **extra):
        env = dict(self.env, **extra)
        result = subprocess.run([sys.executable, str(SCRIPT)] + list(args), capture_output=True, text=True, env=env)
        return result.returncode, json.loads(result.stdout)

    def test_route_a_subtitles_writes_txt_and_json(self):
        code, data = self.run_cli("subs", "https://youtu.be/dQw4w9WgXcQ", "--out", str(self.dir / "out"))
        self.assertEqual(code, 0)
        self.assertEqual(data["method"], "subs")
        self.assertEqual(data["segments"], 2)
        txt = Path(data["txt"]).read_text(encoding="utf-8")
        self.assertIn("[00:00:01] Bonjour le monde", txt)
        self.assertTrue(Path(data["json"]).is_file())

    def test_no_subtitles_returns_code_3(self):
        code, data = self.run_cli("subs", "dQw4w9WgXcQ", "--out", str(self.dir / "out"), FAKE_MODE="nosubs")
        self.assertEqual(code, 3)
        self.assertFalse(data["ok"])
        self.assertIn("audio command", data["error"])

    def test_block_returns_code_4_without_automatic_proxy(self):
        code, data = self.run_cli("subs", "dQw4w9WgXcQ", "--out", str(self.dir / "out"), FAKE_MODE="blocked")
        self.assertEqual(code, 4)
        self.assertIn("429", data["error"])

    def test_requested_proxy_without_configuration_returns_code_5(self):
        empty = self.dir / "empty.env"
        empty.write_text("", encoding="utf-8")  # isolates the test from the machine's real local.env
        code, data = self.run_cli("subs", "dQw4w9WgXcQ", "--use-proxy", "--out", str(self.dir / "out"),
                                  CLAUDE_TOOLS_LOCAL=str(empty))
        self.assertEqual(code, 5)
        self.assertIn("IPROYAL_RESIDENTIAL_URL", data["error"])

    def test_doctor_never_reveals_proxy_value(self):
        local = self.dir / "local.env"
        local.write_text("IPROYAL_RESIDENTIAL_URL=http://user:secret@proxy.example:1234\n", encoding="utf-8")
        code, data = self.run_cli("doctor", CLAUDE_TOOLS_LOCAL=str(local))
        self.assertEqual(code, 0)
        self.assertTrue(data["proxy_configured"])
        self.assertNotIn("secret", json.dumps(data))


if __name__ == "__main__":
    unittest.main()
