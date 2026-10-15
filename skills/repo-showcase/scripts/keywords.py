"""repo-showcase: keywords (a short, sourced keyword list for the GitHub topics, description and README).

Command:
  keywords <repo> [--seed TERM ...] [--no-remote] [--max-search N] [--save]

Steps: seed terms from the repository itself (GitHub description and topics, README headings and first paragraph,
package.json / pyproject.toml / Cargo.toml keywords, project type and languages, --seed), then candidates from similar
repositories (topics weighted by log(1 + stars)), GitHub topic search, npm (JS/TS) or crates.io (Rust), Stack Exchange
tags and DuckDuckGo suggestions (phrases only), then a score and a placement proposal. Nothing is written except with
--save (<git dir>/repo-showcase/keywords.json, mode 600).

Seeds: existing topics, --seed and multi-word phrases lead. Brand names (repository, owner, the owner's other
repositories, "by X" in the description, product-name headings) and generic single words (bot, fork, countries...)
never seed a search; brands are never proposed as missing. The owner's repositories and starless forks are not
similar; the upstream parent is similar but not an independent source; `missing` needs 2 independent sources.

Similar repositories: searched with the 2 or 3 strongest pairs of seed terms (strength: origin weight, pairs of words,
README frequency), then filtered. A repository counts only if its topics and description contain at least 2 distinct
seed terms (1 with fewer than 4 seeds; a term inside a longer matched term is one hit), and its topics weigh
log(1 + stars) times its overlap relative to the best overlap. The others are listed in `similar_repos_dropped`.

Score (0 to 100), every part in 0..1:
  sources    min(distinct sources, 4) / 4          (the repository's own metadata counts as one source)      weight 30
  similar    topic weight / best topic weight      (weight = sum of log(1 + stars) of the similar repos)      weight 30
  density    log10(1 + repo_count) / 6             (repo_count = repositories carrying the topic; only fetched
                                                    for the best candidates, within the search budget)         weight 15
  relevance  overlap with the seeds                (mean seed weight of the term's words)                     weight 25
When repo_count was not fetched the density part is left out and the others are rescaled. repo_count measures how
many repositories use a topic (findability), not its popularity. Source facts: docs.github.com (search matches name,
description and topics; the README only with in:readme; no published ranking formula); topics are at most 20 per
repository, lowercase letters, digits and hyphens, 50 characters at most.

Privacy: only generic seed terms leave the machine, never the repository name, the owner, file names, git config or an
e-mail (terms containing them are dropped; for a private or internal repository, file names too). The single call that
names the repository is the owner's own `gh repo view` of it. With --no-remote there is no network call at all.
GitHub search is paced (30 requests a minute allowed): minimum interval PACE_INTERVAL, at most --max-search calls.
A source that fails is recorded in `errors`; exit 7 only when nothing answered at all.

Exit codes: 0 ok; 2 no usable seed; 3 not a git repository; 7 no source answered. Python 3.9 compatible.
"""
import gzip
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventory  # noqa: E402
from common import (EXIT_MISSING, EXIT_OK, EXIT_USAGE, EXIT_NETWORK, GITHUB_REMOTE_RE, Failure, gh_json,  # noqa: E402
                    git_call, github_slug, print_json, read_text, repo_root, state_dir)

TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
MAX_TOPICS = 20
DESCRIPTION_LIMIT = 350  # about: GitHub's exact limit is not documented in the pages we rely on
PACE_INTERVAL = 2.1      # seconds between two GitHub search calls (30 a minute allowed)
HTTP_INTERVAL = 0.5      # seconds between two calls to the same other service
CRATES_INTERVAL = 1.1    # crates.io asks for one request a second
HTTP_TIMEOUT = 10
SE_MIN_QUOTA = 10
UA = "repo-showcase-keywords (+https://github.com)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/17.0 Safari/605.1.15")
MAX_KEYWORDS = 40
GENERIC_PRIMARY = {"other", "config", "docs", "catalog", "profile"}

STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been before being below between both but by can
could did do does doing down during each few for from further had has have having he her here hers him his how i if in
into is it its itself just me more most my no nor not now of off on once only or other our out over own same she should
so some such than that the one two three first second time their them then there these they this those
through to too under until up us very was we were what when where which while who whom why will with would you
your yours via per etc
le la les des du un une et pour avec dans sur est sont par pas que qui ce ces au aux en ou ne se sa son ses
""".split())
# Words that name a README section or filler rather than the project: never a keyword on their own.
NOISE = frozenset("""
install installation usage license licence contributing contribution contributions features feature overview
documentation docs example examples requirements setup started getting quick start quickstart credits changelog
roadmap support faq author authors thanks download downloads verify publish release releases version versions file
files using use used like get make makes made new app apps simple easy free open source repository repo project
projects readme table contents link links badge badges screenshot screenshots demo todo get gets inside
maintained maintainer maintainers developed created powered includes included including choose exists existing
without anything fresh path migrate disclaimer
""".split())
# Single words too vague to start a search or a topic on their own (they may still sit inside a longer term):
# generic nouns, countries, human and programming languages.
GENERIC_WORDS = frozenset("""
bot bots fork forks tool tools app apps project projects data code software system platform ultimate production grade
custom multi learn highlights france germany spain italy china japan india usa english french german spanish chinese
japanese korean russian portuguese python javascript typescript java rust golang
""".split())
SIM_MIN_WEIGHT = math.log1p(100)  # a term backed by one similar repository counts as a source above this weight
ORIGIN_WEIGHT = OrderedDict((("--seed", 1.0), ("topics", 1.0), ("package.json", 1.0), ("pyproject.toml", 1.0),
                             ("Cargo.toml", 1.0), ("description", 1.0), ("readme-heading", 0.8),
                             ("project-type", 0.7), ("language", 0.7), ("readme-intro", 0.5)))
SOURCE_GROUP = {"seed": "seed", "github-similar": "github-similar", "github-topics": "github-topics",
                "npm": "registry", "crates": "registry", "stackexchange": "stackexchange",
                "duckduckgo": "duckduckgo"}
CHUNK_SPLIT_RE = re.compile(r"[.,;:!?()\[\]{}<>\"/\\|\n\r\t*=~`\u2022\u00b7\u2013\u2014]+")
TOKEN_RE = re.compile(r"[^\W_]+[+#]*")
HEADING_LINE_RE = re.compile(r"^\s{0,3}(#{1,2})\s+(.+?)\s*#*\s*$")
TAG_RE = re.compile(r"<[^>]*>")
IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+")


# --------------------------------------------------------------------------- terms

def term_key(text):
    """Canonical form of a term: lowercase words separated by one space (hyphens and underscores are separators)."""
    return " ".join(TOKEN_RE.findall((text or "").lower().replace("-", " ").replace("_", " ")))


def topic_slug(term):
    """Valid GitHub topic slug for a term, or None."""
    slug = "-".join(term_key(term).split())
    return slug if TOPIC_RE.match(slug) else None


def tokens_of(text):
    return [t for t in TOKEN_RE.findall((text or "").lower()) if not t.isdigit() and len(t) >= 3
            and t not in STOPWORDS]


def is_generic(key):
    """True for a single word too vague to be a search or a topic by itself."""
    return " " not in key and (key in GENERIC_WORDS or key in NOISE or key in STOPWORDS)


BY_RE = re.compile(r"\b[Bb]y\s+((?:[A-Z][\w.-]*)(?:\s+[A-Z][\w.-]*){0,3})")


class Brand:
    """Names that identify the maintainer or the products (repository, owner, sibling repositories, "by X" in the
    description): weak as keywords, never searched, never proposed as missing."""

    def __init__(self, phrases=(), tokens=()):
        self.phrases = [p for p in OrderedDict.fromkeys(phrases) if p]
        self.tokens = set(tokens)

    def matches(self, key):
        padded = " %s " % key
        if any(" %s " % p in padded for p in self.phrases) or set(key.split()) & self.tokens:
            return True
        return " " in key and any(" " in p and padded in " %s " % p for p in self.phrases)


def build_brand(name, owner, siblings, description, protected):
    """Brand names; `protected` are the keys of the existing topics and --seed terms: a word the maintainer chose to
    describe the project (freqtrade in "Freqtrade France") stays a normal term."""
    words = {w for key in protected for w in key.split()}
    phrases, tokens = [], set()
    for text in [name, owner] + list(siblings):
        key = term_key(text)
        # A name of four words or more is a description, not a brand.
        if 3 <= len(key) and len(key.split()) <= 3 and key not in protected and (" " in key or not is_generic(key)):
            phrases.append(key)
    owner_key = term_key(owner)
    if owner_key and " " not in owner_key:
        tokens.add(owner_key)
    for found in BY_RE.findall(description or ""):
        key = term_key(found)
        phrases.append(key)
        tokens.update(w for w in key.split() if len(w) >= 3 and w not in words)
    return Brand(phrases, tokens)


def extract_terms(text, noise=False):
    """Unigrams and bigrams of the words that are neither stopwords, numbers nor shorter than 3 characters.
    A bigram joins two neighbours in the same clause; punctuation and stopwords end a clause."""
    out = []
    for chunk in CHUNK_SPLIT_RE.split((text or "").lower()):
        run = []
        for token in TOKEN_RE.findall(chunk.replace("-", " ").replace("_", " ")) + [None]:
            bad = (token is None or token.isdigit() or len(token) < 3 or token in STOPWORDS
                   or (noise and (token in NOISE or token.rstrip("s") in NOISE)))
            if not bad:
                run.append(token)
                continue
            out.extend(run)
            out.extend("%s %s" % pair for pair in zip(run, run[1:]))
            run = []
    return list(OrderedDict.fromkeys(out))


def plain_text(text):
    """Markdown or HTML snippet reduced to its words."""
    text = IMG_RE.sub(" ", text)
    text = LINK_RE.sub(r"\1", text)
    text = URL_RE.sub(" ", text)
    return " ".join(TAG_RE.sub(" ", text).replace("`", " ").replace("*", " ").split())


def readme_parts(text):
    """(heading texts of level 1 and 2, first paragraph of prose) of a README."""
    headings, paragraphs, current, fence = [], [], [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (fence or marker)
            continue
        if fence:
            continue
        match = HEADING_LINE_RE.match(line)
        if match:
            headings.append(plain_text(match.group(2)))
            current = []
            continue
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
            current = []
        elif not stripped.startswith(("|", ">", "-", "*", "+", "1.", "<", "![", "[![")):
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    intro = next((p for p in (plain_text(p) for p in paragraphs) if len(p.split()) >= 6), "")
    return [h for h in headings if h], intro[:500]


def toml_keywords(text, section, key="keywords"):
    """Strings of `key = [...]` inside [section] of a TOML text (tomllib when available, else a small regex)."""
    try:
        import tomllib  # Python 3.11+
        node = tomllib.loads(text)
        for part in section.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        value = node.get(key) if isinstance(node, dict) else None
        return [str(v) for v in value] if isinstance(value, list) else []
    except ImportError:
        pass
    except ValueError:
        return []
    header = re.search(r"^\[%s\]\s*$(.*?)(?=^\[|\Z)" % re.escape(section), text, re.M | re.S)
    if not header:
        return []
    found = re.search(r"^\s*%s\s*=\s*\[(.*?)\]" % re.escape(key), header.group(1), re.M | re.S)
    return re.findall(r"[\"']([^\"']+)[\"']", found.group(1)) if found else []


def manifest_keywords(repo, files):
    """{origin: [keyword phrases]} from the root package.json, pyproject.toml and Cargo.toml."""
    found = {}
    fileset = set(files)
    if "package.json" in fileset:
        try:
            data = json.loads(read_text(Path(repo) / "package.json") or "{}")
        except ValueError:
            data = {}
        words = data.get("keywords") if isinstance(data, dict) else None
        if isinstance(words, list):
            found["package.json"] = [w for w in words if isinstance(w, str)]
    if "pyproject.toml" in fileset:
        text = read_text(Path(repo) / "pyproject.toml") or ""
        words = toml_keywords(text, "project") or toml_keywords(text, "tool.poetry")
        if words:
            found["pyproject.toml"] = words
    if "Cargo.toml" in fileset:
        words = toml_keywords(read_text(Path(repo) / "Cargo.toml") or "", "package")
        if words:
            found["Cargo.toml"] = words
    return found


class Seeds:
    """Seed terms: key -> {"origins": [...], "weight": best origin weight}, plus word weights for the relevance."""

    def __init__(self, blocked=(), brand=None, protected=()):
        self.terms = OrderedDict()
        self.blocked = [b for b in blocked if b]
        self.brand = brand or Brand()
        self.protected = set(protected)

    def blocked_term(self, key):
        padded = " %s " % key
        # The name or owner (inside the term, or the term inside a multi-word name: a brand) never leaves.
        return any(" %s " % b in padded or (" " in key and padded in " %s " % b) for b in self.blocked)

    def add(self, text, origin, taint=False):
        """taint: the term comes from a brand context (a heading naming a product): brand unless the maintainer
        chose it as a topic or --seed."""
        key = term_key(text)
        if not key or self.blocked_term(key):
            return
        flag = self.brand.matches(key) or (taint and key not in self.protected)
        entry = self.terms.setdefault(key, {"origins": [], "weight": 0.0, "brand": True})
        entry["brand"] = entry["brand"] and flag
        if origin not in entry["origins"]:
            entry["origins"].append(origin)
        entry["weight"] = max(entry["weight"], ORIGIN_WEIGHT[origin])

    def add_many(self, texts, origin, taint=False):
        for text in texts:
            self.add(text, origin, taint)

    def word_weights(self):
        weights = {}
        for key, entry in self.terms.items():
            for word in key.split():
                if word not in STOPWORDS and not entry["brand"]:
                    weights[word] = max(weights.get(word, 0.0), entry["weight"])
        return weights

    def strength(self, key):
        """Origin weight, plus 0.5 for an existing topic or --seed, 0.25 for a phrase of several words and up to
        0.5 for the README coming back to the term, minus 0.4 for a phrase holding a generic word ("multi bot")."""
        entry = self.terms[key]
        explicit = 0.5 if {"topics", "--seed"} & set(entry["origins"]) else 0.0
        vague = -0.4 if " " in key and set(key.split()) & GENERIC_WORDS else 0.0
        return entry["weight"] + explicit + (0.25 if " " in key else 0.0) + min(entry.get("freq", 0), 20) / 40.0 + vague

    def specific(self):
        """{term: origin weight} of the seeds that describe the project: not its language or type, not a brand,
        not a section name."""
        weak = {"language", "project-type"}
        return {k: e["weight"] for k, e in self.terms.items()
                if not set(e["origins"]) <= weak and k not in NOISE and not e["brand"]}

    def query_pool(self):
        """Seed terms worth sending to a search, strongest first. A generic single word never starts a search."""
        return sorted((k for k in self.specific() if not is_generic(k)), key=lambda k: (-self.strength(k), k))

    def topic_query(self):
        """`topic:a topic:b` from the two strongest existing topics or --seed terms with a valid slug and no generic
        word (`topic:freqtrade-fork` is too narrow), or None."""
        slugs = [topic_slug(k) for k in self.query_pool()
                 if {"topics", "--seed"} & set(self.terms[k]["origins"]) and not set(k.split()) & GENERIC_WORDS]
        slugs = [x for x in slugs if x]
        return " ".join("topic:" + x for x in slugs[:2]) if len(slugs) >= 2 else None


def seed_pairs(pool, limit=3, max_words=3):
    """The strongest pairs of seed terms for a search (all words must match, so at most max_words words), none
    sharing a word: [(a, b), ...]. Strength is the sum of the two terms' ranks in pool (strongest first)."""
    top = pool[:8]
    pairs = []
    for i, first in enumerate(top):
        for j in range(i + 1, len(top)):
            second = top[j]
            if len(first.split()) + len(second.split()) <= max_words and not set(first.split()) & set(second.split()):
                pairs.append((i + j, i, j))
    pairs.sort()
    out = []
    for _, i, j in pairs:
        if len(out) >= limit:
            break
        out.append((top[i], top[j]))
    return out


