#!/usr/bin/env python3
"""Contrôle avant commit : secrets, noms et chemins personnels dans le contenu.

Analyse le contenu qui sera réellement commité (index git) ou tout le dépôt suivi.
Les termes interdits (nom, pseudo, domaine) ne sont jamais écrits dans le dépôt : ils viennent de local.env
(clé FORBIDDEN_TERMS, séparés par des virgules, insensible à la casse). ALLOWED_TERMS (même format) liste les
chaînes publiques qui contiennent un terme interdit sans être une fuite (ex. le pseudo GitHub dans une URL).

Usage : check_repo.py [--staged | --all] [--root DIR] [--local-env FICHIER] [--identity]
        check_repo.py --commit-msg FICHIER   (hook commit-msg : refuse toute mention d'un assistant IA)
L'e-mail git (user.email) doit toujours être une adresse noreply (ex. ID+pseudo@users.noreply.github.com) :
sinon le commit est refusé. Le nom git n'est contrôlé contre FORBIDDEN_TERMS que sur demande (--identity).
Faux positif : ajouter le commentaire « check-repo: ignore » sur la ligne concernée.
Sortie : une ligne par constat (type, fichier:ligne), jamais la valeur trouvée.
Codes de sortie : 0 rien trouvé ; 1 constats ; 2 erreur d'usage ou dépôt introuvable.
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
# Une ligne portant ce marqueur est ignorée (faux positif assumé : adresse publique, valeur de test).
IGNORE_MARKER = "check-repo: ignore"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?![\d.])")
HOME_RE = re.compile(r"/(?:Users|home)/([A-Za-z0-9._<>$-]+)")
USERINFO_RE = re.compile(r"://([^/\s:@]+):([^/\s@]+)@([A-Za-z0-9.-]+)")
SECRET_RES = (
    ("clé API Anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("jeton GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("clé AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("clé privée", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
# Aucun commit ne mentionne un assistant IA comme coauteur ou générateur (règle du CLAUDE.md, section Git).
AI_ATTRIBUTION_RE = re.compile(
    r"co-authored-by:.*(claude|anthropic)|noreply@anthropic\.com|generated with \[?claude|claude\.com/claude-code",
    re.IGNORECASE)


def load_terms(local_env, key="FORBIDDEN_TERMS"):
    """Termes lus dans local.env (FORBIDDEN_TERMS par défaut) ; liste vide si le fichier ou la clé est absent."""
    if not local_env or not Path(local_env).is_file():
        return []
    for line in Path(local_env).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            raw = line.split("=", 1)[1].strip().strip("\"'")
            return [term.strip().lower() for term in raw.split(",") if term.strip()]
    return []


def scan_text(text, terms, allowed=()):
    """Retourne [(type, numéro de ligne)] pour un texte. Les valeurs trouvées ne sont jamais renvoyées."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if IGNORE_MARKER in line:
            continue
        lowered = line.lower()
        for public in allowed:
            lowered = lowered.replace(public, " ")
        for term in terms:
            if term in lowered:
                findings.append(("terme interdit", number))
                break
        for match in EMAIL_RE.finditer(line):
            address = match.group(0).lower()
            if not (any(safe in address for safe in SAFE_EMAIL_PARTS) or address.endswith(".example")):
                findings.append(("adresse e-mail", number))
        for match in IPV4_RE.finditer(line):
            if not match.group(1).startswith(SAFE_IP_PREFIXES):
                findings.append(("adresse IP", number))
        for match in HOME_RE.finditer(line):
            if match.group(1).lower() not in PLACEHOLDER_USERS:
                findings.append(("chemin personnel", number))
        for match in USERINFO_RE.finditer(line):
            host = match.group(3).lower()
            if not (host.endswith(".example") or host.startswith("example.") or host == "localhost"):
                findings.append(("identifiants dans une URL", number))
        for label, pattern in SECRET_RES:
            if pattern.search(line):
                findings.append((label, number))
    return findings


def scan_commit_message(text):
    """Numéros des lignes d'un message de commit qui attribuent le commit à un assistant IA (commentaires exclus)."""
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
        return None  # binaire
    return data.decode("utf-8", "replace")


def check_identity(root, terms, allowed=()):
    """Vérifie l'identité git configurée (nom et e-mail des futurs commits), hors termes publics autorisés."""
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
            findings.append(("identité git (%s)" % key, 0))
    return findings


def check_email(root):
    """Refuse un e-mail git réel : seules les adresses noreply sont acceptées."""
    try:
        value = git(root, "config", "user.email").decode("utf-8").strip().lower()
    except RuntimeError:
        return ["e-mail git absent (user.email) : configurer une adresse noreply"]
    if "noreply" not in value.split("@")[-1] and not value.startswith("noreply@"):
        return ["e-mail git réel (user.email) : utiliser une adresse noreply"]
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
            report.append("%s : %s:%d" % (kind, name, number))
    if identity:
        report += ["%s" % kind for kind, _ in check_identity(root, terms, allowed)]
    return report, bool(terms)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="contenu de l'index (défaut)")
    group.add_argument("--all", action="store_true", help="tous les fichiers suivis")
    group.add_argument("--commit-msg", metavar="FICHIER", help="message de commit à contrôler (hook commit-msg)")
    parser.add_argument("--identity", action="store_true", help="contrôle aussi user.name et user.email")
    parser.add_argument("--root", default=".")
    parser.add_argument("--local-env", default=None, help="défaut : local.env à la racine du dépôt")
    args = parser.parse_args(argv)
    if args.commit_msg:
        lines = scan_commit_message(Path(args.commit_msg).read_text(encoding="utf-8", errors="replace"))
        for number in lines:
            print("mention d'un assistant IA : message de commit, ligne %d" % number)
        if lines:
            print("commit refusé : retirer la ligne (aucun Co-Authored-By ni « Generated with » IA)", file=sys.stderr)
        return 1 if lines else 0
    root = Path(args.root).resolve()
    local_env = args.local_env or str(root / "local.env")
    try:
        report, has_terms = run(root, "all" if args.all else "staged", local_env, args.identity)
    except RuntimeError as error:
        print("erreur git : %s" % error, file=sys.stderr)
        return 2
    if not has_terms:
        print("avertissement : FORBIDDEN_TERMS absent de local.env, les noms personnels ne sont pas contrôlés",
              file=sys.stderr)
    for line in report:
        print(line)
    if report:
        print("%d constat(s) : commit refusé" % len(report), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
