"""Temporary git repositories and CLI helpers for the scan and history tests (no network, no user git config)."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import history  # noqa: E402
import scan  # noqa: E402

IDENTITY_NAME = "Tester"
IDENTITY_EMAIL = "1+tester@users.noreply.github.com"
REAL_EMAIL = "someone" + "@" + "corp.io"
ANTHROPIC = "sk-ant-" + "a" * 30
OPENAI = "sk-" + "a1" * 24
GITHUB = "ghp_" + "A1b2" * 9
AWS = "AKIA" + "ABCDEFGH12345678"
GOOGLE = "AIza" + "B" * 35
SLACK = "xox" + "b-" + "1234567890-abcdefghij"
STRIPE = "sk_" + "live_" + "a1" * 12
SENDGRID = "SG." + "a" * 22 + "." + "b" * 22
TELEGRAM = "123456789:" + "A" * 35
JWT = "eyJ" + "a" * 10 + ".eyJ" + "b" * 10 + "." + "c" * 12
PRIVATE_KEY = ("-----BEGIN " + "RSA PRIVATE KEY-----\n" + "MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Q\n" * 2
               + "-----END " + "RSA PRIVATE KEY-----\n")
AI_TRAILER = "Co-Authored-By: Claude <noreply@" + "anthropic.com>"
AI_GENERATED = "Generated with [Claude " + "Code](https://claude.com/" + "claude-code)"


def isolate():
    """Patch the environment so git ignores the user's configuration; call .stop_and_clean() on the result."""
    home = tempfile.mkdtemp(prefix="showcase-home-")
    patcher = mock.patch.dict(os.environ, {
        "HOME": home, "XDG_CONFIG_HOME": home, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    patcher.start()
    patcher.stop_and_clean = lambda: (patcher.stop(), shutil.rmtree(home, ignore_errors=True))
    return patcher


def patch_identity(test):
    """Neutral personal terms and no gh lookup for the scan and history modules."""
    for target, value in (("scan.local_settings", {}), ("scan.auto_terms", (set(), set())),
                          ("scan.gh_user", None), ("history.gh_user", None)):
        patcher = mock.patch(target, mock.Mock(return_value=value))
        patcher.start()
        test.addCleanup(patcher.stop)


class Repo:
    def __init__(self, path):
        self.path = Path(path)

    def git(self, *args, check=True, env=None):
        full = dict(os.environ, **(env or {}))
        result = subprocess.run(["git", "-C", str(self.path)] + list(args), capture_output=True, text=True, env=full)
        if check and result.returncode != 0:
            raise AssertionError("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout

    def write(self, name, content):
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def commit(self, message, files=None, author=None, remove=()):
        for name, content in (files or {}).items():
            self.write(name, content)
        for name in remove:
            (self.path / name).unlink()
        self.git("add", "-A")
        args = ["commit", "-q", "--allow-empty", "-m", message]
        if author:
            args += ["--author", author]
        self.git(*args)
        return self.git("rev-parse", "HEAD").strip()


def make_repo(parent, name="proj"):
    path = Path(parent) / name
    path.mkdir(parents=True)
    repo = Repo(path)
    repo.git("init", "-q", "-b", "main")
    repo.git("config", "user.name", IDENTITY_NAME)
    repo.git("config", "user.email", IDENTITY_EMAIL)
    repo.git("config", "commit.gpgsign", "false")
    return repo


def add_origin(repo, parent):
    """A bare repository used as origin: returns its path (pushes in tests stay local)."""
    bare = Path(parent) / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    repo.git("remote", "add", "origin", str(bare))
    repo.git("push", "-q", "-u", "origin", "main")
    return bare


def run_cli(module, argv):
    """Run module.main(argv) and return (exit code, parsed JSON or None, raw stdout)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(argv)
    text = buffer.getvalue()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    return code, data, text
