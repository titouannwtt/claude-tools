"""repo-showcase: inventory (what the repository is) and structure (is the layout clean).

Commands:
  inventory <repo> [--no-remote]   local facts, project type, run hints, docs, README stats, assets and, unless
                                   --no-remote, GitHub metadata (gh) with the owner's other repositories as style sources
  structure <repo>                 layout audit: findings with a suggestion and an optional command that is never run

Both print one JSON object. Nothing is deleted, moved or written: the commands in the findings are for the user to approve.
Public functions used by ready.py: collect(repo, remote=True), structure_audit(repo), find_readme(repo, files=None).
Exit codes: 0 ok; 3 not a git repository (other codes come from common.py). Python 3.9 compatible.
"""
import json
import os
import re
import shlex
import shutil
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_OK, Failure, gh_json, git, github_slug, print_json, read_text,  # noqa: E402
                    repo_root, run, tracked_files)

REFERENCE_FILE = "references/structure.md"
DEP_DIRS = {"node_modules", "vendor", "bower_components", ".venv", "venv", "__pycache__", "site-packages",
            "__pypackages__"}
ML_EXT = {".ipynb", ".onnx", ".pt", ".pth", ".safetensors", ".ckpt", ".h5", ".pb", ".tflite"}
DATA_EXT = {".md", ".mdx", ".rst", ".txt", ".json", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".xml", ".jsonl"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico", ".bmp"}
README_NAMES = ("readme.md", "readme.markdown", "readme.mdx", "readme.rst", "readme.txt", "readme")

LANG_BY_EXT = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".kts": "Kotlin", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".swift": "Swift", ".scala": "Scala", ".dart": "Dart",
    ".php": "PHP", ".rb": "Ruby", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".sql": "SQL",
    ".lua": "Lua", ".hs": "Haskell", ".r": "R", ".pl": "Perl", ".ex": "Elixir", ".exs": "Elixir",
    ".gd": "GDScript", ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS", ".less": "Less",
    ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro", ".ipynb": "Jupyter Notebook",
}
# Comment counting also covers config languages that LANG_BY_EXT leaves out of the language statistics.
EXTRA_COMMENT_LANG = {".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".xml": "XML"}
SYNTAX_BY_EXT = {}
for _exts, _syntax in (
        ((".py", ".pyi"), "python"),
        ((".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".r", ".pl", ".ex", ".exs", ".gd"), "hash"),
        ((".rb",), "ruby"),
        ((".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".c", ".h", ".cpp", ".cc", ".cxx",
          ".hpp", ".cs", ".go", ".rs", ".swift", ".scala", ".dart"), "c"),
        ((".php",), "php"), ((".css", ".less"), "css"), ((".scss",), "scss"),
        ((".sql", ".hs"), "dash"), ((".lua",), "lua"),
        ((".html", ".htm", ".xml"), "html"), ((".vue", ".svelte", ".astro"), "sfc")):
    for _ext in _exts:
        SYNTAX_BY_EXT[_ext] = _syntax
# syntax -> (line comment prefixes, block comment (start, end) pairs); blocks are tested before line prefixes
SYNTAXES = {
    "python": (("#",), (('"""', '"""'), ("'''", "'''"))), "hash": (("#",), ()),
    "ruby": (("#",), (("=begin", "=end"),)), "c": (("//",), (("/*", "*/"),)),
    "php": (("//", "#"), (("/*", "*/"),)), "css": ((), (("/*", "*/"),)), "scss": (("//",), (("/*", "*/"),)),
    "dash": (("--",), ()), "lua": (("--",), (("--[[", "]]"),)), "html": ((), (("<!--", "-->"),)),
    "sfc": (("//",), (("<!--", "-->"), ("/*", "*/"))),
}
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
             "Gemfile.lock", "composer.lock", "Pipfile.lock", "bun.lockb"}
NO_COMMENT_FINDING = {"YAML", "TOML", "HTML", "XML"}  # markup and config: low ratios are normal
MIN_COMMENT_LINES = 50

PRIORITY = ("profile", "game", "ml", "mobile-app", "website", "web-app", "backend", "cli", "library", "docs",
            "catalog", "config", "other")
CODE_TYPES = {"web-app", "mobile-app", "cli", "library", "backend", "ml", "game"}
WEB_DEPS = {"next": 3000, "vite": 5173, "react-scripts": 3000, "nuxt": 3000, "@sveltejs/kit": 5173, "vue": 5173,
            "@angular/core": 4200, "@remix-run/react": 3000, "@remix-run/node": 3000, "remix": 3000}
WEBSITE_DEPS = {"astro": 4321, "@11ty/eleventy": 8080, "@docusaurus/core": 3000, "gatsby": 8000, "hexo": 4000}
DOCS_DEPS = ("vitepress", "vuepress", "@vuepress/core")
MOBILE_DEPS = ("expo", "react-native")
BACKEND_JS = ("express", "fastify", "koa", "@nestjs/core", "@hapi/hapi", "hono")
BACKEND_PY = ("fastapi", "flask", "django", "aiohttp", "tornado", "sanic", "starlette", "uvicorn")
UI_PY = {"streamlit": 8501, "gradio": 7860, "nicegui": 8080, "dash": 8050}
ML_PY = ("torch", "tensorflow", "jax", "scikit-learn", "sklearn", "transformers", "xgboost", "lightgbm",
         "pytorch-lightning", "keras")
DOTFILES = {".zshrc", ".bashrc", ".bash_profile", ".vimrc", ".gitconfig", ".tmux.conf", ".profile", ".zprofile",
            ".inputrc", ".zshenv", ".config"}
SECTION_KEYWORDS = OrderedDict((
    ("install", ("install", "installation", "setup", "set up", "getting started", "quick start", "quickstart",
                 "installer", "demarrage", "prise en main", "prerequis", "requirements")),
    ("usage", ("usage", "utilisation", "utiliser", "how to use", "example", "examples", "exemple", "exemples")),
    ("screenshots", ("screenshot", "screenshots", "screen shot", "capture", "captures", "gallery", "galerie",
                     "preview", "apercu", "visuals")),
    ("demo", ("demo", "demos", "demonstration", "live demo", "try it", "live")),
    ("license", ("license", "licence", "licensing")),
    ("contributing", ("contributing", "contribute", "contribution", "contributions", "contribuer")),
))
BADGE_RE = re.compile(r"shields\.io|/badge[/.]|badgen\.net|badge\.fury\.io|badge\.svg", re.I)
IMG_MD_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")
IMG_MD_RE_FULL = re.compile(r"!\[[^\]]*\]\([^)]*\)")
IMG_HTML_RE = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
LINK_MD_RE = re.compile(r"(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)")
LINK_HTML_RE = re.compile(r"<a\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
HEADING_HTML_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.I)
ANIMATION_RE = re.compile(r"<animate|<set\b|@keyframes|animation\s*:|animation-name", re.I)


# --------------------------------------------------------------------------- generic helpers

def _json_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _norm(text):
    """Lowercase text without accents, for keyword matching in English and French."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _has_word(text, name):
    return re.search(r"(?<![\w@/.-])%s(?![\w-])" % re.escape(name), text) is not None


def _in_dep_dir(path):
    return bool(set(path.split("/")[:-1]) & DEP_DIRS)


def tracked_present(repo):
    """Tracked files that still exist in the working tree."""
    repo = Path(repo)
    return [name for name in tracked_files(repo) if os.path.lexists(str(repo / name))]


def find_readme(repo, files=None):
    """Relative path of the README (root first, then .github/ and docs/), preferring Markdown, or None."""
    files = files if files is not None else tracked_present(repo)
    best = None
    for name in files:
        path = PurePosixPath(name)
        if path.name.lower() not in README_NAMES:
            continue
        depth = len(path.parts) - 1
        if depth > 1 or (depth == 1 and path.parts[0] not in (".github", "docs")):
            continue
        rank = (depth, README_NAMES.index(path.name.lower()))
        if best is None or rank < best[0]:
            best = (rank, name)
    return best[1] if best else None


def _file_sizes(repo, files):
    sizes = {}
    for name in files:
        try:
            sizes[name] = (Path(repo) / name).lstat().st_size
        except OSError:
            continue
    return sizes


def _count_lines(repo, name, limit=500000):
    text = read_text(Path(repo) / name, limit)
    return None if text is None else len(text.splitlines())


# --------------------------------------------------------------------------- local facts

def _default_branch(repo):
    ref = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False).strip()
    if "/" in ref:
        return ref.split("/", 1)[1]
    return git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).strip() or None


def language_stats(files, sizes):
    """Top 8 languages by bytes plus the most common other extensions (docs and data)."""
    langs = {}
    others = Counter()
    for name in files:
        ext = PurePosixPath(name).suffix.lower()
        lang = LANG_BY_EXT.get(ext)
        if lang and not _in_dep_dir(name) and ".min." not in name:
            entry = langs.setdefault(lang, {"language": lang, "files": 0, "bytes": 0})
            entry["files"] += 1
            entry["bytes"] += sizes.get(name, 0)
        elif ext:
            others[ext] += 1
    total = sum(item["bytes"] for item in langs.values()) or 1
    ranked = sorted(langs.values(), key=lambda item: (-item["bytes"], item["language"]))[:8]
    for item in ranked:
        item["percent"] = round(100.0 * item["bytes"] / total, 1)
    return ranked, [{"extension": ext, "files": n} for ext, n in others.most_common(6)]


def local_info(repo, files, sizes, slug):
    log = git(repo, "log", "--format=%aI%x09%ae", check=False).splitlines()
    dates = [line.split("\t")[0] for line in log if line]
    emails = {line.split("\t")[1].lower() for line in log if "\t" in line}
    languages, other_ext = language_stats(files, sizes)
    count = git(repo, "rev-list", "--count", "HEAD", check=False).strip()
    return {
        "name": slug.split("/")[1] if slug else Path(repo).name,
        "default_branch": _default_branch(repo),
        "head": git(repo, "rev-parse", "--short", "HEAD", check=False).strip() or None,
        "commit_count": int(count) if count.isdigit() else 0,
        "first_commit": dates[-1] if dates else None,
        "last_commit": dates[0] if dates else None,
        "author_count": len(emails),
        "tracked_files": len(files),
        "total_bytes": sum(sizes.values()),
        "languages": languages,
        "other_extensions": other_ext,
    }


# --------------------------------------------------------------------------- project type

def _node_packages(repo, files):
    """[(folder, package.json data)] for package.json files at most two levels deep, outside dependency folders."""
    found = []
    for name in files:
        parts = name.split("/")
        if parts[-1] == "package.json" and len(parts) <= 3 and not _in_dep_dir(name):
            data = _json_file(Path(repo) / name)
            if data is not None:
                found.append(("/".join(parts[:-1]), data))
    return found


def _node_deps(data):
    deps = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = data.get(key)
        if isinstance(value, dict):
            deps.update(value)
    return deps


def _manifest_text(repo, files):
    """Lowercase text of the dependency manifests of the repository (Python, Ruby, Go, Rust, Java, PHP)."""
    wanted = ("pyproject.toml", "requirements.txt", "pipfile", "setup.py", "setup.cfg", "environment.yml", "gemfile",
              "go.mod", "cargo.toml", "pom.xml", "build.gradle", "composer.json")
    chunks = []
    for name in files:
        base = PurePosixPath(name).name.lower()
        if len(name.split("/")) <= 3 and not _in_dep_dir(name) and (
                base in wanted or (base.startswith("requirements") and base.endswith(".txt"))):
            text = read_text(Path(repo) / name, 300000)
            if text:
                chunks.append(text.lower())
    return "\n".join(chunks)


def _go_main(repo, files):
    for name in files:
        if name.endswith(".go") and not name.endswith("_test.go") and (name.count("/") == 0 or name.startswith("cmd/")):
            text = read_text(Path(repo) / name, 100000)
            if text and re.search(r"^package main\b", text, re.M):
                return name
    return None


def detect_project_type(repo, files, slug=None):
    """{"primary", "secondary", "evidence", "signals"}: what kind of project this is, with the proof."""
    repo = Path(repo)
    fileset = set(files)
    root_names = {name.split("/")[0] for name in files}
    base_names = {PurePosixPath(name).name for name in files}
    signals = {}

    def add(kind, why):
        signals.setdefault(kind, []).append(why)

    packages = _node_packages(repo, files)
    node_deps = set()
    for folder, data in packages:
        deps = _node_deps(data)
        node_deps |= deps
        where = " in %s/package.json" % folder if folder else " in package.json"
        for dep in sorted(deps & set(WEB_DEPS)):
            add("web-app", "dependency %s%s" % (dep, where))
        for dep in sorted(deps & set(WEBSITE_DEPS)):
            add("website", "dependency %s%s" % (dep, where))
        for dep in sorted(deps & set(DOCS_DEPS)):
            add("docs", "dependency %s%s" % (dep, where))
        for dep in sorted(deps & set(MOBILE_DEPS)):
            add("mobile-app", "dependency %s%s" % (dep, where))
        for dep in sorted(deps & set(BACKEND_JS)):
            add("backend", "dependency %s%s" % (dep, where))
        if "bin" in data:
            add("cli", 'package.json "bin"' + (" in %s" % folder if folder else ""))
        if not folder and any(key in data for key in ("main", "module", "exports", "types")):
            add("library", 'package.json "main"/"exports"')
    manifest = _manifest_text(repo, files)
    for dep in BACKEND_PY:
        if _has_word(manifest, dep):
            add("backend", "Python dependency %s" % dep)
    for dep in UI_PY:
        if _has_word(manifest, dep):
            add("web-app", "Python UI framework %s" % dep)
    for dep in ML_PY:
        if _has_word(manifest, dep) or dep in node_deps:
            add("ml", "dependency %s" % dep)
    for dep, label in (("rails", "Gemfile rails"), ("gin-gonic/gin", "go.mod gin"), ("labstack/echo", "go.mod echo"),
                       ("actix-web", "Cargo actix-web"), ("axum", "Cargo axum"), ("spring-boot", "pom spring-boot"),
                       ("laravel/framework", "composer laravel")):
        if _has_word(manifest, dep):
            add("backend", label)

    ml_files = [name for name in files if PurePosixPath(name).suffix.lower() in ML_EXT]
    substantive = [name for name in files if PurePosixPath(name).suffix.lower() not in (".md", ".txt", ".rst")
                   and not PurePosixPath(name).name.startswith(".")
                   and not PurePosixPath(name).name.lower().startswith(("license", "requirements"))]
    if ml_files and len(ml_files) * 2 > len(substantive):
        add("ml", "%d of %d files are notebooks or model files" % (len(ml_files), len(substantive)))

    if "project.godot" in base_names:
        add("game", "project.godot (Godot)")
    if {"Assets", "ProjectSettings"} <= root_names:
        add("game", "Assets/ and ProjectSettings/ (Unity)")
    if any(name.endswith(".uproject") for name in files):
        add("game", ".uproject (Unreal)")
    if "main.lua" in fileset and "conf.lua" in fileset:
        add("game", "main.lua and conf.lua (LOVE)")

    app_json = _json_file(repo / "app.json") if "app.json" in fileset else None
    if app_json and "expo" in app_json:
        add("mobile-app", 'app.json with "expo"')
    if {"android", "ios"} <= root_names:
        add("mobile-app", "android/ and ios/ folders")
    if "pubspec.yaml" in fileset:
        add("mobile-app", "pubspec.yaml (Flutter)")
    if any(name.endswith("AndroidManifest.xml") for name in files):
        add("mobile-app", "AndroidManifest.xml")

    if "astro" in node_deps or any(name.startswith("astro.config.") for name in files):
        add("website", "Astro")
    for name in files:
        base = PurePosixPath(name).name
        if len(name.split("/")) > 2:
            continue
        if base in ("hugo.toml", "hugo.yaml", "hugo.json") or (
                base in ("config.toml", "config.yaml") and any(f.startswith("content/") for f in files)):
            add("website", "Hugo config %s" % name)
        elif base == "_config.yml":
            add("website", "Jekyll _config.yml")
        elif base.startswith((".eleventy.", "eleventy.config.")):
            add("website", "Eleventy config %s" % name)
        elif base.startswith("docusaurus.config."):
            add("website", "Docusaurus config %s" % name)
        elif base == "mkdocs.yml":
            add("docs", "mkdocs.yml")
        elif base == "book.toml":
            add("docs", "book.toml (mdBook)")
    if "index.html" in fileset and not packages:
        add("website", "index.html at the root, no package.json")

    pyproject = read_text(repo / "pyproject.toml", 200000) if "pyproject.toml" in fileset else ""
    setup_py = read_text(repo / "setup.py", 200000) if "setup.py" in fileset else ""
    setup_cfg = read_text(repo / "setup.cfg", 200000) if "setup.cfg" in fileset else ""
    if re.search(r"^\[(project|tool\.poetry)\.(gui-)?scripts\]", pyproject or "", re.M):
        add("cli", "pyproject.toml scripts")
    elif "console_scripts" in (setup_py or "") + (setup_cfg or ""):
        add("cli", "setup console_scripts")
    elif (pyproject and re.search(r"^\[(project|tool\.poetry)\]", pyproject, re.M)) or setup_py:
        add("library", "Python package metadata")
    if any(PurePosixPath(name).name == "__main__.py" and name.count("/") <= 2 for name in files):
        add("cli", "__main__.py entry point")
    cargo = read_text(repo / "Cargo.toml", 100000) if "Cargo.toml" in fileset else ""
    if cargo:
        if "[[bin]]" in cargo or "src/main.rs" in fileset:
            add("cli", "Cargo binary target")
        if "src/lib.rs" in fileset:
            add("library", "Cargo src/lib.rs")
        if re.search(r"^bevy\s*=", cargo, re.M):
            add("game", "Cargo dependency bevy")
    if "go.mod" in fileset:
        main_file = _go_main(repo, files)
        if main_file:
            add("cli", "Go main package in %s" % main_file)
        else:
            add("library", "go.mod without a main package")
    if any(name.endswith(".gemspec") for name in files):
        add("library", "gemspec")

    docs_like = sum(1 for n in files if PurePosixPath(n).suffix.lower() in DATA_EXT)
    code = sum(1 for n in files if PurePosixPath(n).suffix.lower() in LANG_BY_EXT
               and PurePosixPath(n).suffix.lower() not in (".html", ".htm", ".css", ".ipynb"))
    if len(files) >= 5 and docs_like >= 0.7 * len(files) and code <= max(1, 0.1 * len(files)):
        add("catalog", "%d of %d files are Markdown or data, %d code files" % (docs_like, len(files), code))
    name = slug.split("/")[1] if slug else repo.name
    if name.lower().startswith("awesome"):
        add("catalog", "name starts with awesome")

    dot_roots = {n for n in root_names if n.startswith(".")}
    if name.lower() in ("dotfiles", "dots") or len(DOTFILES & root_names) >= 3 or (
            len(root_names) >= 4 and len(dot_roots - {".github", ".gitignore"}) >= 0.6 * len(root_names)):
        add("config", "dotfiles at the root")
    if slug and name.lower() == slug.split("/")[0].lower():
        add("profile", "repository name equals the owner (profile README)")

    present = [kind for kind in PRIORITY if kind in signals]
    primary = present[0] if present else "other"
    secondary = present[1:]
    evidence = []
    for kind in ([primary] if present else []) + secondary:
        evidence.extend("%s: %s" % (kind, why) for why in signals[kind][:4])
    return {"primary": primary, "secondary": secondary, "evidence": evidence[:14]}


# --------------------------------------------------------------------------- run hints

def run_hints(repo, files):
    """How the project starts locally: commands, guessed URLs, Docker files."""
    repo = Path(repo)
    fileset = set(files)
    commands, urls, docker = [], [], []
    manager = "npm"
    for lock, tool in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun")):
        if lock in fileset:
            manager = tool
            break
    for folder, data in _node_packages(repo, files):
        scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
        deps = _node_deps(data)
        script = next((key for key in ("dev", "start", "preview", "serve") if key in scripts), None)
        if not script:
            continue
        if manager == "npm":
            cmd = "npm start" if script == "start" else "npm run %s" % script
        else:
            cmd = "%s %s" % (manager, script) if manager != "bun" else "bun run %s" % script
        commands.append(("cd %s && " % folder if folder else "") + cmd)
        port = next((p for dep, p in list(WEB_DEPS.items()) + list(WEBSITE_DEPS.items()) if dep in deps), None)
        given = re.search(r"(?:--port|-p)[ =](\d{2,5})|PORT=(\d{2,5})", scripts[script])
        if given:
            port = int(given.group(1) or given.group(2))
        if port:
            urls.append("http://localhost:%d" % port)
    manifest = _manifest_text(repo, files)
    names = {PurePosixPath(n).name: n for n in files}
    if _has_word(manifest, "streamlit"):
        app = next((names[n] for n in ("streamlit_app.py", "app.py", "main.py") if n in names), "app.py")
        commands.append("streamlit run %s" % app)
        urls.append("http://localhost:8501")
    if _has_word(manifest, "gradio"):
        urls.append("http://localhost:7860")
    if "manage.py" in names:
        commands.append("python %s runserver" % names["manage.py"])
        urls.append("http://localhost:8000")
    elif _has_word(manifest, "flask"):
        commands.append("flask run")
        urls.append("http://localhost:5000")
    elif _has_word(manifest, "fastapi") or _has_word(manifest, "uvicorn"):
        module = "main" if "main.py" in names else "app.main" if "app/main.py" in fileset else "main"
        commands.append("uvicorn %s:app --reload" % module)
        urls.append("http://localhost:8000")
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if name in fileset:
            docker.append(name)
    if any(n.startswith("compose.") or n.startswith("docker-compose.") for n in docker):
        commands.append("docker compose up")
    return {"commands": commands, "urls": list(OrderedDict.fromkeys(urls)), "docker": docker}


# --------------------------------------------------------------------------- docs and README

def docs_info(repo, files):
    mds = [n for n in files if PurePosixPath(n).suffix.lower() in (".md", ".mdx") and not _in_dep_dir(n)]
    listed = []
    for name in mds[:60]:
        listed.append({"path": name, "lines": _count_lines(repo, name)})
    return {"markdown_count": len(mds), "files": listed, "truncated": len(mds) > 60,
            "has_docs_folder": any(n.startswith("docs/") for n in files)}


def _strip_tags(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _section_hits(headings):
    hits = {key: False for key in SECTION_KEYWORDS}
    for heading in headings:
        text = _norm(heading)
        words = set(re.findall(r"[a-z0-9]+", text))
        for key, keywords in SECTION_KEYWORDS.items():
            for word in keywords:
                if (" " in word and word in text) or word in words:
                    hits[key] = True
    return hits


def readme_stats(repo, name):
    """Structure of the README: size, headings, images, badges, links, sections, banner, animated SVG."""
    repo = Path(repo)
    text = read_text(repo / name, 2000000)
    if text is None:
        return None
    lines = text.splitlines()
    headings, images, links = [], [], []
    fence = None
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (fence or marker)
            continue
        if fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append({"level": len(match.group(1)), "text": _strip_tags(match.group(2)), "line": number})
        for html_heading in HEADING_HTML_RE.finditer(line):
            headings.append({"level": int(html_heading.group(1)), "text": _strip_tags(html_heading.group(2)),
                             "line": number})
        for kind, regex in (("markdown", IMG_MD_RE), ("html", IMG_HTML_RE)):
            for found in regex.finditer(line):
                images.append({"src": found.group(1), "line": number, "kind": kind})
        without_images = IMG_MD_RE_FULL.sub("", line)
        for regex, source in ((LINK_MD_RE, without_images), (LINK_HTML_RE, line)):
            links.extend(found.group(1) for found in regex.finditer(source))
    badges = [img for img in images if BADGE_RE.search(img["src"])]
    visuals = [img for img in images if not BADGE_RE.search(img["src"])]
    first = min((img["line"] for img in visuals), default=None)
    animated, gifs = [], 0
    base = (repo / name).parent
    for img in visuals:
        src = img["src"].split("#")[0].split("?")[0]
        if src.lower().endswith(".gif"):
            gifs += 1
        if not src.lower().endswith(".svg") or re.match(r"[a-z]+://", src):
            continue
        target = repo / src.lstrip("/") if src.startswith("/") else base / src
        svg = read_text(target, 500000)
        if svg and ANIMATION_RE.search(svg):
            animated.append(src)
    return {
        "path": name,
        "lines": len(lines),
        "words": len(text.split()),
        "headings": headings[:20],
        "heading_count": len(headings),
        "images": {"markdown": sum(1 for i in images if i["kind"] == "markdown"),
                   "html": sum(1 for i in images if i["kind"] == "html"), "total": len(images),
                   "badges": len(badges), "visuals": len(visuals), "gifs": gifs},
        "links": {"total": len(links), "external": sum(1 for link in links if re.match(r"https?://", link))},
        "sections": _section_hits([h["text"] for h in headings]),
        "first_image_line": first,
        "has_banner": first is not None and first <= 5,
        "animated_svg": len(set(animated)),
    }


def assets_info(files, sizes):
    by_ext, by_folder, largest = Counter(), Counter(), []
    for name in files:
        ext = PurePosixPath(name).suffix.lower()
        if ext in IMAGE_EXT and not _in_dep_dir(name):
            by_ext[ext] += 1
            by_folder[str(PurePosixPath(name).parent)] += 1
            largest.append((sizes.get(name, 0), name))
    largest.sort(reverse=True)
    return {"total": sum(by_ext.values()), "by_extension": dict(by_ext.most_common()),
            "by_folder": dict(by_folder.most_common(15)),
            "largest": [{"path": n, "bytes": s} for s, n in largest[:5]]}


# --------------------------------------------------------------------------- GitHub (every call tolerant of failure)

def _gh(args):
    """gh_json that never raises: None when gh is missing, offline, 404 or unparsable."""
    try:
        return gh_json(args, check=False)
    except (Failure, ValueError):
        return None


def _topic_names(raw):
    names = []
    for item in raw or []:
        if isinstance(item, dict):
            name = item.get("name") or (item.get("topic") or {}).get("name")
            if name:
                names.append(name)
        elif isinstance(item, str):
            names.append(item)
    return names


def github_info(slug):
    """Repository metadata, community profile, latest release, owner profile and the owner's style sources."""
    owner, name = slug.split("/", 1)
    fields = ("name,owner,visibility,description,homepageUrl,repositoryTopics,licenseInfo,stargazerCount,forkCount,"
              "isArchived,isFork,defaultBranchRef,url,pushedAt")
    view = _gh(["repo", "view", slug, "--json", fields])
    if view is None:
        return {"available": False, "reason": "gh could not read %s (not installed, offline or no access)" % slug}
    lic = view.get("licenseInfo") or {}
    info = {
        "available": True, "slug": slug, "visibility": (view.get("visibility") or "").upper() or None,
        "description": view.get("description") or None, "homepage": view.get("homepageUrl") or None,
        "topics": _topic_names(view.get("repositoryTopics")), "license": lic.get("spdxId") or lic.get("name"),
        "stars": view.get("stargazerCount"), "forks": view.get("forkCount"), "archived": view.get("isArchived"),
        "is_fork": view.get("isFork"), "default_branch": (view.get("defaultBranchRef") or {}).get("name"),
        "url": view.get("url"), "pushed_at": view.get("pushedAt"),
    }
    profile = _gh(["api", "repos/%s/community/profile" % slug])
    if isinstance(profile, dict):
        files = profile.get("files") or {}
        wanted = [key for key in files if key != "code_of_conduct_file"]
        info["community"] = {
            "health_percentage": profile.get("health_percentage"),
            "present": sorted(key for key in wanted if files.get(key)),
            "missing": sorted([key for key in wanted if not files.get(key)]
                              + [key for key in ("description", "documentation") if not profile.get(key)]),
        }
    release = _gh(["api", "repos/%s/releases/latest" % slug])
    info["latest_release"] = ({"tag": release.get("tag_name"), "date": release.get("published_at")}
                              if isinstance(release, dict) else None)
    user = _gh(["api", "users/%s" % owner])
    info["owner_profile"] = ({key: user.get(key) for key in ("login", "name", "blog", "bio", "twitter_username",
                                                             "html_url")} if isinstance(user, dict) else None)
    listing = _gh(["repo", "list", owner, "--visibility", "public", "--source", "--no-archived", "--limit", "100",
                   "--json", "name,stargazerCount,description"])
    sources = []
    ranked = sorted((r for r in (listing or []) if r.get("name") != name),
                    key=lambda r: -(r.get("stargazerCount") or 0))[:8]
    for other in ranked:
        contents = _gh(["api", "repos/%s/%s/contents/assets" % (owner, other["name"])])
        assets = sorted(item.get("name", "") for item in (contents if isinstance(contents, list) else [])
                        if item.get("name", "").lower().endswith((".svg", ".png")))
        sources.append({"repo": "%s/%s" % (owner, other["name"]), "stars": other.get("stargazerCount"),
                        "description": other.get("description"), "assets": assets[:12]})
    info["style_sources"] = sources
    info["profile_repo"] = {"slug": "%s/%s" % (owner, owner), "exists": _gh(["api", "repos/%s/%s" % (owner, owner)])
                            is not None}
    return info


# --------------------------------------------------------------------------- hints

def build_hints(local, ptype, hints, docs, readme, assets, files, github):
    out = []
    kinds = [ptype["primary"]] + ptype["secondary"]
    if {"web-app", "website", "mobile-app"} & set(kinds) or hints["urls"]:
        text = "web UI detected: screenshots recommended"
        if hints["commands"]:
            port = hints["urls"][0].rsplit(":", 1)[-1] if hints["urls"] else "?"
            text += ", run hint: %s on %s" % (hints["commands"][0], port)
        out.append(text)
    if "cli" in kinds:
        out.append("CLI detected: a terminal recording or a pasted output shows it better than prose")
    if "library" in kinds:
        out.append("library detected: a short usage snippet is the best visual")
    if ptype["primary"] == "profile":
        out.append("profile repository: the README is the owner's front page")
    if not any(PurePosixPath(n).name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "UNLICENSE"))
               for n in files):
        out.append("no LICENSE")
    if readme is None:
        out.append("no README")
    else:
        first = readme["first_image_line"]
        if first is None:
            out.append("README has no image")
        elif first > 15:
            out.append("README has no visual in the first 15 lines (first at line %d)" % first)
        if not readme["has_banner"]:
            out.append("no banner in the first 5 lines of the README")
        if readme["lines"] > 300:
            out.append("README is long (%d lines): move details to docs/" % readme["lines"])
        if readme["images"]["badges"] > 6:
            out.append("%d badges: keep only the useful ones" % readme["images"]["badges"])
        for key in ("install", "usage"):
            if not readme["sections"].get(key):
                out.append("README has no %s section" % key)
    if assets["total"] == 0:
        out.append("no image in the repository")
    if github and github.get("available"):
        if github["visibility"] in ("PRIVATE", "INTERNAL"):
            out.append("repository is %s: making it public is the user's last step" % github["visibility"].lower())
        if not github["description"]:
            out.append("GitHub description is empty")
        if len(github["topics"]) < 3:
            out.append("fewer than 3 GitHub topics")
        if not github["homepage"] and ptype["primary"] in ("web-app", "website"):
            out.append("no homepage URL set on GitHub")
        styled = [s["repo"] for s in github.get("style_sources", []) if s["assets"]]
        if styled:
            out.append("style sources with SVG or PNG assets: %s" % ", ".join(styled[:3]))
        if github.get("profile_repo", {}).get("exists"):
            out.append("owner has a profile repository: its style can be reused")
    return out


