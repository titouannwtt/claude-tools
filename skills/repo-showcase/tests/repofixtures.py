"""Temporary git repositories and CLI helpers for the inventory, counts and ready tests (no network, no user config)."""
import argparse
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

EMAIL = "1+tester@users.noreply.github.com"
REAL_EMAIL = "someone" + "@" + "corp.io"


def isolate():
    """Patch the environment so git ignores the user's configuration; call .stop_and_clean() on the result."""
    home = tempfile.mkdtemp(prefix="showcase-home-")
    patcher = mock.patch.dict(os.environ, {
        "HOME": home, "XDG_CONFIG_HOME": home, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    patcher.start()
    patcher.stop_and_clean = lambda: (patcher.stop(), shutil.rmtree(home, ignore_errors=True))
    return patcher


class Repo:
    def __init__(self, path):
        self.path = Path(path)

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.path)] + list(args), capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout

    def write(self, name, content):
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def commit(self, message="commit", files=None):
        for name, content in (files or {}).items():
            self.write(name, content)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def stage(self, files):
        """Write and stage files without committing."""
        for name, content in files.items():
            self.write(name, content)
        self.git("add", "-A")


def make_repo(parent, name="proj", origin=None):
    path = Path(parent) / name
    path.mkdir(parents=True)
    repo = Repo(path)
    repo.git("init", "-q", "-b", "main")
    repo.git("config", "user.name", "Tester")
    repo.git("config", "user.email", EMAIL)
    repo.git("config", "commit.gpgsign", "false")
    if origin:
        repo.git("remote", "add", "origin", origin)
    return repo


def run_cli(module, argv):
    """Parse argv with the module's add_commands and run the handler: (exit code, parsed JSON or None)."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    module.add_commands(sub)
    args = parser.parse_args(argv)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = args.func(args)
    try:
        return code, json.loads(buffer.getvalue())
    except ValueError:
        return code, None
