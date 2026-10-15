import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import repofixtures as fx

import counts


class CountsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def config(self, counters, **extra):
        self.write(".showcase.json", json.dumps(dict({"counters": counters}, **extra)))

    def read(self, name):
        return (self.root / name).read_text(encoding="utf-8")


class SyncTest(CountsCase):
    def setUp(self):
        super().setUp()
        for name in ("a", "b", "c"):
            self.write("plugins/%s.md" % name, "x\n")
        self.write("plugins/README.md", "index\n")
        self.config({"vst": {"glob": "plugins/*.md", "exclude": ["README.md"]}})
        self.write("README.md", "Over <!-- count:vst -->57<!-- /count --> plugins. 2026 and v1.2.3.\n")
        self.write("assets/hero.svg", '<svg><text><tspan data-count="vst">57</tspan> VSTs</text></svg>\n')

    def test_sync_rewrites_markers_and_svg(self):
        result = counts.sync(self.root)
        self.assertEqual(result["counters"], {"vst": 3})
        self.assertEqual(sorted(result["updated"]), ["README.md", "assets/hero.svg"])
        self.assertIn("<!-- count:vst -->3<!-- /count -->", self.read("README.md"))
        self.assertIn('<tspan data-count="vst">3</tspan>', self.read("assets/hero.svg"))
        self.assertEqual(counts.sync(self.root, check=True)["stale"], [])

    def test_check_exit_code(self):
        code, data = fx.run_cli(counts, ["counts", "sync", str(self.root), "--check"])
        self.assertEqual(code, 4)
        self.assertEqual(sorted(data["stale"]), ["README.md", "assets/hero.svg"])
        self.assertIn("57", self.read("README.md"))
        self.assertEqual(fx.run_cli(counts, ["counts", "sync", str(self.root)])[0], 0)
        self.assertEqual(fx.run_cli(counts, ["counts", "sync", str(self.root), "--check"])[0], 0)

    def test_unknown_marker_fails_check(self):
        self.write("NOTES.md", "<!-- count:ghost -->1<!-- /count -->\n")
        code, data = fx.run_cli(counts, ["counts", "sync", str(self.root), "--check"])
        self.assertEqual(code, 4)
        self.assertEqual(data["unknown"], [{"file": "NOTES.md", "name": "ghost"}])

    def test_format_round_and_suffix(self):
        for i in range(12):
            self.write("many/%d.md" % i, "x\n")
        self.config({"many": {"glob": "many/*.md"}, "few": {"glob": "plugins/*.md"}},
                    format={"many": {"round": 10, "suffix": "+"}, "few": {"round": 10, "suffix": "+"}})
        self.write("README.md", "<!-- count:many -->0<!-- /count --> and <!-- count:few -->0<!-- /count -->\n")
        counts.sync(self.root)
        self.assertEqual(self.read("README.md").strip(),
                         "<!-- count:many -->10+<!-- /count --> and <!-- count:few -->4<!-- /count -->")

    def test_counter_kinds(self):
        for name in ("p/one", "p/two"):
            (self.root / name).mkdir(parents=True)
        self.write("data/list.txt", "# comment\none\n\ntwo\n three\n")
        self.write("data/items.json", json.dumps({"items": [1, 2, 3, 4], "deep": {"list": [[1], [2]]}}))
        self.config({"packs": {"dirs": "p/*"}, "lines": {"lines": "data/list.txt"},
                     "items": {"json": "data/items.json", "path": "items"},
                     "deep": {"json": "data/items.json", "path": "deep.list"},
                     "multi": {"glob": ["plugins/*.md", "data/*.txt"], "exclude": ["README.md"]}})
        self.assertEqual(counts.sync(self.root, check=True)["counters"],
                         {"packs": 2, "lines": 3, "items": 4, "deep": 2, "multi": 4})

    def test_invalid_configuration(self):
        self.config({"x": {"glob": "../outside/*"}})
        self.assertEqual(fx.run_cli(counts, ["counts", "sync", str(self.root)])[0], 2)
        self.config({"x": {"nothing": 1}})
        self.assertEqual(fx.run_cli(counts, ["counts", "sync", str(self.root)])[0], 2)
        (self.root / ".showcase.json").unlink()
        self.assertEqual(fx.run_cli(counts, ["counts", "sync", str(self.root)])[0], 6)


