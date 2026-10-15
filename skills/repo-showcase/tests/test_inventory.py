import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import repofixtures as fx

import inventory

_env = None


def setUpModule():
    global _env
    _env = fx.isolate()


def tearDownModule():
    _env.stop_and_clean()


class TempRepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def repo(self, files, name="proj", origin=None):
        repo = fx.make_repo(self.tmp, name, origin)
        repo.commit("initial", files)
        return repo


def finding_ids(audit):
    return {f["id"] for f in audit["findings"]}


def find(audit, fid):
    return next(f for f in audit["findings"] if f["id"] == fid)


VITE_APP = {
    "package.json": json.dumps({"name": "demo", "scripts": {"dev": "vite", "build": "vite build"},
                                "dependencies": {"react": "^18"}, "devDependencies": {"vite": "^5"}}),
    "index.html": "<div id='root'></div>\n",
    "src/main.jsx": "import React from 'react'\n",
    "README.md": "# Demo\n\nA small app.\n",
}


class ProjectTypeTest(TempRepoCase):
    def test_vite_web_app(self):
        repo = self.repo(VITE_APP)
        data = inventory.collect(repo.path, remote=False)
        self.assertEqual(data["project_type"]["primary"], "web-app")
        self.assertTrue(any("vite" in e for e in data["project_type"]["evidence"]))
        self.assertEqual(data["run_hints"]["commands"], ["npm run dev"])
        self.assertEqual(data["run_hints"]["urls"], ["http://localhost:5173"])
        hint = next(h for h in data["hints"] if h.startswith("web UI detected"))
        self.assertIn("screenshots recommended", hint)
        self.assertIn("npm run dev on 5173", hint)

    def test_pnpm_and_custom_port(self):
        files = dict(VITE_APP)
        files["package.json"] = json.dumps({"scripts": {"dev": "next dev -p 4100"}, "dependencies": {"next": "14"}})
        files["pnpm-lock.yaml"] = "lockfileVersion: 9\n"
        data = inventory.collect(self.repo(files).path, remote=False)
        self.assertEqual(data["run_hints"]["commands"], ["pnpm dev"])
        self.assertEqual(data["run_hints"]["urls"], ["http://localhost:4100"])

    def test_python_cli_and_library(self):
        cli = self.repo({"pyproject.toml": '[project]\nname = "tool"\n\n[project.scripts]\ntool = "tool.cli:main"\n',
                         "src/tool/cli.py": "def main():\n    pass\n", "README.md": "# Tool\n"}, "cli")
        data = inventory.collect(cli.path, remote=False)
        self.assertEqual(data["project_type"]["primary"], "cli")
        self.assertIn("CLI detected", " ".join(data["hints"]))
        lib = self.repo({"pyproject.toml": '[project]\nname = "lib"\n', "lib/__init__.py": "x = 1\n"}, "lib")
        self.assertEqual(inventory.collect(lib.path, remote=False)["project_type"]["primary"], "library")

    def test_backend_and_fullstack(self):
        api = self.repo({"requirements.txt": "fastapi==0.110\nuvicorn\n", "main.py": "app = None\n"}, "api")
        data = inventory.collect(api.path, remote=False)
        self.assertEqual(data["project_type"]["primary"], "backend")
        self.assertEqual(data["run_hints"]["commands"], ["uvicorn main:app --reload"])
        files = dict(VITE_APP)
        files["package.json"] = json.dumps({"dependencies": {"express": "4"}, "devDependencies": {"vite": "5"}})
        full = inventory.detect_project_type(self.repo(files, "full").path, list(files), None)
        self.assertEqual(full["primary"], "web-app")
        self.assertIn("backend", full["secondary"])

    def test_catalog(self):
        files = {"README.md": "# Plugins\n", "LICENSE": "MIT\n", "data.json": "[]\n"}
        for i in range(6):
            files["plugins/p%d.md" % i] = "# Plugin %d\n\ntext\nmore\n" % i
        data = inventory.collect(self.repo(files).path, remote=False)
        self.assertEqual(data["project_type"]["primary"], "catalog")

    def test_profile_game_ml_mobile_docs(self):
        profile = self.repo({"README.md": "# Hi\n"}, "work", origin="https://github.com/octo/octo.git")
        self.assertEqual(inventory.collect(profile.path, remote=False)["project_type"]["primary"], "profile")
        game = self.repo({"project.godot": "config_version=5\n", "main.gd": "extends Node\n"}, "game")
        self.assertEqual(inventory.collect(game.path, remote=False)["project_type"]["primary"], "game")
        ml = self.repo({"a.ipynb": "{}", "b.ipynb": "{}", "c.py": "x = 1\n", "README.md": "# ML\n"}, "ml")
        self.assertEqual(inventory.collect(ml.path, remote=False)["project_type"]["primary"], "ml")
        mobile = self.repo({"package.json": json.dumps({"dependencies": {"expo": "50"}}), "app.json": '{"expo": {}}'},
                           "mobile")
        self.assertEqual(inventory.collect(mobile.path, remote=False)["project_type"]["primary"], "mobile-app")
        docs = self.repo({"mkdocs.yml": "site_name: x\n", "docs/index.md": "# x\n"}, "docs")
        self.assertEqual(inventory.collect(docs.path, remote=False)["project_type"]["primary"], "docs")

    def test_other(self):
        data = inventory.collect(self.repo({"notes.txt": "hello\n"}).path, remote=False)
        self.assertEqual(data["project_type"]["primary"], "other")