def collect_seeds(repo, files, inv, meta, extra, blocked, brand=None):
    protected = {term_key(t) for t in list(extra) + list((meta or {}).get("topics") or [])}
    seeds = Seeds(blocked, brand, protected)
    seeds.add_many(extra, "--seed")
    if meta:
        seeds.add_many(meta.get("topics") or [], "topics")
        seeds.add_many(extract_terms(meta.get("description") or "", noise=True), "description")
    for origin, words in manifest_keywords(repo, files).items():
        seeds.add_many(words, origin)
    readme_path = inventory.find_readme(repo, files)
    text = read_text(Path(repo) / readme_path) if readme_path else None
    body = " %s " % term_key(text or "")
    if text:
        headings, intro = readme_parts(text)
        for heading in headings:  # a heading that names a product of the owner taints its words
            seeds.add_many(extract_terms(heading, noise=True), "readme-heading",
                           taint=seeds.brand.matches(term_key(heading)))
        # Words of the opening paragraph count when the README comes back to them (3 times, 2 for a pair).
        seeds.add_many([t for t in extract_terms(intro, noise=True)
                        if body.count(" %s " % t) >= (2 if " " in t else 3)], "readme-intro")
    primary = (inv.get("project_type") or {}).get("primary")
    if primary and primary not in GENERIC_PRIMARY:
        seeds.add(primary, "project-type")
    for item in ((inv.get("local") or {}).get("languages") or [])[:3]:
        if (item.get("percent") or 0) >= 5:
            seeds.add(item["language"], "language")
    for key, entry in seeds.terms.items():
        entry["freq"] = body.count(" %s " % key)
    return seeds, text or ""