class LintTest(CountsCase):
    def lint(self, readme, **files):
        self.write("README.md", readme)
        for name, content in files.items():
            self.write(name, content)
        return counts.lint(self.root)

    def kinds(self, result):
        return [(i["kind"], i["number"]) for i in result["items"]]

    def test_flags_counts_not_years_versions_measures_or_markers(self):
        result = self.lint("\n".join([
            "# Plugins",
            "We ship 57 VSTs and 12 free plugins.",
            "Released in 2026, version v1.2.3 and 1.2.",
            "Runs 75 % faster, uses 120 MB and 30 fps in 5 minutes.",
            "Total: <!-- count:vst -->57<!-- /count --> plugins.",
            "Done on 15 October, step 3 of 4, Python 3, GPT-4, 3D, 2FA.",
            "Install in 3 steps.",
            "```",
            "99 plugins in code",
            "```",
            "[57 plugins](https://example.org/57-plugins) ![99 plugins](x.png) `88 plugins`",
        ]))
        self.assertEqual(self.kinds(result), [("count-like", "57"), ("count-like", "12"), ("measure", "75"),
                                              ("measure", "120"), ("measure", "30"), ("measure", "5"),
                                              ("count-like", "57")])
        self.assertEqual(result["warnings"], 3)
        self.assertEqual(result["items"][0]["line"], 2)
        self.assertEqual(result["items"][0]["noun"], "VSTs")
        self.assertEqual(result["items"][-1]["line"], 11)

    def test_exit_code(self):
        self.write("README.md", "57 VSTs\n")
        self.assertEqual(fx.run_cli(counts, ["counts", "lint", str(self.root)])[0], 4)
        self.write("README.md", "Many VSTs, released in 2026, 75 % done.\n")
        code, data = fx.run_cli(counts, ["counts", "lint", str(self.root)])
        self.assertEqual(code, 0)
        self.assertEqual(data["info"], 1)

    def test_svg_text_only(self):
        svg = ('<svg width="57" height="40"><rect x="57" y="12"/>'
               '<text x="1" y="2">Over 57 strategies</text>'
               '<text><tspan data-count="s">57</tspan> strategies</text></svg>')
        result = self.lint("# Hi\n", **{"assets/hero.svg": svg})
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["file"], "assets/hero.svg")

    def test_proposes_a_counter_when_a_folder_matches(self):
        (self.root / "strategies" / "alpha").mkdir(parents=True)
        (self.root / "strategies" / "beta").mkdir()
        self.write("plugins/a.md", "x\n")
        self.write("plugins/README.md", "x\n")
        result = self.lint("57 strategies and 40 plugins\n")
        by_noun = {i["noun"]: i for i in result["items"]}
        self.assertEqual(by_noun["strategies"]["counter"]["config"], {"dirs": "strategies/*"})
        self.assertEqual(by_noun["strategies"]["counter"]["marker"], "<!-- count:strategies -->57<!-- /count -->")
        self.assertEqual(by_noun["plugins"]["counter"]["config"], {"glob": "plugins/*", "exclude": ["README.md"]})
        self.assertIn('{"counters": {"strategies": {"dirs": "strategies/*"}}}', by_noun["strategies"]["suggestion"])

    def test_suggests_badge_or_rewording(self):
        result = self.lint("Loved by 2k stars? 1,200 downloads and 300 users.\n")
        suggestions = {i["noun"]: i["suggestion"] for i in result["items"]}
        self.assertIn("--kind stars", suggestions["stars"])
        self.assertIn("--kind downloads", suggestions["downloads"])
        self.assertIn("Reword", suggestions["users"])

    def test_ignore_marker_and_other_markdown(self):
        result = self.lint("57 plugins <!-- showcase: ignore -->\n40 tools\n", **{"NOTES.md": "9 files\n"})
        self.assertEqual([(i["file"], i["number"]) for i in result["items"]], [("README.md", "40"),
                                                                              ("NOTES.md", "9")])