def collect(repo, remote=True):
    """The whole inventory as a dict (used by the inventory command and by ready.py)."""
    repo = Path(repo)
    files = tracked_present(repo)
    sizes = _file_sizes(repo, files)
    slug = github_slug(repo)
    local = local_info(repo, files, sizes, slug)
    ptype = detect_project_type(repo, files, slug)
    hints = run_hints(repo, files)
    docs = docs_info(repo, files)
    readme_path = find_readme(repo, files)
    readme = readme_stats(repo, readme_path) if readme_path else None
    assets = assets_info(files, sizes)
    if not remote:
        github = {"available": False, "reason": "--no-remote"}
    elif not slug:
        github = {"available": False, "reason": "origin is not a GitHub remote"}
    elif shutil.which("gh") is None:
        github = {"available": False, "reason": "gh is not installed"}
    else:
        github = github_info(slug)
    return {"local": local, "project_type": ptype, "run_hints": hints, "docs": docs, "readme": readme,
            "assets": assets, "github": github,
            "hints": build_hints(local, ptype, hints, docs, readme, assets, files, github)}


# --------------------------------------------------------------------------- structure: rules

JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".coverage", "coverage.xml", "lcov.info"}
JUNK_GLOBS = ("*.pyc", "*.pyo", "*.log", "*.tmp", "*.bak", "*.orig", "*.swp", "*.swo", "*~")
JUNK_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", ".nyc_output", ".hypothesis"}
BUILD_DIRS = {"dist", "build", "out", ".next", ".nuxt", ".output", ".svelte-kit", ".turbo"}
SHARED_VSCODE = {"settings.json", "extensions.json", "launch.json", "tasks.json"}
STANDARD_MD = {"readme", "license", "licence", "changelog", "changes", "history", "contributing", "security",
               "code_of_conduct", "support", "authors", "citation", "governance", "maintainers", "notice", "claude",
               "agents", "codeowners", "release_notes", "contributors", "funding"}