class LocalAndReadmeTest(TempRepoCase):
    def test_local_facts(self):
        repo = self.repo({"a.py": "x = 1\n" * 10, "b.js": "let a = 1\n", "README.md": "# A\n"})
        repo.commit("second", {"c.py": "y = 2\n"})
        local = inventory.collect(repo.path, remote=False)["local"]
        self.assertEqual(local["commit_count"], 2)
        self.assertEqual(local["author_count"], 1)
        self.assertEqual(local["default_branch"], "main")
        self.assertEqual(local["tracked_files"], 4)
        self.assertEqual(local["languages"][0]["language"], "Python")
        self.assertEqual(local["languages"][0]["files"], 2)
        self.assertNotIn("@", json.dumps(local))

    def test_readme_stats(self):
        (Path(self.tmp) / "x").mkdir()
        readme = "\n".join([
            '<p align="center"><img src="assets/banner.svg" alt="banner"></p>',
            "",
            "[![CI](https://img.shields.io/badge/ci-passing-green)](https://example.org)",
            "![](https://github.com/o/r/workflows/ci/badge.svg)",
            "",
            "# Project",
            "",
            "## Installation",
            "```",
            "![ignored](code.png)",
            "# not a heading",
            "```",
            "## Utilisation",
            "![shot](docs/shot.png) and [docs](docs/a.md) and [site](https://example.org)",
            "## Captures d'écran",
            "## Licence",
            "",
        ])
        repo = self.repo({"README.md": readme,
                          "assets/banner.svg": '<svg xmlns="x"><circle><animate attributeName="r"/></circle></svg>',
                          "docs/shot.png": b"\x89PNG"})
        stats = inventory.collect(repo.path, remote=False)["readme"]
        self.assertTrue(stats["has_banner"])
        self.assertEqual(stats["first_image_line"], 1)
        self.assertEqual(stats["animated_svg"], 1)
        self.assertEqual(stats["images"]["badges"], 2)
        self.assertEqual(stats["images"]["visuals"], 2)
        self.assertEqual(stats["images"]["html"], 1)
        self.assertEqual(stats["links"], {"total": 3, "external": 2})
        self.assertEqual([h["text"] for h in stats["headings"]],
                         ["Project", "Installation", "Utilisation", "Captures d'écran", "Licence"])
        sections = stats["sections"]
        self.assertTrue(sections["install"] and sections["usage"] and sections["screenshots"] and sections["license"])
        self.assertFalse(sections["demo"] or sections["contributing"])

    def test_readme_hints(self):
        text = "# A\n\n" + "line\n" * 20 + "![x](a.png)\n"
        data = inventory.collect(self.repo({"README.md": text, "a.png": b"\x89PNG"}).path, remote=False)
        joined = " | ".join(data["hints"])
        self.assertIn("no visual in the first 15 lines", joined)
        self.assertIn("no LICENSE", joined)
        self.assertEqual(data["assets"]["by_extension"], {".png": 1})


