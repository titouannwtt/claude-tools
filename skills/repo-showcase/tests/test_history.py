import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gitfixtures as fx

history = fx.history
scan = fx.scan

_env = None
ENGINE_OK = None


def setUpModule():
    global _env, ENGINE_OK
    _env = fx.isolate()
    ENGINE_OK = history.engine_status()[0]


def tearDownModule():
    _env.stop_and_clean()


def need_engine(test):
    return unittest.skipUnless(subprocess.run(["git", "filter-repo", "--version"], capture_output=True).returncode == 0
                               and history.git_version() >= history.MIN_GIT,
                               "git-filter-repo and git >= 2.36 are required")(test)


class HistoryCase(unittest.TestCase):
    """A repository with a secret, an AI trailer and a real e-mail identity in its history, plus a local origin."""

    def setUp(self):
        fx.patch_identity(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backups = Path(self.tmp.name) / "backups"
        self.repo = fx.make_repo(self.tmp.name)
        self.repo.commit("add config", {"app.py": 'KEY = "%s"\n' % fx.ANTHROPIC, "README.md": "# demo\n"},
                         author="Dev <%s>" % fx.REAL_EMAIL)
        self.repo.commit("remove the key\n\n" + fx.AI_TRAILER, {"app.py": "KEY = None\n"})
        self.origin = fx.add_origin(self.repo, self.tmp.name)
        self.path = str(self.repo.path)

    def cli(self, *argv):
        return fx.run_cli(history, list(argv))

    def plan(self, *extra):
        return self.cli("fix-plan", self.path, "--replace-category", "secret", "--strip-ai", *extra)

    def origin_refs(self):
        return history.remote_refs(self.path, "origin")[0]

    def log(self, repo=None):
        return (repo or self.repo).git("log", "--all", "-p", "--format=%an <%ae> %cn <%ce>%n%B")


@need_engine
class PlanTests(HistoryCase):
    def test_dry_run_reports_remaining_zero_and_cleans_up(self):
        before = self.repo.git("for-each-ref")
        temp_before = self.dry_run_folders()
        code, data, text = self.plan()
        self.assertEqual(code, 0, text)
        dry = data["dry_run"]
        self.assertEqual(dry["remaining"]["total"], 0)
        self.assertEqual(dry["commits_rewritten"], 2)
        self.assertTrue(dry["first_rewritten_commit"])
        self.assertIn("refs/heads/main", dry["refs_affected"])
        self.assertIn("size_kib_before", dry)
        self.assertEqual(self.repo.git("for-each-ref"), before, "the dry run must not touch the repository")
        self.assertEqual(self.dry_run_folders(), temp_before, "the temporary clone must be deleted")

    @staticmethod
    def dry_run_folders():
        return {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("repo-showcase-dry-")}

    def test_plan_files_and_secrecy(self):
        code, data, text = self.plan("--map-email", "%s=9+dev@users.noreply.github.com" % fx.REAL_EMAIL,
                                     "--remove-path", "README.md", "--strip-blobs-bigger-than", "10m")
        self.assertEqual(code, 0, text)
        plan_dir = Path(data["plan_dir"])
        self.assertEqual(sorted(p.name for p in plan_dir.iterdir()),
                         ["mailmap.txt", "message-callback.py", "paths.txt", "plan.json", "replacements.txt"])
        replacements = plan_dir / "replacements.txt"
        self.assertEqual(stat.S_IMODE(replacements.stat().st_mode), 0o600)
        self.assertIn(history.replacement_line(fx.ANTHROPIC), replacements.read_text())
        self.assertIn("<9+dev@users.noreply.github.com> <%s>" % fx.REAL_EMAIL, (plan_dir / "mailmap.txt").read_text())
        self.assertEqual((plan_dir / "paths.txt").read_text(), "literal:README.md\n")
        plan = json.loads((plan_dir / "plan.json").read_text())
        self.assertEqual(plan["args"], data["filter_repo_args"])
        self.assertIn("--strip-blobs-bigger-than", plan["args"])
        self.assertIn("10M", plan["args"])
        for name in ("plan.json",):
            self.assertNotIn(fx.ANTHROPIC, (plan_dir / name).read_text())
        for raw in (fx.ANTHROPIC, fx.REAL_EMAIL):
            self.assertNotIn(raw, text)
        self.assertEqual(data["dry_run"]["remaining"]["total"], 0)

    def test_replace_by_fingerprint_and_path_fingerprints(self):
        self.repo.commit("secret file", {"deploy/id_rsa": "x\n"})
        found = scan.scan_repo(self.repo.path)["findings"]
        key = [f for f in found if f["category"] == "secret"][0]["fingerprint"]
        cred = [f for f in found if f["category"] == "credential-file"][0]["fingerprint"]
        code, data, text = self.cli("fix-plan", self.path, "--replace", key, "--replace", cred, "--replace", "0" * 12)
        self.assertEqual(code, 0, text)
        plan_dir = Path(data["plan_dir"])
        self.assertIn(history.replacement_pattern(fx.ANTHROPIC), (plan_dir / "replacements.txt").read_text())
        self.assertEqual((plan_dir / "paths.txt").read_text(), "literal:deploy/id_rsa\n")
        self.assertTrue(any("not found" in w for w in data["warnings"]))
        self.assertEqual(data["dry_run"]["remaining"]["total"], 0)

    def test_identity_mapping_and_third_party_listing(self):
        stranger = "Pat <pat" + "@" + "elsewhere.io>"
        self.repo.commit("by someone else", {"x.txt": "1\n"}, author=stranger)
        with mock.patch.object(history, "gh_user", return_value={"login": "dev", "id": 9, "name": "Dev"}):
            code, data, text = self.cli("fix-plan", self.path, "--map-mine")
        self.assertEqual(code, 0, text)
        mailmap = (Path(data["plan_dir"]) / "mailmap.txt").read_text()
        self.assertEqual(mailmap, "Dev <9+dev@users.noreply.github.com> Dev <%s>\n" % fx.REAL_EMAIL)
        self.assertEqual([i["commits"] for i in data["third_party_identities"]], [1])
        self.assertNotIn("elsewhere", text)
        self.assertEqual(data["dry_run"]["remaining"]["identities"], 0)

    def test_map_name_and_explicit_email_pair(self):
        code, data, text = self.cli("fix-plan", self.path, "--map-name", "Dev=Developer")
        self.assertEqual(code, 0, text)
        self.assertEqual((Path(data["plan_dir"]) / "mailmap.txt").read_text(),
                         "Developer <%s> Dev <%s>\n" % (fx.REAL_EMAIL, fx.REAL_EMAIL))
        self.assertEqual(data["dry_run"]["remaining"]["identities"], 0)


class PlanArgumentTests(HistoryCase):
    def test_map_mine_without_gh_is_missing(self):
        code, data, _ = self.cli("fix-plan", self.path, "--map-mine", "--no-dry-run")
        self.assertEqual(code, 5)
        self.assertIn("gh", data["error"])
        code, data, _ = self.cli("fix-plan", self.path, "--map-mine", "--map-email", "a@x.io=b@x.io", "--no-dry-run")  # check-repo: ignore
        self.assertEqual(code, 0)
        self.assertTrue(any("skipped" in w for w in data["warnings"]))

    def test_nothing_to_do_is_refused(self):
        code, data, _ = self.cli("fix-plan", self.path, "--no-dry-run")
        self.assertEqual(code, 6)
        self.assertIn("nothing to do", data["error"])

    def test_invalid_arguments(self):
        self.assertEqual(self.cli("fix-plan", self.path, "--map-email", "nonsense", "--no-dry-run")[0], 2)
        self.assertEqual(self.cli("fix-plan", self.path, "--map-email", "a=b", "--no-dry-run")[0], 2)
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "env-file", "--no-dry-run")[0], 2)
        self.assertEqual(self.cli("fix-plan", self.path, "--strip-blobs-bigger-than", "big", "--strip-ai",
                                  "--no-dry-run")[0], 2)

    def test_old_git_refuses_plan_and_apply_cleanly(self):
        with mock.patch.object(history, "git_version", return_value=(2, 30, 2)):
            code, data, _ = self.cli("fix-plan", self.path, "--strip-ai")
            self.assertEqual(code, 6)
            self.assertIn("git >= 2.36", data["error"])
            code, data, _ = self.cli("fix-plan", self.path, "--strip-ai", "--no-dry-run")
            self.assertEqual(code, 0)
            code, data, _ = self.cli("fix-apply", self.path, "--confirm", "--backup-dir", str(self.backups))
            self.assertEqual(code, 6)
            self.assertIn("git >= 2.36", data["error"])
        self.assertFalse(self.backups.exists())

    def test_missing_filter_repo_refuses(self):
        done = subprocess.CompletedProcess([], 1, b"", b"not a git command")
        with mock.patch.object(history, "run", return_value=done), \
                mock.patch.object(history, "git_version", return_value=(2, 50, 0)):
            code, data, _ = self.cli("fix-plan", self.path, "--strip-ai")
        self.assertEqual(code, 6)
        self.assertIn("git-filter-repo", data["error"])

    def test_plan_script_is_valid_python_with_the_shared_patterns(self):
        self.cli("fix-plan", self.path, "--strip-ai", "--no-dry-run")
        source = (Path(self.path) / ".git" / "repo-showcase" / "plan" / "message-callback.py").read_text()
        self.assertTrue(source.isascii())
        namespace = {}
        exec("def callback(message):\n" + "".join("    " + line + "\n" for line in source.splitlines()), namespace)
        message = ("Fix\n\nBody\n\n" + fx.AI_TRAILER + "\n\U0001F916 Generated with a tool\n"
                   + fx.AI_GENERATED + "\n").encode()
        self.assertEqual(namespace["callback"](message), b"Fix\n\nBody\n")
        plain = b"Fix\n\n\nBody\n\n"
        self.assertEqual(namespace["callback"](plain), plain)
        self.assertEqual(namespace["callback"](b"aider: add parser\n"), b"add parser\n")