CLUTTER_KEEP = re.compile(
    r"^(readme|license|licence|copying|changelog|contributing|security|code_of_conduct|support|authors|citation|"
    r"notice|codeowners|makefile|justfile|dockerfile|docker-compose|compose|package(-lock)?\.json|yarn\.lock|"
    r"pnpm-lock\.yaml|bun\.lockb|tsconfig|jsconfig|pyproject\.toml|setup\.(py|cfg)|requirements|pipfile|poetry\.lock|"
    r"uv\.lock|cargo\.|go\.(mod|sum)|gemfile|composer\.|pom\.xml|build\.gradle|settings\.gradle|gradlew|index\.html|"
    r"manage\.py|app\.json|pubspec\.|procfile|vercel\.json|netlify\.toml|mkdocs\.yml|_config\.yml|claude\.md|"
    r"agents\.md|conftest\.py|tox\.ini|noxfile\.py|pytest\.ini|mypy\.ini|project\.godot|.*\.config\.|.*\.sln$)", re.I)
UNCLEAR_REGEXES = (
    (re.compile(r"^copy of\b|\bcopy( \d+)?$|\(\d+\)$"), "copy"),
    (re.compile(r"^(untitled|sans titre|nouveau|new (folder|file|document))"), "default name"),
    (re.compile(r"^(screenshot|screen shot|capture d.?[ée]cran|img_\d+|dsc_?\d+)"), "default capture name"),
    (re.compile(r"[-_ ]v\d+(\.\d+)*$"), "version suffix"),
)
UNCLEAR_ANY = {"copy", "backup", "bak", "final", "tmp", "temp", "draft", "untitled"}
TEST_NAME_RE = re.compile(r"(^test_|_test\.|\.test\.|\.spec\.|tests?\.(swift|kt|java)$|Tests?\.(swift|kt|java|cs)$)")