# --------------------------------------------------------------------------- network helpers (mocked in tests)

def _gh(args):
    """Parsed JSON of a gh command; Failure(EXIT_NETWORK) on error, Failure(EXIT_MISSING) if gh is absent."""
    return gh_json(args)


def _repo_meta(slug):
    """Visibility, description, topics and fork parent of the repository (the owner's own read), or None."""
    fields = "visibility,description,repositoryTopics,isFork,parent"
    try:
        view = gh_json(["repo", "view", slug, "--json", fields], check=False)
    except (Failure, ValueError):
        return None
    if not isinstance(view, dict):
        return None
    parent = view.get("parent")
    if isinstance(parent, dict):
        owner = (parent.get("owner") or {}).get("login")
        parent = parent.get("nameWithOwner") or ("%s/%s" % (owner, parent.get("name")) if owner else None)
    return {"visibility": (view.get("visibility") or "").upper() or None, "description": view.get("description"),
            "topics": inventory._topic_names(view.get("repositoryTopics")), "parent": parent or None}


def _owner_repos(owner):
    """Names of the owner's repositories (the owner's own read, for the brand names), [] if unavailable."""
    try:
        listing = gh_json(["repo", "list", owner, "--limit", "100", "--json", "name"], check=False)
    except (Failure, ValueError):
        return []
    return [item["name"] for item in listing or [] if isinstance(item, dict) and item.get("name")]


def _upstream_slug(repo):
    """"owner/name" of an `upstream` git remote on github.com, or None."""
    result = run_git_remote(repo)
    match = GITHUB_REMOTE_RE.search(result) if result else None
    return "%s/%s" % match.groups() if match else None


def run_git_remote(repo):
    code, out, _ = git_call(repo, "remote", "get-url", "upstream", timeout=10)
    return out.strip() if code == 0 else ""


def _http_json(url, headers=None):
    """GET url, decompress gzip, parse JSON. Failure(EXIT_NETWORK) on any network or format error."""
    merged = dict({"User-Agent": UA, "Accept-Encoding": "gzip"}, **(headers or {}))
    request = urllib.request.Request(url, headers=merged)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            data = response.read(4000000)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Failure(EXIT_NETWORK, "%s: %s" % (urllib.parse.urlsplit(url).netloc, error))
    try:
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8", "replace"))
    except (OSError, EOFError, ValueError) as error:
        raise Failure(EXIT_NETWORK, "%s: unreadable response (%s)" % (urllib.parse.urlsplit(url).netloc, error))


class Pacer:
    """Minimum interval between calls and an optional cap on their number (injectable clock and sleep for tests)."""

    def __init__(self, interval, cap=None, sleep=time.sleep, clock=time.monotonic):
        self.interval, self.cap, self.used = interval, cap, 0
        self._sleep, self._clock, self._last = sleep, clock, None

    def acquire(self):
        """Wait for the interval, count the call; False (no wait) when the cap is already reached."""
        if self.cap is not None and self.used >= self.cap:
            return False
        if self._last is not None and self.interval > 0:
            wait = self.interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        self.used += 1
        return True


