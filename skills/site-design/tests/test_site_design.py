import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "site_design.py"
sys.path.insert(0, str(SCRIPT.parent))
import site_design as sd  # noqa: E402

PAGE = """<!doctype html><html lang="en"><head><title>Demo</title><meta name="theme-color" content="#112233">
<style>
:root{--brand:#ff0066;--space:24px}
body{margin:0;font-family:Georgia,serif;color:#222}
h1{font-size:40px;color:#ff0066;margin:0 0 24px}
.card{background:#f5f5f5;padding:24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.2)}
@media (max-width:600px){.card{padding:12px}}
@media (prefers-color-scheme:dark){body{color:#eee}}
</style></head><body><h1>Demo title</h1><div class="card"><p>Text</p><img src="x.png"></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/blocked"):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def log_message(self, *args):
        pass


class PureTest(unittest.TestCase):
    def test_to_hex(self):
        self.assertEqual(sd.to_hex("rgb(255, 0, 102)"), "#ff0066")
        self.assertEqual(sd.to_hex("rgba(0, 0, 0, 0.5)"), "#00000080")
        self.assertEqual(sd.to_hex("transparent"), "transparent")

    def test_top_groups_after_conversion(self):
        counter = {"rgb(0, 0, 0)": 3, "rgba(0, 0, 0, 1)": 2, "rgb(255, 255, 255)": 1}
        self.assertEqual(sd.top(counter, 5, sd.to_hex)[0], {"value": "#000000", "count": 5})

    def test_parse_proxy(self):
        self.assertEqual(sd.parse_proxy("http://u:p@proxy.example:1234"),
                         {"server": "http://proxy.example:1234", "username": "u", "password": "p"})

    def test_main_family(self):
        self.assertEqual(sd.first_family('"Inter", system-ui, sans-serif'), "Inter")


class BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        doctor = subprocess.run([sys.executable, str(SCRIPT), "doctor"], capture_output=True, text=True)
        info = json.loads(doctor.stdout or "{}")
        if not (info.get("playwright") and info.get("chromium")):
            raise unittest.SkipTest("Playwright or Chromium missing")
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server"):
            cls.server.shutdown()

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT)] + list(args), capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def test_full_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, data = self.run_cli("analyze", self.base + "/", "--out", tmp, "--widths", "375,1000")
            self.assertEqual(code, 0, data)
            self.assertEqual(data["screenshots"], ["shot-375.png", "shot-1000.png"])
            design = json.loads((Path(tmp) / "design.json").read_text(encoding="utf-8"))["summary"]
            self.assertEqual(design["css_variables"]["--brand"], "#ff0066")
            self.assertIn("#ff0066", [c["value"] for c in design["palette"]["text"]])
            self.assertIn("40px", [s["value"] for s in design["typography"]["sizes"]])
            self.assertEqual(design["typography"]["families"][0]["value"], "Georgia")
            self.assertIn("max 600px", design["breakpoints"])
            self.assertTrue(design["dark_mode_in_css"])
            self.assertEqual(design["radii"][0]["value"], "12px")
            self.assertEqual(design["counts"]["imagesWithoutAlt"], 1)
            summary = (Path(tmp) / "summary.md").read_text(encoding="utf-8")
            self.assertIn("#ff0066", summary)
            self.assertTrue((Path(tmp) / "shot-375.png").stat().st_size > 500)

    def test_blocked_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, data = self.run_cli("analyze", self.base + "/blocked", "--out", tmp)
            self.assertEqual(code, 4, data)

    def test_invalid_url(self):
        code, _ = self.run_cli("analyze", "ftp://site.example/")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