def _finding(fid, category, severity, paths, count, why, suggestion, command=None, detail=None):
    item = {"id": fid, "category": category, "severity": severity, "paths": list(paths)[:10], "count": count,
            "why": why, "suggestion": suggestion}
    if command:
        item["command"] = command
    if detail:
        item["detail"] = detail
    return item


def _junk(parts, name):
    """Pathspec of a junk rule matching this path, plus the tracked target to remove."""
    for index, comp in enumerate(parts[:-1]):
        if comp in JUNK_DIRS:
            return ":(glob)**/" + comp, "/".join(parts[:index + 1])
    if parts[0] == "coverage" and (parts[-1] in ("lcov.info", "clover.xml", "coverage-final.json")
                                   or "lcov-report" in parts):
        return ":(glob)coverage", "coverage"
    base = parts[-1]
    if base in JUNK_NAMES:
        return ":(glob)**/" + base, name
    for pattern in JUNK_GLOBS:
        if PurePosixPath(base).match(pattern):
            return ":(glob)**/" + pattern, name
    return None


def _sibling(parts, index, name):
    return "/".join(parts[:index] + [name])


def _build_dir(parts, fileset):
    for index, comp in enumerate(parts[:-1]):
        if comp in BUILD_DIRS or (comp == "target" and any(
                _sibling(parts, index, n) in fileset for n in ("Cargo.toml", "pom.xml", "build.gradle"))):
            return "/".join(parts[:index + 1])
    return None