class Run:
    """Calls made, errors by source, sources that answered, and the queries sent (for the privacy audit)."""

    def __init__(self, max_search):
        self.calls, self.errors, self.answered, self.queries = {}, {}, set(), []
        self.search = Pacer(PACE_INTERVAL, max_search)
        self.others = {}
        self.gh_stopped = False
        self.budget_hit = False
        self.se_quota = None

    def _count(self, source, query):
        self.calls[source] = self.calls.get(source, 0) + 1
        self.queries.append({"source": source, "query": query})

    def error(self, source, message):
        bucket = self.errors.setdefault(source, [])
        if message not in bucket:
            bucket.append(message[:300])

    def gh_search(self, source, endpoint, params, query):
        """One paced GitHub search call, or None (budget reached, rate limited, gh missing or failed)."""
        if self.gh_stopped:
            return None
        if not self.search.acquire():
            self.budget_hit = True
            return None
        self._count(source, query)
        args = ["api", endpoint, "-X", "GET", "-H", "Accept: application/vnd.github+json"]
        for key, value in params:
            args += ["-f", "%s=%s" % (key, value)]
        try:
            data = _gh(args)
        except Failure as error:
            text = str(error)
            self.error(source, text)
            if error.code == EXIT_MISSING or re.search(r"rate limit|\b(403|429)\b", text, re.I):
                self.gh_stopped = True
            return None
        except ValueError as error:
            self.error(source, "unreadable response: %s" % error)
            return None
        if not isinstance(data, dict):
            self.error(source, "unexpected response")
            return None
        self.answered.add(source)
        return data

    def http(self, source, url, query, headers=None, interval=None):
        """One polite call to another service, or None on failure."""
        self.others.setdefault(source, Pacer(HTTP_INTERVAL if interval is None else interval)).acquire()
        self._count(source, query)
        try:
            data = _http_json(url, headers)
        except Failure as error:
            self.error(source, str(error))
            return None
        self.answered.add(source)
        return data


# --------------------------------------------------------------------------- candidates

class Candidate:
    def __init__(self, key):
        self.key = key
        self.sources = OrderedDict()   # (source, evidence)
        self.sim_weight = 0.0
        self.sim_repos = []
        self.sim_other = []            # similar repositories other than the upstream parent
        self.sim_other_weight = 0.0
        self.relevance = 0.0
        self.repo_count = None
        self.score = 0.0

    def add(self, source, evidence):
        self.sources.setdefault((source, evidence), None)

    def groups(self):
        return {SOURCE_GROUP.get(s.split(":")[0], s) for s, _ in self.sources}

    def independent(self):
        """Independent external sources: github-similar counts only with 2 repositories (not the upstream) or one
        heavy enough; the repository's own words never count."""
        groups = {g for g in self.groups() if g not in ("seed", "github-similar")}
        if len(self.sim_other) >= 2 or self.sim_other_weight >= SIM_MIN_WEIGHT:
            groups.add("github-similar")
        return len(groups)

    def phrase_only(self):
        return {s for s, _ in self.sources} <= {"duckduckgo"}


def score_candidates(cands, word_weights):
    """Set .score on every candidate (see the module docstring for the formula) and return them best first."""
    best_sim = max((c.sim_weight for c in cands), default=0.0) or 1.0
    for cand in cands:
        words = cand.key.split()
        relevance = sum(word_weights.get(w, 0.0) for w in words) / len(words) if words else 0.0
        parts = [(30, min(len(cand.groups()), 4) / 4.0), (30, cand.sim_weight / best_sim), (25, relevance)]
        if cand.repo_count is not None:
            parts.append((15, min(1.0, math.log10(1 + cand.repo_count) / 6.0)))
        cand.relevance = relevance
        cand.score = round(100.0 * sum(w * v for w, v in parts) / sum(w for w, _ in parts), 1)
    return sorted(cands, key=lambda c: (-c.score, c.key))


class Pool:
    def __init__(self, blocked):
        self.items = OrderedDict()
        self.blocked = blocked

    def get(self, text):
        key = term_key(text)
        if not key or len(key) > 60 or self.blocked(key):
            return None
        return self.items.setdefault(key, Candidate(key))

    def add(self, text, source, evidence):
        cand = self.get(text)
        if cand:
            cand.add(source, evidence)
        return cand


def _short(items, limit=3):
    return ", ".join(items[:limit]) + (" ..." if len(items) > limit else "")


def seed_overlap(repo, seed_terms):
    """Seed terms found in a repository's topics and description, longest only (a term inside a longer matched term
    is the same hit): (list of terms, sum of their origin weights)."""
    text = " %s %s " % (term_key(" ".join(repo["topics"])), term_key(repo.get("description") or ""))
    matched = [k for k in seed_terms if " %s " % k in text]
    longest = [k for k in matched if not any(k != o and " %s " % k in " %s " % o for o in matched)]
    return longest, sum(seed_terms[k] for k in longest)


def from_similar(run, pool, queries, own, seed_terms, owner=None, parents=(), per_page=30):
    """Topics of the most starred repositories matching the seed queries, kept only when the repository really is
    about the project: its topics and description share at least 2 distinct seed terms (1 when there are fewer than
    4 seeds), and its contribution is weighted by that overlap. Returns (kept, dropped), both most starred first."""
    found = OrderedDict()
    for query in queries:
        data = run.gh_search("github-similar", "search/repositories",
                             [("q", query), ("sort", "stars"), ("per_page", str(per_page))], query)
        for item in (data or {}).get("items") or []:
            name = item.get("full_name")
            stars = int(item.get("stargazers_count") or 0)
            if not name or name.lower() in own or name in found:
                continue
            if owner and name.split("/")[0].lower() == owner.lower():
                continue  # the owner's own repositories are not a signal about the field
            if item.get("fork") and stars == 0:
                continue  # a fork nobody starred repeats its upstream
            found[name] = {"full_name": name, "stars": stars,
                           "topics": [t for t in item.get("topics") or [] if isinstance(t, str)],
                           "description": item.get("description")}
    needed = 2 if len(seed_terms) >= 4 else 1
    kept, dropped = [], []
    for repo in found.values():
        terms, weight = seed_overlap(repo, seed_terms)
        repo["overlap"], repo["matched"], repo["overlap_weight"] = len(terms), terms, weight
        if len(terms) >= needed:
            kept.append(repo)
        else:
            repo["reason"] = "shares %d seed term%s (%s), %d needed" % (
                len(terms), "" if len(terms) == 1 else "s", ", ".join(terms) or "none", needed)
            dropped.append(repo)
    best = max((r["overlap_weight"] for r in kept), default=0.0) or 1.0
    for repo in kept:
        for topic in repo["topics"]:
            cand = pool.get(topic)
            if cand:
                share = math.log1p(repo["stars"]) * repo["overlap_weight"] / best
                cand.sim_weight += share
                cand.sim_repos.append(repo["full_name"])
                if repo["full_name"].lower() not in {p.lower() for p in parents}:  # the upstream is similar, not news
                    cand.sim_other.append(repo["full_name"])
                    cand.sim_other_weight += share
    for cand in pool.items.values():
        if cand.sim_repos:
            cand.add("github-similar",
                     "topic of %d similar repos (%s)" % (len(cand.sim_repos), _short(cand.sim_repos, 2)))
    by_stars = lambda r: -r["stars"]  # noqa: E731
    return sorted(kept, key=by_stars), sorted(dropped, key=by_stars)


