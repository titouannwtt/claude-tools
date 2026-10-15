#!/usr/bin/env python3
"""Secrets, personal data and AI co-authorship audit of a repository and its whole git history.

Usage: showcase.py security <repo> [--history|--no-history] [--terms a,b] [--limit 100] [--no-remote]
       showcase.py attribution <repo> [--no-remote] [--limit 100]
       showcase.py allow <repo> <fingerprint>... [--remove]

Python API (used by ready.py and history.py):
  scan_repo(repo, history=True, terms=None, include_remote=False, raw=False) -> {"findings", "summary"}
  attribution_scan(repo, include_remote=True, raw=False) -> same shape
Every finding comes from common.finding(); the raw value is never printed nor stored (preview and fingerprint
only). With raw=True the findings also carry private "_value" and "_match" keys, for history.py to build a plan.
A line carrying "showcase: ignore" is skipped; allowed fingerprints (`allow`) are removed from the results.
Optional extras: gitleaks (merged when on PATH), Pillow (EXIF), cv2 or pyobjc Vision (faces).
Exit codes: 0 nothing to fix; 4 high or medium finding; 3 not a repository. Python 3.9 compatible.
"""
import argparse
import datetime
import getpass
import io
import ipaddress
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_FINDINGS, EXIT_NETWORK, EXIT_OK, GITHUB_REMOTE_RE, ignored_line,  # noqa: E402
                    SEVERITIES, Failure, finding, fingerprint, gh_json, git, git_bytes, github_slug, load_allowlist,
                    local_settings, print_json, read_text, redact, repo_root, run, save_allowlist, split_terms,
                    state_dir, tracked_files)

MAX_TEXT = 2000000          # larger blobs are not read (name-based checks still apply)
MAX_OFFICE = 30000000
MAX_IMAGE = 40000000
LARGE_BLOB = 5 * 1024 * 1024
IMAGE_CAP = 300
LOOKUP_CAP = 50
HITS_PER_TEXT = 300

# ---------------------------------------------------------------- patterns

SECRET_PATTERNS = (
    ("Anthropic API key", ("sk-ant-",), r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ("OpenAI API key", ("sk-",),
     r"(?<![A-Za-z0-9])sk-(?!ant-)(?:proj-|svcacct-|admin-)?(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,}"),
    ("GitHub token", ("ghp_", "gho_", "ghu_", "ghs_", "ghr_"), r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{30,}"),
    ("GitHub fine-grained token", ("github_pat_",), r"github_pat_[A-Za-z0-9_]{40,}"),
    ("AWS access key id", ("AKIA", "ASIA"), r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])"),
    ("AWS secret access key", ("ecret_access_key", "ECRET_ACCESS_KEY"),
     r"(?i)aws_secret_access_key[\"']?[ \t]*[:=][ \t]*[\"']?(?P<v>[A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"),
    ("Google API key", ("AIza",), r"AIza[0-9A-Za-z_-]{35}"),
    ("Slack token", ("xox",), r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    ("Stripe live key", ("_live_",), r"[sr]k_live_[A-Za-z0-9]{16,}"),
    ("SendGrid key", ("SG.",), r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    ("Telegram bot token", (":",), r"(?<![0-9])\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    ("JWT", ("eyJ",), r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    ("private key", ("PRIVATE KEY",),
     r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----(?P<v>[^-]{40,}?)(?=-----END|\Z)"),
)
SECRET_RES = tuple((label, needles, re.compile(pattern)) for label, needles, pattern in SECRET_PATTERNS)
FAKE_PARTS = ("xxxx", "example", "your", "placeholder", "dummy", "...", "<", "$")
KEYWORD_RE = re.compile(r"password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key|"
                        r"client[_-]?secret|auth(?!or)", re.IGNORECASE)
TAIL_RE = re.compile(r"(?P<rest>[A-Za-z0-9_.-]{0,40})[\"']?[ \t]*(?::=|=>|[:=])[ \t]*"
                     r"(?P<value>\"[^\"\n]{0,300}\"|'[^'\n]{0,300}'|[^\s\"',;#]{1,300})")
NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")
NAME_SUFFIXES = ("_url", "_uri", "_path", "_file", "_type", "_method", "_mode", "_header", "_name", "_endpoint",
                 "_provider", "_scheme", "_class", "_ttl", "_expiry", "_expires", "_enabled", "_required",
                 "_length", "_field", "_prompt", "_label", "_env", "_var", "_id", "-url", "-file", "-type")
PLACEHOLDER_WORDS = frozenset((
    "changeme", "change_me", "password", "passwd", "secret", "token", "example", "dummy", "null", "none", "true",
    "false", "basic", "bearer", "oauth", "oauth2", "digest", "jwt", "string", "required", "optional", "disabled",
    "enabled", "session", "cookie", "header", "query", "apikey", "api_key", "undefined", "empty", "default"))
PLACEHOLDER_PREFIXES = (
    "your", "<", "${", "{{", "$", "%(", "process.env", "os.environ", "os.getenv", "getenv", "env.", "env(",
    "config", "settings", "secrets.", "vault", "ref+", "example", "dummy", "test", "fake", "sample", "demo",
    "placeholder", "changeme", "change_me", "replace", "insert", "todo", "fixme", "none", "null", "true", "false",
    "http://", "https://", "/", "./", "~/", "@")
CODE_EXTS = frozenset((".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"))
CONFIG_EXTS = frozenset((".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".cfg", ".conf", ".properties", ".sh",
                         ".bash", ".zsh", ".tf", ".tfvars"))
CRYPTO_KEY_RE = re.compile(r"(?P<name>[A-Za-z0-9_.-]*(?:private|secret|key|seed|mnemonic)[A-Za-z0-9_.-]*)[\"']?"
                           r"[ \t]*[:=][ \t]*[\"']?(?P<v>0x[0-9a-fA-F]{64})(?![0-9a-fA-F])", re.IGNORECASE)
SEED_RE = re.compile(r"(?i:mnemonic|seed|phrase)[A-Za-z0-9_.-]*[\"']?[ \t]*[:=][ \t]*[\"'](?P<v>(?:[a-z]{3,8} ){11}"
                     r"(?:(?:[a-z]{3,8} ){12}(?:[a-z]{3,8})|[a-z]{3,8}))[\"']")
USERINFO_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]{1,15}://(?P<v>(?P<user>[^/\s:@\"'<>]+):(?P<pw>[^/\s@\"'<>]+))@"
                         r"(?P<host>[A-Za-z0-9.-]+)")
LOCAL_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._%+-")
DOMAIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
                       r"[A-Za-z0-9])?)*\.[A-Za-z]{2,24}")
FILE_TLDS = frozenset((
    "png jpg jpeg gif svg webp ico css scss less js jsx ts tsx mjs cjs json yml yaml toml md txt py rb rs go java "
    "kt c h cpp hpp cs php sh bash html htm xml lock cfg ini conf env log pdf zip gz tar woff woff2 ttf eot map "
    "vue swift pyc gd tscn tres gdshader lua csv tsv sql ipynb scala dart").split())
SAFE_DOMAINS = frozenset(("example.com", "example.org", "example.net", "localhost", "domain.tld", "domain.com",
                          "yourdomain.com", "yourcompany.com", "company.com", "site.com", "website.com",
                          "users.noreply.github.com"))
PLACEHOLDER_LOCALS = frozenset(("you", "user", "username", "name", "email", "youremail", "your-email", "your.email",
                                "yourname", "foo", "bar", "test", "me", "git", "mail"))
IPV4_RE = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?!\d)(?!\.\d)")
IPV6_RE = re.compile(r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:.])")
VERSION_CTX_RE = re.compile(r"(?:\bv|version|\bver|\brev|release|==|>=|<=|~=|\^|~)[\s:=\"'@-]*$", re.IGNORECASE)
DOC_NETS = tuple(ipaddress.ip_network(net) for net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24",
                                                       "2001:db8::/32"))
HOST_RE = r"(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}|\d{1,3}(?:\.\d{1,3}){3})"
PORT_RE = re.compile(r"(?<![\w.-])(?P<host>%s):(?P<port>\d{2,5})(?![\w.]?\d)" % HOST_RE)
HOST_PORT_RE = re.compile(r"\b(?:host|hostname|server|ip)[ \t]*[=:][ \t]*[\"']?(?P<host>%s)[\"']?[^\n]{0,40}?\bport"
                          r"[ \t]*[=:][ \t]*[\"']?(?P<port>\d{2,5})" % HOST_RE, re.IGNORECASE)
HOME_RES = (re.compile(r"(?<![A-Za-z0-9_.-])/(?:Users|home)/(?P<v>[A-Za-z0-9._<>$%{}*~-]+)"),
            re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}(?P<v>[A-Za-z0-9._<>$%{}*~-]+)"))