def fake_gh(args, check=True):
    key = " ".join(args[:2])
    if key == "repo view":
        return {"name": "demo", "owner": {"login": "acme"}, "visibility": "PRIVATE", "description": "A demo",
                "homepageUrl": "", "repositoryTopics": [{"name": "python"}, {"name": "cli"}],
                "licenseInfo": {"spdxId": "MIT"}, "stargazerCount": 3, "forkCount": 0, "isArchived": False,
                "isFork": False, "defaultBranchRef": {"name": "main"}, "url": "https://github.com/acme/demo",
                "pushedAt": "2026-01-01T00:00:00Z"}
    if key == "repo list":
        return [{"name": "demo", "stargazerCount": 3}, {"name": "big", "stargazerCount": 90, "description": "d"},
                {"name": "small", "stargazerCount": 1}]
    if args[1].endswith("community/profile"):
        return {"health_percentage": 57, "description": "A demo", "documentation": None,
                "files": {"code_of_conduct": None, "contributing": None, "license": {"key": "mit"},
                          "readme": {"url": "u"}, "code_of_conduct_file": None}}
    if args[1].endswith("releases/latest"):
        return None
    if args[1] == "users/acme":
        return {"login": "acme", "name": "Acme", "blog": "https://acme.example", "bio": "bio",
                "twitter_username": None, "html_url": "https://github.com/acme", "email": "secret@corp.example",
                "id": 1}
    if args[1] == "repos/acme/big/contents/assets":
        return [{"name": "banner.svg"}, {"name": "notes.txt"}, {"name": "shot.png"}]
    if args[1] == "repos/acme/acme":
        return {"name": "acme"}
    return None


class GithubTest(TempRepoCase):
    def test_github_section(self):
        repo = self.repo({"README.md": "# A\n"}, origin="https://github.com/acme/demo.git")
        with mock.patch.object(inventory, "gh_json", side_effect=fake_gh) as gh, \
                mock.patch.object(inventory.shutil, "which", return_value="/usr/bin/gh"):
            data = inventory.collect(repo.path, remote=True)
        github = data["github"]
        self.assertTrue(github["available"])
        self.assertEqual(github["visibility"], "PRIVATE")
        self.assertEqual(github["topics"], ["python", "cli"])
        self.assertEqual(github["community"]["missing"], ["code_of_conduct", "contributing", "documentation"])
        self.assertIsNone(github["latest_release"])
        self.assertEqual(sorted(github["owner_profile"]), ["bio", "blog", "html_url", "login", "name",
                                                          "twitter_username"])
        self.assertNotIn("secret", json.dumps(data))
        self.assertEqual(github["style_sources"][0]["repo"], "acme/big")
        self.assertEqual(github["style_sources"][0]["assets"], ["banner.svg", "shot.png"])
        self.assertNotIn("acme/demo", [s["repo"] for s in github["style_sources"]])
        self.assertTrue(github["profile_repo"]["exists"])
        self.assertTrue(any("repository is private" in h for h in data["hints"]))
        for call in gh.call_args_list:
            self.assertNotIn("edit", call[0][0])

    def test_no_remote_and_no_origin(self):
        repo = self.repo({"README.md": "# A\n"}, origin="https://github.com/acme/demo.git")
        with mock.patch.object(inventory, "gh_json") as gh:
            data = inventory.collect(repo.path, remote=False)
        gh.assert_not_called()
        self.assertEqual(data["github"], {"available": False, "reason": "--no-remote"})
        other = self.repo({"README.md": "# A\n"}, "plain")
        self.assertFalse(inventory.collect(other.path, remote=True)["github"]["available"])

    def test_gh_failure_is_tolerated(self):
        repo = self.repo({"README.md": "# A\n"}, origin="https://github.com/acme/demo.git")
        with mock.patch.object(inventory, "gh_json", return_value=None), \
                mock.patch.object(inventory.shutil, "which", return_value="/usr/bin/gh"):
            github = inventory.collect(repo.path, remote=True)["github"]
        self.assertFalse(github["available"])

    def test_cli(self):
        repo = self.repo(VITE_APP)
        code, data = fx.run_cli(inventory, ["inventory", str(repo.path), "--no-remote"])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["project_type"]["primary"], "web-app")