class ApplyRefusalTests(HistoryCase):
    def apply(self, *extra):
        return self.cli("fix-apply", self.path, "--backup-dir", str(self.backups), *extra)

    def test_refuses_without_confirm_and_without_plan(self):
        code, data, _ = self.apply()
        self.assertEqual(code, 6)
        self.assertIn("--confirm", data["error"])
        code, data, _ = self.apply("--confirm")
        self.assertEqual(code, 6)
        self.assertIn("no plan", data["error"])
        self.assertFalse(self.backups.exists())

    @need_engine
    def test_refuses_on_a_dirty_tree(self):
        self.assertEqual(self.plan("--no-dry-run")[0], 0)
        (self.repo.path / "app.py").write_text("changed\n")
        code, data, _ = self.apply("--confirm")
        self.assertEqual(code, 6)
        self.assertIn("changes", data["error"])
        self.repo.git("checkout", "app.py")
        self.repo.write("untracked.txt", "fine\n")
        self.repo.git("add", "untracked.txt")
        self.assertEqual(self.apply("--confirm")[0], 6)
        self.assertFalse(self.backups.exists())

    @need_engine
    def test_refuses_when_refs_changed_since_the_plan(self):
        self.assertEqual(self.plan("--no-dry-run")[0], 0)
        self.repo.commit("later", {"later.txt": "x\n"})
        code, data, _ = self.apply("--confirm")
        self.assertEqual(code, 6)
        self.assertIn("changed since fix-plan", data["error"])

    @need_engine
    def test_push_needs_an_existing_remote(self):
        self.assertEqual(self.plan("--no-dry-run")[0], 0)
        code, data, _ = self.apply("--confirm", "--push", "--remote", "nowhere")
        self.assertEqual(code, 6)
        self.assertFalse(self.backups.exists())