def from_topic_search(run, pool, terms):
    for term in terms:
        data = run.gh_search("github-topics", "search/topics", [("q", term), ("per_page", "10")], term)
        for item in (data or {}).get("items") or []:
            name = item.get("name")
            if name and TOPIC_RE.match(name):
                kind = "curated topic" if item.get("curated") else "topic"
                pool.add(name, "github-topics", "%s found by the topic search for '%s'" % (kind, term))


def from_npm(run, pool, terms):
    counts = {}
    for term in terms:
        url = "https://registry.npmjs.org/-/v1/search?" + urllib.parse.urlencode({"text": term, "size": 20})
        data = run.http("npm", url, term)
        for obj in (data or {}).get("objects") or []:
            for word in ((obj.get("package") or {}).get("keywords") or []):
                if isinstance(word, str) and word.strip():
                    counts[word] = counts.get(word, 0) + 1
    for word, n in sorted(counts.items(), key=lambda kv: -kv[1])[:15]:
        pool.add(word, "npm", "keyword of %d npm packages" % n)


def from_crates(run, pool, terms):
    counts = {}
    for term in terms:
        url = "https://crates.io/api/v1/crates?" + urllib.parse.urlencode({"q": term, "per_page": 10})
        data = run.http("crates", url, term, interval=CRATES_INTERVAL)
        for crate in ((data or {}).get("crates") or [])[:5]:
            name = crate.get("name") if isinstance(crate, dict) else None
            if not name:
                continue
            detail = run.http("crates", "https://crates.io/api/v1/crates/" + urllib.parse.quote(name), "crate details",
                              interval=CRATES_INTERVAL)
            if not isinstance(detail, dict):
                continue
            words = list((detail.get("crate") or {}).get("keywords") or [])
            words += [c.get("slug") or c.get("category") for c in detail.get("categories") or [] if isinstance(c, dict)]
            for word in words:
                if isinstance(word, str) and word.strip():
                    counts[word] = counts.get(word, 0) + 1
    for word, n in sorted(counts.items(), key=lambda kv: -kv[1])[:15]:
        pool.add(word, "crates", "keyword or category of %d crates" % n)


def from_stackexchange(run, pool, terms):
    for term in terms:
        if run.se_quota is not None and run.se_quota < SE_MIN_QUOTA:
            run.error("stackexchange", "quota low (%d left), stopped" % run.se_quota)
            return
        url = "https://api.stackexchange.com/2.3/tags?" + urllib.parse.urlencode(
            {"inname": term, "site": "stackoverflow", "order": "desc", "sort": "popular", "pagesize": 10})
        data = run.http("stackexchange", url, term)
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("quota_remaining"), int):
            run.se_quota = data["quota_remaining"]
        for item in data.get("items") or []:
            if item.get("name") and TOPIC_RE.match(item["name"]):
                pool.add(item["name"], "stackexchange", "Stack Overflow tag, %s questions" % item.get("count", "?"))


def from_duckduckgo(run, pool, terms, seed_words):
    for term in terms:
        url = "https://duckduckgo.com/ac/?" + urllib.parse.urlencode({"q": term, "type": "list"})
        data = run.http("duckduckgo", url, term, headers={"User-Agent": BROWSER_UA})
        if not (isinstance(data, list) and len(data) > 1 and isinstance(data[1], list)):
            if data is not None:
                run.error("duckduckgo", "unexpected response")
            continue
        for phrase in data[1][:8]:
            if not isinstance(phrase, str):
                continue
            key = term_key(phrase)
            if key != term_key(term) and 2 <= len(key.split()) <= 5 and any(w in seed_words for w in key.split()):
                pool.add(key, "duckduckgo", "autocomplete suggestion for '%s'" % term)


def fetch_counts(run, pool, limit=12):
    """repo_count of the best topic candidates (preliminary order), within the search budget."""
    ranked = score_candidates(list(pool.items.values()), pool.word_weights)
    for cand in [c for c in ranked if topic_slug(c.key) and not c.phrase_only()][:limit]:
        slug = topic_slug(cand.key)
        data = run.gh_search("github-count", "search/repositories", [("q", "topic:" + slug), ("per_page", "1")],
                             "topic:" + slug)
        if run.gh_stopped or (data is None and run.budget_hit):
            break
        if isinstance(data, dict) and isinstance(data.get("total_count"), int):
            cand.repo_count = data["total_count"]


