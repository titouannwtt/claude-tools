import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAKE_KEY = "sk-ant-" + "b" * 30


def run(cmd, cwd, env=None, check=True):
    full_env = dict(os.environ, GIT_AUTHOR_NAME="Dev Neutre", GIT_AUTHOR_EMAIL="dev@users.noreply.github.com",
                    GIT_COMMITTER_NAME="Dev Neutre", GIT_COMMITTER_EMAIL="dev@users.noreply.github.com")
    full_env.update(env or {})
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=full_env, check=check)


class PublishFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        self.repo = base / "repo"
        self.home = base / "claude-home"
        run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], base)
        self.repo.mkdir()
        run(["git", "init", "-q", "-b", "main"], self.repo)
        run(["git", "config", "user.name", "Dev Neutre"], self.repo)
        run(["git", "config", "user.email", "dev@users.noreply.github.com"], self.repo)
        run(["git", "remote", "add", "origin", str(self.remote)], self.repo)
        shutil.copy(ROOT / "install.sh", self.repo / "install.sh")
        (self.repo / "tools").mkdir()
        for name in ("check_repo.py", "publish_skill.sh"):
            shutil.copy(ROOT / "tools" / name, self.repo / "tools" / name)
        (self.repo / "local.env").write_text("FORBIDDEN_TERMS=zorglub\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("local.env\n", encoding="utf-8")
        run(["git", "add", "-A"], self.repo)
        run(["git", "commit", "-q", "-m", "init"], self.repo)
        run(["git", "push", "-q", "-u", "origin", "main"], self.repo)
        self.env = {"CLAUDE_HOME": str(self.home)}

    def tearDown(self):
        self.tmp.cleanup()

    def make_skill(self, name, body="Skill de démonstration.\n"):
        folder = self.repo / "skills" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text("---\nname: %s\ndescription: demo\n---\n%s" % (name, body), encoding="utf-8")

    def test_install_est_idempotent_et_cree_les_liens_et_le_hook(self):
        self.make_skill("demo")
        first = run(["bash", "install.sh"], self.repo, self.env).stdout
        self.assertIn("lien créé : demo", first)
        self.assertTrue((self.home / "skills" / "demo").is_symlink())
        self.assertTrue((self.repo / ".git" / "hooks" / "pre-commit").is_file())
        second = run(["bash", "install.sh"], self.repo, self.env).stdout
        self.assertIn("lien mis à jour : demo", second)

    def test_publication_propre_pousse_sur_le_distant(self):
        self.make_skill("demo")
        result = run(["bash", "tools/publish_skill.sh", "demo"], self.repo, self.env)
        self.assertIn("poussé :", result.stdout)
        log = run(["git", "log", "--oneline", "-1"], self.remote).stdout
        self.assertIn("feat(skill): demo", log)

    def test_secret_bloque_le_commit_et_laisse_l_index_propre(self):
        self.make_skill("demo", "clé : %s\n" % FAKE_KEY)
        result = run(["bash", "tools/publish_skill.sh", "demo"], self.repo, self.env, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(FAKE_KEY, result.stdout + result.stderr)
        self.assertEqual(run(["git", "diff", "--cached", "--name-only"], self.repo).stdout.strip(), "")
        self.assertEqual(run(["git", "log", "--oneline"], self.remote).stdout.count("\n"), 1)

    def test_terme_interdit_bloque_le_commit(self):
        self.make_skill("demo", "écrit par Zorglub\n")
        result = run(["bash", "tools/publish_skill.sh", "demo"], self.repo, self.env, check=False)
        self.assertEqual(result.returncode, 1)

    def test_nom_invalide_ou_skill_absent(self):
        self.assertEqual(run(["bash", "tools/publish_skill.sh", "Mauvais Nom"], self.repo, self.env, check=False).returncode, 2)
        self.assertEqual(run(["bash", "tools/publish_skill.sh", "absent"], self.repo, self.env, check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
