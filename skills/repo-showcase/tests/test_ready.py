import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import repofixtures as fx

import ready

_env = None
CLEAN_README = "# Demo\n\nA small tool that does one thing well.\n\n## Usage\n\nRun it.\n"
GH_VIEW = {"description": "A demo", "repositoryTopics": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
           "visibility": "PUBLIC", "url": "https://github.com/acme/demo"}


def setUpModule():
    global _env
    _env = fx.isolate()


def tearDownModule():
    _env.stop_and_clean()


def fake_modules(security=(), attribution=(), static=None):
    """Replacement scan and capture modules returning the given findings."""
    scan = types.SimpleNamespace(
        scan_repo=mock.Mock(return_value={"findings": list(security), "summary": {}}),
        attribution_scan=mock.Mock(return_value={"findings": list(attribution), "summary": {}}))
    capture = types.SimpleNamespace(static_readme_checks=mock.Mock(
        return_value=static if static is not None else {"ok": True, "blocking": [], "warnings": [], "stats": {}}))
    return scan, capture


def found(severity, category="api-key"):
    return {"category": category, "severity": severity, "where": "working-tree", "preview": "sk…(40)",
            "fingerprint": "abc123", "path": "app.py", "line": 3, "commit": None, "remedy": []}


class ReadyCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.repo = fx.make_repo(self.tmp, "demo", origin="https://github.com/acme/demo.git")
        self.repo.commit("initial", {"README.md": CLEAN_README, "LICENSE": "MIT\n", ".gitignore": ".env\n.DS_Store\n",
                                     "main.py": "print('hi')\n"})

    def run_ready(self, scan=None, capture=None, gh=GH_VIEW, remote=True, skip_preview=False, ls_remote=False):
        """ls_remote=False: the fake github.com origin is not contacted (remote listing reported as unreachable);
        True: the real `git ls-remote`, for tests whose origin is a local bare repository."""
        default_scan, default_capture = fake_modules()
        scan, capture = scan or default_scan, capture or default_capture
        patches = mock.patch.dict(sys.modules, {"scan": scan, "capture": capture})
        gh_mock = mock.Mock(return_value=gh)
        listing = ready.remote_refs if ls_remote else mock.Mock(return_value=(None, "not contacted in tests"))
        with patches, mock.patch.object(ready, "gh_json", gh_mock), mock.patch.object(ready, "remote_refs", listing):
            report = ready.ready_report(self.repo.path, remote=remote, skip_preview=skip_preview)
        return report, scan, capture, gh_mock

    def checks(self, items):
        return [i["check"] for i in items]


