#!/usr/bin/env python3
"""Update the counters of the README and the banner (assets/hero.svg): number of skills and agents.

Counts skills/*/SKILL.md and kit/agents/*.md, then rewrites:
- assets/hero.svg: the tspan id="n-skills" and id="n-agents";
- README.md: "N skills, each ..." and "N subagents, ...".
Also reports skills missing from the README table or from assets/skills.svg (manual addition: icon, tagline).

Usage: sync_counts.py [--root DIR] [--check]
--check: writes nothing, exit code 1 if a file is out of date.
Exit codes: 0 up to date (or updated); 1 mismatch in --check mode. Python 3.9 compatible.
"""
import argparse
import re
import sys
from pathlib import Path


def counts(root):
    skills = sorted(p.parent.name for p in (root / "skills").glob("*/SKILL.md"))
    agents = sorted((root / "kit" / "agents").glob("*.md"))
    return skills, len(agents)


def rewrite(text, n_skills, n_agents, kind):
    """Return the text with up-to-date counters (kind: 'svg' or 'md')."""
    if kind == "svg":
        text = re.sub(r'(<tspan id="n-skills"[^>]*>)\d+(</tspan>)', r"\g<1>%d\g<2>" % n_skills, text)
        return re.sub(r'(<tspan id="n-agents"[^>]*>)\d+(</tspan>)', r"\g<1>%d\g<2>" % n_agents, text)
    text = re.sub(r"\b\d+ skills, each", "%d skills, each" % n_skills, text)
    return re.sub(r"\b\d+ subagents,", "%d subagents," % n_agents, text)


def missing(root, skills):
    """Skills with no row in the README table or no card in assets/skills.svg."""
    notes = []
    readme = root / "README.md"
    board = root / "assets" / "skills.svg"
    for name in skills:
        if readme.is_file() and "(skills/%s)" % name not in readme.read_text(encoding="utf-8"):
            notes.append("%s: row missing from the Skills table of README.md" % name)
        if board.is_file() and ">%s</text>" % name not in board.read_text(encoding="utf-8"):
            notes.append("%s: card missing from assets/skills.svg" % name)
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--check", action="store_true", help="check without writing")
    args = parser.parse_args(argv)
    root = Path(args.root)
    skills, n_agents = counts(root)
    stale = []
    for rel, kind in (("assets/hero.svg", "svg"), ("README.md", "md")):
        path = root / rel
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        new = rewrite(old, len(skills), n_agents, kind)
        if new != old:
            stale.append(rel)
            if not args.check:
                path.write_text(new, encoding="utf-8")
    for note in missing(root, skills):
        print("to complete: " + note, file=sys.stderr)
    verb = "out of date" if args.check else "updated"
    for rel in stale:
        print("%s: %s (%d skills, %d agents)" % (rel, verb, len(skills), n_agents))
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