PLACEHOLDER_USERS = frozenset((
    "user", "username", "you", "name", "me", "runner", "ubuntu", "example", "your-name", "yourname", "<user>",
    "$user", "nom", "root", "shared", "public", "default", "admin", "vagrant", "runneradmin", "app", "node", "git",
    "docker", "jenkins", "circleci", "travis", "test", "tester", "foo", "bar", "john", "jane", "jdoe", "johndoe",
    "linuxbrew", "all", "guest", "home", "login", "logout", "dashboard", "settings", "about", "contact", "main",
    "page", "users", "profile", "search", "help", "docs", "api", "static", "assets", "new", "edit", "view",
    "index", "signup", "register", "account", "projects", "feed", "explore"))
PHONE_RES = (
    re.compile(r"(?<![\w.+-])(?:\+33|0033)[\s.-]?\(?0?\)?[1-9](?:[\s.-]?\d{2}){4}(?![\w-])"),
    re.compile(r"(?<![\w.+-])0[1-9](?:[\s.-]\d{2}){4}(?![\w-])"),
    re.compile(r"(?<![\w.+-])\+(?!33)\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}(?![\w-])"),
    re.compile(r"(?<![\w.+-])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w-])"),
)
ADDRESS_RES = (
    re.compile(r"(?<![\w.])\d{1,4}(?:[ ]?(?i:bis|ter))?,?[ ]+(?i:rue|avenue|av\.|boulevard|bd|all[e\u00e9]e|chemin|"
               r"impasse|place|quai|route)[ ]+(?:(?i:de la|de l'|du|des|de|d')[ ]?[A-Za-z\u00c0-\u00ff]|"
               r"[A-Z\u00c0-\u00de])[A-Za-z\u00c0-\u00ff'-]*"),
    re.compile(r"(?<![\w.])\d{1,5}[ ]+(?:[A-Z][a-z]+[ ]+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|"
               r"Ln|Drive|Dr)\b"),
)
IBAN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{3,4}){3,8}(?![A-Za-z0-9])")
CARD_RE = re.compile(r"(?<![\d.,-])\d(?:[ -]?\d){12,18}(?![\d-])(?!\.\d)")
# A bare digit run passes Luhn one time in ten: it needs card-like grouping or a card word on its line.
CARD_GROUPED_RE = re.compile(r"\d{4}([ -])\d{4}\1\d{4}\1\d{1,7}|\d{4}([ -])\d{6}\2\d{4,5}")
CARD_HINT_RE = re.compile(r"card|carte|cr[e\u00e9]dit|visa|mastercard|amex|\bcb\b|\bcc\b|\bpan\b", re.IGNORECASE)
CARD_PREFIX_RE = re.compile(r"^(?:4\d{12}(?:\d{3}){0,2}|5[1-5]\d{14}|2(?:2[2-9]|[3-6]\d|7[01])\d{13}|2720\d{12}|"
                            r"3[47]\d{13}|6(?:011|5\d\d)\d{12,15}|3(?:0[0-5]|[68]\d)\d{11,16}|35\d{14,17})$")
NOISY_RE = re.compile(r"(?:\.lock|package-lock\.json|go\.sum|\.min\.(?:js|css)|\.map|\.svg|\.snap)$", re.IGNORECASE)
NOISY_CATEGORIES = frozenset(("ip", "port", "phone", "postal-address", "iban", "card-number"))
MESSAGE_SKIP = frozenset(("port", "phone", "postal-address"))

ENV_FILE_RE = re.compile(r"^(?:\.env(?:\.[^/]+)?|[^/]+\.env)$", re.IGNORECASE)
ENV_SAFE_RE = re.compile(r"\.(?:example|sample|template|dist|defaults|schema)$", re.IGNORECASE)
CRED_FILE_RE = re.compile(r"(?:^|/)(?:[^/]+\.(?:pem|key|p12|pfx|keystore|jks|kdbx|ovpn)|id_rsa|id_ed25519|id_ecdsa|"
                          r"id_dsa|credentials\.json|service[-_]account[^/]*\.json|\.pypirc|\.netrc|\.htpasswd|"
                          r"kubeconfig|\.npmrc)$", re.IGNORECASE)
PERSONAL_FILE_RE = re.compile(
    r"(?<![a-z0-9])(?:contrats?|contracts?|nda|factures?|invoices?|devis|payslips?|fiche[ _-]?de[ _-]?paie|"
    r"bulletins?[ _-]?de[ _-]?salaire|passport|passeport|carte[ _-]?d[' _-]?identit[eé]|id[ _-]?card|cni|cv|"
    r"resume|curriculum|rib|iban|imp[oô]ts?|avis[ _-]?d[' _-]?imposition|rel[eé]v[eé]s?|statements?|"
    r"ordonnances?|medical|signatures?)(?![a-z0-9])", re.IGNORECASE)
DOCUMENT_EXTS = frozenset((".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".csv", ".ppt", ".pptx",
                           ".odp", ".pages", ".numbers", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
                           ".tif", ".tiff", ".bmp"))
OFFICE_EXTS = frozenset((".docx", ".odt", ".xlsx", ".pptx", ".ods", ".odp"))
CONTRACT_RE = re.compile(r"contrat|contract|agreement|\bnda\b|salaire|salary|payslip|bulletin de|passeport|passport|"
                         r"\biban\b|s[eé]curit[eé] sociale|social security|date de naissance|"
                         r"date of birth", re.IGNORECASE)
PII_CATEGORIES = frozenset(("email", "phone", "iban", "card-number", "postal-address", "personal-name", "secret"))
IMAGE_EXTS = frozenset((".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff", ".dng", ".png"))
AI_CONFIG_RE = re.compile(r"(?:^|/)(?:CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.cursorrules|\.cursor/|\.claude/|"
                          r"\.aider[^/]*|\.github/copilot-instructions\.md)", re.IGNORECASE)

REMEDIES = {
    "secret": ("rotate", "redact-head", "rewrite-history", "allow"),
    "credentials-url": ("rotate", "redact-head", "rewrite-history"),
    "env-file": ("untrack", "move-to-env", "rewrite-history"),
    "credential-file": ("untrack", "rotate", "rewrite-history"),
    "email": ("redact-head", "mailmap", "rewrite-history", "allow"),
    "ip": ("redact-head", "rewrite-history", "allow"),
    "port": ("redact-head", "allow"),
    "username": ("redact-head", "rewrite-history"),
    "personal-name": ("redact-head", "rewrite-history", "mailmap"),
    "phone": ("redact-head", "rewrite-history", "allow"),
    "postal-address": ("redact-head", "rewrite-history", "allow"),
    "iban": ("redact-head", "rewrite-history", "allow"),
    "card-number": ("redact-head", "rewrite-history", "allow"),
    "personal-file": ("review", "untrack", "rewrite-history"),
    "photo": ("review", "untrack", "rewrite-history"),
    "photo-location": ("review", "untrack", "rewrite-history"),
    "photo-person": ("review", "untrack", "rewrite-history"),
    "large-blob": ("lfs-or-release", "rewrite-history"),
    "ai-config-file": ("keep", "untrack"),
    "ai-coauthor": ("strip-messages", "rewrite-history"),
    "ai-author": ("mailmap", "rewrite-history"),
}
RANKS = {"secret": 0, "credentials-url": 0, "iban": 1, "card-number": 1, "email": 2, "username": 2, "ip": 3}
LOWERED_FP = frozenset(("email", "username", "personal-name"))
GENERIC_LOGINS = frozenset(("root", "admin", "ubuntu", "debian", "user", "runner", "ec2-user", "pi", "administrator",
                            "guest", "test", "vagrant", "codespace", "node", "docker", "nobody"))
GENERIC_NAME_TOKENS = frozenset(("user", "admin", "root", "guest", "test", "system", "administrator", "unknown",
                                 "nobody", "account", "owner", "local", "default", "this", "that"))

# AI co-authorship phrasing (single source of truth, also used to build the filter-repo message callback).
AI_STRONG = "copilot|chatgpt|openai|gpt|cursor|codeium|windsurf|aider|codex|amazon q|codewhisperer|tabnine"
AI_AMBIGUOUS = "claude|cody|jules|devin|gemini"
AI_SIGNAL = r"noreply|\[bot\]|\bbot\b|anthropic|openai|sourcegraph|cognition|google|\bai\b|agent|assistant|" \
            r"opus|sonnet|haiku|claude code"
