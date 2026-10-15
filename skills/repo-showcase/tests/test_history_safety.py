"""Regression tests of the history rewrite safety: exact replacements, rescan, remote work, backups, cleanup."""
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import gitfixtures as fx

history = fx.history
scan = fx.scan

_env = None

PHONE = "+3" + "3 6 12 34 56 78"
IBAN = "FR" + "76 3000 6000 0112 3456 7890 189"
CARD = "4111" + "-1111" * 3
DB_HOST = "db.acme" + "-intra.net"
HOST_PORT = 'host = "%s", port = 5432\n' % DB_HOST
KEY_LINE = fx.PRIVATE_KEY.splitlines()[1]
IP_TARGET = "52.10" + ".4.1"
IP_NEIGHBOUR = IP_TARGET + "7"


def setUpModule():
    global _env
    _env = fx.isolate()


def tearDownModule():
    _env.stop_and_clean()


def engine_ok():
    return (subprocess.run(["git", "filter-repo", "--version"], capture_output=True).returncode == 0
            and history.git_version() >= history.MIN_GIT)


def docx(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:body>"
                                              "</w:document>" % text)
    return buffer.getvalue()


@unittest.skipUnless(engine_ok(), "git-filter-repo and git >= 2.36 are required")
class SafetyCase(unittest.TestCase):
    def setUp(self):
        fx.patch_identity(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backups = Path(self.tmp.name) / "backups"
        self.repo = fx.make_repo(self.tmp.name)
        self.repo.commit("start", {"README.md": "# demo\n", "app.py": 'KEY = "%s"\n' % fx.ANTHROPIC})
        self.origin = fx.add_origin(self.repo, self.tmp.name)
        self.path = str(self.repo.path)

    def cli(self, *argv):
        return fx.run_cli(history, list(argv))

    def apply(self, *extra):
        return self.cli("fix-apply", self.path, "--backup-dir", str(self.backups), "--confirm", *extra)

    def log(self, repo=None):
        return (repo or self.repo).git("log", "--all", "-p", "--format=%an <%ae>%n%B")

    def origin_log(self):
        return subprocess.run(["git", "--git-dir", str(self.origin), "log", "--all", "-p", "--format=%B"],
                              capture_output=True, text=True).stdout

    def collaborator(self):
        """A second clone of origin, as a collaborator would have."""
        path = Path(self.tmp.name) / "collab"
        if not path.exists():
            subprocess.run(["git", "clone", "-q", "-b", "main", str(self.origin), str(path)], check=True,
                           capture_output=True)
            other = fx.Repo(path)
            other.git("config", "user.name", "Collab")
            other.git("config", "user.email", "2+collab@users.noreply.github.com")
            other.git("config", "commit.gpgsign", "false")
        return fx.Repo(path)

    def plan_dir(self):
        return Path(self.path) / ".git" / "repo-showcase" / "plan"


class ExactReplacementTests(SafetyCase):
    """Defect 1: replacements carry the exact matched texts; remaining comes from a rescan."""

    def test_normalized_values_are_really_removed(self):
        self.repo.commit("data", {
            "notes/key.txt": fx.PRIVATE_KEY, "contact.txt": "Call %s\n" % PHONE,
            "bank.txt": "IBAN %s\ncard %s\n" % (IBAN, CARD), "config.py": HOST_PORT,
            "docs/notes.docx": docx("IBAN %s" % IBAN)})
        self.repo.commit("drop some", remove=["notes/key.txt", "contact.txt"])
        self.repo.git("push", "-q", "origin", "main")
        log = self.log()
        for raw in (fx.ANTHROPIC, KEY_LINE, PHONE, IBAN, CARD, DB_HOST):
            self.assertIn(raw, log)
        # A document a text replacement cannot edit is never removed implicitly.
        code, data, text = self.cli("fix-plan", self.path, "--replace-category",
                                    "secret,phone,iban,card-number,port")
        self.assertEqual(code, 6, text)
        self.assertIn("docs/notes.docx", data["error"])
        self.assertIn("--remove-path", data["error"])
        code, data, text = self.cli("fix-plan", self.path, "--replace-category",
                                    "secret,phone,iban,card-number,port", "--remove-path", "docs/notes.docx")
        self.assertEqual(code, 0, text)
        self.assertGreater(data["dry_run"]["commits_rewritten"], 0)
        self.assertEqual(data["dry_run"]["remaining"]["total"], 0)
        self.assertEqual([r["path"] for r in data["routed_to_path_removal"]], ["docs/notes.docx"])
        self.assertTrue(any("docs/notes.docx" in w and "explicit --remove-path" in w for w in data["warnings"]))
        for raw in (fx.ANTHROPIC, KEY_LINE, PHONE, IBAN, CARD, DB_HOST):
            self.assertNotIn(raw, text)
        code, data, text = self.apply()
        self.assertEqual(code, 0, text)
        self.assertEqual(data["remaining"]["total"], 0)
        log = self.log()
        compact_iban = IBAN.replace(" ", "")
        for raw in (fx.ANTHROPIC, KEY_LINE, PHONE, IBAN, compact_iban, CARD, DB_HOST):
            self.assertNotIn(raw, log)
        self.assertIn("***REMOVED***", log)
        self.assertNotIn("notes.docx", self.repo.git("log", "--all", "--name-only", "--format="))
        self.assertIn('host = "***REMOVED***\n', log, "only the host to port span is replaced")

    def test_remaining_is_computed_by_the_scanner(self):
        """No replacements file at all: the rescan still finds the targeted fingerprint."""
        target = [f["fingerprint"] for f in scan.scan_repo(self.repo.path)["findings"] if f["category"] == "secret"]
        empty = Path(self.tmp.name) / "empty-plan"
        empty.mkdir()
        remaining = history.remaining_targets(self.repo.path, empty, {"target_fingerprints": target})
        self.assertGreaterEqual(remaining["values"], 1)
        self.assertEqual(remaining["total"], remaining["values"])

    def test_regex_lines_compile_on_bytes_and_keep_neighbours(self):
        line = history.replacement_line(IP_TARGET)
        self.assertTrue(line.startswith("regex:"))
        pattern = re.compile(line[len("regex:"):].rsplit("==>", 1)[0].encode("utf-8"))
        sample = ("%s %s 1.%s %s.5 x%s" % (IP_TARGET, IP_NEIGHBOUR, IP_TARGET, IP_TARGET, IP_TARGET)).encode()
        self.assertEqual(pattern.sub(b"R", sample), ("R %s 1.%s %s.5 x%s" % (IP_NEIGHBOUR, IP_TARGET, IP_TARGET,
                                                                            IP_TARGET)).encode())
        tricky = "a==>b\n\tcé (x)"
        pattern = history.replacement_pattern(tricky)
        self.assertNotIn("==>", pattern)
        self.assertNotIn("\n", pattern)
        self.assertEqual(re.compile(pattern.encode("utf-8")).sub(b"R", ("<%s>" % tricky).encode()), b"<R>")


class NeighbourTests(SafetyCase):
    """Defect 6: an allowlisted IP next to a replaced one survives intact."""

    def test_allowlisted_neighbour_ip_survives(self):
        self.repo.commit("ips", {"hosts.txt": "a = '%s'\nb = '%s'\n" % (IP_TARGET, IP_NEIGHBOUR)})
        self.repo.git("push", "-q", "origin", "main")
        found = [f for f in scan.scan_repo(self.repo.path)["findings"] if f["category"] == "ip"]
        neighbour = [f["fingerprint"] for f in found if f["preview"].endswith("(10)")]
        self.assertEqual(len(neighbour), 1)
        scan.save_allowlist(self.repo.path, neighbour)
        code, data, text = self.cli("fix-plan", self.path, "--replace-category", "ip")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.apply()[0], 0)
        content = self.repo.git("show", "HEAD:hosts.txt")
        self.assertEqual(content, "a = '***REMOVED***'\nb = '%s'\n" % IP_NEIGHBOUR)


