import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_url.py"
sys.path.insert(0, str(SCRIPT.parent))
sys.path.insert(0, str(SCRIPT.parents[3] / "lib"))
import fetch_url as fu  # noqa: E402

PAGE = "<html><head><style>p{}</style><script>var x=1</script></head><body><h1>Titre</h1><p>Un  texte</p></body></html>"


class Handler(BaseHTTPRequestHandler):
    """Sert la même page à tous, sauf aux accès directs sur /bloque (403) : un accès via proxy arrive en URL absolue."""

    def do_GET(self):
        via_proxy = self.path.startswith("http://")
        path = self.path.split("127.0.0.1", 1)[-1].split("/", 1)[-1] if via_proxy else self.path.lstrip("/")
        if path.startswith("absent"):
            self.send_response(404)
        elif path.startswith("bloque") and not via_proxy:
            self.send_response(403)
        elif path.startswith("bloque-toujours"):
            self.send_response(403)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def log_message(self, *args):
        pass


class FetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = Path(self.tmp.name) / "local.env"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, proxy=True):
        self.env.write_text(("IPROYAL_RESIDENTIAL_URL=%s\n" % self.base) if proxy else "", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT)] + list(args), capture_output=True, text=True,
                                env={"CLAUDE_TOOLS_LOCAL": str(self.env), "PATH": "/usr/bin:/bin", "no_proxy": ""})
        return result.returncode, json.loads(result.stdout)

    def test_acces_direct(self):
        code, data = self.run_cli(self.base + "/ok", "--text")
        self.assertEqual((code, data["via"], data["status"]), (0, "direct", 200))
        self.assertEqual(data["text"], "Titre\n\nUn texte")

    def test_repli_proxy_apres_403(self):
        code, data = self.run_cli(self.base + "/bloque")
        self.assertEqual((code, data["via"]), (0, "proxy"))

    def test_blocage_sans_proxy_configure(self):
        code, data = self.run_cli(self.base + "/bloque", proxy=False)
        self.assertEqual(code, 4)
        self.assertIn("proxy de repli non configuré", data["error"])

    def test_no_proxy_n_utilise_jamais_le_proxy(self):
        code, _ = self.run_cli(self.base + "/bloque", "--no-proxy")
        self.assertEqual(code, 4)

    def test_404_ne_declenche_pas_le_proxy(self):
        code, data = self.run_cli(self.base + "/absent")
        self.assertEqual((code, data["status"]), (6, 404))

    def test_url_invalide(self):
        code, _ = self.run_cli("ftp://exemple.example/x")
        self.assertEqual(code, 2)

    def test_sortie_fichier(self):
        out = Path(self.tmp.name) / "page.txt"
        code, data = self.run_cli(self.base + "/ok", "--text", "--out", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(out.read_text(encoding="utf-8"), "Titre\n\nUn texte")
        self.assertNotIn("text", data)

    def test_le_proxy_n_apparait_jamais_dans_la_sortie(self):
        _, data = self.run_cli(self.base + "/bloque")
        self.assertNotIn("127.0.0.1", json.dumps(data.get("via", "")))

    def test_html_to_text(self):
        self.assertEqual(fu.html_to_text(PAGE), "Titre\n\nUn texte")


if __name__ == "__main__":
    unittest.main()