AI_LINE_PATTERNS = (
    ("Co-authored-by trailer", r"co-authored-by:[^\n]*?(?<![a-z0-9])(?:%s)(?![a-z0-9])" % AI_STRONG),
    ("Co-authored-by trailer",
     r"co-authored-by:(?=[^\n]*(?:%s))[^\n]*?(?<![a-z0-9])(?:%s)(?![a-z0-9])" % (AI_SIGNAL, AI_AMBIGUOUS)),
    ("noreply anthropic address", r"noreply@anthropic\.com"),
    ("Generated-with line", r"generated (?:with|by)\s+\[?\s*(?:claude(?: code)?|chatgpt|(?:github )?copilot|"
                            r"cursor|aider|gemini|codex)"),
    ("robot Generated line", "\U0001F916\\s*generated"),
    ("claude-code link", r"claude\.com/claude-code|claude\.ai/code"),
    ("Generated-by or Assisted-by trailer", r"^\s*(?:generated|assisted)-by:"),
)
AI_LINE_RES = tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in AI_LINE_PATTERNS)
AI_SUBJECT_RE = re.compile(r"^aider:\s+", re.IGNORECASE)
AI_TOOL_RE = re.compile(r"(?<![a-z0-9])(claude|anthropic|copilot|chatgpt|openai|gpt|cursor|codeium|windsurf|aider|"
                        r"devin|gemini|codex|amazon q|codewhisperer|tabnine|cody|jules)(?![a-z0-9])")
AI_NEEDLES = ("co-authored-by", "anthropic", "generated", "assisted-by", "claude", "\U0001F916", "aider:")
AI_BOT_STRONG = frozenset(("copilot", "devin-ai-integration", "cursoragent", "aider", "codex"))
AI_BOT_NAME_RE = re.compile(r"^(?:claude(?: code| opus| sonnet| haiku)?(?: [0-9.]+)?|github copilot|copilot|"
                            r"cursor agent|cursoragent|aider|codex|gemini|devin(?:-ai-integration)?)(?:\[bot\])?$")
AI_BOT_TOKEN_RE = re.compile(r"(?<![a-z0-9])(claude|copilot|devin-ai-integration|cursoragent|aider|codex|gemini)"
                             r"(?![a-z0-9])")


def ai_line_match(line):
    """(label, tool) when a line credits an AI assistant (co-authorship phrasing only), else None."""
    for label, regex in AI_LINE_RES:
        if regex.search(line):
            tool = AI_TOOL_RE.search(line.lower())
            return label, tool.group(1) if tool else None
    return None


def strip_ai_text(text):
    """(cleaned text, removed lines): drops the lines of a message or body that credit an AI assistant."""
    kept, removed = [], []
    for line in text.split("\n"):
        (removed if ai_line_match(line) else kept).append(line)
    while removed and kept and not kept[-1].strip():
        kept.pop()
    return ("\n".join(kept) + ("\n" if text.endswith("\n") and kept else "")) if removed else text, removed


def ai_identity(name, email):
    """Name of the AI tool when an author or committer identity is a bot of an AI assistant, else None."""
    name, email = name.strip().lower(), email.strip().lower()
    local, _, domain = email.rpartition("@")
    core = re.sub(r"^\d+\+", "", local).replace("[bot]", "")
    if domain == "anthropic.com":
        return "claude"
    if core in AI_BOT_STRONG:
        return core
    if core in ("claude", "gemini") and ("noreply" in domain or "[bot]" in local):
        return core
    if AI_BOT_NAME_RE.match(name):
        return AI_BOT_TOKEN_RE.search(name).group(1)
    if "[bot]" in name:
        match = AI_BOT_TOKEN_RE.search(name)
        return match.group(1) if match else None
    return None


# ---------------------------------------------------------------- terms and context

def auto_terms():
    """({login terms}, {full-name tokens}) of the OS account: personal terms found without any configuration."""
    logins, names = set(), set()
    try:
        login = getpass.getuser().lower()
        if len(login) >= 4 and login not in GENERIC_LOGINS:
            logins.add(login)
    except Exception:  # noqa: BLE001 - no login name available (containers)
        pass
    try:
        import pwd
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0]
        for token in re.findall(r"[A-Za-z]{4,}", gecos):
            if token.lower() not in GENERIC_NAME_TOKENS:
                names.add(token.lower())
    except (ImportError, KeyError, OSError):
        pass
    return logins, names