class RemoteSafetyTests(SafetyCase):
    """Defects 2, 7 and 9: remote work is never destroyed, remote-only refs refuse, local-only refs stay local."""

    def test_local_branch_behind_origin_refuses(self):
        other = self.collaborator()
        other.commit("collaborator work", {"theirs.txt": "x\n"})
        other.git("push", "-q", "origin", "main")
        code, data, _ = self.cli("fix-plan", self.path, "--replace-category", "secret")
        self.assertEqual(code, 6)
        self.assertIn("behind origin/main", data["error"])

    def test_diverged_branch_refuses(self):
        other = self.collaborator()
        other.commit("collaborator work", {"theirs.txt": "x\n"})
        other.git("push", "-q", "origin", "main")
        self.repo.commit("mine", {"mine.txt": "y\n"})
        code, data, _ = self.cli("fix-plan", self.path, "--replace-category", "secret", "--no-dry-run")
        self.assertEqual(code, 6)
        self.assertIn("diverged", data["error"])

    def test_remote_only_branch_and_tag_refuse(self):
        other = self.collaborator()
        other.git("checkout", "-q", "-b", "feature")
        other.commit("feature", {"f.txt": "x\n"})
        other.git("push", "-q", "origin", "feature")
        code, data, _ = self.cli("fix-plan", self.path, "--replace-category", "secret")
        self.assertEqual(code, 6)
        self.assertIn("git branch --track feature origin/feature", data["error"])
        self.repo.git("branch", "--track", "feature", "origin/feature")
        other.commit("tagged only", {"t.txt": "x\n"})
        other.git("tag", "v9")
        other.git("push", "-q", "origin", "v9")  # the tagged commit is on no branch: fetch does not follow it
        code, data, _ = self.cli("fix-plan", self.path, "--replace-category", "secret")
        self.assertEqual(code, 6)
        self.assertIn("tag v9 exists only on origin", data["error"])

    def test_ahead_is_allowed_and_reported(self):
        self.repo.commit("mine", {"mine.txt": "y\n"})
        code, data, text = self.cli("fix-plan", self.path, "--replace-category", "secret")
        self.assertEqual(code, 0, text)
        self.assertEqual(data["remote"]["branches_ahead"], ["main"])

    def test_unreachable_remote_refuses(self):
        self.repo.git("remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        code, data, _ = self.cli("fix-plan", self.path, "--replace-category", "secret", "--no-dry-run")
        self.assertEqual(code, 6)
        self.assertIn("cannot fetch the remote origin", data["error"])

    def test_remote_moved_between_plan_and_apply_refuses(self):
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        other = self.collaborator()
        other.commit("late push", {"late.txt": "x\n"})
        other.git("push", "-q", "origin", "main")
        refs = self.repo.git("for-each-ref")
        code, data, _ = self.apply("--push")
        self.assertEqual(code, 6)
        self.assertIn("changed since fix-plan", data["error"])
        self.assertEqual(self.repo.git("for-each-ref"), refs)
        self.assertFalse(self.backups.exists())
        self.assertIn("late push", self.origin_log())

    def test_push_uses_a_lease_and_only_pre_existing_refs(self):
        self.repo.git("tag", "v1")
        self.repo.git("push", "-q", "origin", "v1")
        self.repo.git("branch", "wip")
        self.repo.git("tag", "local-only")
        old = history.remote_refs(self.path, "origin")[0]
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        code, data, text = self.apply("--push")
        self.assertEqual(code, 0, text)
        self.assertEqual(data["push_refs"], ["refs/heads/main", "refs/tags/v1"])
        self.assertIn("refs/heads/wip", data["not_pushed"])
        self.assertIn("refs/tags/local-only", data["not_pushed"])
        now = history.remote_refs(self.path, "origin")[0]
        self.assertEqual(sorted(now), ["refs/heads/main", "refs/tags/v1"])
        self.assertNotEqual(now["refs/heads/main"], old["refs/heads/main"])
        self.assertNotIn(fx.ANTHROPIC, self.origin_log())
        command, pushed, _ = history.push_plan(self.path, "origin", old)
        self.assertIn("--force-with-lease=refs/heads/main:%s" % old["refs/heads/main"], command)
        self.assertNotIn("--force", command)
        self.assertNotIn("--all", command)

    def test_lease_rejects_a_push_made_after_the_check(self):
        """Someone pushes between the apply-time check and the force push: the lease keeps their commit."""
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        other = self.collaborator()
        real_run = history.run

        def racing_run(cmd, *args, **kwargs):
            if "--atomic" in cmd:
                other.commit("racing push", {"race.txt": "x\n"})
                other.git("push", "-q", "origin", "main")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(history, "run", side_effect=racing_run):
            code, data, _ = self.apply("--push")
        self.assertEqual(code, 7)
        self.assertIn("stale lease", data["push"]["hint"])
        self.assertIn("racing push", self.origin_log())


class ReadyAfterRewriteTests(SafetyCase):
    """Defect 3: ready blocks while the remote still holds the pre-rewrite history."""

    def ready_report(self, remote=True):
        import ready
        fake_scan = types.SimpleNamespace(
            scan_repo=mock.Mock(return_value={"findings": [], "summary": {}}),
            attribution_scan=mock.Mock(return_value={"findings": [], "summary": {}}))
        with mock.patch.dict(sys.modules, {"scan": fake_scan}), \
                mock.patch.object(ready, "gh_json", return_value=None):
            return ready.ready_report(self.repo.path, remote=remote, skip_preview=True)

    def test_ready_blocks_until_the_force_push(self):
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        code, data, text = self.apply()
        self.assertEqual(code, 0, text)
        report = self.ready_report()
        self.assertFalse(report["ready"])
        remote = [b for b in report["blocking"] if b["check"] == "remote"]
        self.assertEqual(len(remote), 1, report["blocking"])
        self.assertIn("the remote still holds the old history: run the force push printed by fix-apply",
                      remote[0]["message"])
        offline = self.ready_report(remote=False)
        self.assertTrue(any("remote was not checked" in b["message"] for b in offline["blocking"]), offline)
        self.assertEqual(subprocess.run(data["next_steps"][0], shell=True, capture_output=True).returncode, 0)
        report = self.ready_report()
        self.assertEqual([b for b in report["blocking"] if b["check"] == "remote"], [])

    def test_unreachable_remote_is_a_warning(self):
        self.repo.git("remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        report = self.ready_report()
        self.assertTrue(any("could not check the remote origin" in w["message"] for w in report["warnings"]))


class FailureRestoreTests(SafetyCase):
    """Defect 4: a failing rewrite leaves the remotes, upstream config and remote-tracking refs restored."""

    def test_failing_message_callback_restores_remotes(self):
        self.repo.commit("ai\n\n" + fx.AI_TRAILER, {"x.txt": "1\n"})
        self.repo.git("push", "-q", "origin", "main")
        self.assertEqual(self.cli("fix-plan", self.path, "--strip-ai", "--replace-category", "secret",
                                  "--no-dry-run")[0], 0)
        tracking = self.repo.git("rev-parse", "refs/remotes/origin/main").strip()
        callback = self.plan_dir() / "message-callback.py"
        callback.write_text("raise RuntimeError('callback failure')\n")
        code, data, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("the rewrite failed", data["error"])
        self.assertIn("origin %s" % self.origin, data["error"])
        self.assertIn("git clone", data["error"])
        self.assertIn(".git.tar.gz", data["error"])
        self.assertEqual(self.repo.git("remote", "get-url", "origin").strip(), str(self.origin))
        self.assertEqual(self.repo.git("config", "branch.main.remote").strip(), "origin")
        self.assertEqual(self.repo.git("config", "branch.main.merge").strip(), "refs/heads/main")
        self.assertEqual(self.repo.git("rev-parse", "refs/remotes/origin/main").strip(), tracking)
        self.assertTrue((self.plan_dir() / "replacements.txt").exists(), "plan files are kept to retry")

    def test_interrupt_is_reported_and_remotes_kept(self):
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret", "--no-dry-run")[0], 0)
        real_run = history.run

        def interrupted(cmd, *args, **kwargs):
            if "filter-repo" in cmd and "--version" not in cmd:
                raise KeyboardInterrupt
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(history, "run", side_effect=interrupted):
            code, data, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("interrupted", data["error"])
        self.assertEqual(self.repo.git("remote", "get-url", "origin").strip(), str(self.origin))


class SubjectTests(SafetyCase):
    """Defect 8: an AI mention in the subject line is cleaned too."""

    def test_subject_only_mention_is_cleaned(self):
        self.repo.commit(fx.AI_GENERATED, {"a.txt": "1\n"})
        self.repo.commit(fx.AI_GENERATED + "\n\nReal subject\n\nbody", {"b.txt": "1\n"})
        self.repo.git("push", "-q", "origin", "main")
        code, data, text = self.cli("fix-plan", self.path, "--strip-ai")
        self.assertEqual(code, 0, text)
        self.assertEqual(data["dry_run"]["remaining"]["ai_messages"], 0)
        self.assertEqual(self.apply()[0], 0)
        subjects = self.repo.git("log", "--format=%s").splitlines()
        self.assertEqual(subjects[:2], ["Real subject", "Update"])
        self.assertNotIn("Generated with", self.log())


class BackupTests(SafetyCase):
    """Defects 10 and 11: the backup folder mode is kept; the git directory archive restores reflog-only commits."""

    def test_existing_backup_dir_keeps_its_mode_and_archive_restores_reflog_commits(self):
        self.backups.mkdir()
        os.chmod(str(self.backups), 0o755)
        lost = self.repo.commit("only in the reflog", {"lost.txt": "x\n"})
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        code, data, text = self.apply()
        self.assertEqual(code, 0, text)
        self.assertEqual(stat.S_IMODE(self.backups.stat().st_mode), 0o755)
        archive = Path(data["backup_archive"])
        for path in (Path(data["backup"]), archive):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotEqual(self.repo.git("cat-file", "-t", lost, check=False).strip(), "commit")
        with tarfile.open(str(archive)) as tar:
            names = tar.getnames()
        self.assertFalse(any(n.startswith(".git/repo-showcase") for n in names))
        restored = Path(self.tmp.name) / "restored"
        restored.mkdir()
        subprocess.run(["tar", "-xzf", str(archive), "-C", str(restored)], check=True)
        back = fx.Repo(restored)
        self.assertEqual(back.git("cat-file", "-t", lost).strip(), "commit")
        back.git("reset", "-q", "--hard")
        self.assertIn(fx.ANTHROPIC, (restored / "app.py").read_text())

    def test_backup_dir_is_created_private(self):
        self.assertEqual(self.cli("fix-plan", self.path, "--replace-category", "secret")[0], 0)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(stat.S_IMODE(self.backups.stat().st_mode), 0o700)


class CleanupTests(SafetyCase):
    """Defect 12: the sensitive plan files are deleted after a successful rewrite."""

    def test_sensitive_plan_files_are_gone_after_success(self):
        self.repo.commit("by me", {"private/cv.txt": "x\n", "zz.txt": "zorblax\n"}, author="Dev <%s>" % fx.REAL_EMAIL)
        self.repo.commit("ai\n\n" + fx.AI_TRAILER)
        self.repo.git("push", "-q", "origin", "main")
        code, data, text = self.cli("fix-plan", self.path, "--replace-category", "secret,personal-name", "--strip-ai",
                                    "--map-email", "%s=9+dev@users.noreply.github.com" % fx.REAL_EMAIL,
                                    "--remove-path", "private/cv.txt", "--terms", "zorblax")
        self.assertEqual(code, 0, text)
        self.assertTrue((self.plan_dir() / "terms.txt").exists())
        code, data, text = self.apply()
        self.assertEqual(code, 0, text)
        self.assertTrue(data["plan_files_deleted"])
        self.assertEqual(sorted(p.name for p in self.plan_dir().iterdir()), ["plan.applied.json"])
        applied = (self.plan_dir() / "plan.applied.json").read_text()
        for raw in (fx.ANTHROPIC, fx.REAL_EMAIL, "private/cv.txt", "zorblax"):
            self.assertNotIn(raw, applied)
        self.assertIn("pre_rewrite_refs", json.loads(applied))
        self.assertNotIn("zorblax", self.log())


if __name__ == "__main__":
    unittest.main()