class ReadyTest(ReadyCase):
    def test_clean_public_repository_is_ready(self):
        report, scan, capture, _ = self.run_ready()
        self.assertTrue(report["ready"], report["blocking"])
        self.assertEqual(report["blocking"], [])
        self.assertEqual(report["visibility"], "PUBLIC")
        self.assertEqual(report["final_step"], "Already public: pin it on your profile if it should be seen first.")
        scan.scan_repo.assert_called_once()
        self.assertEqual(scan.scan_repo.call_args[1], {"history": True, "include_remote": False})
        self.assertEqual(scan.attribution_scan.call_args[1], {"include_remote": True})
        capture.static_readme_checks.assert_called_once()

    def test_private_repository_gets_the_final_step_and_never_runs_gh_edit(self):
        gh = dict(GH_VIEW, visibility="PRIVATE")
        real_run = subprocess.run
        with mock.patch("subprocess.run", wraps=real_run) as spy:
            report, _, _, gh_mock = self.run_ready(gh=gh)
        self.assertTrue(report["ready"])
        self.assertEqual(report["visibility"], "PRIVATE")
        self.assertEqual(report["final_step"], "Last step, done by you: gh repo edit acme/demo --visibility public "
                                               "--accept-visibility-change-consequences")
        for call in spy.call_args_list:
            command = call[0][0]
            self.assertFalse(command[0] == "gh", command)
            self.assertNotIn("edit", command)
        for call in gh_mock.call_args_list:
            self.assertEqual(call[0][0][:2], ["repo", "view"])

    def test_high_and_medium_findings_block_low_do_not(self):
        scan, capture = fake_modules(security=[found("high"), found("low")],
                                     attribution=[found("medium", "ai-coauthor")])
        report, _, _, _ = self.run_ready(scan, capture)
        self.assertFalse(report["ready"])
        self.assertEqual([b["check"] for b in report["blocking"]], ["security", "attribution"])
        self.assertIn("api-key (high) in working-tree app.py:3", report["blocking"][0]["message"])
        self.assertTrue(any("1 low or info" in i["message"] for i in report["info"]))

    def test_exit_code_four_when_blocked(self):
        scan, capture = fake_modules(security=[found("high")])
        with mock.patch.dict(sys.modules, {"scan": scan, "capture": capture}), \
                mock.patch.object(ready, "gh_json", return_value=GH_VIEW), \
                mock.patch.object(ready, "remote_refs", return_value=(None, "not contacted in tests")):
            code, data = fx.run_cli(ready, ["ready", str(self.repo.path)])
        self.assertEqual(code, 4)
        self.assertFalse(data["ready"])
        self.assertFalse(data["ok"])

    def test_exit_code_zero_when_clean(self):
        scan, capture = fake_modules()
        with mock.patch.dict(sys.modules, {"scan": scan, "capture": capture}), \
                mock.patch.object(ready, "gh_json", return_value=GH_VIEW), \
                mock.patch.object(ready, "remote_refs", return_value=(None, "not contacted in tests")):
            code, data = fx.run_cli(ready, ["ready", str(self.repo.path)])
        self.assertEqual(code, 0)
        self.assertTrue(data["ready"])

    def test_real_email_blocks_without_printing_it(self):
        self.repo.git("config", "user.email", fx.REAL_EMAIL)
        report, _, _, _ = self.run_ready()
        self.assertFalse(report["ready"])
        self.assertEqual(self.checks(report["blocking"]), ["identity"])
        self.assertNotIn(fx.REAL_EMAIL, json.dumps(report))
        self.repo.git("config", "--unset", "user.email")
        report, _, _, _ = self.run_ready()
        self.assertIn("not set", report["blocking"][0]["message"])

    def test_missing_readme_blocks(self):
        self.repo.git("rm", "-q", "README.md")
        self.repo.git("commit", "-q", "-m", "drop readme")
        report, _, _, _ = self.run_ready()
        self.assertIn("readme", self.checks(report["blocking"]))

    def test_capture_checks_and_skip_preview(self):
        static = {"ok": False, "blocking": ["image missing: a.png"], "warnings": ["image is 3 MB"], "stats": {}}
        scan, capture = fake_modules(static=static)
        report, _, _, _ = self.run_ready(scan, capture)
        self.assertEqual([b["message"] for b in report["blocking"]], ["image missing: a.png"])
        self.assertEqual([w["message"] for w in report["warnings"] if w["check"] == "readme"], ["image is 3 MB"])
        report, _, capture, _ = self.run_ready(scan, capture, skip_preview=True)
        self.assertEqual(capture.static_readme_checks.call_count, 1)
        self.assertTrue(report["ready"])

    def test_counters_must_be_in_sync(self):
        self.repo.commit("counter", {"plugins/a.md": "x\n", "plugins/b.md": "x\n",
                                     ".showcase.json": json.dumps({"counters": {"p": {"glob": "plugins/*.md"}}}),
                                     "README.md": CLEAN_README + "\nTotal: <!-- count:p -->9<!-- /count -->.\n"})
        report, _, _, _ = self.run_ready()
        self.assertFalse(report["ready"])
        self.assertEqual(self.checks(report["blocking"]), ["counts"])
        self.assertIn("README.md", report["blocking"][0]["stale"])
        self.repo.commit("sync", {"README.md": CLEAN_README + "\nTotal: <!-- count:p -->2<!-- /count -->.\n"})
        self.assertTrue(self.run_ready()[0]["ready"])

    def test_hard_coded_counts_are_warnings(self):
        self.repo.commit("count", {"README.md": CLEAN_README + "\nIncludes 57 VSTs.\n"})
        report, _, _, _ = self.run_ready()
        self.assertTrue(report["ready"])
        self.assertTrue(any(w["check"] == "counts" and "57" in w["message"] for w in report["warnings"]))

    def test_structure_warnings(self):
        self.repo.commit("junk", {"debug.log": "x", "dist/a.js": "x"})
        self.repo.git("rm", "-q", "LICENSE")
        self.repo.git("commit", "-q", "-m", "no license")
        report, _, _, _ = self.run_ready()
        self.assertTrue(report["ready"])
        categories = {w.get("category") for w in report["warnings"] if w["check"] == "structure"}
        self.assertEqual(categories, {"junk-tracked", "build-output-tracked", "missing-license"})

    def test_github_metadata_warnings(self):
        gh = {"description": "", "repositoryTopics": [{"name": "a"}], "visibility": "PUBLIC"}
        report, _, _, _ = self.run_ready(gh=gh)
        messages = [w["message"] for w in report["warnings"] if w["check"] == "github"]
        self.assertEqual(len(messages), 2)
        self.assertIn("no description", messages[0])
        self.assertIn("fewer than 3 topics", messages[1])

    def test_no_remote_skips_github_and_remote_scans(self):
        report, scan, _, gh_mock = self.run_ready(remote=False)
        gh_mock.assert_not_called()
        self.assertEqual(scan.attribution_scan.call_args[1], {"include_remote": False})
        self.assertEqual(report["visibility"], "unknown")
        self.assertIn("Visibility unknown", report["final_step"])

    def test_gh_unreachable_is_not_blocking(self):
        report, _, _, _ = self.run_ready(gh=None)
        self.assertTrue(report["ready"])
        self.assertEqual(report["visibility"], "unknown")
        self.assertTrue(any("GitHub checks skipped" in i["message"] for i in report["info"]))

    def test_unpushed_commits_and_dirty_tree(self):
        bare = Path(self.tmp) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
        self.repo.git("remote", "set-url", "--push", "origin", str(bare))
        self.repo.git("remote", "add", "local", str(bare))
        self.repo.git("push", "-q", "-u", "local", "main")
        self.repo.commit("one more")
        self.repo.write("scratch.txt", "x")
        report, _, _, _ = self.run_ready()
        self.assertTrue(any("1 commit(s) not pushed" in i["message"] for i in report["info"]))
        self.assertTrue(any("uncommitted" in w["message"] for w in report["warnings"]))

    def test_source_has_no_visibility_change(self):
        source = Path(ready.__file__).read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("run(", source)
        self.assertEqual(source.count("gh repo edit"), 1)


if __name__ == "__main__":
    unittest.main()
