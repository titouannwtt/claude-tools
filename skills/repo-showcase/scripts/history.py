#!/usr/bin/env python3
"""Rewrite git history to remove secrets, personal data and AI co-authorship (engine: git-filter-repo).

Usage: showcase.py fix-plan <repo> [--map-email OLD=NEW]... [--map-name OLD=NEW]... [--map-mine] [--strip-ai]
                                   [--replace FINGERPRINT]... [--replace-category secret,email,...]
                                   [--remove-path PATH]... [--strip-blobs-bigger-than 10M] [--terms a,b]
                                   [--no-dry-run] [--remote origin]
       showcase.py fix-apply <repo> --confirm [--backup-dir DIR] [--push] [--remote origin]
       showcase.py fix-prs <repo> [--confirm] [--limit 300]

fix-plan fetches the remote (default origin) and refuses when it is unreachable or holds work the local refs lack
(branch behind or diverged, remote-only branch or tag). It writes the plan files in <git dir>/repo-showcase/plan/
(mailmap.txt, replacements.txt with the exact texts to remove as bounded regex lines: mode 600,
message-callback.py, paths.txt, terms.txt, plan.json with the remote ref shas) and, by default, runs the exact
rewrite on a temporary mirror clone, then rescans it with the scanner itself ("remaining" must be 0). Values
inside zipped documents need an explicit --remove-path. fix-apply refuses without --confirm, with uncommitted
changes to tracked files, when local refs or the remote moved since the plan, without git-filter-repo or with git
older than 2.36. It makes a verified `git bundle` and a tar.gz of the git directory first, rewrites, restores the
remotes (also on failure or interrupt), rescans, deletes the sensitive plan files on success and prints one
`git push --atomic --force-with-lease=<ref>:<sha>` command for the refs that already exist on the remote
(--push runs it).
fix-prs removes AI mentions from pull request and release texts through `gh api`.
Exit codes: 0 ok; 1 error or targets remaining after the rewrite; 4 plan leaves targets in the clone; 5 gh
or an explicit mapping is missing; 6 refusal (no --confirm, dirty tree, old git, stale plan); 7 push or gh
error. Python 3.9 compatible.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_ERROR, EXIT_FINDINGS, EXIT_MISSING, EXIT_NETWORK, EXIT_OK,  # noqa: E402
                    EXIT_REFUSED, EXIT_USAGE, Failure, git, git_bytes, git_call, git_version, github_slug,
                    load_allowlist, local_refs, print_json, redact, remote_refs, repo_root, run, state_dir)
from scan import (AI_LINE_PATTERNS, AI_SUBJECT_RE, ai_identity, attribution_scan, collect_hits,  # noqa: E402
                  fetch_pull_requests, fetch_releases, gh_user, history_blobs, list_identities, safe_email,
                  strip_ai_text, ai_line_match)

MIN_GIT = (2, 36)
TEXT_CATEGORIES = frozenset(("secret", "credentials-url", "email", "ip", "port", "username", "personal-name", "phone",
                             "postal-address", "iban", "card-number"))
PATH_CATEGORIES = frozenset(("env-file", "credential-file", "personal-file", "photo", "photo-location",
                             "photo-person"))
MIN_LITERAL = 4
REMOVED = "***REMOVED***"
STATE_NAME = "repo-showcase"
# Personal terms the scanner matches anywhere, even inside a word: the replacement must do the same.
UNBOUNDED_TERM_SOURCES = ("term source: --terms", "term source: FORBIDDEN_TERMS")
SENSITIVE_PLAN_FILES = ("replacements.txt", "mailmap.txt", "paths.txt", "message-callback.py", "terms.txt")
SIZE_RE = re.compile(r"^\d+[KMG]?$", re.IGNORECASE)
MAILMAP_RE = re.compile(r"^\s*(?:(?P<pname>[^<]*?)\s*)?<(?P<pemail>[^>]*)>\s*(?:(?P<cname>[^<]*?)\s*)?"
                        r"<(?P<cemail>[^>]*)>\s*$")
REMOTE_CLEANUP = (
    "Rotate every exposed secret now: a secret that was ever public must be considered compromised.",
    "Forks and clones made before the rewrite keep the old commits: ask their owners to delete or re-clone them.",
    "Cached views of old commits stay reachable by SHA on GitHub until the server garbage-collects them; "
    "contact GitHub Support to purge them.",
    "refs/pull/* are read-only on GitHub: closed pull requests keep the old commits; only GitHub Support can "
    "remove them.",
    "Collaborators must re-clone (or `git fetch` then `git reset --hard origin/<branch>`): their old history "
    "would otherwise be merged back.",
    "Delete the backup bundle and the git directory archive once the result is verified: they still contain the "
    "removed data.",
)
CALLBACK_TEMPLATE = '''import re
PATTERNS = [re.compile(p.encode("utf-8"), re.IGNORECASE) for p in %s]
SUBJECT = re.compile(rb"^aider:\\s+", re.IGNORECASE)
lines = message.split(b"\\n")
kept = [line for line in [SUBJECT.sub(b"", lines[0])] + lines[1:] if not any(p.search(line) for p in PATTERNS)]
if kept == lines:
    return message
while kept and not kept[0].strip():
    kept.pop(0)
while kept and not kept[-1].strip():
    kept.pop()
return b"\\n".join(kept or [b"Update"]) + b"\\n"
'''


# ---------------------------------------------------------------- engine and snapshot

def engine_status():
    """(ok, reason): git >= 2.36 and git-filter-repo installed."""
    version = git_version()
    if version < MIN_GIT:
        return False, "git %s is too old for git-filter-repo (needs >= 2.36)" % ".".join(map(str, version))
    result = run(["git", "filter-repo", "--version"], check=False)
    if result.returncode != 0:
        return False, "git-filter-repo is not installed (pip install git-filter-repo)"
    return True, result.stdout.decode().strip()


def require_engine():
    ok, reason = engine_status()
    if not ok:
        raise Failure(EXIT_REFUSED, "%s. Run the history rewrite on a machine with git >= 2.36 and "
                      "git-filter-repo." % reason)


def snapshot(repo):
    """(hash of all refs, HEAD sha): the plan is valid only while both are unchanged."""
    refs = git_bytes(repo, "for-each-ref", check=False)
    head = git(repo, "rev-parse", "-q", "--verify", "HEAD", check=False).strip()
    return hashlib.sha256(refs).hexdigest(), head


def size_kib(repo):
    out = git(repo, "count-objects", "-v")
    values = dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)
    return int(values.get("size", 0)) + int(values.get("size-pack", 0))


def write_private(path, text):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(str(path), 0o600)


def plan_dir_of(repo):
    path = state_dir(repo) / "plan"
    path.mkdir(exist_ok=True)
    os.chmod(str(path), 0o700)
    return path


# ---------------------------------------------------------------- plan building

def parse_pair(raw, option):
    if "=" not in raw or not raw.split("=", 1)[0].strip() or not raw.split("=", 1)[1].strip():
        raise Failure(EXIT_USAGE, "%s expects OLD=NEW, got an invalid value" % option)
    old, new = raw.split("=", 1)
    return old.strip(), new.strip()


def mailmap_for(repo, args, identities):
    """(mailmap lines, mapped old (name or None, email) pairs, warnings, third-party identity list)."""
    lines, olds, warnings = [], [], []
    for raw in args.map_email:
        old, new = parse_pair(raw, "--map-email")
        if "@" not in old or "@" not in new:
            raise Failure(EXIT_USAGE, "--map-email expects two e-mail addresses (OLD=NEW or OLD=Name <NEW>)")
        proper = new if "<" in new else "<%s>" % new
        lines.append("%s <%s>" % (proper, old.strip("<>")))
        olds.append((None, old.strip("<>").lower()))
    for raw in args.map_name:
        old, new = parse_pair(raw, "--map-name")
        matched = [i for i in identities if i["name"] == old and i["email"]]
        if not matched:
            warnings.append("--map-name: no identity carries that name")
        for entry in matched:
            lines.append("%s <%s> %s <%s>" % (new, entry["email"], old, entry["email"]))
            olds.append((old, entry["email"].lower()))
    if args.map_mine:
        user = gh_user(repo)
        if not user:
            if not (args.map_email or args.map_name):
                raise Failure(EXIT_MISSING, "--map-mine needs `gh api user` (gh installed and logged in) to build "
                              "the noreply address; otherwise pass --map-email OLD=ID+LOGIN@users.noreply.github.com")
            warnings.append("--map-mine skipped: gh user unavailable")
        else:
            noreply = ("%s+%s" % (user["id"], user["login"]) if user.get("id") else str(user["login"])) \
                + "@users.noreply.github.com"
            names = {n.lower() for n in (git(repo, "config", "user.name", check=False).strip(), user.get("name"),
                                         user.get("login")) if n}
            for entry in identities:
                if entry["name"].lower() in names and entry["email"] and "noreply" not in entry["email"].lower():
                    lines.append("%s <%s> %s <%s>" % (entry["name"], noreply, entry["name"], entry["email"]))
                    olds.append((entry["name"], entry["email"].lower()))
    mapped = {email for _, email in olds}
    third_party = [{"name": redact(i["name"]), "email": redact(i["email"]), "commits": i["count"],
                    "roles": sorted(i["roles"])}
                   for i in identities
                   if i["email"] and i["email"].lower() not in mapped and not safe_email(i["email"])]
    return lines, olds, warnings, third_party


def replacements_for(repo, args, terms):
    """Text targets of --replace and --replace-category, from the exact texts the scanner matched.

    Returns a dict: targets {exact text: boundary flag}, paths (extra --remove-path), fingerprints (all selected),
    text_fingerprints (verified by rescan), warnings, skipped (too short), routed (values only reachable by
    removing their file)."""
    wanted_fp = set(args.replace)
    categories = {c.strip() for c in (args.replace_category or "").split(",") if c.strip()}
    bad = categories - TEXT_CATEGORIES
    if bad:
        raise Failure(EXIT_USAGE, "--replace-category accepts only text categories (%s); use --remove-path for "
                      "files: %s" % (", ".join(sorted(TEXT_CATEGORIES)), ", ".join(sorted(bad))))
    out = {"targets": {}, "paths": [], "fingerprints": set(), "text_fingerprints": set(), "warnings": [],
           "skipped": 0, "routed": []}
    if not wanted_fp and not categories:
        return out
    hits, _ = collect_hits(repo, history=True, terms=terms, include_remote=False, allow=set(), dedupe=False)
    allowed = load_allowlist(repo)
    targets, paths, warnings = out["targets"], out["paths"], out["warnings"]
    routed = {}
    for hit in hits:
        by_fp = hit["fingerprint"] in wanted_fp
        by_cat = hit["category"] in categories and hit["fingerprint"] not in allowed
        if not (by_fp or by_cat):
            continue
        out["fingerprints"].add(hit["fingerprint"])
        if hit["category"] in PATH_CATEGORIES and by_fp:
            if hit["path"] and hit["path"] not in paths:
                paths.append(hit["path"])
            continue
        if hit["category"] not in TEXT_CATEGORIES or hit["where"] == "identity":
            continue
        out["text_fingerprints"].add(hit["fingerprint"])
        exact = hit.get("_match") or hit["_value"]
        if hit.get("_in_name"):
            warnings.append("fingerprint %s is in the file name %s: a text replacement cannot rename it; rename "
                            "the file (git mv) and add --remove-path for the old name, or allow the fingerprint"
                            % (hit["fingerprint"], hit["path"]))
            continue
        if hit.get("_office") or "�" in exact:
            why = "inside a zipped document" if hit.get("_office") else "in a file that is not valid UTF-8"
            if not hit["path"]:
                warnings.append("fingerprint %s is in a message that is not valid UTF-8: it cannot be replaced"
                                % hit["fingerprint"])
                continue
            routed.setdefault(hit["path"], {"path": hit["path"], "reason": why, "fingerprints": set()})[
                "fingerprints"].add(hit["fingerprint"])
            continue
        if len(exact) < MIN_LITERAL:
            out["skipped"] += 1
            continue
        boundary = not (hit["category"] == "personal-name" and
                        any(s in (hit.get("detail") or "") for s in UNBOUNDED_TERM_SOURCES))
        targets[exact] = targets.get(exact, True) and boundary
    for fp in sorted(wanted_fp - out["fingerprints"]):
        warnings.append("fingerprint %s not found by the scan" % fp)
    for entry in routed.values():
        warnings.append("%d targeted value(s) %s: %s cannot be edited by a text replacement; removing the whole "
                        "file from every commit needs the user's agreement and an explicit --remove-path, otherwise "
                        "allow the fingerprints" % (len(entry["fingerprints"]), entry["reason"], entry["path"]))
        out["routed"].append({"path": entry["path"], "reason": entry["reason"],
                              "fingerprints": sorted(entry["fingerprints"])})
    return out


def _escape(text):
    """Regex source matching text exactly, on one line, without '==>' (filter-repo splits lines on it)."""
    out = []
    for char in text:
        if char.isascii() and (char.isalnum() or char == "_"):
            out.append(char)
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif ord(char) < 32 or ord(char) == 127:
            out.append("\\x%02x" % ord(char))
        elif char.isascii():
            out.append("\\" + char)
        else:
            out.append(char)
    return "".join(out)


def replacement_pattern(text, boundary=True):
    """Regex (Python re, applied to bytes by filter-repo) for an exact text, with boundaries so neighbours survive:
    no letter or digit glued to the value, and for a value starting or ending with a digit no 'digit.' before
    and no '.digit' after (an IP address must not match inside a longer one)."""
    body = _escape(text)
    if not boundary:
        return body
    first, last = text[0], text[-1]
    before = after = ""
    if first.isascii() and first.isalnum():
        before = "(?<![A-Za-z0-9])"
        if first.isdigit():
            before += "(?<![0-9]\\.)"
    if last.isascii() and last.isalnum():
        after = "(?![A-Za-z0-9])"
        if last.isdigit():
            after += "(?!\\.[0-9])"
    return before + body + after


def replacement_line(text, boundary=True):
    return "regex:%s==>%s" % (replacement_pattern(text, boundary), REMOVED)


def callback_source():
    return CALLBACK_TEMPLATE % ascii([pattern for _, pattern in AI_LINE_PATTERNS])


# ---------------------------------------------------------------- remote safety

def remote_names(repo):
    return set(git(repo, "remote", check=False).split())


def _is_ancestor(repo, old, new):
    return git_call(repo, "merge-base", "--is-ancestor", old, new)[0] == 0


def remote_check(repo, remote):
    """Fetch remote and compare it with the local branches and tags.

    Returns {"remote", "url", "refs", "ahead", "not_on_remote"}, or None when the remote does not exist. Refuses
    (EXIT_REFUSED) when the remote is unreachable or holds work the local refs do not have: a rewrite followed by
    a force push would destroy it, and remote-only refs would never be rewritten."""
    if remote not in remote_names(repo):
        return None
    code, _, err = git_call(repo, "fetch", "--prune", "--quiet", remote, timeout=600)
    if code != 0:
        raise Failure(EXIT_REFUSED, "cannot fetch the remote %s (offline or no access: %s). The plan needs the "
                      "current state of the remote so that the force push cannot destroy work pushed by others: "
                      "retry when %s is reachable" % (remote, err.strip()[-200:], remote))
    refs, error = remote_refs(repo, remote)
    if refs is None:
        raise Failure(EXIT_REFUSED, "cannot list the refs of %s (%s): retry when it is reachable" % (remote, error))
    local = local_refs(repo)
    problems, ahead = [], []
    for ref, sha in sorted(refs.items()):
        mine = local.get(ref)
        short = ref.split("/", 2)[2]
        if ref.startswith("refs/heads/"):
            if mine is None:
                problems.append("branch %s exists only on %s: create it locally with `git branch --track %s %s/%s`"
                                % (short, remote, short, remote, short))
            elif mine != sha:
                if _is_ancestor(repo, sha, mine):
                    ahead.append(short)
                elif _is_ancestor(repo, mine, sha):
                    problems.append("branch %s is behind %s/%s: integrate it first (`git pull` on %s)"
                                    % (short, remote, short, short))
                else:
                    problems.append("branch %s and %s/%s have diverged: merge or rebase first" % (short, remote, short))
        elif mine is None:
            problems.append("tag %s exists only on %s: fetch it with `git fetch %s tag %s`" % (short, remote, remote,
                                                                                               short))
        elif mine != sha:
            problems.append("tag %s differs from the tag on %s: make them identical first" % (short, remote))
    if problems:
        raise Failure(EXIT_REFUSED, "the remote %s holds work that the local branches and tags do not have; a "
                      "rewrite and force push would destroy it or leave it unrewritten. Fix this first, then run "
                      "fix-plan again: %s" % (remote, "; ".join(problems)))
    url = git(repo, "remote", "get-url", remote, check=False).strip()
    return {"remote": remote, "url": url, "refs": refs, "ahead": ahead,
            "not_on_remote": sorted(r for r in local if r not in refs)}


# ---------------------------------------------------------------- plan building

def build_plan(repo, args):
    remote = remote_check(repo, args.remote)
    plan_dir = plan_dir_of(repo)
    for old in plan_dir.iterdir():
        if old.is_file():
            old.unlink()
    identities = list_identities(repo)
    mailmap, olds, warnings, third_party = mailmap_for(repo, args, identities)
    found = replacements_for(repo, args, args.terms)
    warnings += found["warnings"]
    targets = found["targets"]
    paths = list(args.remove_path)
    unapproved = [entry["path"] for entry in found["routed"] if entry["path"] not in paths]
    if unapproved:  # never delete a file implicitly: the user must agree, then the agent passes --remove-path
        raise Failure(EXIT_REFUSED, "targeted values sit in files a text replacement cannot edit (zipped documents "
                      "or non-UTF-8 files): %s. Ask the user, then rerun with --remove-path for each file to remove "
                      "it from every commit, or allow the fingerprints" % ", ".join(sorted(unapproved)))
    for path in found["paths"]:
        if path not in paths:
            paths.append(path)
    if args.strip_blobs_bigger_than and not SIZE_RE.match(args.strip_blobs_bigger_than):
        raise Failure(EXIT_USAGE, "--strip-blobs-bigger-than expects a size such as 10M")
    if not (mailmap or targets or found["text_fingerprints"] or args.strip_ai or paths
            or args.strip_blobs_bigger_than):
        raise Failure(EXIT_REFUSED, "nothing to do: give at least one of --map-email, --map-name, --map-mine, "
                      "--strip-ai, --replace, --replace-category, --remove-path, --strip-blobs-bigger-than")
    files, filter_args = {}, []
    if mailmap:
        path = plan_dir / "mailmap.txt"
        write_private(path, "\n".join(mailmap) + "\n")
        files["mailmap"] = str(path)
        filter_args += ["--mailmap", str(path)]
    if targets:
        path = plan_dir / "replacements.txt"
        ordered = sorted(targets, key=lambda t: (-len(t), t))  # longest first: a value inside another goes last
        write_private(path, "\n".join(replacement_line(t, targets[t]) for t in ordered) + "\n")
        files["replacements"] = str(path)
        filter_args += ["--replace-text", str(path), "--replace-message", str(path)]
    if args.terms:
        path = plan_dir / "terms.txt"
        write_private(path, args.terms + "\n")
        files["terms"] = str(path)
    if args.strip_ai:
        path = plan_dir / "message-callback.py"
        write_private(path, callback_source())
        files["message_callback"] = str(path)
        filter_args += ["--message-callback", str(path)]
    if paths:
        path = plan_dir / "paths.txt"
        write_private(path, "\n".join("literal:" + p for p in paths) + "\n")
        files["paths"] = str(path)
        filter_args += ["--invert-paths", "--paths-from-file", str(path)]
    if args.strip_blobs_bigger_than:
        filter_args += ["--strip-blobs-bigger-than", args.strip_blobs_bigger_than.upper()]
    refs_hash, head = snapshot(repo)
    plan = {"created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "repo": str(repo), "refs_hash": refs_hash, "head": head, "args": filter_args, "files": files,
            "counts": {"mailmap_entries": len(mailmap), "replacements": len(targets), "paths": len(paths)},
            "paths": paths, "strip_ai": bool(args.strip_ai),
            "target_fingerprints": sorted(found["text_fingerprints"]),
            "blob_limit": args.strip_blobs_bigger_than.upper() if args.strip_blobs_bigger_than else None,
            "remote": remote["remote"] if remote else None, "remote_url": remote["url"] if remote else None,
            "remote_refs": remote["refs"] if remote else {}}
    write_private(plan_dir / "plan.json", json.dumps(plan, indent=1))
    ai_ids = [{"name": i["name"], "email": i["email"], "commits": i["count"]} for i in identities
              if ai_identity(i["name"], i["email"])]
    extra = {"warnings": warnings, "third_party_identities": third_party, "ai_identities": ai_ids,
             "skipped_short_values": found["skipped"], "fingerprints": sorted(found["fingerprints"]),
             "routed_to_path_removal": found["routed"]}
    if remote:
        extra["remote"] = {"name": remote["remote"], "branches_ahead": remote["ahead"],
                           "not_pushed": remote["not_on_remote"],
                           "note": "only refs that already exist on %s are pushed (with a lease); the refs under "
                                   "not_pushed stay local" % remote["remote"]}
    else:
        extra["remote"] = {"name": args.remote, "note": "no remote named %s: nothing will be pushed" % args.remote}
    return plan, plan_dir, extra


# ---------------------------------------------------------------- verification

def blob_limit_bytes(text):
    if not text:
        return None
    unit = {"K": 1024, "M": 1048576, "G": 1073741824}.get(text[-1].upper(), 1)
    return int(text[:-1] if text[-1].isalpha() else text) * unit


def read_mailmap_olds(plan_dir):
    path = plan_dir / "mailmap.txt"
    if not path.exists():
        return []
    olds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MAILMAP_RE.match(line)
        if match:
            olds.append((match.group("cname") or None, match.group("cemail").lower()))
    return olds


def read_terms(plan_dir):
    path = plan_dir / "terms.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def remaining_targets(repo, plan_dir, plan):
    """Counts of targeted items still present in repo (all must be 0). Values are found again by the scanner itself
    (same detectors, same fingerprints), never by searching the replaced texts."""
    result = {"values": 0, "identities": 0, "ai_messages": 0, "paths": 0, "big_blobs": 0}
    targets = set(plan.get("target_fingerprints") or [])
    if targets:
        hits, _ = collect_hits(repo, history=True, terms=read_terms(plan_dir), include_remote=False, allow=set(),
                               dedupe=False)
        result["values"] = sum(1 for hit in hits if hit["fingerprint"] in targets and hit["where"] != "identity")
    olds = read_mailmap_olds(plan_dir)
    if olds:
        for entry in list_identities(repo):
            if any(entry["email"].lower() == email and (name is None or entry["name"] == name) for name, email in olds):
                result["identities"] += 1
    if plan.get("strip_ai"):
        found = attribution_scan(repo, include_remote=False)["findings"]
        result["ai_messages"] = sum(1 for f in found if f["category"] == "ai-coauthor" and f["where"] ==
                                    "commit-message")
    blobs = history_blobs(repo) if plan.get("paths") or plan.get("blob_limit") else []
    for target in plan.get("paths", []):
        result["paths"] += sum(1 for _, _, path in blobs if path == target or path.startswith(target + "/"))
    limit = blob_limit_bytes(plan.get("blob_limit"))
    if limit:
        result["big_blobs"] = sum(1 for _, size, _ in blobs if size > limit)
    result["total"] = sum(result.values())
    return result


def rewrite_stats(source, clone):
    """Commits and refs rewritten, from the commit-map and ref-map files of git-filter-repo."""
    stats = {"commits_rewritten": 0, "first_rewritten_commit": None, "refs_affected": []}
    commit_map = Path(clone) / "filter-repo" / "commit-map"
    changed = set()
    if commit_map.exists():
        for line in commit_map.read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2 and parts[0] != parts[1]:
                changed.add(parts[0])
    stats["commits_rewritten"] = len(changed)
    if changed:
        dates = []
        for line in git(source, "log", "--all", "--format=%H %ct", check=False).splitlines():
            sha, _, stamp = line.partition(" ")
            if sha in changed and stamp.isdigit():
                dates.append(int(stamp))
        if dates:
            stats["first_rewritten_commit"] = datetime.datetime.fromtimestamp(
                min(dates), datetime.timezone.utc).isoformat(timespec="seconds")
    ref_map = Path(clone) / "filter-repo" / "ref-map"
    if ref_map.exists():
        for line in ref_map.read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) == 3 and parts[0] != parts[1]:
                stats["refs_affected"].append(parts[2])
    stats["refs_affected_total"] = len(stats["refs_affected"])
    stats["refs_affected"] = stats["refs_affected"][:30]
    return stats


def dry_run(repo, plan_dir, plan):
    """Run the plan on a temporary mirror clone; report the effect and rescan the clone."""
    work = tempfile.mkdtemp(prefix="repo-showcase-dry-")
    try:
        clone = Path(work) / "mirror.git"
        run(["git", "clone", "--quiet", "--mirror", "--no-local", str(repo), str(clone)])
        before = size_kib(clone)
        run(["git", "-C", str(clone), "filter-repo", "--force"] + plan["args"])
        report = rewrite_stats(repo, clone)
        report["size_kib_before"], report["size_kib_after"] = before, size_kib(clone)
        report["remaining"] = remaining_targets(clone, plan_dir, plan)
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)


def cmd_fix_plan(args):
    repo = repo_root(args.repo)
    if not args.no_dry_run:
        require_engine()
    plan, plan_dir, extra = build_plan(repo, args)
    result = {"ok": True, "plan_dir": str(plan_dir), "files": plan["files"], "filter_repo_args": plan["args"],
              "counts": plan["counts"], "refs_hash": plan["refs_hash"], "head": plan["head"], "dry_run": None}
    result.update(extra)
    code = EXIT_OK
    if not args.no_dry_run:
        result["dry_run"] = dry_run(repo, plan_dir, plan)
        if result["dry_run"]["remaining"]["total"]:
            result["ok"] = False
            result["error"] = "the plan leaves targeted data in the rewritten clone (see dry_run.remaining)"
            code = EXIT_FINDINGS
    else:
        result["note"] = "dry run skipped: nothing was tested; fix-apply will rescan after the rewrite"
    result["next"] = "fix-apply %s --confirm" % repo
    print_json(result)
    return code


# ---------------------------------------------------------------- apply

def record_remotes(repo):
    remotes = []
    for name in git(repo, "remote", check=False).split():
        fetch = git(repo, "remote", "get-url", name, check=False).strip()
        push = git(repo, "remote", "get-url", "--push", "--all", name, check=False).split()
        remotes.append({"name": name, "fetch": fetch, "push": push})
    return remotes


def record_tracking(repo):
    """{branch: (remote, merge)} from the config, restored after the rewrite."""
    out = git(repo, "config", "--get-regexp", r"^branch\..*\.(remote|merge)$", check=False)
    tracking = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        branch, _, field = key[len("branch."):].rpartition(".")
        tracking.setdefault(branch, {})[field] = value
    return {b: v for b, v in tracking.items() if "remote" in v and "merge" in v}


def record_remote_tracking_refs(repo):
    out = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes", check=False)
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line)


def restore_remotes(repo, remotes, tracking, tracking_refs=None):
    """Re-add the remotes git-filter-repo removed and the branch upstream config; with tracking_refs (after a
    failure), also the remote-tracking refs it deleted. Never raises: returns (restored names, errors)."""
    restored, errors = [], []
    present = remote_names(repo)
    for remote in remotes:
        if remote["name"] in present or not remote["fetch"]:
            continue
        steps = [["remote", "add", remote["name"], remote["fetch"]]]
        if remote["push"] and remote["push"] != [remote["fetch"]]:
            steps.append(["remote", "set-url", "--push", remote["name"], remote["push"][0]])
            steps += [["remote", "set-url", "--add", "--push", remote["name"], extra] for extra in remote["push"][1:]]
        failed = [step for step in steps if git_call(repo, *step)[0] != 0]
        if failed:
            errors.append("could not restore the remote %s (%s)" % (remote["name"], remote["fetch"]))
        else:
            restored.append(remote["name"])
    known = {r["name"] for r in remotes}
    for branch, value in tracking.items():
        if value["remote"] in known:
            for field in ("remote", "merge"):
                if git_call(repo, "config", "branch.%s.%s" % (branch, field), value[field])[0] != 0:
                    errors.append("could not restore branch.%s.%s" % (branch, field))
    current = record_remote_tracking_refs(repo)
    for ref, sha in sorted((tracking_refs or {}).items()):
        if ref not in current and git_call(repo, "update-ref", ref, sha)[0] != 0:
            errors.append("could not restore %s" % ref)
    return restored, errors


def push_plan(repo, remote, recorded):
    """(push command or None, refs pushed, remote refs left untouched because the rewrite deleted them locally).
    Only refs that already existed on the remote are pushed, each with a lease on the sha recorded by fix-plan:
    if someone pushed meanwhile, the push is rejected instead of erasing their work."""
    local = local_refs(repo)
    pushed = [ref for ref in sorted(recorded) if ref in local]
    gone = [ref for ref in sorted(recorded) if ref not in local]
    if not pushed:
        return None, [], gone
    command = ["git", "-C", str(repo), "push", "--atomic"]
    command += ["--force-with-lease=%s:%s" % (ref, recorded[ref]) for ref in pushed]
    command += [remote] + ["%s:%s" % (ref, ref) for ref in pushed]
    return command, pushed, gone


def make_backups(repo, backup_dir):
    """Verified bundle of every ref plus a tar.gz of the whole git directory (reflogs and unreachable objects
    included, the repo-showcase state folder excluded), both mode 600. Returns {bundle, archive, restore...}."""
    created = not backup_dir.exists()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        if created:
            os.chmod(str(backup_dir), 0o700)
    except OSError as error:
        raise Failure(EXIT_REFUSED, "cannot create the backup folder %s: %s" % (backup_dir, error))
    if not os.access(str(backup_dir), os.W_OK):
        raise Failure(EXIT_REFUSED, "the backup folder %s is not writable: pass --backup-dir" % backup_dir)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = backup_dir / ("%s-%s.bundle" % (repo.name, stamp))
    run(["git", "-C", str(repo), "bundle", "create", str(bundle), "--all"])
    os.chmod(str(bundle), 0o600)
    verified = run(["git", "-C", str(repo), "bundle", "verify", str(bundle)], check=False)
    if verified.returncode != 0:
        raise Failure(EXIT_ERROR, "the backup bundle did not verify, nothing was rewritten: %s"
                      % verified.stderr.decode("utf-8", "replace")[:300])
    git_dir = state_dir(repo).parent
    archive = backup_dir / ("%s-%s.git.tar.gz" % (repo.name, stamp))
    excluded = ".git/" + STATE_NAME

    def keep(info):
        return None if info.name == excluded or info.name.startswith(excluded + "/") else info

    fd = os.open(str(archive), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle, tarfile.open(fileobj=handle, mode="w:gz") as tar:
            tar.add(str(git_dir), arcname=".git", filter=keep)
    except (OSError, tarfile.TarError) as error:
        raise Failure(EXIT_ERROR, "the git directory archive failed, nothing was rewritten: %s" % error)
    os.chmod(str(archive), 0o600)
    return {"bundle": str(bundle), "archive": str(archive),
            "restore": "git clone %s <new-folder>" % shlex.quote(str(bundle)),
            "restore_archive": "mkdir <new-folder> && tar -xzf %s -C <new-folder> && git -C <new-folder> reset "
                               "--hard (reflogs and unreachable commits included)" % shlex.quote(str(archive))}


def _remote_moved(recorded, current):
    return sorted(ref for ref in set(recorded) | set(current) if recorded.get(ref) != current.get(ref))


def cmd_fix_apply(args):
    repo = repo_root(args.repo)
    if not args.confirm:
        raise Failure(EXIT_REFUSED, "fix-apply rewrites history: it needs --confirm (run fix-plan first, show the "
                      "dry run to the user and ask)")
    plan_path = state_dir(repo) / "plan" / "plan.json"
    if not plan_path.exists():
        raise Failure(EXIT_REFUSED, "no plan: run fix-plan first")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_dir = plan_path.parent
    require_engine()
    if git(repo, "status", "--porcelain", "--untracked-files=no", check=False).strip():
        raise Failure(EXIT_REFUSED, "the working tree has staged or unstaged changes to tracked files: commit or "
                      "stash them first")
    if snapshot(repo) != (plan["refs_hash"], plan["head"]):
        raise Failure(EXIT_REFUSED, "refs or HEAD changed since fix-plan: run fix-plan again")
    recorded = plan.get("remote_refs") or {}
    remote = plan.get("remote")
    if args.push and remote != args.remote:
        raise Failure(EXIT_REFUSED, "--push: the plan was not built against a remote named %s (run fix-plan "
                      "--remote %s)" % (args.remote, args.remote))
    if remote:
        if remote not in remote_names(repo):
            raise Failure(EXIT_REFUSED, "the remote %s recorded by fix-plan is gone: run fix-plan again" % remote)
        current, error = remote_refs(repo, remote)
        if current is None:
            raise Failure(EXIT_REFUSED, "cannot check that %s did not move since fix-plan (%s): retry when it is "
                          "reachable" % (remote, error))
        moved = _remote_moved(recorded, current)
        if moved:
            raise Failure(EXIT_REFUSED, "the remote %s changed since fix-plan (%s): someone pushed; run fix-plan "
                          "again" % (remote, ", ".join(r.split("/", 2)[2] for r in moved[:20])))
    backups = make_backups(repo, Path(args.backup_dir).expanduser())
    remotes, tracking = record_remotes(repo), record_tracking(repo)
    tracking_refs, before = record_remote_tracking_refs(repo), local_refs(repo)
    keep_note = ("the plan files in %s are kept to retry; they hold raw values: delete the folder when done"
                 % plan_dir)
    failure = None
    try:
        run(["git", "-C", str(repo), "filter-repo", "--force"] + plan["args"])
    except Failure as error:
        failure = str(error)
    except KeyboardInterrupt:
        failure = "interrupted"
    finally:
        restored, restore_errors = restore_remotes(repo, remotes, tracking, tracking_refs if failure else None)
    if failure:
        raise Failure(EXIT_ERROR, "the rewrite failed (%s). Remotes restored: %s%s. Recorded remotes: %s. Backup: %s "
                      "(restore with `%s`) and %s (`%s`); %s" % (
                          failure, ", ".join(restored) or "none needed",
                          "; " + "; ".join(restore_errors) if restore_errors else "",
                          ", ".join("%s %s" % (r["name"], r["fetch"]) for r in remotes) or "none",
                          backups["bundle"], backups["restore"], backups["archive"], backups["restore_archive"],
                          keep_note))
    remaining = remaining_targets(repo, plan_dir, plan)
    result = {"ok": remaining["total"] == 0, "backup": backups["bundle"], "restore": backups["restore"],
              "backup_archive": backups["archive"], "restore_archive": backups["restore_archive"],
              "remotes_restored": restored, "remaining": remaining, "remote_cleanup": list(REMOTE_CLEANUP)}
    if restore_errors:
        result["restore_errors"] = restore_errors
    if remaining["total"]:
        result["error"] = "targeted data remains after the rewrite; the backup is intact; " + keep_note
        print_json(result)
        return EXIT_ERROR
    for name in SENSITIVE_PLAN_FILES:
        try:
            (plan_dir / name).unlink()
        except OSError:
            pass
    after = local_refs(repo)
    applied = {"applied": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "created": plan.get("created"), "counts": plan.get("counts"), "strip_ai": plan.get("strip_ai"),
               "target_fingerprints": plan.get("target_fingerprints"), "remote": remote,
               "remote_refs": recorded, "pre_rewrite_refs": before, "post_rewrite_refs": after,
               "backup": backups["bundle"], "backup_archive": backups["archive"]}
    write_private(plan_dir / "plan.applied.json", json.dumps(applied, indent=1))
    plan_path.unlink()
    result["plan_files_deleted"] = True
    if not remote:
        result["next_steps"] = []
        result["note"] = "no remote was recorded by fix-plan: nothing to push"
        print_json(result)
        return EXIT_OK
    command, pushed, gone = push_plan(repo, remote, recorded)
    result["push_refs"] = pushed
    result["not_pushed"] = sorted(r for r in after if r not in recorded)
    if gone:
        result["remote_refs_left"] = {"refs": gone, "why": "deleted locally by the rewrite: the remote copy still "
                                      "holds the old history; delete it on the remote if it must go"}
    if command is None or not args.push:
        result["next_steps"] = [shlex.join(command)] if command else []
        print_json(result)
        return EXIT_OK
    result["next_steps"] = []
    done = run(command, check=False, timeout=600)
    if done.returncode != 0:
        result["ok"] = False
        result["push"] = {"command": shlex.join(command),
                          "error": done.stderr.decode("utf-8", "replace").strip()[-500:],
                          "hint": "a stale lease means someone pushed since fix-plan: fetch and check before "
                                  "anything else; if a protected branch rejects the force-push, lift the protection "
                                  "temporarily in the repository settings, then run the command again"}
        print_json(result)
        return EXIT_NETWORK
    result["pushed"] = True
    print_json(result)
    return EXIT_OK


# ---------------------------------------------------------------- pull requests and releases

def mask(line):
    return re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", lambda m: redact(m.group(0)), line.strip())[:200]


def gh_patch(endpoint, fields):
    """PATCH a GitHub resource through `gh api` (fields: dict of raw string parameters)."""
    command = ["gh", "api", "-X", "PATCH", endpoint]
    for key, value in fields.items():
        command += ["-f", "%s=%s" % (key, value)]
    result = run(command, check=False, timeout=60)
    if result.returncode != 0:
        raise Failure(EXIT_NETWORK, "gh api PATCH %s failed: %s" % (endpoint, result.stderr.decode(
            "utf-8", "replace").strip()[:200]))


def pr_candidates(prs, releases):
    items = []
    for pr in prs:
        title = pr.get("title") or ""
        new_title = AI_SUBJECT_RE.sub("", title)
        new_body, removed = strip_ai_text(pr.get("body") or "")
        manual = ai_line_match(new_title) is not None
        if new_title != title or removed or manual:
            items.append({"kind": "pull-request", "number": pr.get("number"), "url": pr.get("url"),
                          "removed_lines": [mask(line) for line in removed] +
                          ([mask(title)] if new_title != title else []),
                          "manual_title": manual, "_title": new_title, "_body": new_body,
                          "_changed": bool(removed) or new_title != title})
    for rel in releases:
        new_body, removed = strip_ai_text(rel.get("body") or "")
        if removed:
            items.append({"kind": "release", "id": rel.get("id"), "tag": rel.get("tag_name"),
                          "url": rel.get("html_url"), "removed_lines": [mask(line) for line in removed],
                          "_body": new_body, "_changed": True})
    return items


def cmd_fix_prs(args):
    repo = repo_root(args.repo)
    slug = github_slug(repo)
    if not slug:
        raise Failure(EXIT_MISSING, "no GitHub remote: fix-prs works on a repository whose origin is on github.com")
    candidates = pr_candidates(fetch_pull_requests(slug, args.limit) or [], fetch_releases(slug) or [])
    updated, errors = [], []
    if args.confirm:
        for item in candidates:
            if not item["_changed"]:
                continue
            try:
                if item["kind"] == "pull-request":
                    gh_patch("repos/%s/pulls/%s" % (slug, item["number"]),
                             {"title": item["_title"], "body": item["_body"]})
                else:
                    gh_patch("repos/%s/releases/%s" % (slug, item["id"]), {"body": item["_body"]})
                updated.append(item.get("number") or item.get("id"))
            except Failure as error:
                errors.append(str(error))
    shown = [{k: v for k, v in item.items() if not k.startswith("_")} for item in candidates]
    print_json({"ok": not errors, "applied": bool(args.confirm), "candidates": shown, "updated": updated,
                "errors": errors, "note": None if args.confirm else "dry run: add --confirm to edit them on GitHub"})
    return EXIT_NETWORK if errors else EXIT_OK


# ---------------------------------------------------------------- command line

def add_commands(subparsers):
    parser = subparsers.add_parser("fix-plan", help="history rewrite plan and dry run on a temporary mirror")
    parser.add_argument("repo")
    parser.add_argument("--map-email", action="append", default=[], metavar="OLD=NEW")
    parser.add_argument("--map-name", action="append", default=[], metavar="OLD=NEW")
    parser.add_argument("--map-mine", action="store_true", help="map my identities to the GitHub noreply address")
    parser.add_argument("--strip-ai", action="store_true", help="remove AI co-authorship lines from messages")
    parser.add_argument("--replace", action="append", default=[], metavar="FINGERPRINT")
    parser.add_argument("--replace-category", default=None, metavar="CATEGORIES",
                        help="comma-separated text categories (secret,email,...)")
    parser.add_argument("--remove-path", action="append", default=[], metavar="PATH")
    parser.add_argument("--strip-blobs-bigger-than", default=None, metavar="SIZE", help="e.g. 10M")
    parser.add_argument("--terms", default=None, help="personal terms used to find --replace fingerprints")
    parser.add_argument("--no-dry-run", action="store_true", help="write the plan without testing it")
    parser.add_argument("--remote", default="origin", help="remote fetched and compared before planning")
    parser.set_defaults(func=cmd_fix_plan)

    parser = subparsers.add_parser("fix-apply", help="backup, rewrite, restore remotes, rescan (needs --confirm)")
    parser.add_argument("repo")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--backup-dir", default="~/repo-showcase-backups")
    parser.add_argument("--push", action="store_true", help="also run the force-push commands")
    parser.add_argument("--remote", default="origin")
    parser.set_defaults(func=cmd_fix_apply)

    parser = subparsers.add_parser("fix-prs", help="remove AI mentions from pull requests and releases")
    parser.add_argument("repo")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--limit", type=int, default=300)
    parser.set_defaults(func=cmd_fix_prs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True
    add_commands(sub)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Failure as error:
        print_json({"ok": False, "error": str(error)})
        return error.code


if __name__ == "__main__":
    sys.exit(main())
