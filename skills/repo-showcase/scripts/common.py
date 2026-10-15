"""Helpers shared by the repo-showcase modules (Python 3.9, standard library only).

Conventions every module follows:
- A command prints exactly one JSON object on stdout (print_json) and returns a code from the EXIT_* constants.
- A sensitive value is never printed: redact() builds a preview, fingerprint() identifies it across files and commits.
- Local state (reports, plans, allowlist) lives in <repo>/.git/repo-showcase/: never committed, never pushed.
- A line carrying one of IGNORE_MARKERS is skipped by every scanner (accepted false positive).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1       # unexpected error: repair the script
EXIT_USAGE = 2       # invalid arguments (argparse also exits with 2)
EXIT_NOT_REPO = 3    # the path is not a git repository
EXIT_FINDINGS = 4    # findings present or checks not passed (security, attribution, lint, ready)
EXIT_MISSING = 5     # an optional dependency needed by this command is missing
EXIT_REFUSED = 6     # safety refusal: dirty tree, missing --confirm, git too old, nothing to do
EXIT_NETWORK = 7     # GitHub or network unreachable

SEVERITIES = ("high", "medium", "low", "info")
IGNORE_MARKER = "showcase: ignore"
# Markers of other scanners are honoured too, so a repository keeps its existing exemptions.
IGNORE_MARKERS = (IGNORE_MARKER, "check-repo: ignore", "gitleaks:allow", "pragma: allowlist secret")
SKILL_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = Path(__file__).resolve().parents[3]  # claude-tools clone (lib/, local.env)
GITHUB_REMOTE_RE = re.compile(r"github\.com[:/]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class Failure(Exception):
    """Expected failure: the dispatcher prints {"ok": false, "error": message} and exits with code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def print_json(data):
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1, default=str)
    sys.stdout.write("\n")


def run(cmd, cwd=None, check=True, input_bytes=None, timeout=None, env=None):
    """Run a command, return CompletedProcess with bytes stdout/stderr. FileNotFoundError becomes EXIT_MISSING."""
    try:
        result = subprocess.run(cmd, cwd=None if cwd is None else str(cwd), input=input_bytes,
                                capture_output=True, timeout=timeout, env=env)
    except FileNotFoundError:
        raise Failure(EXIT_MISSING, "command not found: %s" % cmd[0])
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip() or "exit code %d" % result.returncode
        raise Failure(EXIT_ERROR, "%s failed: %s" % (" ".join(cmd[:3]), message[:500]))
    return result


def git_bytes(repo, *args, check=True):
    return run(["git", "-C", str(repo)] + list(args), check=check).stdout


def git(repo, *args, check=True):
    return git_bytes(repo, *args, check=check).decode("utf-8", "replace")


