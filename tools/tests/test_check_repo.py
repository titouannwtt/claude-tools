import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS / "check_repo.py"
sys.path.insert(0, str(TOOLS))
import check_repo as cr  # noqa: E402

# Sensitive values assembled at runtime: the test file itself stays clean.
FAKE_KEY = "sk-ant-" + "a" * 30
FAKE_MAIL = "someone" + "@" + "corp.io"
FAKE_IP = ".".join(["8", "8", "8", "8"])
FAKE_HOME = "/" + "Users" + "/zorglub/projet"
FAKE_URL = "http://bob:" + "pw" + "@proxy.corp.io:80"


class ScanTextTest(unittest.TestCase):
    def kinds(self, text, terms=()):
        return {kind for kind, _ in cr.scan_text(text, list(terms))}

    def test_detects_each_family(self):
        self.assertIn("Anthropic API key", self.kinds(FAKE_KEY))
        self.assertIn("email address", self.kinds(FAKE_MAIL))
        self.assertIn("IP address", self.kinds(FAKE_IP))
        self.assertIn("personal path", self.kinds(FAKE_HOME))
        self.assertIn("credentials in a URL", self.kinds(FAKE_URL))
        self.assertIn("forbidden term", self.kinds("author Zorglub", ["zorglub"]))

    def test_neutral_values_accepted(self):
        neutres = ["contact@example.com", "123456+bot@users.noreply.github.com", "127.0.0.1", "192.0.2.10",
                   "/home/user/x", "/Users/you/x", "http://user:secret@proxy.example:1234", "version 1.2.3"]
        for text in neutres:
            with self.subTest(text=text):
                self.assertEqual(cr.scan_text(text, []), [])

    def test_marker_ignores_false_positive(self):
        self.assertEqual(cr.scan_text(FAKE_MAIL + '  # check-repo: ignore', []), [])
        self.assertNotEqual(cr.scan_text(FAKE_MAIL + '  # another comment', []), [])

    def test_never_returns_value(self):
        for _, number in cr.scan_text(FAKE_KEY, []):
            self.assertIsInstance(number, int)

    def test_allowed_term_masks_only_its_string(self):
        self.assertEqual(cr.scan_text("github.com/zorglubdev/x", ["zorglub"], ["zorglubdev"]), [])
        self.assertNotEqual(cr.scan_text("zorglubdev and Zorglub Dupont", ["zorglub"], ["zorglubdev"]), [])

    def test_terms_from_local_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "local.env"
            env.write_text("OTHER=1\nFORBIDDEN_TERMS=Alpha, beta\n", encoding="utf-8")
            self.assertEqual(cr.load_terms(str(env)), ["alpha", "beta"])
            self.assertEqual(cr.load_terms(str(Path(tmp) / "absent.env")), [])


class CommitMessageTest(unittest.TestCase):
    def test_ai_mention_refused(self):
        trailers = ["Co-Authored-By: Claude Opus 5.5 <noreply" + "@anthropic.com>",
                    "co-authored-by: claude", "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)"]
        for trailer in trailers:
            with self.subTest(trailer=trailer):
                self.assertEqual(cr.scan_commit_message("feat: x\n\n" + trailer + "\n"), [3])

    def test_normal_message_and_comments_accepted(self):
        text = "feat(skill): claude-tools supports Claude Code\n\nCo-Authored-By: Alice <alice@example.com>\n# Generated with Claude\n"
        self.assertEqual(cr.scan_commit_message(text), [])

    def test_cli_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg = Path(tmp) / "MSG"
            msg.write_text("fix: y\n\nCo-Authored-By: Claude <x>\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--commit-msg", str(msg)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            msg.write_text("fix: y\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--commit-msg", str(msg)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)


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

    def test_clean_index_passes(self):
        self.stage("a.md", "nothing personal here\n")
        code, out, _ = self.run_check()
        self.assertEqual((code, out), (0, ""))

    def test_index_with_secret_refused_without_showing_value(self):
        self.stage("a.md", "line 1\nkey: %s\n" % FAKE_KEY)
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("a.md:2", out)
        self.assertNotIn(FAKE_KEY, out)

    def test_only_staged_content_counts(self):
        self.stage("a.md", "clean\n")
        (self.root / "a.md").write_text("dirty %s\n" % FAKE_KEY, encoding="utf-8")  # modified but not staged
        code, _, _ = self.run_check()
        self.assertEqual(code, 0)

    def test_git_identity_not_blocking_by_default(self):
        self.git("config", "user.name", "Zorglub Dupont")
        self.stage("a.md", "clean\n")
        code, _, _ = self.run_check()
        self.assertEqual(code, 0)

    def test_git_identity_reported_on_request(self):
        self.git("config", "user.name", "Zorglub Dupont")
        self.stage("a.md", "clean\n")
        code, out, _ = self.run_check("--identity")
        self.assertEqual(code, 1)
        self.assertIn("git identity (user.name)", out)

    def test_git_identity_with_allowed_public_handle(self):
        (self.root / "local.env").write_text("FORBIDDEN_TERMS=zorglub\nALLOWED_TERMS=zorglubx\n", encoding="utf-8")
        self.git("config", "user.name", "zorglubx")
        self.git("config", "user.email", "1+zorglubx@users.noreply.github.com")
        self.stage("a.md", "clean\n")
        code, _, _ = self.run_check("--identity")
        self.assertEqual(code, 0)

    def test_real_git_email_blocks_commit(self):
        self.git("config", "user.email", "dev" + "@" + "corp.io")
        self.stage("a.md", "clean\n")
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("real git email", out)
        self.assertNotIn("corp.io", out)

    def test_missing_repo_returns_code_2(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "absent")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