def _dependency_dir(parts, fileset):
    for index, comp in enumerate(parts[:-1]):
        folder = "/".join(parts[:index + 1])
        if comp in ("node_modules", "bower_components", ".venv", "__pypackages__", "site-packages"):
            return folder
        if comp == "venv" and folder + "/pyvenv.cfg" in fileset:
            return folder
        if comp == "vendor" and _sibling(parts, index, "package.json") in fileset and not any(
                _sibling(parts, index, n) in fileset for n in ("go.mod", "composer.json", "Gemfile")):
            return folder
    return None


def _editor(parts):
    """Tracked editor file or folder to untrack, or None."""
    for index, comp in enumerate(parts[:-1]):
        if comp in (".idea", ".vs"):
            return "/".join(parts[:index + 1])
        if comp == ".vscode" and parts[-1] not in SHARED_VSCODE and not parts[-1].endswith(".code-snippets"):
            return "/".join(parts)
    return "/".join(parts) if parts[-1].endswith(".iml") else None


def _unclear(name, is_dir):
    if name.startswith("."):
        return None
    stem = name if is_dir else PurePosixPath(name).stem
    lower = stem.lower()
    for regex, reason in UNCLEAR_REGEXES:
        if regex.search(lower):
            return reason
    tokens = [t for t in re.split(r"[\s._-]+", lower) if t]
    for index, token in enumerate(tokens):
        last = index == len(tokens) - 1
        if token in UNCLEAR_ANY or re.fullmatch(r"test\d+", token):
            return "placeholder word '%s'" % token
        if token == "old" and (index == 0 or last):
            return "placeholder word 'old'"
        if token == "new" and (last or len(tokens) == 1):
            return "placeholder word 'new'"
    if " " in name:
        return "space in the name"
    return None