def gh_user(repo, network=True):
    """{"login", "id", "name"} of the authenticated gh user (cached in the state dir), or None."""
    cache = state_dir(repo) / "gh-user.json"
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("login"):
            return data
    except (OSError, ValueError):
        pass
    if not network:
        return None
    try:
        info = gh_json(["api", "user"], check=False)
    except (Failure, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(info, dict) or not info.get("login"):
        return None
    data = {"login": info["login"], "id": info.get("id"), "name": info.get("name")}
    cache.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(str(cache), 0o600)
    return data


def remote_owner(repo):
    result = run(["git", "-C", str(repo), "remote", "get-url", "origin"], check=False)
    match = GITHUB_REMOTE_RE.search(result.stdout.decode().strip()) if result.returncode == 0 else None
    return match.group(1).lower() if match else None


class Terms:
    """Personal terms to look for, minus the public strings (owner handle, allowed terms) that contain them."""

    def __init__(self, groups, allowed):
        self.groups = []
        for label, words, boundary in groups:
            words = sorted({w for w in words if w}, key=len, reverse=True)
            if words:
                body = "|".join(re.escape(w) for w in words)
                if boundary:
                    body = "(?<![a-z0-9])(?:%s)(?![a-z0-9])" % body
                self.groups.append((label, re.compile(body, re.IGNORECASE), len(words)))
        self.allowed = sorted({a.lower() for a in allowed if a}, key=len, reverse=True)

    def sources(self):
        return {label: count for label, _, count in self.groups}

    def find(self, text):
        """[(start, end, matched text, source label)] of the personal terms, allowed strings excluded."""
        found = []
        for label, regex, _ in self.groups:
            for match in regex.finditer(text):
                if not self._masked(text, match.start(), match.end()):
                    found.append((match.start(), match.end(), match.group(0), label))
        return found

    def _masked(self, text, start, end):
        if not self.allowed:
            return False
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        line_end = len(text) if line_end < 0 else line_end
        line = text[line_start:line_end].lower()
        if len(line) != line_end - line_start:
            return False
        for public in self.allowed:
            if public in line:
                line = line.replace(public, " " * len(public))
        return line[start - line_start:end - line_start] != text[start:end].lower()


def build_terms(repo, terms=None, network=True):
    """Terms object for the repository: --terms, local.env FORBIDDEN_TERMS, OS login and full name."""
    settings = local_settings()
    explicit = split_terms(",".join(terms) if isinstance(terms, (list, tuple, set)) else terms)
    configured = split_terms(settings.get("FORBIDDEN_TERMS"))
    logins, names = auto_terms()
    allowed = set(split_terms(settings.get("ALLOWED_TERMS")))
    owner = remote_owner(repo)
    if owner:
        allowed.add(owner)
    user = gh_user(repo, network=network)
    if user:
        allowed.add(str(user["login"]).lower())
    groups = [("--terms", explicit, False), ("FORBIDDEN_TERMS", configured, False),
              ("os login", logins, True), ("os full name", names, True)]
    return Terms(groups, allowed)


# ---------------------------------------------------------------- value checks

def looks_fake(value):
    low = value.lower()
    return any(part in low for part in FAKE_PARTS)


def is_placeholder(value):
    """True for an empty, short, templated, environment-reference or dummy value."""
    stripped = value.strip().strip("\"'")
    low = stripped.lower()
    if len(stripped) < 6 or low in PLACEHOLDER_WORDS or low.startswith(PLACEHOLDER_PREFIXES):
        return True
    if re.fullmatch(r"[x*.#_-]+", low) or "xxxx" in low or "****" in low or "..." in low:
        return True
    if any(part in low for part in ("example", "changeme", "placeholder", "dummy", "your_", "your-", "<your")):
        return True
    return any(char in stripped for char in "()[]{}<>") or stripped.startswith("$")


def secret_like(value):
    """Cheap entropy hint: digits, symbols, capitals or length separate a password from a plain word."""
    return len(value) >= 8 or any(not char.islower() for char in value)


def luhn(digits):
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2:
            number = number * 2 - 9 if number > 4 else number * 2
        total += number
    return total % 10 == 0


def iban_valid(compact):
    if not 15 <= len(compact) <= 34:
        return False
    rearranged = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def safe_email(address):
    low = address.lower()
    local, _, domain = low.rpartition("@")
    tld = domain.rsplit(".", 1)[-1]
    if "noreply" in low or "no-reply" in low or tld in FILE_TLDS or domain in SAFE_DOMAINS:
        return True
    if domain.endswith((".example", ".test", ".invalid", ".localhost", ".local")) or domain.startswith("example."):
        return True
    return local in PLACEHOLDER_LOCALS or domain.split(".")[0] in ("example", "yourdomain", "yourcompany")


def classify_ip(text):
    """"high"/"medium"/"low" label for an IP literal (medium public, low private), None to ignore."""
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return None
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_reserved or any(ip in n for n in DOC_NETS):
        return None
    if ip.version == 4 and (int(text.split(".")[0]) == 0 or int(text.split(".")[0]) >= 224):
        return None
    return "medium" if ip.is_global else "low"


def safe_host(host):
    low = host.lower()
    return (low == "localhost" or low.startswith(("127.", "0.", "example.")) or low in SAFE_DOMAINS
            or low.endswith((".example", ".test", ".invalid", ".localhost", ".local", ".example.com"))
            or low.rsplit(".", 1)[-1] in FILE_TLDS)


# ---------------------------------------------------------------- text detectors
# Each detector yields (category, severity, start, end, value, detail[, (match start, match end)]): the optional
# span is the exact text a history rewrite must replace when it differs from the reported span.

def detect_secrets(text):
    for label, needles, regex in SECRET_RES:
        if not any(needle in text for needle in needles):
            continue
        for match in regex.finditer(text):
            group = "v" if "v" in regex.groupindex else 0
            value = match.group(group)
            if label == "private key":
                value = re.sub(r"\s+", "", value)
            if label != "private key" and looks_fake(value):
                continue
            yield "secret", "high", match.start(), match.end(), value, label, match.span(group)
    if "0x" in text:
        for match in CRYPTO_KEY_RE.finditer(text):
            yield "secret", "high", match.start(), match.end(), match.group("v"), "crypto private key", match.span("v")
    if "mnemonic" in text.lower() or "seed" in text.lower() or "phrase" in text.lower():
        for match in SEED_RE.finditer(text):
            yield "secret", "high", match.start(), match.end(), match.group("v"), "seed phrase", match.span("v")


def detect_assignments(text, path):
    name = Path(path).name.lower()
    suffix = Path(path).suffix.lower()
    if not (suffix in CODE_EXTS or suffix in CONFIG_EXTS or name.startswith(".env") or name.endswith(".env")
            or "docker-compose" in name):
        return
    quoted_only = suffix in CODE_EXTS
    resume = 0
    for keyword in KEYWORD_RE.finditer(text):
        if keyword.start() < resume:
            continue
        tail = TAIL_RE.match(text, keyword.end())
        if not tail:
            continue
        start = keyword.start()
        while start > 0 and text[start - 1] in NAME_CHARS and keyword.start() - start < 60:
            start -= 1
        full = text[start:keyword.end() + len(tail.group("rest"))]
        resume = tail.end()
        if start < keyword.start() and not text[start:keyword.start()].endswith(("_", ".", "-")):
            prev = text[keyword.start() - 1]
            if prev.isalpha() and not ((keyword.group(0)[0].isupper() and prev.islower()) or full.isupper()):
                continue
        rest = tail.group("rest")
        if rest and not (rest[0] in "_.-0123456789" or rest[0].isupper() or rest in ("s", "es")):
            continue
        if full.lower().endswith(NAME_SUFFIXES):
            continue
        raw = tail.group("value")
        quoted = raw[0] in "\"'"
        value = raw[1:-1] if quoted else raw
        if (quoted_only and not quoted) or re.search(r"\s", value) or is_placeholder(value) or not secret_like(value) \
                or re.fullmatch(r"[A-Z][a-z]+(?:-[A-Z][a-z]+)+", value):
            continue
        yield "secret", "high", tail.start("value"), tail.end("value"), value, "credential assignment"


def detect_credentials_url(text):
    if "://" not in text:
        return
    for match in USERINFO_RE.finditer(text):
        if safe_host(match.group("host")) or is_placeholder(match.group("pw")) \
                or match.group("pw").lower() in ("pass", "password", "pwd", "secret"):
            continue
        yield "credentials-url", "high", match.start(), match.end(), match.group("v"), "user:password in a URL", \
            match.span("v")


def detect_emails(text):
    pos = text.find("@")
    while pos != -1:
        start = pos
        while start > 0 and pos - start < 64 and text[start - 1] in LOCAL_CHARS:
            start -= 1
        domain = DOMAIN_RE.match(text, pos + 1)
        if domain and start < pos:
            address = text[start:domain.end()]
            if not safe_email(address):
                yield "email", "high", start, domain.end(), address, None
        pos = text.find("@", pos + 1)


def detect_ips(text):
    if "." in text:
        for match in IPV4_RE.finditer(text):
            before = text[max(0, match.start() - 20):match.start()]
            if VERSION_CTX_RE.search(before):
                continue
            level = classify_ip(match.group(1))
            if level:
                yield "ip", level, match.start(1), match.end(1), match.group(1), "public" if level == "medium" \
                    else "private range"
    if text.count(":") >= 3:
        for match in IPV6_RE.finditer(text):
            candidate = match.group(0)
            if sum(1 for group in candidate.split(":") if group) < 3 or candidate.count(":") < 3:
                continue
            level = classify_ip(candidate)
            if level:
                yield "ip", level, match.start(), match.end(), candidate, "IPv6"


def detect_ports(text):
    if ":" not in text and "port" not in text.lower():
        return
    seen = set()
    for regex in (PORT_RE, HOST_PORT_RE):
        for match in regex.finditer(text):
            host, port = match.group("host"), match.group("port")
            if host != host.lower():  # Code identifiers (Module.Class:12), not host names
                continue
            if safe_host(host) or int(port) > 65535 or (match.start(), host) in seen:
                continue
            seen.add((match.start(), host))
            yield "port", "low", match.start(), match.end(), "%s:%s" % (host, port), "non-local host and port", \
                (match.start("host"), match.end("port"))


def detect_usernames(text):
    if "/Users" not in text and "/home" not in text and "\\Users" not in text:
        return
    for regex in HOME_RES:
        for match in regex.finditer(text):
            user = match.group("v")
            if user.lower() in PLACEHOLDER_USERS or re.search(r"[<>$%{}*~]", user) or user.isdigit() or len(user) < 2:
                continue
            yield "username", "medium", match.start("v"), match.end("v"), user, "home directory"


def detect_phones(text):
    if not re.search(r"\d{2}", text):
        return
    for regex in PHONE_RES:
        for match in regex.finditer(text):
            digits = re.sub(r"\D", "", match.group(0))
            if 9 <= len(digits) <= 15 and len(set(digits)) > 2 and not (len(digits) == 10 and digits[3:6] == "555"):
                yield "phone", "medium", match.start(), match.end(), digits, None


def detect_addresses(text):
    for regex in ADDRESS_RES:
        for match in regex.finditer(text):
            yield "postal-address", "medium", match.start(), match.end(), re.sub(r"\s+", " ", match.group(0)), None


def detect_financial(text):
    for match in IBAN_RE.finditer(text):
        compact = match.group(0).replace(" ", "")
        if iban_valid(compact):
            yield "iban", "high", match.start(), match.end(), compact, None
    for match in CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if not (13 <= len(digits) <= 19 and CARD_PREFIX_RE.match(digits) and luhn(digits)):
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start:len(text) if line_end < 0 else line_end]
        if CARD_GROUPED_RE.fullmatch(match.group(0)) or CARD_HINT_RE.search(line):
            yield "card-number", "high", match.start(), match.end(), digits, None


# ---------------------------------------------------------------- images and documents

def office_text(data):
    """Plain text of a docx/odt/xlsx/pptx/ods/odp (XML parts of the zip, tags removed), '' if unreadable."""
    parts = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                low = info.filename.lower()
                wanted = (low in ("word/document.xml", "content.xml", "xl/sharedstrings.xml")
                          or low.startswith(("ppt/slides/slide", "xl/worksheets/", "word/header", "word/footer")))
                if wanted and info.file_size < 20000000:
                    xml = archive.read(info).decode("utf-8", "replace")
                    parts.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)))
    except (zipfile.BadZipFile, OSError, KeyError, RuntimeError, ValueError):
        return ""
    return "\n".join(parts)