@need_engine
class ApplyTests(HistoryCase):
    def apply(self, *extra):
        return self.cli("fix-apply", self.path, "--backup-dir", str(self.backups), *extra)

    def test_rewrite_removes_secret_and_trailer_keeps_origin(self):
        self.assertIn(fx.ANTHROPIC, self.log())
        self.assertEqual(self.plan("--map-email", "%s=9+dev@users.noreply.github.com" % fx.REAL_EMAIL)[0], 0)
        code, data, text = self.apply("--confirm")
        self.assertEqual(code, 0, text)
        self.assertTrue(data["ok"])
        log = self.log()
        for gone in (fx.ANTHROPIC, "anthropic", fx.REAL_EMAIL):
            self.assertNotIn(gone, log)
        self.assertIn("***REMOVED***", log)
        self.assertIn("9+dev@users.noreply.github.com", log)
        bundle = Path(data["backup"])
        self.assertEqual(bundle.parent, self.backups)
        self.assertTrue(bundle.name.startswith("proj-") and bundle.suffix == ".bundle")
        self.assertEqual(subprocess.run(["git", "bundle", "verify", str(bundle)], capture_output=True,
                                        cwd=self.path).returncode, 0)
        self.assertEqual(self.repo.git("remote", "get-url", "origin").strip(), str(self.origin))
        self.assertEqual(self.repo.git("config", "branch.main.remote").strip(), "origin")
        self.assertEqual(data["remotes_restored"], ["origin"])
        self.assertEqual(data["remaining"]["total"], 0)
        root = Path(self.path).resolve()
        old_main = self.origin_refs()["refs/heads/main"]
        self.assertEqual(data["next_steps"], ["git -C %s push --atomic --force-with-lease=refs/heads/main:%s origin "
                                              "refs/heads/main:refs/heads/main" % (root, old_main)])
        self.assertTrue(any("refs/pull" in line for line in data["remote_cleanup"]))
        self.assertTrue(any("Rotate" in line for line in data["remote_cleanup"]))
        plan_dir = Path(self.path) / ".git" / "repo-showcase" / "plan"
        self.assertFalse((plan_dir / "replacements.txt").exists())
        self.assertTrue((plan_dir / "plan.applied.json").exists())
        self.assertEqual(self.apply("--confirm")[0], 6, "a plan cannot be applied twice")
        restored = Path(self.tmp.name) / "restored"
        subprocess.run(["git", "clone", "-q", str(bundle), str(restored)], check=True, capture_output=True)
        self.assertIn(fx.ANTHROPIC, self.log(fx.Repo(restored)))

    def test_origin_still_has_the_old_history_until_the_push(self):
        self.assertEqual(self.plan()[0], 0)
        self.assertEqual(self.apply("--confirm")[0], 0)
        remote_log = subprocess.run(["git", "--git-dir", str(self.origin), "log", "--all", "-p"], capture_output=True,
                                    text=True).stdout
        self.assertIn(fx.ANTHROPIC, remote_log)

    def test_push_updates_the_remote(self):
        self.assertEqual(self.plan()[0], 0)
        code, data, text = self.apply("--confirm", "--push")
        self.assertEqual(code, 0, text)
        self.assertTrue(data["pushed"])
        remote_log = subprocess.run(["git", "--git-dir", str(self.origin), "log", "--all", "-p"], capture_output=True,
                                    text=True).stdout
        self.assertNotIn(fx.ANTHROPIC, remote_log)
        self.assertNotIn("anthropic", remote_log)

    def test_rejected_push_is_reported_with_a_hint(self):
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho protected branch >&2\nexit 1\n")
        hook.chmod(0o755)
        self.assertEqual(self.plan()[0], 0)
        code, data, _ = self.apply("--confirm", "--push")
        self.assertEqual(code, 7)
        self.assertFalse(data["ok"])
        self.assertIn("lift the protection", data["push"]["hint"])
        self.assertIn("protected branch", data["push"]["error"])
        self.assertTrue(Path(data["backup"]).exists())

    def test_remove_path_and_big_blobs(self):
        self.repo.commit("blob", {"data/big.bin": "0123456789" * 400, "keep.txt": "ok\n"})
        self.repo.commit("drop", remove=["data/big.bin"])
        self.repo.git("push", "-q", "origin", "main")
        code, data, text = self.cli("fix-plan", self.path, "--remove-path", "data/big.bin",
                                    "--strip-blobs-bigger-than", "2K", "--replace-category", "secret")
        self.assertEqual(code, 0, text)
        self.assertEqual(data["dry_run"]["remaining"]["paths"], 0)
        self.assertEqual(self.apply("--confirm")[0], 0)
        self.assertNotIn("big.bin", self.repo.git("log", "--all", "--name-only", "--format="))
        self.assertTrue((self.repo.path / "keep.txt").exists())

    def test_failed_backup_aborts_before_rewriting(self):
        self.assertEqual(self.plan()[0], 0)
        refs = self.repo.git("for-each-ref")
        failed = subprocess.CompletedProcess([], 1, b"", b"bad bundle")
        real_run = history.run

        def fake_run(cmd, *args, **kwargs):
            if "verify" in cmd:
                return failed
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(history, "run", side_effect=fake_run):
            code, data, _ = self.apply("--confirm")
        self.assertEqual(code, 1)
        self.assertIn("did not verify", data["error"])
        self.assertEqual(self.repo.git("for-each-ref"), refs)

    def test_targets_remaining_after_the_rewrite_are_reported(self):
        self.assertEqual(self.plan()[0], 0)
        remaining = {"values": 1, "identities": 0, "ai_messages": 0, "paths": 0, "big_blobs": 0, "total": 1}
        with mock.patch.object(history, "remaining_targets", return_value=remaining):
            code, data, _ = self.apply("--confirm")
        self.assertEqual(code, 1)
        self.assertFalse(data["ok"])
        self.assertIn("backup is intact", data["error"])
        self.assertTrue(Path(data["backup"]).exists())