def name_style(name):
    if name.startswith((".", "__")) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return None
    if "_" in name and "-" not in name and name == name.lower():
        return "snake_case"
    if "-" in name and "_" not in name and name == name.lower():
        return "kebab-case"
    if re.fullmatch(r"[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*", name):
        return "camelCase"
    return None


def count_comment_lines(text, syntax):
    """(code lines, comment lines) of a source text. Python docstrings count as comments."""
    prefixes, blocks = SYNTAXES[syntax]
    code = comment = 0
    closing = None
    for number, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line:
            continue
        if closing:
            comment += 1
            if closing in line:
                closing = None
            continue
        if number == 0 and line.startswith("#!"):
            code += 1
            continue
        probe = line
        if syntax == "python":
            probe = re.sub(r"^[rRuUbBfF]{1,2}(?=\"\"\"|''')", "", line)
        hit = next((pair for pair in blocks if probe.startswith(pair[0])), None)
        if hit:
            comment += 1
            if hit[1] not in probe[len(hit[0]):]:
                closing = hit[1]
        elif any(line.startswith(prefix) for prefix in prefixes):
            comment += 1
        else:
            code += 1
    return code, comment


def comment_stats(repo, files, skip):
    """({language: stats}, {language: [(path, code, comment)]}) over the tracked source files."""
    languages, per_file = {}, {}
    for name in files:
        base = PurePosixPath(name).name
        ext = PurePosixPath(name).suffix.lower()
        syntax = SYNTAX_BY_EXT.get(ext)
        if not syntax or name in skip or base in LOCKFILES or ".min." in base:
            continue
        text = read_text(Path(repo) / name, 1000000)
        if not text or any(len(line) > 500 for line in text.splitlines()):
            continue
        code, comment = count_comment_lines(text, syntax)
        lang = LANG_BY_EXT.get(ext) or EXTRA_COMMENT_LANG.get(ext)
        entry = languages.setdefault(lang, {"code": 0, "comment": 0, "files": 0})
        entry["code"] += code
        entry["comment"] += comment
        entry["files"] += 1
        per_file.setdefault(lang, []).append((name, code, comment))
    for entry in languages.values():
        total = entry["code"] + entry["comment"]
        entry["ratio"] = round(entry["comment"] / total, 3) if total else 0.0
        entry["verdict"] = "low" if entry["ratio"] < 0.05 else "high" if entry["ratio"] > 0.40 else "ok"
    return languages, per_file


def _cmd_mv(paths, target):
    quoted = " ".join(shlex.quote(p) for p in paths)
    return "mkdir -p %s && git mv %s %s/" % (target, quoted, target)


