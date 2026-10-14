"""Helpers shared by the claude-tools skills (local settings, fallback proxy).

local.env is read but never displayed: its values (proxy) never leave this module towards a log.
Python 3.9 compatible.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROXY_KEYS = ("IPROYAL_RESIDENTIAL_URL", "IPROYAL_PROXY_URL")


def load_local_env(explicit=None):
    """Read local.env (KEY=VALUE): explicit path, CLAUDE_TOOLS_LOCAL variable, or repo root."""
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
    """URL of the configured residential proxy, or None."""
    values = load_local_env(explicit_env)
    return next((values[key] for key in PROXY_KEYS if values.get(key)), None)