def parse_tiff(tiff):
    """{"make", "model", "gps"} from a TIFF/EXIF stream, or None when it is not one."""
    if tiff[:2] not in (b"II", b"MM"):
        return None
    end = "<" if tiff[:2] == b"II" else ">"
    try:
        if struct.unpack(end + "H", tiff[2:4])[0] != 42:
            return None

        def entries(offset):
            count = struct.unpack(end + "H", tiff[offset:offset + 2])[0]
            for index in range(min(count, 300)):
                entry = tiff[offset + 2 + 12 * index:offset + 14 + 12 * index]
                tag, kind, size = struct.unpack(end + "HHI", entry[:8])
                yield tag, kind, size, entry[8:12]

        def text_value(kind, size, raw):
            if kind != 2:
                return None
            if size <= 4:
                return raw[:size].rstrip(b"\0").decode("ascii", "replace")
            offset = struct.unpack(end + "I", raw)[0]
            return tiff[offset:offset + size].rstrip(b"\0").decode("ascii", "replace")

        info = {"make": None, "model": None, "gps": False}
        for tag, kind, size, raw in entries(struct.unpack(end + "I", tiff[4:8])[0]):
            if tag == 0x010F:
                info["make"] = text_value(kind, size, raw)
            elif tag == 0x0110:
                info["model"] = text_value(kind, size, raw)
            elif tag == 0x8825:
                gps_offset = struct.unpack(end + "I", raw)[0]
                info["gps"] = any(t in (2, 4) for t, _, _, _ in entries(gps_offset))
        return info
    except (struct.error, IndexError):
        return {"make": None, "model": None, "gps": False}


def exif_stdlib(data, ext):
    """EXIF summary from a JPEG, TIFF or PNG without Pillow; None when no EXIF block is found."""
    tiff = None
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 <= len(data) and data[pos] == 0xFF:
            marker = data[pos + 1]
            if marker == 0xDA:
                break
            length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if marker == 0xE1 and data[pos + 4:pos + 10] == b"Exif\0\0":
                tiff = data[pos + 10:pos + 2 + length]
                break
            pos += 2 + length
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        pos = 8
        while pos + 8 <= len(data):
            length, kind = struct.unpack(">I4s", data[pos:pos + 8])
            if kind == b"eXIf":
                tiff = data[pos + 8:pos + 8 + length]
                break
            pos += 12 + length
    elif data[:2] in (b"II", b"MM"):
        tiff = data
    return parse_tiff(tiff) if tiff else None


XMP_JPEG_PREFIX = b"http://ns.adobe.com/xap/1.0/\0"


def xmp_packet(data):
    """Text of the XMP packet of a PNG (iTXt chunk) or a JPEG (APP1 segment), '' when there is none."""
    packet = b""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            pos = 8
            while pos + 8 <= len(data):
                length, kind = struct.unpack(">I4s", data[pos:pos + 8])
                body = data[pos + 8:pos + 8 + length]
                if kind == b"iTXt" and body.startswith(b"XML:com.adobe.xmp\0"):
                    rest = body[len(b"XML:com.adobe.xmp\0"):]
                    flag, rest = rest[0], rest[2:]
                    packet = rest.split(b"\0", 2)[2] if rest.count(b"\0") >= 2 else b""
                    if flag == 1:
                        packet = zlib.decompress(packet)
                    break
                if kind in (b"IDAT", b"IEND"):
                    break
                pos += 12 + length
        elif data[:2] == b"\xff\xd8":
            pos = 2
            while pos + 4 <= len(data) and data[pos] == 0xFF:
                marker = data[pos + 1]
                if marker == 0xDA:
                    break
                length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
                if marker == 0xE1 and data[pos + 4:pos + 4 + len(XMP_JPEG_PREFIX)] == XMP_JPEG_PREFIX:
                    packet = data[pos + 4 + len(XMP_JPEG_PREFIX):pos + 2 + length]
                    break
                pos += 2 + length
    except (struct.error, IndexError, zlib.error):
        return ""
    return packet.decode("utf-8", "replace")


def xmp_value(packet, name):
    """Value of an XMP property written as an attribute or as an element, None when absent or empty."""
    match = re.search(r'\b%s\s*=\s*"([^"]*)"|<%s[^>]*>([^<]*)<' % (name, name), packet)
    value = (match.group(1) or match.group(2) or "").strip() if match else ""
    return value or None


def xmp_info(data):
    """{"make", "model", "gps"} from the XMP packet of an image, or None when it holds no XMP."""
    packet = xmp_packet(data)
    if not packet:
        return None
    return {"make": xmp_value(packet, "tiff:Make"), "model": xmp_value(packet, "tiff:Model"),
            "gps": bool(xmp_value(packet, "exif:GPSLatitude") and xmp_value(packet, "exif:GPSLongitude"))}


def exif_info(data, ext):
    """{"make", "model", "gps"} of an image (EXIF merged with XMP), or None without metadata. Pillow when
    importable, else the stdlib parser."""
    info = None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            exif = image.getexif()
            if exif:
                gps = False
                try:
                    gps = bool(exif.get_ifd(0x8825))
                except Exception:  # noqa: BLE001 - old Pillow without get_ifd
                    gps = 0x8825 in exif
                info = {"make": exif.get(0x010F), "model": exif.get(0x0110), "gps": gps}
    except Exception:  # noqa: BLE001 - Pillow absent or unreadable image: fall back
        info = exif_stdlib(data, ext)
    xmp = xmp_info(data)
    if xmp:
        if not info:
            return xmp
        info = {"make": info["make"] or xmp["make"], "model": info["model"] or xmp["model"],
                "gps": info["gps"] or xmp["gps"]}
    return info