def repo_root(path):
    """Top-level folder of the git repository containing path, or Failure(EXIT_NOT_REPO)."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise Failure(EXIT_NOT_REPO, "path not found: %s" % target)
    result = run(["git", "-C", str(target), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode == 0:
        return Path(result.stdout.decode().strip())
    bare = run(["git", "-C", str(target), "rev-parse", "--is-bare-repository"], check=False)
    if bare.returncode == 0 and bare.stdout.decode().strip() == "true":  # mirror clone: history only
        return Path(run(["git", "-C", str(target), "rev-parse", "--absolute-git-dir"]).stdout.decode().strip())
    raise Failure(EXIT_NOT_REPO, "not a git repository: %s" % target)


def git_version():
    """Installed git version as a tuple, e.g. (2, 47, 1)."""
    out = run(["git", "--version"]).stdout.decode()
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
    return tuple(int(part or 0) for part in match.groups()) if match else (0, 0, 0)


def state_dir(repo):
    """<git dir>/repo-showcase, created with owner-only permissions."""
    common = git(repo, "rev-parse", "--git-common-dir").strip()
    path = Path(common) if Path(common).is_absolute() else Path(repo) / common
    path = path / "repo-showcase"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(str(path), 0o700)
    return path


def tracked_files(repo):
    return [name for name in git_bytes(repo, "ls-files", "-z").decode("utf-8", "replace").split("\0") if name]


def is_binary(data):
    return b"\0" in data[:8000]


def read_text(path, limit=2000000):
    """Text content of a file, or None if binary, unreadable or larger than limit bytes."""
    try:
        path = Path(path)
        if path.stat().st_size > limit:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return None if is_binary(data) else data.decode("utf-8", "replace")


def github_slug(repo):
    """"owner/name" of the origin remote if it points to github.com, else None."""
    result = run(["git", "-C", str(repo), "remote", "get-url", "origin"], check=False)
    match = GITHUB_REMOTE_RE.search(result.stdout.decode().strip()) if result.returncode == 0 else None
    return "%s/%s" % match.groups() if match else None


def gh_json(args, check=True):
    """Run gh with args and parse its JSON output. Failure(EXIT_MISSING) if gh is absent, EXIT_NETWORK on error."""
    result = run(["gh"] + list(args), check=False, timeout=60)
    if result.returncode != 0:
        if not check:
            return None
        message = result.stderr.decode("utf-8", "replace").strip()
        raise Failure(EXIT_NETWORK, "gh %s failed: %s" % (" ".join(args[:2]), message[:300]))
    text = result.stdout.decode("utf-8", "replace").strip()
    return json.loads(text) if text else None


def fingerprint(value):
    """Stable short id of a sensitive value (same value, same id), safe to print and store."""
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:12]


def redact(value):
    """Preview that hints at a value without revealing it: 'sk…(40)', 'j***@g***.com'."""
    if "@" in value and "." in value.split("@")[-1]:
        local, domain = value.split("@", 1)
        name, _, tld = domain.rpartition(".")
        return "%s***@%s***.%s" % (local[:1], name[:1], tld)
    if len(value) <= 4:
        return "*" * len(value)
    return "%s…(%d)" % (value[:2], len(value))


def finding(category, severity, where, preview, fp, path=None, line=None, commit=None, remedy=(), detail=None):
    """One finding. where: working-tree | history | commit-message | identity | pull-request | release | metadata."""
    assert severity in SEVERITIES, severity
    item = {"category": category, "severity": severity, "where": where, "preview": preview, "fingerprint": fp,
            "path": path, "line": line, "commit": commit, "remedy": list(remedy)}
    if detail:
        item["detail"] = detail
    return item


def load_allowlist(repo):
    """Fingerprints accepted as false positives for this repository."""
    path = state_dir(repo) / "allow.json"
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("fingerprints", []))
    except (OSError, ValueError):
        return set()


def save_allowlist(repo, fingerprints):
    path = state_dir(repo) / "allow.json"
    path.write_text(json.dumps({"fingerprints": sorted(set(fingerprints))}, indent=1), encoding="utf-8")
    os.chmod(str(path), 0o600)
    return path


def local_settings():
    """Values of the claude-tools local.env (FORBIDDEN_TERMS, ALLOWED_TERMS...), or {} outside a clone."""
    sys.path.insert(0, str(TOOLS_ROOT / "lib"))
    try:
        import cttools
    except ImportError:
        return {}
    return cttools.load_local_env()


def split_terms(raw):
    return [term.strip().lower() for term in (raw or "").split(",") if term.strip()]


def ignored_line(line):
    """True if the line carries an accepted-false-positive marker."""
    return any(marker in line for marker in IGNORE_MARKERS)


def git_call(repo, *args, timeout=None):
    """(return code, stdout, stderr) of a git command as text; never raises (-1 when git cannot run or times out).
    Prompts are disabled so an unreachable remote fails instead of waiting for a password."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, timeout=timeout, env=env,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, "", str(error)
    return (result.returncode, result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"))


def remote_refs(repo, remote, timeout=120):
    """({ref: sha} of the branches and tags of remote (git ls-remote), None) or (None, error text) if unreachable.
    Annotated tags map to the tag object, as in the local refs/tags."""
    code, out, err = git_call(repo, "ls-remote", remote, timeout=timeout)
    if code != 0:
        return None, (err.strip() or "exit code %d" % code)[-300:]
    refs = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith(("refs/heads/", "refs/tags/")) and not ref.endswith("^{}"):
            refs[ref] = sha.strip()
    return refs, None


def local_refs(repo):
    """{ref: sha} of the local branches and tags."""
    out = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags", check=False)
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line)