def structure_audit(repo):
    """Layout audit of the tracked files: findings, comment ratios, Markdown organisation, layout reference."""
    repo = Path(repo)
    files = tracked_present(repo)
    fileset = set(files)
    sizes = _file_sizes(repo, files)
    findings = []
    skip = set()

    # junk, build output, dependencies, editor files
    junk, builds, deps, editors = OrderedDict(), OrderedDict(), OrderedDict(), OrderedDict()
    junk_count = 0
    for name in files:
        parts = name.split("/")
        hit = _junk(parts, name)
        if hit:
            junk.setdefault(hit[1], hit[0])
            junk_count += 1
            skip.add(name)
            continue
        target = _dependency_dir(parts, fileset)
        if target:
            deps.setdefault(target, []).append(name)
            skip.add(name)
            continue
        target = _build_dir(parts, fileset)
        if target:
            builds.setdefault(target, []).append(name)
            skip.add(name)
            continue
        target = _editor(parts)
        if target:
            editors.setdefault(target, []).append(name)
    if junk:
        specs = list(OrderedDict.fromkeys(junk.values()))
        findings.append(_finding(
            "junk-tracked", "junk-tracked", "low", list(junk), junk_count,
            "System, cache, log or temporary files are tracked: they add noise and may leak local data.",
            "Untrack them and add the patterns to .gitignore (the files stay on disk).",
            "git rm -r --cached -- " + " ".join(shlex.quote(s) for s in specs[:12])))
    for fid, mapping, severity, why in (
            ("build-output-tracked", builds, "medium",
             "Build output is tracked (it may be intentional, for instance scripts kept in build/)."),
            ("dependency-dir-tracked", deps, "medium",
             "Installed dependencies are tracked: huge diffs and licence noise.")):
        if mapping:
            paths = list(mapping)
            findings.append(_finding(
                fid, fid, severity, paths, sum(len(v) for v in mapping.values()), why,
                "Untrack the folder and add it to .gitignore; it is rebuilt by the install or build step.",
                "git rm -r --cached -- " + " ".join(shlex.quote(p) for p in paths[:10])))
    if editors:
        findings.append(_finding(
            "editor-config-tracked", "editor-config-tracked", "info", list(editors),
            sum(len(v) for v in editors.values()),
            "Personal editor settings are tracked (shared settings such as .vscode/settings.json are fine).",
            "Untrack them unless the team needs them; add them to .gitignore.",
            "git rm -r --cached -- " + " ".join(shlex.quote(p) for p in list(editors)[:10])))

    # duplicates and large files
    by_blob = {}
    out = git(repo, "ls-files", "-s", "-z", check=False)
    for entry in out.split("\0"):
        match = re.match(r"(\d+) ([0-9a-f]+) \d\t(.+)$", entry)
        if match and match.group(1) in ("100644", "100755") and match.group(3) in sizes \
                and match.group(3) not in skip and sizes[match.group(3)] > 1024:
            by_blob.setdefault(match.group(2), []).append(match.group(3))
    groups = [sorted(paths) for paths in by_blob.values() if len(paths) > 1]
    if groups:
        groups.sort(key=lambda g: (-len(g), g[0]))
        extra = sum(len(g) - 1 for g in groups)
        findings.append(_finding(
            "duplicate-files", "duplicate-files", "low", [p for g in groups for p in g], extra,
            "%d identical files (same content, over 1 KB) exist in %d groups." % (extra, len(groups)),
            "Keep one copy and reference it, or generate the others at build time.",
            detail={"groups": groups[:5]}))
    large = sorted(((s, n) for n, s in sizes.items() if s > 5 * 1024 * 1024), reverse=True)
    if large:
        findings.append(_finding(
            "large-file", "large-file", "medium", [n for _, n in large], len(large),
            "Files over 5 MB slow every clone and stay in the history forever.",
            "Use Git LFS or attach them as release assets; removing them from the history needs the rewrite step.",
            detail={"megabytes": {n: round(s / 1048576.0, 1) for s, n in large[:10]}}))

    # naming
    unclear = OrderedDict()
    seen_dirs = set()
    for name in files:
        if name in skip:
            continue
        parts = name.split("/")
        for index, comp in enumerate(parts):
            is_dir = index < len(parts) - 1
            path = "/".join(parts[:index + 1])
            if is_dir:
                if path in seen_dirs:
                    continue
                seen_dirs.add(path)
            reason = _unclear(comp, is_dir)
            if reason:
                unclear[path + ("/" if is_dir else "")] = reason
    if unclear:
        findings.append(_finding(
            "unclear-name", "unclear-name", "low", list(unclear), len(unclear),
            "Names that look like leftovers, copies or defaults make the repository look unfinished.",
            "Rename with git mv (history is kept) or delete if it is a real leftover; ask the user first.",
            "git mv -- %s <new-name>" % shlex.quote(list(unclear)[0].rstrip("/")),
            detail={"reasons": dict(list(unclear.items())[:10])}))

    # root layout
    root_entries = sorted({n.split("/")[0] for n in files if not n.startswith(".")})
    root_files = [e for e in root_entries if e in fileset]
    if len(root_entries) > 12:
        moves = OrderedDict((("docs", []), ("scripts", []), ("examples", []), ("assets", []), ("data", [])))
        for entry in root_files:
            lower, ext = entry.lower(), PurePosixPath(entry).suffix.lower()
            if CLUTTER_KEEP.match(entry) or CLUTTER_KEEP.match(lower):
                continue
            if lower.startswith(("example", "sample", "demo")):
                moves["examples"].append(entry)
            elif ext in (".md", ".rst", ".txt", ".pdf", ".docx", ".odt"):
                moves["docs"].append(entry)
            elif ext in (".sh", ".bash", ".ps1", ".bat", ".cmd"):
                moves["scripts"].append(entry)
            elif ext in IMAGE_EXT:
                moves["assets"].append(entry)
            elif ext in (".csv", ".tsv", ".xlsx", ".parquet", ".sqlite", ".db"):
                moves["data"].append(entry)
        moves = OrderedDict((k, v) for k, v in moves.items() if v)
        movable = [p for v in moves.values() for p in v]
        findings.append(_finding(
            "root-clutter", "root-clutter", "low", movable or root_entries, len(root_entries),
            "%d visible entries at the root (more than 12): the first screen of the repository is crowded." %
            len(root_entries),
            "Group loose files by purpose; see the reference layout for this project type.",
            " && ".join(_cmd_mv(v[:10], k) for k, v in moves.items()) or None,
            detail={"could_move": dict(moves)}))

    # Markdown
    mds = [n for n in files if PurePosixPath(n).suffix.lower() in (".md", ".mdx") and n not in skip]
    root_md = [n for n in mds if "/" not in n]
    nonstandard = [n for n in root_md if re.split(r"[.-]", PurePosixPath(n).stem.lower())[0] not in STANDARD_MD
                   and PurePosixPath(n).stem.lower() not in STANDARD_MD]
    if len(nonstandard) >= 3:
        findings.append(_finding(
            "md-scattered", "md-scattered", "low", nonstandard, len(nonstandard),
            "Several non-standard Markdown files sit at the root next to the README.",
            "Move long-form notes into docs/ and link them from the README.", _cmd_mv(nonstandard[:10], "docs")))
    empty = []
    for name in mds:
        if name.startswith(".github/"):
            continue
        text = read_text(repo / name, 500000)
        if text is not None and sum(1 for line in text.splitlines() if line.strip()) < 3:
            empty.append(name)
    if empty:
        findings.append(_finding(
            "md-empty", "md-empty", "low", empty, len(empty),
            "Markdown files with fewer than 3 non-empty lines are placeholders.",
            "Write them, merge them into the README, or remove them."))

    # standard files
    readme = find_readme(repo, files)
    if not readme:
        findings.append(_finding("missing-readme", "missing-readme", "high", [], 0, "No README.",
                                 "Write one: short, with a visual and the one command that gets a reader started."))
    if not any(re.match(r"(license|licence|copying|unlicense)", PurePosixPath(n).name, re.I)
               and "/" not in n for n in files):
        findings.append(_finding(
            "missing-license", "missing-license", "medium", [], 0,
            "No LICENSE: without one, nobody may legally reuse the code.",
            "Ask the user which licence fits (choosealicense.com), then add the file; never pick one for them."))
    gitignore = ".gitignore" in fileset
    stacks = _stacks(files)
    if not gitignore:
        findings.append(_finding(
            "missing-gitignore", "missing-gitignore", "medium", [], 0,
            "No .gitignore: caches, dependencies and secrets can be committed by accident.",
            "Create one covering the detected stacks.", detail={"suggested_lines": _gitignore_lines(stacks)}))
    else:
        findings.extend(_gitignore_gaps(repo, stacks))
    community = [("CONTRIBUTING", "CONTRIBUTING.md"), ("SECURITY", "SECURITY.md"),
                 ("CODE_OF_CONDUCT", "CODE_OF_CONDUCT.md")]
    present = {PurePosixPath(n).stem.upper() for n in files
               if n.split("/")[0] in (PurePosixPath(n).name, ".github", "docs")}
    missing = [fname for key, fname in community if key not in present]
    if missing:
        findings.append(_finding(
            "missing-community", "missing-community", "info", missing, len(missing),
            "Community health files missing (GitHub shows them in the community profile).",
            "Add only what the audience needs: contributors want CONTRIBUTING, a security contact wants SECURITY."))

    # comments
    languages, per_file = comment_stats(repo, files, skip)
    for verdict, category in (("low", "comments-low"), ("high", "comments-high")):
        langs = [lang for lang, st in languages.items() if st["verdict"] == verdict and lang not in NO_COMMENT_FINDING
                 and st["code"] + st["comment"] >= MIN_COMMENT_LINES]
        if not langs:
            continue
        rows = [row for lang in langs for row in per_file[lang]]
        if verdict == "low":
            rows = sorted((r for r in rows if r[1] >= MIN_COMMENT_LINES and r[2] == 0), key=lambda r: -r[1])
            why = "Very few comments (under 5 % of lines): readers cannot tell why the code is the way it is."
            suggestion = "Add docstrings to the public API and comments that explain why, not what."
        else:
            rows = sorted((r for r in rows if r[1] + r[2] >= 30 and r[2] > 0.4 * (r[1] + r[2])), key=lambda r: -r[2])
            why = "Comments are over 40 % of lines: often narration or commented-out code."
            suggestion = "Delete commented-out code and comments that repeat the code; keep the ones explaining why."
        findings.append(_finding(category, category, "low" if verdict == "low" else "info",
                                 [r[0] for r in rows], len(rows), why, suggestion,
                                 detail={"languages": {lang: languages[lang]["ratio"] for lang in langs}}))

    # structure depth, naming consistency, tests
    live = [n for n in files if n not in skip]
    deep = sorted({"/".join(n.split("/")[:-1]) for n in live if n.count("/") > 8})
    if deep:
        findings.append(_finding("deep-nesting", "deep-nesting", "info", deep, len(deep),
                                 "Folders nested more than 8 levels deep are hard to navigate.",
                                 "Flatten the hierarchy or split the project."))
    dirs_by_parent = {}
    for name in live:
        parts = name.split("/")[:-1]
        for index in range(len(parts)):
            dirs_by_parent.setdefault("/".join(parts[:index]) or ".", set()).add(parts[index])
    mixed, details = [], {}
    for parent, children in sorted(dirs_by_parent.items()):
        styles = {}
        for child in sorted(children):
            style = name_style(child)
            if style:
                styles.setdefault(style, []).append(child)
        if len(styles) >= 2:
            mixed.append(parent)
            details[parent] = {k: v[:5] for k, v in styles.items()}
    if mixed:
        findings.append(_finding("mixed-naming", "mixed-naming", "info", mixed, len(mixed),
                                 "Folders at the same level mix naming styles (snake_case, kebab-case, camelCase).",
                                 "Pick one style per project and rename with git mv.", detail={"folders": details}))
    ptype = detect_project_type(repo, files, github_slug(repo))
    if ptype["primary"] in CODE_TYPES and sum(1 for n in live if PurePosixPath(n).suffix.lower() in LANG_BY_EXT) >= 3 \
            and not any(set(n.split("/")[:-1]) & {"tests", "test", "__tests__", "spec", "e2e"}
                        or TEST_NAME_RE.search(PurePosixPath(n).name) for n in live):
        findings.append(_finding("no-tests", "no-tests", "info", [], 0, "No test files found in a code project.",
                                 "Even one smoke test makes the project look maintained; a CI badge shows it."))

    rank = {sev: i for i, sev in enumerate(("high", "medium", "low", "info"))}
    findings.sort(key=lambda f: (rank[f["severity"]], f["id"]))
    anchor = ptype["primary"] if ptype["primary"] != "other" else "what-belongs-at-the-root"
    return {
        "findings": findings,
        "summary": dict(Counter(f["severity"] for f in findings)),
        "comments": languages,
        "markdown": {"count": len(mds), "root_files": root_md, "non_standard_at_root": nonstandard, "empty": empty,
                     "has_docs_folder": any(n.startswith("docs/") for n in files),
                     "has_changelog": any(PurePosixPath(n).stem.upper().startswith("CHANGELOG") for n in root_md)},
        "layout": {"root_entries": len(root_entries), "primary_type": ptype["primary"],
                   "reference": "%s#%s" % (REFERENCE_FILE, anchor)},
    }