def count_faces(data):
    """Number of faces (cv2 Haar cascade, or macOS Vision), None when no detector is available."""
    try:
        import cv2
        import numpy
        image = cv2.imdecode(numpy.frombuffer(data, numpy.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return 0
        scale = 800.0 / max(image.shape[:2])
        if scale < 1:
            image = cv2.resize(image, None, fx=scale, fy=scale)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        return len(cascade.detectMultiScale(image, 1.1, 5, minSize=(40, 40)))
    except Exception:  # noqa: BLE001 - cv2 missing or failing: try Vision
        pass
    if sys.platform == "darwin":
        try:
            import Foundation
            import Vision
            ns_data = Foundation.NSData.dataWithBytes_length_(data, len(data))
            handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(ns_data, {})
            request = Vision.VNDetectFaceRectanglesRequest.alloc().init()
            handler.performRequests_error_([request], None)
            return len(request.results() or [])
        except Exception:  # noqa: BLE001 - pyobjc Vision missing
            return None
    return None


def image_findings(data, ext):
    """[(category, severity, detail)] for one image file."""
    if ext in (".heic", ".heif"):
        return [("photo", "medium", "HEIC/HEIF: usually a phone photo, metadata not parsed")]
    info = exif_info(data, ext)
    if ext == ".png" and not info:
        return []
    faces = count_faces(data)
    out = []
    if info and info["gps"]:
        out.append(("photo-location", "high", "GPS coordinates in the EXIF metadata"))
    if faces:
        out.append(("photo-person", "high", "%d face(s) detected" % faces))
    if not out:
        note = "" if faces is not None else "; face detection unavailable"
        if info and (info["make"] or info["model"]):
            out.append(("photo", "medium", "camera metadata present%s" % note))
        elif info:
            out.append(("photo", "low", "metadata without camera make or model (screenshot or edited image)%s"
                        % note))
        else:
            out.append(("photo", "low", "no EXIF metadata%s" % note))
    return out


# ---------------------------------------------------------------- findings

def remedies_for(category, where):
    out = list(REMEDIES[category])
    if where != "working-tree":
        out = [r for r in out if r not in ("redact-head", "untrack", "move-to-env")]
    if where != "identity":
        out = [r for r in out if r != "mailmap"]
    return out


def make_hit(category, severity, where, value, path=None, line=None, commit=None, detail=None, preview=None,
             norm=None, blob=None, match=None):
    """A finding dict plus the private "_value" (raw, normalized), "_match" (exact text found, what a rewrite
    replaces) and "_blob" keys; callers strip them before printing."""
    if norm is None:
        norm = value.lower() if category in LOWERED_FP else value
    hit = finding(category, severity, where, preview if preview is not None else redact(value),
                  fingerprint(norm), path, line, commit, remedies_for(category, where), detail)
    hit["_value"] = value
    hit["_match"] = value if match is None else match
    hit["_blob"] = blob
    return hit


def public(hit):
    return {key: val for key, val in hit.items() if not key.startswith("_")}


def line_info(text, start):
    return text.count("\n", 0, start) + 1


class Scanner:
    """Scans texts and files, applying the allowlist, the ignore marker and the personal terms."""

    def __init__(self, repo, terms, allow):
        self.repo = repo
        self.terms = terms
        self.allow = allow
        self.counts = {"files": 0, "blobs": 0, "commits": 0, "images": 0, "texts": 0}
        self.analysed_blobs = set()

    def text_hits(self, text, path, where, commit=None, kind="file", blob=None):
        """Hits of one decoded text. kind is "file" or "message" (messages skip the noisy categories)."""
        if not text.strip():
            return []
        self.counts["texts"] += 1
        noisy = kind == "file" and (bool(NOISY_RE.search(path or "")) or
                                    (len(text) > 100000 and text.count("\n") * 400 < len(text)))
        raw = []
        detectors = [detect_secrets(text), detect_credentials_url(text), detect_emails(text),
                     detect_usernames(text)]
        if kind == "file":
            detectors.append(detect_assignments(text, path or ""))
        if not noisy:
            detectors += [detect_ips(text), detect_financial(text)]
            if kind == "file":
                detectors += [detect_ports(text), detect_phones(text), detect_addresses(text)]
        for detector in detectors:
            for item in detector:
                raw.append(item)
                if len(raw) > 4 * HITS_PER_TEXT:
                    break
        for start, end, matched, label in self.terms.find(text):
            raw.append(("personal-name", "high", start, end, matched, "term source: " + label))
        spans = [(RANKS.get(item[0], 4), item[2], item[3]) for item in raw]
        hits, seen = [], set()
        for item, (rank, start, end) in zip(raw, spans):
            category, severity, _, _, value, detail = item[:6]
            exact = item[6] if len(item) > 6 else (start, end)
            if rank == 4 and any(r < 4 and s <= start and end <= e for r, s, e in spans):
                continue
            hit = make_hit(category, severity, where, value, path, line_info(text, start), commit,
                           detail=detail, blob=blob, match=text[exact[0]:exact[1]])
            key = (category, hit["fingerprint"], hit["line"])
            if hit["fingerprint"] in self.allow or key in seen:
                continue
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", end)
            if ignored_line(text[line_start:len(text) if line_end < 0 else line_end]):
                continue
            seen.add(key)
            hits.append(hit)
            if len(hits) >= HITS_PER_TEXT:
                break
        return hits

    def name_hits(self, path, where, size=None, data=None, blob=None):
        """Findings that depend on the file name (and size, and content when available)."""
        out = []
        base = path.rsplit("/", 1)[-1]
        ext = Path(base).suffix.lower()

        def add(category, severity, preview=None, detail=None):
            hit = make_hit(category, severity, where, path, path, None, None, detail, preview or base, blob=blob)
            if hit["fingerprint"] not in self.allow:
                out.append(hit)
            return hit

        if ENV_FILE_RE.match(base) and not ENV_SAFE_RE.search(base):
            add("env-file", "high")
        symlink = data is not None and len(data) < 300 and re.fullmatch(rb"[\w./~@+-]+", data) is not None
        if CRED_FILE_RE.search(path) and not symlink:
            text = data.decode("utf-8", "replace") if data is not None and not is_binary_bytes(data) else None
            if base.lower() == ".npmrc":
                if text is not None and re.search(r"_authToken[ \t]*=[ \t]*(?!\$\{)[^\s$]{6,}", text):
                    add("credential-file", "high", detail="npm auth token")
            elif ext == ".pem" and text is not None and "PRIVATE KEY" not in text and (
                    "BEGIN CERTIFICATE" in text or "BEGIN PUBLIC KEY" in text):
                add("credential-file", "low", detail="certificate or public key only")
            else:
                add("credential-file", "high")
        if size is not None and size > LARGE_BLOB:
            hit = make_hit("large-blob", "low", where, blob or path, path, None, None,
                           "%.1f MB" % (size / 1048576.0), "%.1f MB" % (size / 1048576.0))
            if hit["fingerprint"] not in self.allow:
                out.append(hit)
        for start, end, matched, label in self.terms.find(path):
            hit = make_hit("personal-name", "high", where, matched, path, None, None, "in the file name; term source: "
                           + label, blob=blob)
            hit["_in_name"] = True
            if hit["fingerprint"] not in self.allow:
                out.append(hit)
        return out

    def file_hits(self, path, data, where, size=None, blob=None, commit=None):
        """All findings for one file version. data is None when the content was not read."""
        self.counts["files"] += 1
        base = path.rsplit("/", 1)[-1]
        ext = Path(base).suffix.lower()
        hits = self.name_hits(path, where, size, data, blob)
        content = []
        personal = PERSONAL_FILE_RE.search(base) and ext in DOCUMENT_EXTS
        severity, detail = "medium", None
        if data is not None:
            if ext in OFFICE_EXTS:
                text = office_text(data)
                content = self.text_hits(text, path, where, commit, blob=blob)
                for hit in content:  # text extracted from a zip: a text rewrite cannot reach it
                    hit["_office"] = True
                if any(h["category"] in PII_CATEGORIES for h in content) or CONTRACT_RE.search(text):
                    severity, detail = "high", "personal data or contract wording in the text"
            elif ext in IMAGE_EXTS:
                content = self.image_hits(path, data, ext, where, blob)
            elif not is_binary_bytes(data):
                content = self.text_hits(data.decode("utf-8", "replace"), path, where, commit, blob=blob)
        elif ext in IMAGE_EXTS and ext != ".png":
            content = self.image_hits(path, None, ext, where, blob)
        if personal:
            hit = make_hit("personal-file", severity, where, path, path, None, None, detail, base, blob=blob)
            if hit["fingerprint"] not in self.allow:
                hits.append(hit)
        return hits + content

    def image_hits(self, path, data, ext, where, blob):
        key = blob or path
        if key in self.analysed_blobs:
            return []
        self.analysed_blobs.add(key)
        if data is None:
            findings = [("photo", "medium", "too large to analyse, probably a photo")]
        elif self.counts["images"] >= IMAGE_CAP:
            findings = [("photo", "low", "not analysed: image cap of %d reached" % IMAGE_CAP)]
        else:
            self.counts["images"] += 1
            findings = image_findings(data, ext)
        out = []
        for category, severity, detail in findings:
            hit = make_hit(category, severity, where, path, path, None, None, detail, Path(path).name, blob=blob)
            if hit["fingerprint"] not in self.allow:
                out.append(hit)
        return out


def is_binary_bytes(data):
    return b"\0" in data[:8000]


# ---------------------------------------------------------------- repository walkers

def is_bare(repo):
    return git(repo, "rev-parse", "--is-bare-repository", check=False).strip() == "true"


def scan_tree(scanner, repo):
    """Findings of the tracked files as they are on disk. Returns (hits, tracked path set)."""
    names = tracked_files(repo)
    hits = []
    for name in names:
        path = Path(repo) / name
        try:
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
        except OSError:
            continue
        ext = path.suffix.lower()
        limit = MAX_OFFICE if ext in OFFICE_EXTS else MAX_IMAGE if ext in IMAGE_EXTS else MAX_TEXT
        data = None
        if size <= limit:
            try:
                data = path.read_bytes()
            except OSError:
                data = None
        hits += scanner.file_hits(name, data, "working-tree", size)
    return hits, set(names)


def history_blobs(repo):
    """[(sha, size, path)] of every unique blob reachable from any ref."""
    listing = git_bytes(repo, "rev-list", "--objects", "--all", check=False)
    if not listing.strip():
        return []
    fmt = "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)"
    checked = run(["git", "-C", str(repo), "cat-file", fmt], input_bytes=listing).stdout.decode("utf-8", "replace")
    blobs = []
    for line in checked.splitlines():
        parts = line.split(" ", 3)
        if len(parts) == 4 and parts[1] == "blob" and parts[3]:
            blobs.append((parts[0], int(parts[2]), parts[3]))
    return blobs


def read_blobs(repo, items, chunk_bytes=64 * 1048576):
    """Yield (sha, bytes or None) for [(sha, size)], reading by chunks through `git cat-file --batch`."""
    chunk, total = [], 0
    for sha, size in items:
        chunk.append(sha)
        total += size
        if total >= chunk_bytes or len(chunk) >= 5000:
            yield from _batch(repo, chunk)
            chunk, total = [], 0
    if chunk:
        yield from _batch(repo, chunk)


def _batch(repo, shas):
    out = run(["git", "-C", str(repo), "cat-file", "--batch"], input_bytes=("\n".join(shas) + "\n").encode()).stdout
    pos = 0
    for sha in shas:
        newline = out.index(b"\n", pos)
        header = out[pos:newline].split()
        if len(header) < 3:
            pos = newline + 1
            yield sha, None
            continue
        size = int(header[2])
        yield sha, out[newline + 1:newline + 1 + size]
        pos = newline + 2 + size


def scan_history_blobs(scanner, repo):
    blobs = history_blobs(repo)
    wanted, sizes, hits = [], {}, []
    for sha, size, path in blobs:
        ext = Path(path).suffix.lower()
        limit = MAX_OFFICE if ext in OFFICE_EXTS else MAX_IMAGE if ext in IMAGE_EXTS else MAX_TEXT
        sizes[sha] = (size, path)
        if size <= limit:
            wanted.append((sha, size))
        else:
            hits += scanner.file_hits(path, None, "history", size, sha)
    scanner.counts["blobs"] = len(blobs)
    for sha, data in read_blobs(repo, wanted):
        size, path = sizes[sha]
        hits += scanner.file_hits(path, data, "history", size, sha)
    return hits


def commit_records(repo):
    """[{hash, an, ae, cn, ce, message}] for every commit of every ref."""
    out = git_bytes(repo, "log", "--all", "--format=%x1e%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B", check=False)
    records = []
    for chunk in out.decode("utf-8", "replace").split("\x1e")[1:]:
        parts = chunk.split("\x1f", 5)
        if len(parts) == 6:
            records.append(dict(zip(("hash", "an", "ae", "cn", "ce", "message"), parts)))
    return records


def tag_records(repo):
    """[{ref, name, email, message}] for annotated tags."""
    fmt = "%(refname)%1f%(objecttype)%1f%(taggername)%1f%(taggeremail)%1f%(contents)%1e"
    out = git_bytes(repo, "for-each-ref", "--format=" + fmt, "refs/tags", check=False).decode("utf-8", "replace")
    tags = []
    for chunk in out.split("\x1e"):
        parts = chunk.strip("\n").split("\x1f", 4)
        if len(parts) == 5 and parts[1] == "tag":
            tags.append({"ref": parts[0], "name": parts[2], "email": parts[3].strip("<>"), "message": parts[4]})
    return tags


def list_identities(repo, commits=None, tags=None):
    """[{name, email, roles, count}] distinct (name, email) pairs of authors, committers and taggers."""
    commits = commit_records(repo) if commits is None else commits
    tags = tag_records(repo) if tags is None else tags
    found = {}

    def note(name, email, role):
        entry = found.setdefault((name, email), {"name": name, "email": email, "roles": set(), "count": 0})
        entry["roles"].add(role)
        entry["count"] += 1

    for record in commits:
        note(record["an"], record["ae"], "author")
        note(record["cn"], record["ce"], "committer")
    for tag in tags:
        note(tag["name"], tag["email"], "tagger")
    return sorted(found.values(), key=lambda e: (-e["count"], e["name"]))


def identity_hits(scanner, identities):
    hits = []
    for entry in identities:
        name, email = entry["name"], entry["email"]
        roles = "/".join(sorted(entry["roles"]))
        detail = "%s of %d commit(s) or tag(s)" % (roles, entry["count"])
        if email and not safe_email(email) and "@" in email:
            hit = make_hit("email", "high", "identity", email, detail=detail)
            if hit["fingerprint"] not in scanner.allow:
                hits.append(hit)
        for _, _, matched, label in scanner.terms.find(name):
            hit = make_hit("personal-name", "high", "identity", matched, detail="in a git author name; " + detail +
                           "; term source: " + label)
            hit["_identity"] = name
            if hit["fingerprint"] not in scanner.allow:
                hits.append(hit)
    return hits


def message_hits(scanner, commits, tags):
    hits = []
    for record in commits:
        hits += scanner.text_hits(record["message"], None, "commit-message", record["hash"][:8], kind="message")
    for tag in tags:
        hits += scanner.text_hits(tag["message"], None, "commit-message", tag["ref"].replace("refs/tags/", "tag "),
                                  kind="message")
    return hits


def resolve_commits(repo, hits):
    """Fills the `commit` field of history hits with the commit that added the blob (at most LOOKUP_CAP lookups)."""
    done = {}
    for hit in sorted(hits, key=lambda h: SEVERITIES.index(h["severity"])):
        blob = hit.get("_blob")
        if hit["where"] != "history" or not blob or hit["commit"]:
            continue
        if blob not in done:
            if len(done) >= LOOKUP_CAP:
                continue
            out = git(repo, "log", "--all", "--format=%h", "-1", "--diff-filter=A", "--find-object=" + blob,
                      check=False).strip()
            if not out:
                out = git(repo, "log", "--all", "--format=%h", "-1", "--find-object=" + blob, check=False).strip()
            done[blob] = out.splitlines()[0] if out else None
        hit["commit"] = done[blob]


def gitleaks_hits(repo, history, known, tracked, allow):
    """Extra findings from gitleaks when installed (silently nothing otherwise)."""
    exe = shutil.which("gitleaks")
    if not exe:
        return []
    report = state_dir(repo) / ("gitleaks-%d.json" % os.getpid())
    cmd = [exe, "git" if history else "dir", "--report-format", "json", "--report-path", str(report),
           "--exit-code", "0", "--no-banner", str(repo)]
    try:
        run(cmd, check=False, timeout=900)
        items = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
    except (Failure, OSError, ValueError, subprocess.SubprocessError):
        return []
    finally:
        try:
            report.unlink()
        except OSError:
            pass
    hits = []
    for item in items if isinstance(items, list) else []:
        secret = item.get("Secret") or ""
        if len(secret) < 6 or secret == "REDACTED":
            continue
        path = str(item.get("File") or "")
        if path.startswith(str(repo)):
            path = os.path.relpath(path, str(repo))
        if not history and path not in tracked:
            continue
        hit = make_hit("secret", "high", "history", secret, path, item.get("StartLine"),
                       (item.get("Commit") or "")[:8] or None, "gitleaks rule %s" % item.get("RuleID", "?"))
        if hit["fingerprint"] in known or hit["fingerprint"] in allow:
            continue
        text = read_text(Path(repo) / path) if path else None
        if not item.get("Commit") or (text and secret in text):
            hit["where"] = "working-tree"
            hit["remedy"] = remedies_for("secret", "working-tree")
        known.add(hit["fingerprint"])
        hits.append(hit)
    return hits


# ---------------------------------------------------------------- reports

WHERE_ORDER = ("working-tree", "history", "commit-message", "identity", "pull-request", "release")


def group_findings(findings, per_group=5):
    """Collapse findings by (category, fingerprint): the first one (working tree first), the union of the remedies
    and up to per_group occurrences."""
    groups = {}
    ordered = sorted(findings, key=lambda f: WHERE_ORDER.index(f["where"]) if f["where"] in WHERE_ORDER else 9)
    for item in ordered:
        key = (item["category"], item["fingerprint"])
        group = groups.get(key)
        if group is None:
            group = groups[key] = {"first": dict(item), "occurrences": []}
        elif SEVERITIES.index(item["severity"]) < SEVERITIES.index(group["first"]["severity"]):
            group["first"]["severity"] = item["severity"]
        group["occurrences"].append(item)
    out = []
    for group in groups.values():
        entry = group["first"]
        entry["remedy"] = list(dict.fromkeys(r for occ in group["occurrences"] for r in occ["remedy"]))
        entry["occurrences_total"] = len(group["occurrences"])
        entry["occurrences"] = [{k: occ.get(k) for k in ("where", "path", "line", "commit", "detail") if occ.get(k)}
                                for occ in group["occurrences"][:per_group]]
        out.append(entry)
    out.sort(key=lambda e: (SEVERITIES.index(e["severity"]), e["category"], -e["occurrences_total"]))
    return out


def summarize(findings, extra=None):
    groups = group_findings(findings, per_group=0)
    summary = {sev: 0 for sev in SEVERITIES}
    by_category = {}
    for entry in groups:
        summary[entry["severity"]] += 1
        info = by_category.setdefault(entry["category"], {"severity": entry["severity"], "occurrences": 0,
                                                          "values": 0})
        info["occurrences"] += entry["occurrences_total"]
        info["values"] += 1
        if SEVERITIES.index(entry["severity"]) < SEVERITIES.index(info["severity"]):
            info["severity"] = entry["severity"]
    summary["by_category"] = dict(sorted(by_category.items(), key=lambda kv: (SEVERITIES.index(kv[1]["severity"]),
                                                                              kv[0])))
    summary.update(extra or {})
    return summary


def collect_hits(repo, history=True, terms=None, include_remote=False, allow=None, dedupe=True):
    """Raw hits (with "_value" and "_match") of the working tree and, optionally, the whole history; plus run
    information. dedupe=False keeps the history hits of values also in the working tree (every variant)."""
    repo = Path(repo)
    allow = load_allowlist(repo) if allow is None else set(allow)
    termset = build_terms(repo, terms, network=include_remote)
    scanner = Scanner(repo, termset, allow)
    bare = is_bare(repo)
    tree_hits, tracked = ([], set()) if bare else scan_tree(scanner, repo)
    hits = list(tree_hits)
    if history:
        tree_keys = {(h["category"], h["fingerprint"]) for h in tree_hits}
        commits, tags = commit_records(repo), tag_records(repo)
        scanner.counts["commits"] = len(commits)
        past = scan_history_blobs(scanner, repo)
        past += message_hits(scanner, commits, tags)
        past += identity_hits(scanner, list_identities(repo, commits, tags))
        if dedupe:
            past = [h for h in past if (h["category"], h["fingerprint"]) not in tree_keys]
        resolve_commits(repo, past)
        hits += past
    known = {h["fingerprint"] for h in hits if h["category"] == "secret"}
    hits += gitleaks_hits(repo, history, known, tracked, allow)
    info = {"term_sources": termset.sources(), "scanned": scanner.counts, "history": history,
            "bare": bare, "gitleaks": bool(shutil.which("gitleaks"))}
    return hits, info


def scan_repo(repo, history=True, terms=None, include_remote=False, raw=False):
    """{"findings": [...], "summary": {...}} for the security categories; allowlisted fingerprints removed."""
    hits, info = collect_hits(repo, history, terms, include_remote)
    findings = hits if raw else [public(h) for h in hits]
    return {"findings": findings, "summary": summarize(hits, info)}


# ---------------------------------------------------------------- attribution

def gh_api_list(args):
    """Items of a paginated `gh api` list (pages may be printed as several JSON arrays)."""
    result = run(["gh"] + list(args), check=False, timeout=180)
    if result.returncode != 0:
        raise Failure(EXIT_NETWORK, "gh %s failed: %s" % (args[0], result.stderr.decode("utf-8", "replace")[:200]))
    text, items, pos = result.stdout.decode("utf-8", "replace"), [], 0
    decoder = json.JSONDecoder()
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        value, pos = decoder.raw_decode(text, pos)
        items += value if isinstance(value, list) else [value]
    return items


def fetch_pull_requests(slug, limit=300):
    """[{number, title, body, url}] of the repository pull requests (open and closed)."""
    return gh_json(["pr", "list", "-R", slug, "--state", "all", "--limit", str(limit), "--json",
                    "number,title,body,url"]) or []


def fetch_releases(slug):
    """[{id, tag_name, name, body, html_url}] of the repository releases."""
    return gh_api_list(["api", "repos/%s/releases" % slug, "--paginate"])


def ai_text_hits(text, where, path=None, commit=None, detail=None, subject=False):
    """Hits for each line of a text that credits an AI assistant."""
    hits = []
    low = text.lower()
    if not any(needle in low for needle in AI_NEEDLES):
        return hits
    for number, line in enumerate(text.split("\n"), 1):
        match = ai_line_match(line)
        label = None
        if match:
            label, tool = match
        elif subject and number == 1 and AI_SUBJECT_RE.match(line):
            label, tool = "aider: subject prefix", "aider"
        if not label or ignored_line(line):
            continue
        extra = "tool: %s" % tool if tool else None
        hits.append(make_hit("ai-coauthor", "high", where, line.strip(), path, number if path else None, commit,
                             "; ".join(p for p in (detail, extra) if p) or None, label,
                             norm=where + ":" + re.sub(r"\s+", " ", line.strip().lower())))
    return hits


def attribution_hits(repo, include_remote, allow):
    repo = Path(repo)
    hits, remote = [], "disabled"
    commits, tags = commit_records(repo), tag_records(repo)
    for record in commits:
        hits += ai_text_hits(record["message"], "commit-message", commit=record["hash"][:8], subject=True)
    for tag in tags:
        hits += ai_text_hits(tag["message"], "commit-message", commit=tag["ref"].replace("refs/tags/", "tag "))
    tracked = set() if is_bare(repo) else set(tracked_files(repo))
    for name in sorted(tracked):
        text = read_text(Path(repo) / name)
        if text:
            hits += ai_text_hits(text, "working-tree", path=name)
    for entry in list_identities(repo, commits, tags):
        tool = ai_identity(entry["name"], entry["email"])
        if tool:
            hits.append(make_hit("ai-author", "medium", "identity", entry["email"] or entry["name"],
                                 detail="%s; %d commit(s) or tag(s); tool: %s" % ("/".join(sorted(entry["roles"])),
                                                                                  entry["count"], tool),
                                 preview="AI bot identity (%s)" % tool))
    for _, _, path in history_blobs(repo):
        match = AI_CONFIG_RE.search(path)
        if match:
            where = "working-tree" if path in tracked else "history"
            key = path[:match.end()]
            hits.append(make_hit("ai-config-file", "info", where, key, key, preview=key))
    slug = github_slug(repo) if include_remote else None
    if include_remote:
        remote = "skipped: no GitHub remote" if not slug else "ok"
    if slug:
        try:
            for pr in fetch_pull_requests(slug) or []:
                for field in ("title", "body"):
                    hits += ai_text_hits(pr.get(field) or "", "pull-request",
                                         detail="PR #%s %s %s" % (pr.get("number"), field, pr.get("url") or ""))
            for rel in fetch_releases(slug) or []:
                hits += ai_text_hits(rel.get("body") or "", "release",
                                     detail="release %s %s" % (rel.get("tag_name"), rel.get("html_url") or ""))
        except (Failure, ValueError) as error:
            remote = "skipped: %s" % str(error)[:120]
    for hit in hits:
        if hit["category"] == "ai-coauthor":
            hit["remedy"] = {"working-tree": ["redact-head"], "pull-request": ["edit-pr"], "release": ["edit-pr"]}.get(
                hit["where"], ["strip-messages", "rewrite-history"])
    keep = [h for h in hits if h["fingerprint"] not in allow]
    return keep, {"remote": remote}


def attribution_scan(repo, include_remote=True, raw=False):
    """{"findings", "summary"} for AI co-authorship in commits, files, identities, pull requests and releases."""
    hits, info = attribution_hits(repo, include_remote, load_allowlist(repo))
    findings = hits if raw else [public(h) for h in hits]
    return {"findings": findings, "summary": summarize(hits, info)}


# ---------------------------------------------------------------- commands

def write_report(repo, name, data):
    path = state_dir(repo) / name
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1, default=str)
    os.chmod(str(path), 0o600)
    return path


def report_command(repo, result, limit, report_name):
    findings = result["findings"]
    summary = result["summary"]
    full = group_findings(findings, per_group=200)
    path = write_report(repo, report_name, {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "summary": summary, "findings": full})
    shown = group_findings(findings, per_group=5)[:max(limit, 0)]
    blocking = summary["high"] + summary["medium"] > 0
    print_json({"ok": not blocking, "summary": summary, "findings": shown, "truncated": max(len(full) - len(shown), 0),
                "report": str(path)})
    return EXIT_FINDINGS if blocking else EXIT_OK


def cmd_security(args):
    repo = repo_root(args.repo)
    result = scan_repo(repo, history=args.history, terms=args.terms, include_remote=not args.no_remote)
    return report_command(repo, result, args.limit, "security-report.json")


def cmd_attribution(args):
    repo = repo_root(args.repo)
    result = attribution_scan(repo, include_remote=not args.no_remote)
    return report_command(repo, result, args.limit, "attribution-report.json")


def cmd_allow(args):
    repo = repo_root(args.repo)
    current = load_allowlist(repo)
    given = {fp.strip() for fp in args.fingerprints if fp.strip()}
    updated = current - given if args.remove else current | given
    save_allowlist(repo, updated)
    print_json({"ok": True, "allowed": len(updated), "added": sorted(updated - current),
                "removed": sorted(current - updated)})
    return EXIT_OK


def add_commands(subparsers):
    parser = subparsers.add_parser("security", help="secrets and personal data in the files and the history")
    parser.add_argument("repo")
    parser.add_argument("--history", action=argparse.BooleanOptionalAction, default=True,
                        help="scan every blob and message of all refs (default)")
    parser.add_argument("--terms", default=None, help="extra personal terms, comma-separated")
    parser.add_argument("--limit", type=int, default=100, help="findings listed on stdout (full report on disk)")
    parser.add_argument("--no-remote", action="store_true", help="no GitHub call (gh login lookup)")
    parser.set_defaults(func=cmd_security)

    parser = subparsers.add_parser("attribution", help="AI co-authorship in commits, files, PRs and releases")
    parser.add_argument("repo")
    parser.add_argument("--no-remote", action="store_true", help="skip pull requests and releases")
    parser.add_argument("--limit", type=int, default=100)
    parser.set_defaults(func=cmd_attribution)

    parser = subparsers.add_parser("allow", help="accept findings as false positives")
    parser.add_argument("repo")
    parser.add_argument("fingerprints", nargs="+")
    parser.add_argument("--remove", action="store_true", help="forget these fingerprints instead")
    parser.set_defaults(func=cmd_allow)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True
    add_commands(sub)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Failure as error:
        print_json({"ok": False, "error": str(error)})
        return error.code


if __name__ == "__main__":
    sys.exit(main())
