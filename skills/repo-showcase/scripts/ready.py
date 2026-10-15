"""repo-showcase: ready, the final gate before publishing.

Usage: ready <repo> [--no-remote] [--skip-preview]

Aggregates, in one JSON object {"ready", "blocking", "warnings", "info", "visibility", "final_step"}:
  - security scan of the files and the whole history (scan.scan_repo): any high or medium finding blocks;
  - attribution scan of commits, files and, unless --no-remote, pull requests and releases (scan.attribution_scan);
  - git user.email must be a noreply address;
  - a README must exist; unless --skip-preview, capture.static_readme_checks must report nothing blocking;
  - .showcase.json counters must be up to date (counts sync --check); hard-coded counts in the visuals are warnings;
  - tracked junk, build output, dependency folders and a missing LICENSE are warnings (structure audit);
  - GitHub description, topics and visibility, and unpushed commits, unless --no-remote;
  - unless --no-remote, the remote branches and tags (git ls-remote) against the local ones: after fix-apply, a
    remote still pointing to pre-rewrite commits blocks (the old history is still published); other differences
    are warnings, and an unreachable remote is a warning.
Making a repository public is never done here: for a private repository, final_step tells the user the command to run.
Exit codes: 0 ready; 4 not ready (blocking items); 3 not a git repository. Python 3.9 compatible.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_FINDINGS, EXIT_OK, Failure, fingerprint, gh_json, git, git_call,  # noqa: E402
                    github_slug, local_refs, print_json, redact, remote_refs, repo_root, state_dir)
import counts  # noqa: E402
import inventory  # noqa: E402

BLOCKING_SEVERITIES = ("high", "medium")
STRUCTURE_WARNINGS = ("junk-tracked", "build-output-tracked", "dependency-dir-tracked", "missing-license")
NOREPLY_RE = re.compile(r"no-?reply", re.I)
MAX_LISTED = 10


def _item(check, message, **extra):
    item = {"check": check, "message": message}
    item.update(extra)
    return item


def _where(found):
    parts = [found.get("where") or "?"]
    if found.get("path"):
        parts.append("%s:%s" % (found["path"], found["line"]) if found.get("line") else found["path"])
    if found.get("commit"):
        parts.append(str(found["commit"])[:8])
    return " ".join(parts)


def _scan_items(check, result, blocking, info):
    """High and medium findings block; the others are only counted."""
    minor = 0
    for found in (result or {}).get("findings", []):
        if found.get("severity") in BLOCKING_SEVERITIES:
            blocking.append(_item(check, "%s (%s) in %s" % (found.get("category"), found.get("severity"),
                                                            _where(found)), finding=found))
        else:
            minor += 1
    if minor:
        info.append(_item(check, "%d low or info finding(s) not blocking: see the %s report" % (minor, check)))


def _email_check(repo, blocking):
    email = git(repo, "config", "user.email", check=False).strip()
    if not email:
        blocking.append(_item("identity", "git user.email is not set: configure a noreply address "
                                          "(ID+handle@users.noreply.github.com) before committing"))
    elif not NOREPLY_RE.search(email):
        blocking.append(_item("identity", "git user.email is a real address (%s, fingerprint %s): use a noreply address"
                              % (redact(email), fingerprint(email))))


def _counts_checks(repo, blocking, warnings, info):
    if (Path(repo) / counts.CONFIG_NAME).is_file():
        try:
            result = counts.sync(repo, check=True)
        except counts.CountsError as error:
            blocking.append(_item("counts", "invalid %s: %s" % (counts.CONFIG_NAME, error)))
        else:
            if result["stale"] or result["unknown"]:
                blocking.append(_item("counts", "counters out of date: run `counts sync` (stale: %s; unknown markers: %s)"
                                      % (", ".join(result["stale"]) or "none",
                                         ", ".join(sorted({u["name"] for u in result["unknown"]})) or "none"),
                                      stale=result["stale"], unknown=result["unknown"]))
    result = counts.lint(repo)
    likes = [i for i in result["items"] if i["level"] == "warning"]
    for entry in likes[:MAX_LISTED]:
        warnings.append(_item("counts", "%s:%d hard-coded count '%s %s': %s" % (
            entry["file"], entry["line"], entry["number"], entry.get("noun", ""), entry["suggestion"][:120])))
    if len(likes) > MAX_LISTED:
        warnings.append(_item("counts", "%d more hard-coded counts: run `counts lint`" % (len(likes) - MAX_LISTED)))
    if result["info"]:
        info.append(_item("counts", "%d number(s) with a unit: fine if measured and dated" % result["info"]))


def _github_checks(repo, warnings, info):
    """Returns the visibility string. Every call is tolerant of failure."""
    slug = github_slug(repo)
    visibility = "unknown"
    if not slug:
        info.append(_item("github", "origin is not a GitHub remote: remote checks skipped"))
    else:
        view, reason = None, "GitHub unreachable or no access to %s" % slug
        try:
            view = gh_json(["repo", "view", slug, "--json", "description,repositoryTopics,visibility,url"],
                           check=False)
        except Failure as error:
            reason = "gh unavailable (%s)" % error
        if view:
            visibility = (view.get("visibility") or "unknown").upper()
            if not (view.get("description") or "").strip():
                warnings.append(_item("github", "the repository has no description"))
            topics = view.get("repositoryTopics") or []
            if len(topics) < 3:
                warnings.append(_item("github", "fewer than 3 topics (%d): add some for discovery" % len(topics)))
            info.append(_item("github", "visibility: %s" % visibility))
        else:
            info.append(_item("github", "%s: GitHub checks skipped" % reason))
    code, upstream, _ = git_call(repo, "rev-parse", "--abbrev-ref", "@{u}")
    if code == 0 and upstream.strip():
        code, ahead, _ = git_call(repo, "rev-list", "--count", "@{u}..HEAD")
        if code == 0 and ahead.strip().isdigit() and int(ahead.strip()) > 0:
            info.append(_item("git", "%s commit(s) not pushed to %s" % (ahead.strip(), upstream.strip())))
    return visibility, slug


def _applied_rewrite(repo):
    """plan.applied.json written by fix-apply, or None."""
    path = state_dir(repo) / "plan" / "plan.applied.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _remote_checks(repo, blocking, warnings, info):
    """The remote branches and tags compared with the local ones (git ls-remote, read-only)."""
    applied = _applied_rewrite(repo)
    remote = (applied or {}).get("remote") or "origin"
    if remote not in git(repo, "remote", check=False).split():
        if applied and applied.get("remote"):
            warnings.append(_item("remote", "the remote %s used by fix-apply is gone: check that no copy of the old "
                                            "history stays published" % remote))
        return
    refs, error = remote_refs(repo, remote, timeout=60)
    if refs is None:
        warnings.append(_item("remote", "could not check the remote %s (%s): make sure it holds the current history "
                                        "before publishing" % (remote, error)))
        return
    local = local_refs(repo)
    old = set((applied or {}).get("pre_rewrite_refs", {}).values()) - set(local.values())
    stale = sorted(ref for ref, sha in refs.items() if sha in old and local.get(ref) != sha)
    if stale:
        blocking.append(_item("remote", "the remote still holds the old history: run the force push printed by "
                                        "fix-apply (%s on %s)" % (", ".join(r.split("/", 2)[2] for r in stale),
                                                                   remote), refs=stale))
    for ref in sorted(set(refs) | set(local)):
        if ref in stale or refs.get(ref) == local.get(ref):
            continue
        name = ref.split("/", 2)[2]
        kind = "branch" if ref.startswith("refs/heads/") else "tag"
        if ref not in local:
            warnings.append(_item("remote", "%s %s exists only on %s" % (kind, name, remote)))
        elif ref not in refs:
            warnings.append(_item("remote", "%s %s is not on %s (not pushed)" % (kind, name, remote)))
        elif kind == "branch" and git_call(repo, "merge-base", "--is-ancestor", refs[ref], local[ref])[0] == 0:
            warnings.append(_item("remote", "branch %s has commits not pushed to %s" % (name, remote)))
        else:
            warnings.append(_item("remote", "%s %s differs from %s (behind or diverged): fetch and check"
                                  % (kind, name, remote)))
    if not stale and applied:
        info.append(_item("remote", "%s holds no pre-rewrite branch or tag" % remote))


def final_step(visibility, slug):
    """What the user does last. Informational text only: nothing here changes a repository."""
    if visibility in ("PRIVATE", "INTERNAL"):
        return ("Last step, done by you: gh repo edit %s --visibility public "
                "--accept-visibility-change-consequences" % (slug or "OWNER/REPO"))
    if visibility == "PUBLIC":
        return "Already public: pin it on your profile if it should be seen first."
    return "Visibility unknown: check it on GitHub; making a repository public is your decision, done by you."


def ready_report(repo, remote=True, skip_preview=False):
    """Run every check and return the aggregated report."""
    import scan  # lazy: sibling modules are mocked in tests
    repo = Path(repo)
    blocking, warnings, info = [], [], []

    _scan_items("security", scan.scan_repo(repo, history=True, include_remote=False), blocking, info)
    _scan_items("attribution", scan.attribution_scan(repo, include_remote=remote), blocking, info)
    _email_check(repo, blocking)

    if inventory.find_readme(repo) is None:
        blocking.append(_item("readme", "no README at the root"))
    if skip_preview:
        info.append(_item("readme", "rendered preview checks skipped (--skip-preview)"))
    else:
        import capture
        checks = capture.static_readme_checks(repo) or {}
        for message in checks.get("blocking", []):
            blocking.append(_item("readme", str(message)))
        for message in checks.get("warnings", []):
            warnings.append(_item("readme", str(message)))

    _counts_checks(repo, blocking, warnings, info)

    for found in inventory.structure_audit(repo)["findings"]:
        if found["category"] in STRUCTURE_WARNINGS:
            warnings.append(_item("structure", found["why"], category=found["category"], paths=found["paths"],
                                  suggestion=found["suggestion"]))
    dirty = [line for line in git(repo, "status", "--porcelain", check=False).splitlines() if line.strip()]
    if dirty:
        warnings.append(_item("git", "%d uncommitted change(s): only commits are published" % len(dirty)))

    visibility, slug = "unknown", github_slug(repo)
    if remote:
        visibility, slug = _github_checks(repo, warnings, info)
        _remote_checks(repo, blocking, warnings, info)
    elif _applied_rewrite(repo):
        blocking.append(_item("git", "history was rewritten and the remote was not checked: run ready without "
                                     "--no-remote to confirm the force push reached it"))
    return {"ready": not blocking, "blocking": blocking, "warnings": warnings, "info": info,
            "visibility": visibility, "final_step": final_step(visibility, slug)}


def _cmd_ready(args):
    report = ready_report(repo_root(args.repo), remote=not args.no_remote, skip_preview=args.skip_preview)
    result = {"ok": report["ready"]}
    result.update(report)
    print_json(result)
    return EXIT_OK if report["ready"] else EXIT_FINDINGS


def add_commands(subparsers):
    parser = subparsers.add_parser("ready", help="final gate before publishing; never changes visibility")
    parser.add_argument("repo", help="path of the repository")
    parser.add_argument("--no-remote", action="store_true", help="skip the network (GitHub calls, remote ref check)")
    parser.add_argument("--skip-preview", action="store_true", help="skip the static README checks of capture")
    parser.set_defaults(func=_cmd_ready)
