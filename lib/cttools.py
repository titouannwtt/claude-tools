"""Fonctions communes aux skills de claude-tools (réglages locaux, proxy de repli).

local.env est lu sans jamais être affiché : les valeurs (proxy) ne sortent pas de ce module vers un journal.
Python 3.9 compatible.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROXY_KEYS = ("IPROYAL_RESIDENTIAL_URL", "IPROYAL_PROXY_URL")


def load_local_env(explicit=None):
    """Lit local.env (KEY=VALUE) : chemin explicite, variable CLAUDE_TOOLS_LOCAL, ou racine du dépôt."""
    candidates = [explicit, os.environ.get("CLAUDE_TOOLS_LOCAL"), str(REPO_ROOT / "local.env")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            values = {}
            for line in Path(candidate).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
            return values
    return {}


def configured_proxy(explicit_env=None):
    """URL du proxy résidentiel configuré, ou None."""
    values = load_local_env(explicit_env)
    return next((values[key] for key in PROXY_KEYS if values.get(key)), None)