class StructureTest(TempRepoCase):
    def audit(self, files, name="proj"):
        return inventory.structure_audit(self.repo(files, name).path)

    def test_junk_build_dependencies_editor(self):
        audit = self.audit({
            ".DS_Store": "x", "pkg/__pycache__/a.cpython-310.pyc": "x", "debug.log": "x", "dist/app.js": "x",
            "node_modules/lib/index.js": "x", ".idea/workspace.xml": "x", ".vscode/settings.json": "{}",
            ".vscode/private.json": "{}", "README.md": "# A\n\nb\nc\n"})
        junk = find(audit, "junk-tracked")
        self.assertEqual(junk["count"], 3)
        self.assertIn("pkg/__pycache__", junk["paths"])
        self.assertTrue(junk["command"].startswith("git rm -r --cached --"))
        self.assertEqual(find(audit, "build-output-tracked")["paths"], ["dist"])
        self.assertEqual(find(audit, "dependency-dir-tracked")["paths"], ["node_modules"])
        editor = find(audit, "editor-config-tracked")
        self.assertIn(".idea", editor["paths"])
        self.assertIn(".vscode/private.json", editor["paths"])
        self.assertNotIn(".vscode/settings.json", editor["paths"])
        self.assertEqual(editor["severity"], "info")

    def test_duplicates_and_large(self):
        big = "x" * 2000
        audit = self.audit({"a/logo.txt": big, "b/logo.txt": big, "c/small.txt": "tiny", "d/small.txt": "tiny",
                            "huge.bin": b"\x01" * (5 * 1024 * 1024 + 10)})
        dup = find(audit, "duplicate-files")
        self.assertEqual(dup["count"], 1)
        self.assertEqual(sorted(dup["paths"]), ["a/logo.txt", "b/logo.txt"])
        self.assertEqual(find(audit, "large-file")["paths"], ["huge.bin"])
        self.assertIn("Git LFS", find(audit, "large-file")["suggestion"])

    def test_unclear_names(self):
        audit = self.audit({"report_final.md": "x", "notes copy.txt": "x", "Untitled.md": "x", "app-v2.py": "x",
                            "photo (1).png": "x", "old/a.txt": "x", "src/main.py": "x", "src/new_user.py": "x",
                            "Screenshot 2026-01-01.png": "x"})
        paths = set(find(audit, "unclear-name")["paths"])
        for expected in ("report_final.md", "notes copy.txt", "Untitled.md", "app-v2.py", "photo (1).png", "old/",
                         "Screenshot 2026-01-01.png"):
            self.assertIn(expected, paths)
        self.assertNotIn("src/main.py", paths)
        self.assertNotIn("src/new_user.py", paths)

    def test_markdown_findings(self):
        files = {"README.md": "# A\n\nb\nc\n", "docs/empty.md": "# Title\n", ".github/PULL_REQUEST_TEMPLATE.md": "x\n",
                 "NOTES.md": "n\n", "IDEAS.md": "n\n", "TODO.md": "n\n", "CHANGELOG.md": "# c\n\nx\ny\n"}
        audit = self.audit(files)
        self.assertEqual(find(audit, "md-empty")["paths"], ["IDEAS.md", "NOTES.md", "TODO.md", "docs/empty.md"])
        scattered = find(audit, "md-scattered")
        self.assertEqual(scattered["paths"], ["IDEAS.md", "NOTES.md", "TODO.md"])
        self.assertIn("git mv", scattered["command"])
        self.assertTrue(audit["markdown"]["has_changelog"])

    def test_missing_files(self):
        audit = self.audit({"main.py": "x = 1\n"})
        ids = finding_ids(audit)
        for expected in ("missing-readme", "missing-license", "missing-gitignore", "missing-community"):
            self.assertIn(expected, ids)
        self.assertEqual(find(audit, "missing-readme")["severity"], "high")
        self.assertEqual(find(audit, "missing-license")["severity"], "medium")
        self.assertIn("__pycache__/", find(audit, "missing-gitignore")["detail"]["suggested_lines"])
        clean = self.audit({"README.md": "# A\n\nb\nc\n", "LICENSE": "MIT\n", ".gitignore": ".env\n.DS_Store\n"}, "ok")
        self.assertNotIn("missing-readme", finding_ids(clean))
        self.assertNotIn("missing-license", finding_ids(clean))
        self.assertNotIn("missing-gitignore", finding_ids(clean))

    def test_gitignore_gaps(self):
        files = {"README.md": "# A\n\nb\nc\n", "app.py": "x = 1\n", "package.json": "{}", ".gitignore": "node_modules/\n"}
        audit = self.audit(files)
        gaps = {f["id"]: f for f in audit["findings"] if f["category"] == "gitignore-gaps"}
        self.assertEqual(set(gaps), {"gitignore-gaps:python", "gitignore-gaps:node", "gitignore-gaps:macos",
                                     "gitignore-gaps:secrets"})
        self.assertEqual(gaps["gitignore-gaps:node"]["detail"]["missing"], ["dist/"])
        self.assertIn("__pycache__/", gaps["gitignore-gaps:python"]["detail"]["missing"])
        self.assertIn(">> .gitignore", gaps["gitignore-gaps:python"]["command"])
        full = dict(files)
        full[".gitignore"] = "__pycache__/\n*.pyc\n.venv/\nnode_modules/\ndist/\n.DS_Store\n.env\n"
        again = self.audit(full, "full")
        self.assertFalse([f for f in again["findings"] if f["category"] == "gitignore-gaps"])

    def test_comment_ratios(self):
        low = "".join("value_%d = %d\n" % (i, i) for i in range(80))
        ok = "".join("x = 1\n# why this value\n" if i % 4 == 0 else "x = %d\n" % i for i in range(80))
        high = "".join("# comment %d\n" % i if i % 3 else "x = %d\n" % i for i in range(90))
        audit = self.audit({"low/a.py": low, "ok/b.js": "".join(
            "// why\nlet a = 1;\nlet b = 2;\nlet c = 3;\n" for _ in range(20)), "high/c.sh": high})
        self.assertEqual(audit["comments"]["Python"]["verdict"], "low")
        self.assertEqual(audit["comments"]["JavaScript"]["verdict"], "ok")
        self.assertEqual(audit["comments"]["Shell"]["verdict"], "high")
        self.assertIn("low/a.py", find(audit, "comments-low")["paths"])
        self.assertIn("high/c.sh", find(audit, "comments-high")["paths"])

    def test_comment_syntaxes(self):
        py = '"""Module doc.\n\nMore.\n"""\nimport os  # trailing\n# real comment\n\ndef f():\n    """One."""\n    return 1\n'
        self.assertEqual(inventory.count_comment_lines(py, "python"), (3, 5))
        js = "/* a\n * b\n */\nconst a = 1; // trailing\n// c\n/** d */\n"
        self.assertEqual(inventory.count_comment_lines(js, "c"), (1, 5))
        self.assertEqual(inventory.count_comment_lines("-- a\nselect 1;\n", "dash"), (1, 1))
        self.assertEqual(inventory.count_comment_lines("<!-- a\nb -->\n<p>x</p>\n", "html"), (1, 2))
        self.assertEqual(inventory.count_comment_lines("#!/bin/sh\n# c\necho hi\n", "hash"), (2, 1))

    def test_minified_and_lockfiles_skipped(self):
        audit = self.audit({"app.min.js": "var a=1;" * 100, "wide.js": "a" * 600 + "\n", "yarn.lock": "# x\n" * 90})
        self.assertEqual(audit["comments"], {})

    def test_root_clutter_and_layout(self):
        files = {"README.md": "# A\n\nb\nc\n", "LICENSE": "x", "package.json": "{}"}
        for i in range(5):
            files["note%d.md" % i] = "x\n"
        files.update({"run.sh": "x", "deploy.sh": "x", "logo.png": b"\x89PNG", "example.json": "{}",
                      "data.csv": "a,b", "src/a.js": "x"})
        audit = self.audit(files)
        clutter = find(audit, "root-clutter")
        self.assertEqual(clutter["count"], 14)
        moves = clutter["detail"]["could_move"]
        self.assertIn("note0.md", moves["docs"])
        self.assertEqual(sorted(moves["scripts"]), ["deploy.sh", "run.sh"])
        self.assertEqual(moves["assets"], ["logo.png"])
        self.assertIn("git mv", clutter["command"])
        self.assertEqual(audit["layout"]["root_entries"], 14)
        self.assertEqual(audit["layout"]["primary_type"], "other")
        self.assertEqual(audit["layout"]["reference"], "references/structure.md#what-belongs-at-the-root")

    def test_depth_naming_tests(self):
        deep = "/".join("d%d" % i for i in range(10)) + "/f.py"
        files = {"README.md": "# A\n\nb\nc\n", deep: "x = 1\n", "my_utils/a.py": "x = 1\n", "web-ui/b.py": "x = 1\n",
                 "camelCase/c.py": "x = 1\n", "main.py": "x = 1\n"}
        audit = self.audit(files)
        self.assertEqual(find(audit, "deep-nesting")["count"], 1)
        mixed = find(audit, "mixed-naming")
        self.assertEqual(mixed["paths"], ["."])
        self.assertEqual(sorted(mixed["detail"]["folders"]["."]), ["camelCase", "kebab-case", "snake_case"])
        files["pyproject.toml"] = '[project]\nname = "x"\n'
        tested = dict(files, **{"tests/test_a.py": "x = 1\n"})
        self.assertIn("no-tests", finding_ids(self.audit(files, "a")))
        self.assertNotIn("no-tests", finding_ids(self.audit(tested, "b")))

    def test_reference_for_web_app(self):
        audit = self.audit(VITE_APP)
        self.assertEqual(audit["layout"]["reference"], "references/structure.md#web-app")

    def test_cli(self):
        repo = self.repo({"main.py": "x = 1\n"})
        code, data = fx.run_cli(inventory, ["structure", str(repo.path)])
        self.assertEqual(code, 0)
        self.assertIn("missing-readme", {f["id"] for f in data["findings"]})


if __name__ == "__main__":
    unittest.main()