def _stacks(files):
    stacks = []
    names = {PurePosixPath(n).name for n in files}
    if names & {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"} or any(n.endswith(".py") for n in files):
        stacks.append("python")
    if "package.json" in names:
        stacks.append("node")
    if "Cargo.toml" in names:
        stacks.append("rust")
    return stacks


GITIGNORE_WANTS = OrderedDict((
    ("python", (("__pycache__/", "__pycache__/x.pyc"), ("*.pyc", "x.pyc"), (".venv/", ".venv/x"))),
    ("node", (("node_modules/", "node_modules/x"), ("dist/", "dist/x"))),
    ("rust", (("target/", "target/x"),)),
    ("macos", ((".DS_Store", ".DS_Store"),)),
    ("secrets", ((".env", ".env"),)),
))


def _ignored(repo, probe):
    result = run(["git", "-C", str(repo), "-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "--no-index",
                  probe], check=False)
    return result.returncode == 0


def _gitignore_lines(stacks):
    lines = []
    for stack in list(stacks) + ["macos", "secrets"]:
        lines.extend(pattern for pattern, _ in GITIGNORE_WANTS.get(stack, ()))
    return lines


def _gitignore_gaps(repo, stacks):
    found = []
    for stack in list(stacks) + ["macos", "secrets"]:
        missing = [pattern for pattern, probe in GITIGNORE_WANTS[stack] if not _ignored(repo, probe)]
        if missing:
            found.append(_finding(
                "gitignore-gaps:" + stack, "gitignore-gaps", "low", [".gitignore"], len(missing),
                ".gitignore does not cover %s for %s." % (", ".join(missing), stack),
                "Append the missing patterns.",
                "printf '%s\\n' " + " ".join(shlex.quote(m) for m in missing) + " >> .gitignore",
                detail={"stack": stack, "missing": missing}))
    return found


# --------------------------------------------------------------------------- CLI

def _cmd_inventory(args):
    repo = repo_root(args.repo)
    result = {"ok": True}
    result.update(collect(repo, remote=not args.no_remote))
    print_json(result)
    return EXIT_OK


def _cmd_structure(args):
    repo = repo_root(args.repo)
    result = {"ok": True}
    result.update(structure_audit(repo))
    print_json(result)
    return EXIT_OK


def add_commands(subparsers):
    parser = subparsers.add_parser("inventory", help="project type, README stats, GitHub metadata, style sources")
    parser.add_argument("repo", help="path of the repository")
    parser.add_argument("--no-remote", action="store_true", help="local facts only, no gh call")
    parser.set_defaults(func=_cmd_inventory)
    parser = subparsers.add_parser("structure", help="layout audit: junk, duplicates, names, comments, missing files")
    parser.add_argument("repo", help="path of the repository")
    parser.set_defaults(func=_cmd_structure)
