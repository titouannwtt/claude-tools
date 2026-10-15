#!/usr/bin/env python3
"""repo-showcase: make a GitHub repository safe to publish, clear and good-looking.

Usage: showcase.py <command> [options]   (every command prints one JSON object on stdout)

  doctor                         dependencies and what they enable (audit, rewrite, screenshots, faces, demo)
  inventory <repo>               project type, languages, docs, README stats, GitHub metadata, style sources
  keywords <repo> [--save]       sourced keywords for GitHub topics, description and README
  structure <repo>               layout audit: junk, duplicates, unclear names, comments, missing files
  security <repo> [--history]    secrets and personal data in the files (and the whole history)
  attribution <repo>             AI co-authorship mentions in commits, files, pull requests and releases
  allow <repo> <fingerprint>...  accept findings as false positives (stored in .git/repo-showcase)
  fix-plan <repo> [...]          history rewrite plan (mailmap, replacements, message cleanup), dry run
  fix-apply <repo> --confirm     backup, then rewrite with git-filter-repo, re-add origin, rescan
  fix-prs <repo> --confirm       remove AI mentions from pull request titles and bodies
  counts {sync|lint|badge|install-action} <repo>   live counters instead of hard-coded numbers
  shoot <url> --out DIR          screenshots (desktop, mobile, light, dark), optional dev server
  demo <url> --steps FILE        short recorded walkthrough converted to GIF or WebP
  preview <repo>                 README rendered as on GitHub (desktop, mobile, light, dark) and static checks
  social <repo> --source FILE    1280x640 PNG for the repository social preview (uploaded by hand)
  ready <repo>                   final gate before publishing; never changes visibility

Exit codes: 0 ok; 1 unexpected error; 2 usage; 3 not a git repository; 4 findings or failed checks;
5 missing dependency; 6 safety refusal; 7 GitHub or network unreachable. Python 3.9 compatible.
"""
import argparse
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXIT_ERROR, Failure, print_json  # noqa: E402

# Each module exposes add_commands(subparsers); every subparser sets func=handler(args) -> exit code.
MODULES = ("capture", "inventory", "scan", "history", "counts", "ready", "keywords")


def build_parser():
    parser = argparse.ArgumentParser(prog="showcase.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True
    for name in MODULES:
        importlib.import_module(name).add_commands(sub)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Failure as error:
        print_json({"ok": False, "error": str(error)})
        return error.code
    except KeyboardInterrupt:
        print_json({"ok": False, "error": "interrupted"})
        return EXIT_ERROR
    except Exception as error:  # noqa: BLE001 - reported, then the agent repairs the script
        traceback.print_exc(file=sys.stderr)
        print_json({"ok": False, "error": "unexpected: %s: %s" % (type(error).__name__, error)})
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