# --------------------------------------------------------------------------- placement

def covered(key, description, topics, readme_norm):
    padded = lambda text: " %s " % text  # noqa: E731
    slug = topic_slug(key)
    return {"description": padded(key) in padded(description),
            "topics": bool(slug) and slug in topics,
            "readme": padded(key) in padded(readme_norm)}


def _overlap(key, chosen):
    words = set(key.split())
    return any(words & set(other.split()) for other in chosen)


def place(ranked, existing_topics):
    """Topics, description phrases and README terms from the scored keywords (dicts, best first). Brand names and
    generic single words are never proposed (an existing topic stays); `missing` needs 2 independent sources."""
    existing = [t for t in existing_topics if TOPIC_RE.match(t)]
    fit = [i for i in ranked if not i.get("brand") and not is_generic(i["term"])]
    topics, new = [], []
    for item in ranked:
        slug = item["as_topic"]
        if not slug or slug in topics:
            continue
        if slug in existing:
            if item["score"] >= 20:
                topics.append(slug)
            continue
        if item not in fit or len(topics) >= 15 or (len(topics) >= 10 and item["score"] < 30):
            continue
        topics.append(slug)
        new.append(slug)
    # Never more than 20 topics once the existing ones that stay on the repository are counted.
    room = MAX_TOPICS - len([t for t in existing if t not in topics])
    while len(topics) > max(room, 0):
        drop = next((t for t in reversed(topics) if t in new), None)
        if drop is None:
            break
        topics.remove(drop)
        new.remove(drop)
    phrases = []
    for item in fit:
        if len(phrases) >= 3:
            break
        if len(item["term"].split()) >= 2 and item["score"] >= 15 and not _overlap(item["term"], phrases):
            phrases.append(item["term"])
    for item in fit:  # fewer than two phrases: complete with the best single words
        if len(phrases) >= 2:
            break
        if item["term"] not in phrases and not _overlap(item["term"], phrases):
            phrases.append(item["term"])
    terms = []
    for item in fit:
        if len(terms) >= 6:
            break
        if item["score"] >= 20 and not _overlap(item["term"], terms):
            terms.append(item["term"])
    for item in fit:
        if len(terms) >= 3:
            break
        if item["term"] not in terms:
            terms.append(item["term"])
    missing = [i["term"] for i in fit if i["score"] >= 40 and not any(i["covered"].values())
               and i.get("independent_sources", 2) >= 2][:10]
    return {"topics": topics, "topics_new": new, "description_phrases": phrases, "readme_terms": terms,
            "missing": missing}


def description_warnings(description, topics):
    warnings = []
    if len(description) > DESCRIPTION_LIMIT:
        warnings.append("description is %d characters: GitHub's limit is about %d, shorten it"
                        % (len(description), DESCRIPTION_LIMIT))
    words = tokens_of(description)
    repeated = sorted({w for w in words if words.count(w) > 1})
    if repeated:
        warnings.append("repeated words in the description: %s" % ", ".join(repeated))
    if len(topics) > MAX_TOPICS:
        warnings.append("%d topics: GitHub allows %d at most" % (len(topics), MAX_TOPICS))
    return warnings


# --------------------------------------------------------------------------- orchestration

def _stack(inv, files):
    """Which registry fits the project: "npm" (JS/TS), "crates" (Rust) or None (PyPI search is disabled)."""
    top = [item["language"] for item in (inv.get("local") or {}).get("languages") or []][:2]
    if "Cargo.toml" in files or top[:1] == ["Rust"]:
        return "crates"
    if "package.json" in files or {"JavaScript", "TypeScript"} & set(top):
        return "npm"
    return None