class BadgeTest(CountsCase):
    def test_files_badge(self):
        code, data = fx.run_cli(counts, ["counts", "badge", str(self.root), "--kind", "files", "--path", "plugins",
                                         "--slug", "acme/demo", "--color", "#0a7cff"])
        self.assertEqual(code, 0)
        self.assertEqual(data["url"], "https://img.shields.io/badge/dynamic/json?url="
                         "https%3A%2F%2Fapi.github.com%2Frepos%2Facme%2Fdemo%2Fcontents%2Fplugins%3Fref%3Dmain"
                         "&query=%24.length&label=files&color=0a7cff")
        self.assertTrue(data["markdown"].startswith("[![files](https://img.shields.io/badge/dynamic/json"))
        self.assertTrue(data["markdown"].endswith("(https://github.com/acme/demo/tree/main/plugins)"))
        self.assertTrue(any("1,000" in c for c in data["caveats"]))
        self.assertTrue(any("files AND the folders" in c for c in data["caveats"]))

    def test_other_kinds_and_slug_from_origin(self):
        env = fx.isolate()
        self.addCleanup(env.stop_and_clean)
        repo = fx.make_repo(self.root, "r", origin="github.com:acme/demo.git")
        expected = {"stars": "github/stars/acme/demo", "forks": "github/forks/acme/demo",
                    "release": "github/v/release/acme/demo", "last-commit": "github/last-commit/acme/demo",
                    "license": "github/license/acme/demo", "downloads": "github/downloads/acme/demo/total"}
        for kind, path in expected.items():
            code, data = fx.run_cli(counts, ["counts", "badge", str(repo.path), "--kind", kind, "--label", "My Label"])
            self.assertEqual(code, 0)
            self.assertEqual(data["url"], "https://img.shields.io/%s?label=My%%20Label" % path)

    def test_errors(self):
        self.assertEqual(fx.run_cli(counts, ["counts", "badge", str(self.root), "--kind", "stars"])[0], 2)
        self.assertEqual(fx.run_cli(counts, ["counts", "badge", str(self.root), "--kind", "stars", "--slug",
                                             "a/b", "--color", "zz!"])[0], 2)


class InstallActionTest(CountsCase):
    def test_install_refuse_force_and_standalone_run(self):
        code, data = fx.run_cli(counts, ["counts", "install-action", str(self.root), "--branch", "main"])
        self.assertEqual(code, 0)
        script = self.root / ".github" / "scripts" / "showcase_counts.py"
        workflow = self.root / ".github" / "workflows" / "showcase-counts.yml"
        self.assertEqual(data["written"], [".github/scripts/showcase_counts.py",
                                           ".github/workflows/showcase-counts.yml"])
        self.assertEqual(script.read_text(), Path(counts.__file__).read_text())
        text = workflow.read_text()
        for expected in ('branches: ["main"]', "workflow_dispatch:", "contents: write", "actions/checkout@v4",
                         "python3 .github/scripts/showcase_counts.py sync .", "git diff --quiet",
                         'git config user.name "github-actions[bot]"',
                         "41898282+github-actions[bot]@users.noreply.github.com",
                         'git commit -am "chore: update counters"', "git push"):
            self.assertIn(expected, text)
        self.assertTrue(any("missing" in note for note in data["notes"]))

        code, data = fx.run_cli(counts, ["counts", "install-action", str(self.root)])
        self.assertEqual(code, 6)
        self.assertIn("--force", data["error"])
        workflow.write_text("custom\n")
        self.assertEqual(fx.run_cli(counts, ["counts", "install-action", str(self.root), "--force"])[0], 0)
        self.assertIn("workflow_dispatch", workflow.read_text())

        self.write("plugins/a.md", "x\n")
        self.write(".showcase.json", json.dumps({"counters": {"p": {"glob": "plugins/*.md"}}}))
        self.write("README.md", "<!-- count:p -->0<!-- /count -->\n")
        result = subprocess.run([sys.executable, str(script), "sync", str(self.root)], capture_output=True, text=True,
                                cwd=str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["updated"], ["README.md"])
        self.assertIn("<!-- count:p -->1<!-- /count -->", self.read("README.md"))
        result = subprocess.run([sys.executable, str(script), "lint", "."], capture_output=True, text=True,
                                cwd=str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["warnings"], 0)

    def test_script_is_standalone(self):
        tree = ast.parse(Path(counts.__file__).read_text(encoding="utf-8"))
        allowed = {"argparse", "fnmatch", "html", "json", "re", "shutil", "subprocess", "sys", "traceback",
                   "unicodedata", "pathlib", "urllib.parse"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertLessEqual(imported, allowed)


if __name__ == "__main__":
    unittest.main()
