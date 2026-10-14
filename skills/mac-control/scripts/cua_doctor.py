#!/usr/bin/env python3
"""cua-driver diagnostic (Mac control): binary, daemon, permissions, declared MCP server.

Usage: cua_doctor.py        Output: JSON on stdout, read-only (no action on the screen).
Exit codes: 0 everything is ready; 1 unexpected error; 5 something is missing (see "todo").
Python 3.9 compatible.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_UNEXPECTED, EXIT_MISSING = 0, 1, 5


def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def parse_permissions(text):
    """JSON de `cua-driver permissions status --json` -> (accessibility, screen recording) or None."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return bool(data.get("accessibility")), bool(data.get("screen_recording"))


def parse_status(text):
    """Text of `cua-driver status` -> {running, mode}."""
    text = text or ""
    mode = None
    for line in text.splitlines():
        if "permission mode:" in line:
            mode = line.split("permission mode:", 1)[1].split("(")[0].strip()
    return {"running": "daemon is running" in text, "mode": mode}


def mcp_declared(config_path):
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return "cua-driver" in (data.get("mcpServers") or {})


def diagnose(config_path=None):
    config_path = config_path or str(Path.home() / ".claude.json")
    binary = shutil.which("cua-driver")
    report = {"binary": bool(binary), "todo": []}
    if not binary:
        report["todo"].append("install cua-driver (https://github.com/trycua/cua, cua-driver folder)")
        return report
    version = run([binary, "--version"]) or run([binary, "--help"]) or ""
    report["version"] = (version.splitlines() or ["?"])[0].strip()
    report.update(parse_status(run([binary, "status"])))
    perms = parse_permissions(run([binary, "permissions", "status", "--json"]))
    report["accessibility"], report["screen_recording"] = perms if perms else (None, None)
    report["mcp_declared"] = mcp_declared(config_path)
    if not report["running"]:
        report["todo"].append("daemon stopped: it starts on the first call of a cua-driver tool, or with `cua-driver serve`")
    if perms and not perms[0]:
        report["todo"].append("grant Accessibility: `cua-driver permissions grant`")
    if perms and not perms[1]:
        report["todo"].append("grant Screen Recording: `cua-driver permissions grant`")
    if not report["mcp_declared"]:
        report["todo"].append("declare the MCP server: claude mcp add --scope user cua-driver -- cua-driver mcp")
    return report


def main():
    try:
        report = diagnose()
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"error": "unexpected error: %s" % error}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(report, ensure_ascii=False))
    return EXIT_MISSING if report["todo"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