def build(repo, extra_seeds=(), remote=True, max_search=25):
    repo = Path(repo)
    files = inventory.tracked_present(repo)
    inv = inventory.collect(repo, remote=False)
    slug = github_slug(repo)
    run = Run(max_search)
    meta, notes = None, []
    if remote and slug:
        run.calls["github-repo"] = 1
        meta = _repo_meta(slug)
        if meta:
            run.answered.add("github-repo")
        else:
            run.error("github-repo", "gh could not read %s (not installed, offline or no access)" % slug)
    visibility = (meta or {}).get("visibility")
    private = None if visibility is None else visibility in ("PRIVATE", "INTERNAL")
    if remote and private is None:
        private = True  # unknown visibility: assume the worst for the file-name rule
        notes.append("visibility unknown: treated as private (file names are never sent anyway)")

    owner, _, name = (slug or "").partition("/")
    blocked = [term_key(name or repo.name), term_key(owner)]
    if private:  # even a word of the name or owner stays home
        blocked += [w for w in " ".join(blocked).split() if len(w) >= 3 and w not in STOPWORDS]
        for file_name in files:
            base = file_name.rsplit("/", 1)[-1]
            blocked += [term_key(base), term_key(base.rsplit(".", 1)[0])]
    blocked = [b for b in dict.fromkeys(blocked) if len(b) >= 3]

    siblings = []
    if remote and owner:
        run.calls["github-owner"] = 1
        siblings = [n for n in _owner_repos(owner) if n.lower() != (name or repo.name).lower()]
    protected = {term_key(t) for t in list(extra_seeds) + list((meta or {}).get("topics") or [])}
    brand = build_brand(name or repo.name, owner, siblings, (meta or {}).get("description"), protected)
    seeds, readme_text = collect_seeds(repo, files, inv, meta, extra_seeds, blocked, brand)
    if not seeds.terms:
        raise Failure(EXIT_USAGE, "no seed term found in the repository: pass --seed TERM")
    word_weights = seeds.word_weights()
    pool = Pool(seeds.blocked_term)
    pool.word_weights = word_weights
    for key, entry in seeds.terms.items():
        cand = pool.get(key)
        for origin in entry["origins"]:
            cand.add("seed:" + origin, "in the repository's %s" % origin)
    similar, dropped = [], []

    if remote:
        query_pool = seeds.query_pool()
        parents = [x for x in ((meta or {}).get("parent"), _upstream_slug(repo)) if x]
        if query_pool:
            topic_query = seeds.topic_query()
            sim_queries = (["%s %s" % pair for pair in seed_pairs(query_pool, limit=2 if topic_query else 3)]
                           + ([topic_query] if topic_query else [])) or query_pool[:2]
            similar, dropped = from_similar(run, pool, sim_queries, {slug.lower()} if slug else set(),
                                            seeds.specific(), owner or None, parents)
            from_topic_search(run, pool, query_pool[:4])
            stack = _stack(inv, set(files))
            if stack == "npm":
                from_npm(run, pool, query_pool[:2])
            elif stack == "crates":
                from_crates(run, pool, query_pool[:2])
            single = OrderedDict.fromkeys(w for q in query_pool[:4] for w in q.split()
                                          if len(w) >= 3 and w not in GENERIC_WORDS | NOISE | STOPWORDS
                                          and not brand.matches(w))
            from_stackexchange(run, pool, list(single)[:3])
            from_duckduckgo(run, pool, query_pool[:3], set(word_weights))
            fetch_counts(run, pool)
        else:
            notes.append("no sendable seed term: no external source queried")
        if run.budget_hit:
            notes.append("search budget reached (--max-search %d): some sources were skipped" % max_search)
    if remote and run.queries and not run.answered:
        raise Failure(EXIT_NETWORK, "no source answered: " + "; ".join(
            "%s: %s" % (s, m[0]) for s, m in sorted(run.errors.items())))

    scored = score_candidates(list(pool.items.values()), word_weights)
    # An external suggestion that shares no word with the seeds and has a single source is noise.
    scored = [c for c in scored if c.groups() & {"seed", "github-similar"} or c.relevance > 0 or len(c.groups()) > 1]

    description = (meta or {}).get("description") or ""
    topics_now = (meta or {}).get("topics") or []
    desc_norm = term_key(description)
    readme_norm = term_key(readme_text)
    keywords = []
    # Phrases (DuckDuckGo) are not topics and score lower: keep a few of them in the list.
    phrases = [c for c in scored if c.phrase_only()][:6]
    shown = [c for c in scored if not c.phrase_only()][:MAX_KEYWORDS - len(phrases)] + phrases
    for cand in sorted(shown, key=lambda c: (-c.score, c.key)):
        is_brand = seeds.terms[cand.key]["brand"] if cand.key in seeds.terms else brand.matches(cand.key)
        keywords.append({
            "term": cand.key, "score": cand.score, "brand": is_brand, "independent_sources": cand.independent(),
            "sources": [{"source": s, "evidence": e} for s, e in cand.sources],
            "as_topic": None if cand.phrase_only() else topic_slug(cand.key),
            "repo_count": cand.repo_count,
            "covered": covered(cand.key, desc_norm, set(topics_now), readme_norm)})
    placement = place(keywords, topics_now)
    if not remote:
        notes.append("--no-remote: GitHub description and topics unknown (coverage counts the README only)")
    return {
        "ok": True, "slug": slug, "visibility": visibility, "private": private,
        "privacy": "generic terms only", "remote": remote,
        "seeds": [{"term": k, "origins": e["origins"]} for k, e in seeds.terms.items()],
        "current": {"description": description or None, "topics": topics_now},
        "keywords": keywords, "placement": placement,
        "warnings": description_warnings(description, topics_now),
        "similar_repos": [{"full_name": r["full_name"], "stars": r["stars"], "topics": r["topics"],
                           "overlap": r["overlap"]} for r in similar[:8]],
        "similar_repos_dropped": [{"full_name": r["full_name"], "stars": r["stars"], "reason": r["reason"]}
                                  for r in dropped[:5]],
        "brand_names": (brand.phrases + sorted(brand.tokens))[:20],
        "calls": run.calls, "errors": run.errors, "queries": run.queries, "notes": notes,
    }


def save(repo, result):
    path = state_dir(repo) / "keywords.json"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    os.chmod(str(path), 0o600)
    return path


# --------------------------------------------------------------------------- CLI

def _cmd_keywords(args):
    repo = repo_root(args.repo)
    result = build(repo, extra_seeds=args.seed or [], remote=not args.no_remote, max_search=args.max_search)
    result["saved"] = str(save(repo, dict(result, saved=None))) if args.save else None
    print_json(result)
    return EXIT_OK


def add_commands(subparsers):
    parser = subparsers.add_parser("keywords", help="sourced keywords for topics, description and README")
    parser.add_argument("repo", help="path of the repository")
    parser.add_argument("--seed", action="append", metavar="TERM", help="extra seed term (repeatable)")
    parser.add_argument("--no-remote", action="store_true", help="no network call: seeds and coverage only")
    parser.add_argument("--max-search", type=int, default=25, metavar="N",
                        help="most GitHub search calls in one run (default 25, about 2 s apart)")
    parser.add_argument("--save", action="store_true", help="write the result to .git/repo-showcase/keywords.json")
    parser.set_defaults(func=_cmd_keywords)
