#!/usr/bin/env python3
"""Découpe un dossier en lots de fichiers pour une recherche légère par sous-agents Haiku.

Déterministe, sans dépendance : le script ne consomme aucun token de modèle.
Sortie : JSON sur stdout. Codes de sortie : 0 succès, 2 dossier invalide.

Estimation des tokens : taille en octets / 4 (ordre de grandeur pour du code et du texte).
Un fichier plus grand que le budget forme son propre lot, marqué « oversize ».
"""
import argparse
import json
import math
import os
import sys

EXCLUDED_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp3", ".mp4", ".ogg", ".wav",
                   ".glb", ".fbx", ".zip", ".gz", ".tgz", ".pdf", ".so", ".dylib", ".exe", ".bin", ".woff",
                   ".woff2", ".ttf"}
MAX_FILE_BYTES = 2 * 1024 * 1024


def estimate_tokens(size_bytes):
    return max(1, math.ceil(size_bytes / 4))


def collect(root):
    """Retourne (fichiers : [(chemin relatif, tokens)], nombre de fichiers ignorés)."""
    files, skipped = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                skipped += 1
                continue
            if os.path.splitext(name)[1].lower() in BINARY_SUFFIXES:
                skipped += 1
                continue
            size = os.path.getsize(full)
            if size > MAX_FILE_BYTES:
                skipped += 1
                continue
            files.append((os.path.relpath(full, root), estimate_tokens(size)))
    return files, skipped


def pack(files, budget):
    """Regroupe les fichiers en lots dont le total reste sous le budget (sauf fichier isolé trop grand)."""
    batches, current, current_tokens = [], [], 0
    for path, tokens in files:
        if tokens > budget:
            if current:
                batches.append((current, current_tokens, False))
                current, current_tokens = [], 0
            batches.append(([path], tokens, True))
            continue
        if current and current_tokens + tokens > budget:
            batches.append((current, current_tokens, False))
            current, current_tokens = [], 0
        current.append(path)
        current_tokens += tokens
    if current:
        batches.append((current, current_tokens, False))
    return [{"id": i + 1, "files": paths, "tokens": tokens, "oversize": oversize}
            for i, (paths, tokens, oversize) in enumerate(batches)]


def plan(root, budget):
    files, skipped = collect(root)
    batches = pack(files, budget)
    return {
        "root": root,
        "budget_tokens": budget,
        "total_files": len(files),
        "total_tokens": sum(t for _, t in files),
        "skipped": skipped,
        "batches": batches,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", help="dossier à découper")
    parser.add_argument("--budget", type=int, default=25000,
                        help="tokens estimés maximum par lot (défaut 25000 ; recommandé 15000 à 30000)")
    args = parser.parse_args(argv)
    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        print(json.dumps({"error": "dossier introuvable : %s" % root}), file=sys.stderr)
        return 2
    if args.budget < 1000:
        print(json.dumps({"error": "budget trop faible (minimum 1000 tokens)"}), file=sys.stderr)
        return 2
    print(json.dumps(plan(root, args.budget), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
