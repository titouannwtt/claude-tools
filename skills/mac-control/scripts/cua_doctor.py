#!/usr/bin/env python3
"""Diagnostic de cua-driver (pilotage du Mac) : binaire, démon, permissions, serveur MCP déclaré.

Usage : cua_doctor.py        Sortie : JSON sur stdout, lecture seule (aucune action sur l'écran).
Codes de sortie : 0 tout est prêt ; 1 erreur inattendue ; 5 quelque chose manque (voir « todo »).
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
    """JSON de `cua-driver permissions status --json` -> (accessibilité, enregistrement de l'écran) ou None."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return bool(data.get("accessibility")), bool(data.get("screen_recording"))


def parse_status(text):
    """Texte de `cua-driver status` -> {running, mode}."""
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
        report["todo"].append("installer cua-driver (https://github.com/trycua/cua, dossier cua-driver)")
        return report
    version = run([binary, "--version"]) or run([binary, "--help"]) or ""
    report["version"] = (version.splitlines() or ["?"])[0].strip()
    report.update(parse_status(run([binary, "status"])))
    perms = parse_permissions(run([binary, "permissions", "status", "--json"]))
    report["accessibility"], report["screen_recording"] = perms if perms else (None, None)
    report["mcp_declared"] = mcp_declared(config_path)
    if not report["running"]:
        report["todo"].append("démon arrêté : il démarre au premier appel d'un outil cua-driver, ou `cua-driver serve`")
    if perms and not perms[0]:
        report["todo"].append("accorder Accessibilité : `cua-driver permissions grant`")
    if perms and not perms[1]:
        report["todo"].append("accorder Enregistrement de l'écran : `cua-driver permissions grant`")
    if not report["mcp_declared"]:
        report["todo"].append("déclarer le serveur MCP : claude mcp add --scope user cua-driver -- cua-driver mcp")
    return report


def main():
    try:
        report = diagnose()
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"error": "erreur inattendue : %s" % error}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(report, ensure_ascii=False))
    return EXIT_MISSING if report["todo"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
