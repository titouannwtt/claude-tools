#!/usr/bin/env python3
"""Pre-commit check: secrets, personal names and paths in the content.

Scans the content that will actually be committed (git index) or every tracked file of the repo.
Forbidden terms (name, handle, domain) are never written in the repo: they come from local.env
(key FORBIDDEN_TERMS, comma-separated, case-insensitive). ALLOWED_TERMS (same format) lists the
public strings that contain a forbidden term without being a leak (e.g. the GitHub handle in a URL).

Usage: check_repo.py [--staged | --all] [--root DIR] [--local-env FILE] [--identity]
       check_repo.py --commit-msg FILE   (commit-msg hook: rejects any mention of an AI assistant)
The git email (user.email) must always be a noreply address (e.g. ID+handle@users.noreply.github.com):
otherwise the commit is rejected. The git name is only checked against FORBIDDEN_TERMS on request (--identity).
False positive: add the comment "check-repo: ignore" on the line concerned.
Output: one line per finding (type, file:line), never the value found.
Exit codes: 0 nothing found; 1 findings; 2 usage error or repo not found.
Python 3.9 compatible.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER_USERS = {"user", "username", "you", "name", "me", "runner", "ubuntu", "example", "your-name",
                     "yourname", "<user>", "$user", "nom"}
SAFE_EMAIL_PARTS = ("noreply", "no-reply", "example.com", "example.org", "@localhost")
SAFE_IP_PREFIXES = ("127.", "0.", "192.0.2.", "198.51.100.", "203.0.113.")
# A line carrying this marker is ignored (accepted false positive: public address, test value).
IGNORE_MARKER = "check-repo: ignore"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?![\d.])")
HOME_RE = re.compile(r"/(?:Users|home)/([A-Za-z0-9._<>$-]+)")
USERINFO_RE = re.compile(r"://([^/\s:@]+):([^/\s@]+)@([A-Za-z0-9.-]+)")
SECRET_RES = (
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
# No commit mentions an AI assistant as co-author or generator (CLAUDE.md rule, Git section).
AI_ATTRIBUTION_RE = re.compile(
    r"co-authored-by:.*(claude|anthropic)|noreply@anthropic\.com|generated with \[?claude|claude\.com/claude-code",
    re.IGNORECASE)


def load_terms(local_env, key="FORBIDDEN_TERMS"):
    """Terms read from local.env (FORBIDDEN_TERMS by default); empty list if the file or the key is missing."""
    if not local_env or not Path(local_env).is_file():
        return []
    for line in Path(local_env).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            raw = line.split("=", 1)[1].strip().strip("\"'")
            return [term.strip().lower() for term in raw.split(",") if term.strip()]
    return []


def scan_text(text, terms, allowed=()):
    """Return [(type, line number)] for a text. The values found are never returned."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if IGNORE_MARKER in line:
            continue
        lowered = line.lower()
        for public in allowed:
            lowered = lowered.replace(public, " ")
        for term in terms:
            if term in lowered:
                findings.append(("forbidden term", number))
                break
        for match in EMAIL_RE.finditer(line):
            address = match.group(0).lower()
            if not (any(safe in address for safe in SAFE_EMAIL_PARTS) or address.endswith(".example")):
                findings.append(("email address", number))
        for match in IPV4_RE.finditer(line):
            if not match.group(1).startswith(SAFE_IP_PREFIXES):
                findings.append(("IP address", number))
        for match in HOME_RE.finditer(line):
            if match.group(1).lower() not in PLACEHOLDER_USERS:
                findings.append(("personal path", number))
        for match in USERINFO_RE.finditer(line):
            host = match.group(3).lower()
            if not (host.endswith(".example") or host.startswith("example.") or host == "localhost"):
                findings.append(("credentials in a URL", number))
        for label, pattern in SECRET_RES:
            if pattern.search(line):
                findings.append((label, number))
    return findings


def scan_commit_message(text):
    """Line numbers of a commit message that credit the commit to an AI assistant (comments excluded)."""
    return [number for number, line in enumerate(text.splitlines(), 1)
            if not line.startswith("#") and AI_ATTRIBUTION_RE.search(line)]


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def files_to_scan(root, mode):
    if mode == "staged":
        names = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z")
    else:
        names = git(root, "ls-files", "-z")
    return [n for n in names.decode("utf-8").split("\0") if n]


def read_content(root, name, mode):
    data = git(root, "show", ":" + name) if mode == "staged" else (Path(root) / name).read_bytes()
    if b"\0" in data[:8000]:
        return None  # binary
    return data.decode("utf-8", "replace")


def check_identity(root, terms, allowed=()):
    """Check the configured git identity (name and email of future commits), except allowed public terms."""
    findings = []
    for key in ("user.name", "user.email"):
        try:
            value = git(root, "config", key).decode("utf-8").strip()
        except RuntimeError:
            continue
        lowered = value.lower()
        for public in allowed:
            lowered = lowered.replace(public, " ")
        if any(term in lowered for term in terms):
            findings.append(("git identity (%s)" % key, 0))
    return findings


def check_email(root):
    """Reject a real git email: only noreply addresses are accepted."""
    try:
        value = git(root, "config", "user.email").decode("utf-8").strip().lower()
    except RuntimeError:
        return ["git email missing (user.email): configure a noreply address"]
    if "noreply" not in value.split("@")[-1] and not value.startswith("noreply@"):
        return ["real git email (user.email): use a noreply address"]
    return []


def run(root, mode, local_env, identity=False):
    terms = load_terms(local_env)
    allowed = load_terms(local_env, "ALLOWED_TERMS")
    report = [] if mode == "all" else check_email(root)
    for name in files_to_scan(root, mode):
        content = read_content(root, name, mode)
        if content is None:
            continue
        for kind, number in scan_text(content, terms, allowed):
            report.append("%s: %s:%d" % (kind, name, number))
    if identity:
        report += ["%s" % kind for kind, _ in check_identity(root, terms, allowed)]
    return report, bool(terms)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="index content (default)")
    group.add_argument("--all", action="store_true", help="all tracked files")
    group.add_argument("--commit-msg", metavar="FILE", help="commit message to check (commit-msg hook)")
    parser.add_argument("--identity", action="store_true", help="also check user.name and user.email")
    parser.add_argument("--root", default=".")
    parser.add_argument("--local-env", default=None, help="default: local.env at the repo root")
    args = parser.parse_args(argv)
    if args.commit_msg:
        lines = scan_commit_message(Path(args.commit_msg).read_text(encoding="utf-8", errors="replace"))
        for number in lines:
            print("AI assistant mention: commit message, line %d" % number)
        if lines:
            print("commit rejected: remove the line (no Co-Authored-By nor AI \"Generated with\" line)", file=sys.stderr)
        return 1 if lines else 0
    root = Path(args.root).resolve()
    local_env = args.local_env or str(root / "local.env")
    try:
        report, has_terms = run(root, "all" if args.all else "staged", local_env, args.identity)
    except RuntimeError as error:
        print("git error: %s" % error, file=sys.stderr)
        return 2
    if not has_terms:
        print("warning: FORBIDDEN_TERMS missing from local.env, personal names are not checked",
              file=sys.stderr)
    for line in report:
        print(line)
    if report:
        print("%d finding(s): commit rejected" % len(report), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
