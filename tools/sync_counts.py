#!/usr/bin/env python3
"""Met à jour les compteurs du README et de la bannière (assets/hero.svg) : nombre de skills et d'agents.

Compte skills/*/SKILL.md et kit/agents/*.md, puis réécrit :
- assets/hero.svg : les tspan id="n-skills" et id="n-agents" ;
- README.md : « N skills, each ... » et « N subagents, ... ».
Signale aussi les skills absents du tableau du README ou de assets/skills.svg (ajout manuel : icône, accroche).

Usage : sync_counts.py [--root DIR] [--check]
--check : n'écrit rien, code 1 si un fichier n'est pas à jour.
Codes de sortie : 0 à jour (ou mis à jour) ; 1 écart en mode --check. Python 3.9 compatible.
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
    """Retourne le texte avec les compteurs à jour (kind : 'svg' ou 'md')."""
    if kind == "svg":
        text = re.sub(r'(<tspan id="n-skills"[^>]*>)\d+(</tspan>)', r"\g<1>%d\g<2>" % n_skills, text)
        return re.sub(r'(<tspan id="n-agents"[^>]*>)\d+(</tspan>)', r"\g<1>%d\g<2>" % n_agents, text)
    text = re.sub(r"\b\d+ skills, each", "%d skills, each" % n_skills, text)
    return re.sub(r"\b\d+ subagents,", "%d subagents," % n_agents, text)


def missing(root, skills):
    """Skills sans ligne dans le tableau du README ou sans carte dans assets/skills.svg."""
    notes = []
    readme = root / "README.md"
    board = root / "assets" / "skills.svg"
    for name in skills:
        if readme.is_file() and "(skills/%s)" % name not in readme.read_text(encoding="utf-8"):
            notes.append("%s : ligne absente du tableau Skills de README.md" % name)
        if board.is_file() and ">%s</text>" % name not in board.read_text(encoding="utf-8"):
            notes.append("%s : carte absente de assets/skills.svg" % name)
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--check", action="store_true", help="vérifie sans écrire")
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
        print("à compléter : " + note, file=sys.stderr)
    verb = "pas à jour" if args.check else "mis à jour"
    for rel in stale:
        print("%s : %s (%d skills, %d agents)" % (rel, verb, len(skills), n_agents))
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
