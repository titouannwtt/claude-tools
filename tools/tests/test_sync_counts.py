import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_counts as sc  # noqa: E402

HERO = '<text><tspan id="n-agents" fill="#D97757">1</tspan> agents</text><tspan id="n-skills" x="2">1</tspan> skills'
README = "| `skills/` | 1 skills, each with a tested script |\n| `kit/agents/` | 1 subagents, each pinned |\n[`a`](skills/a)\n"


class SyncCountsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("a", "b", "c"):
            (self.root / "skills" / name).mkdir(parents=True)
            (self.root / "skills" / name / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")
        (self.root / "skills" / "sans-skill-md").mkdir()
        (self.root / "kit" / "agents").mkdir(parents=True)
        for name in ("x", "y"):
            (self.root / "kit" / "agents" / ("%s.md" % name)).write_text("x", encoding="utf-8")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "hero.svg").write_text(HERO, encoding="utf-8")
        (self.root / "README.md").write_text(README, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_met_a_jour_bannière_et_readme(self):
        self.assertEqual(sc.main(["--root", str(self.root)]), 0)
        hero = (self.root / "assets" / "hero.svg").read_text(encoding="utf-8")
        self.assertIn('id="n-skills" x="2">3</tspan>', hero)
        self.assertIn('id="n-agents" fill="#D97757">2</tspan>', hero)
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("3 skills, each", readme)
        self.assertIn("2 subagents,", readme)

    def test_check_signale_sans_ecrire_puis_passe(self):
        self.assertEqual(sc.main(["--root", str(self.root), "--check"]), 1)
        self.assertIn(">1</tspan>", (self.root / "assets" / "hero.svg").read_text(encoding="utf-8"))
        sc.main(["--root", str(self.root)])
        self.assertEqual(sc.main(["--root", str(self.root), "--check"]), 0)

    def test_skills_manquants_dans_le_readme(self):
        notes = sc.missing(self.root, ["a", "b"])
        self.assertEqual(notes, ["b : ligne absente du tableau Skills de README.md"])


if __name__ == "__main__":
    unittest.main()
