import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS / "check_repo.py"
sys.path.insert(0, str(TOOLS))
import check_repo as cr  # noqa: E402

# Valeurs sensibles assemblées à l'exécution : le fichier de test reste lui-même propre.
FAKE_KEY = "sk-ant-" + "a" * 30
FAKE_MAIL = "someone" + "@" + "corp.io"
FAKE_IP = ".".join(["8", "8", "8", "8"])
FAKE_HOME = "/" + "Users" + "/zorglub/projet"
FAKE_URL = "http://bob:" + "pw" + "@proxy.corp.io:80"


class ScanTextTest(unittest.TestCase):
    def kinds(self, text, terms=()):
        return {kind for kind, _ in cr.scan_text(text, list(terms))}

    def test_detecte_chaque_famille(self):
        self.assertIn("clé API Anthropic", self.kinds(FAKE_KEY))
        self.assertIn("adresse e-mail", self.kinds(FAKE_MAIL))
        self.assertIn("adresse IP", self.kinds(FAKE_IP))
        self.assertIn("chemin personnel", self.kinds(FAKE_HOME))
        self.assertIn("identifiants dans une URL", self.kinds(FAKE_URL))
        self.assertIn("terme interdit", self.kinds("auteur Zorglub", ["zorglub"]))

    def test_valeurs_neutres_acceptees(self):
        neutres = ["contact@example.com", "123456+bot@users.noreply.github.com", "127.0.0.1", "192.0.2.10",
                   "/home/user/x", "/Users/you/x", "http://user:secret@proxy.example:1234", "version 1.2.3"]
        for text in neutres:
            with self.subTest(text=text):
                self.assertEqual(cr.scan_text(text, []), [])

    def test_ne_renvoie_jamais_la_valeur(self):
        for _, number in cr.scan_text(FAKE_KEY, []):
            self.assertIsInstance(number, int)

    def test_termes_depuis_local_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "local.env"
            env.write_text("AUTRE=1\nFORBIDDEN_TERMS=Alpha, beta\n", encoding="utf-8")
            self.assertEqual(cr.load_terms(str(env)), ["alpha", "beta"])
            self.assertEqual(cr.load_terms(str(Path(tmp) / "absent.env")), [])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Dev Neutre")
        self.git("config", "user.email", "dev@users.noreply.github.com")
        (self.root / "local.env").write_text("FORBIDDEN_TERMS=zorglub\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root)] + list(args), check=True, capture_output=True)

    def run_check(self, *extra):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)] + list(extra),
                                capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def stage(self, name, content):
        (self.root / name).write_text(content, encoding="utf-8")
        self.git("add", name)

    def test_index_propre_passe(self):
        self.stage("a.md", "rien de personnel ici\n")
        code, out, _ = self.run_check()
        self.assertEqual((code, out), (0, ""))

    def test_index_avec_secret_est_refuse_sans_afficher_la_valeur(self):
        self.stage("a.md", "ligne 1\nclé : %s\n" % FAKE_KEY)
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("a.md:2", out)
        self.assertNotIn(FAKE_KEY, out)

    def test_seul_le_contenu_indexe_compte(self):
        self.stage("a.md", "propre\n")
        (self.root / "a.md").write_text("sale %s\n" % FAKE_KEY, encoding="utf-8")  # modifié mais non indexé
        code, _, _ = self.run_check()
        self.assertEqual(code, 0)

    def test_identite_git_avec_terme_interdit(self):
        self.git("config", "user.name", "Zorglub Dupont")
        self.stage("a.md", "propre\n")
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("identité git (user.name)", out)

    def test_depot_inexistant_renvoie_code_2(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "absent")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