class PullRequestTests(HistoryCase):
    def setUp(self):
        super().setUp()
        self.repo.git("remote", "set-url", "origin", "https://github.com/acme/widgets.git")
        self.prs = [{"number": 7, "title": "Add parser", "body": "Details\n\n" + fx.AI_GENERATED + "\n", "url": "u7"},
                    {"number": 8, "title": "aider: fix typo", "body": "", "url": "u8"},
                    {"number": 9, "title": "Plain", "body": "A skill for Claude Code.\n", "url": "u9"}]
        self.releases = [{"id": 5, "tag_name": "v1", "body": "Notes\n" + fx.AI_TRAILER, "html_url": "r5"},
                         {"id": 6, "tag_name": "v2", "body": "Clean notes", "html_url": "r6"}]
        for target, value in (("history.fetch_pull_requests", self.prs), ("history.fetch_releases", self.releases)):
            patcher = mock.patch(target, mock.Mock(return_value=value))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_dry_run_lists_lines_without_editing(self):
        with mock.patch.object(history, "gh_patch") as patch:
            code, data, text = self.cli("fix-prs", self.path)
        self.assertEqual(code, 0)
        patch.assert_not_called()
        self.assertFalse(data["applied"])
        kinds = [(c["kind"], c.get("number") or c.get("id")) for c in data["candidates"]]
        self.assertEqual(kinds, [("pull-request", 7), ("pull-request", 8), ("release", 5)])
        self.assertTrue(any("Claude" in line for line in data["candidates"][0]["removed_lines"]))
        self.assertNotIn("noreply@" + "anthropic", text)

    def test_confirm_patches_through_gh(self):
        with mock.patch.object(history, "gh_patch") as patch:
            code, data, _ = self.cli("fix-prs", self.path, "--confirm")
        self.assertEqual(code, 0)
        calls = {call.args[0]: call.args[1] for call in patch.call_args_list}
        self.assertEqual(calls["repos/acme/widgets/pulls/7"], {"title": "Add parser", "body": "Details\n"})
        self.assertEqual(calls["repos/acme/widgets/pulls/8"], {"title": "fix typo", "body": ""})
        self.assertEqual(calls["repos/acme/widgets/releases/5"], {"body": "Notes"})
        self.assertEqual(len(calls), 3)
        self.assertEqual(data["updated"], [7, 8, 5])

    def test_gh_command_line(self):
        done = subprocess.CompletedProcess([], 0, b"{}", b"")
        with mock.patch.object(history, "run", return_value=done) as run:
            history.gh_patch("repos/acme/widgets/pulls/7", {"title": "T", "body": "B"})
        self.assertEqual(run.call_args.args[0], ["gh", "api", "-X", "PATCH", "repos/acme/widgets/pulls/7", "-f",
                                                 "title=T", "-f", "body=B"])

    def test_patch_errors_exit_7(self):
        with mock.patch.object(history, "gh_patch", side_effect=history.Failure(7, "boom")):
            code, data, _ = self.cli("fix-prs", self.path, "--confirm")
        self.assertEqual(code, 7)
        self.assertEqual(len(data["errors"]), 3)

    def test_no_github_remote_is_missing(self):
        self.repo.git("remote", "set-url", "origin", str(self.origin))
        code, data, _ = self.cli("fix-prs", self.path)
        self.assertEqual(code, 5)
        self.assertIn("GitHub", data["error"])

    def test_gh_missing_is_missing(self):
        with mock.patch.object(history, "fetch_pull_requests", side_effect=history.Failure(5, "command not found: gh")):
            code, data, _ = self.cli("fix-prs", self.path)
        self.assertEqual(code, 5)


if __name__ == "__main__":
    unittest.main()
