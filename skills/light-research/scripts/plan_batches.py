#!/usr/bin/env python3
"""Split a folder into batches of files for a light research by Haiku subagents.

Deterministic, dependency-free: the script consumes no model tokens.
Output: JSON on stdout. Exit codes: 0 success, 2 invalid folder.

Token estimate: size in bytes / 4 (order of magnitude for code and text).
A file larger than the budget forms its own batch, marked "oversize".
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
    """Return (files: [(relative path, tokens)], number of skipped files)."""
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
    """Group files into batches whose total stays under the budget (except a single oversized file)."""
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
    parser.add_argument("root", help="folder to split")
    parser.add_argument("--budget", type=int, default=25000,
                        help="maximum estimated tokens per batch (default 25000; recommended 15000 to 30000)")
    args = parser.parse_args(argv)
    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        print(json.dumps({"error": "folder not found: %s" % root}), file=sys.stderr)
        return 2
    if args.budget < 1000:
        print(json.dumps({"error": "budget too low (minimum 1000 tokens)"}), file=sys.stderr)
        return 2
    print(json.dumps(plan(root, args.budget), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
