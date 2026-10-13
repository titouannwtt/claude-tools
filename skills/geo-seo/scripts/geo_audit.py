#!/usr/bin/env python3
"""geo_audit.py : audit en lecture seule du référencement (Google, Bing, assistants IA) d'un site.

Bibliothèque standard uniquement. Chaque sous-commande écrit du JSON sur stdout.

    python3 geo_audit.py doctor
    python3 geo_audit.py robots  https://exemple.org
    python3 geo_audit.py sitemap https://exemple.org/sitemap-index.xml
    python3 geo_audit.py page    https://exemple.org/une-page/
    python3 geo_audit.py bots    https://exemple.org/une-page/
    python3 geo_audit.py crawl   https://exemple.org --max 40

Codes de sortie : 0 succès, 2 arguments invalides, 4 réseau inaccessible, 1 erreur inattendue.
Le script ne modifie rien, n'envoie rien, ne contourne aucune protection.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

TIMEOUT = 15
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

# Jetons de robots IA et moteurs : (nom, user-agent complet, rôle).
AI_BOTS = {
    "GPTBot": ("Mozilla/5.0 (compatible; GPTBot/1.1; +https://openai.com/gptbot)", "entraînement OpenAI"),
    "OAI-SearchBot": ("Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)", "recherche ChatGPT"),
    "ChatGPT-User": ("Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)", "navigation à la demande ChatGPT"),
    "ClaudeBot": ("Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "entraînement Anthropic"),
    "Claude-SearchBot": ("Mozilla/5.0 (compatible; Claude-SearchBot/1.0)", "recherche Claude"),
    "Claude-User": ("Mozilla/5.0 (compatible; Claude-User/1.0)", "navigation à la demande Claude"),
    "PerplexityBot": ("Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "index Perplexity"),
    "Perplexity-User": ("Mozilla/5.0 (compatible; Perplexity-User/1.0)", "navigation à la demande Perplexity"),
    "Google-Extended": ("Mozilla/5.0 (compatible; Google-Extended)", "jeton Gemini (robots.txt seulement)"),
    "Googlebot": ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "Google Search, AI Overviews"),
    "Bingbot": ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "Bing, Copilot, ChatGPT search"),
    "Applebot": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (Applebot/0.1)", "Apple, Siri"),
    "Amazonbot": ("Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)", "Amazon, Alexa"),
    "Meta-ExternalAgent": ("meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", "Meta AI"),
    "MistralAI-User": ("Mozilla/5.0 (compatible; MistralAI-User/1.0)", "Le Chat Mistral"),
    "DuckAssistBot": ("Mozilla/5.0 (compatible; DuckAssistBot/1.0)", "DuckDuckGo AI"),
    "CCBot": ("CCBot/2.0 (https://commoncrawl.org/faq/)", "Common Crawl (corpus d'entraînement)"),
    "Bytespider": ("Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)", "ByteDance"),
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url: str, ua: str = BROWSER_UA, follow: bool = False, limit: int = 3_000_000):
    """Retourne (statut, en-têtes en minuscules, corps en octets, URL finale). Statut 0 si réseau KO."""
    seen = 0
    while True:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*", "Accept-Encoding": "gzip"})
        try:
            with _OPENER.open(req, timeout=TIMEOUT) as r:
                status, headers, body = r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(limit)
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, {k.lower(): v for k, v in e.headers.items()}, (e.read(limit) if e.fp else b"")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return 0, {}, str(e).encode(), url
        if headers.get("content-encoding") == "gzip":
            try:
                body = gzip.decompress(body)
            except OSError:
                pass
        if follow and status in (301, 302, 303, 307, 308) and seen < 5 and headers.get("location"):
            url = urllib.parse.urljoin(url, headers["location"])
            seen += 1
            continue
        return status, headers, body, url


def origin(url: str) -> str:
    p = urllib.parse.urlsplit(url if "//" in url else "https://" + url)
    return f"{p.scheme}://{p.netloc}"


# --------------------------------------------------------------------------- robots.txt
def parse_robots(text: str):
    """Retourne (groupes, sitemaps). groupes = liste de {agents:[...], rules:[(allow:bool, chemin)]}."""
    groups, sitemaps, cur, last_was_agent = [], [], None, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = (s.strip() for s in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if cur is None or not last_was_agent:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(v.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if k == "sitemap":
            sitemaps.append(v)
        elif k in ("allow", "disallow") and cur is not None:
            cur["rules"].append((k == "allow", v))
    return groups, sitemaps


def _match(pattern: str, path: str) -> bool:
    rx = re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def robots_allows(groups, agent: str, path: str) -> bool:
    """Règle la plus longue gagne, Allow l'emporte à égalité. Groupe le plus spécifique, sinon '*'."""
    agent = agent.lower()
    chosen = [g for g in groups if any(a != "*" and (a in agent or agent in a) for a in g["agents"])]
    if not chosen:
        chosen = [g for g in groups if "*" in g["agents"]]
    best = (-1, True)
    for g in chosen:
        for allow, pat in g["rules"]:
            if pat == "" and not allow:
                continue
            if _match(pat, path) and (len(pat) > best[0] or (len(pat) == best[0] and allow)):
                best = (len(pat), allow)
    return best[1]


def cmd_robots(args):
    base = origin(args.url)
    st, _, body, _ = fetch(base + "/robots.txt", follow=True)
    if st == 0:
        return 4, {"error": body.decode(errors="replace"), "url": base + "/robots.txt"}
    text = body.decode("utf-8", errors="replace") if st == 200 else ""
    groups, sitemaps = parse_robots(text)
    paths = args.path or ["/", "/blog/", "/app/"]
    access = {}
    for name in AI_BOTS:
        access[name] = {p: robots_allows(groups, name, p) for p in paths}
    notes = []
    if st != 200:
        notes.append(f"robots.txt répond {st} : tout est autorisé par défaut, mais aucun sitemap n'est déclaré")
    if not sitemaps:
        notes.append("aucun Sitemap: déclaré dans robots.txt")
    for sm in sitemaps:
        sp = urllib.parse.urlsplit(sm).path
        if not robots_allows(groups, "Googlebot", sp):
            notes.append(f"le sitemap {sm} est bloqué par un Disallow pour Googlebot")
    blocked = [n for n, r in access.items() if not r.get("/", True)]
    if blocked:
        notes.append("robots IA bloqués sur / : " + ", ".join(blocked))
    return 0, {"url": base + "/robots.txt", "status": st, "sitemaps": sitemaps, "access": access, "notes": notes}


# --------------------------------------------------------------------------- sitemap
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}


def parse_sitemap(xml: bytes):
    """Retourne ('index'|'urlset', entrées). Entrée = {loc, lastmod, alternates:[(hreflang, href)]}."""
    root = ET.fromstring(xml)
    kind = "index" if root.tag.endswith("sitemapindex") else "urlset"
    tag = "sitemap" if kind == "index" else "url"
    out = []
    for el in root.findall(f"s:{tag}", NS):
        loc = (el.findtext("s:loc", default="", namespaces=NS) or "").strip()
        lm = (el.findtext("s:lastmod", default="", namespaces=NS) or "").strip() or None
        alts = [(a.get("hreflang"), a.get("href")) for a in el.findall("x:link", NS) if a.get("rel") == "alternate"]
        out.append({"loc": loc, "lastmod": lm, "alternates": alts})
    return kind, out


def load_sitemap(url: str, depth: int = 0, cap: int = 60000):
    st, _, body, _ = fetch(url, follow=True, limit=60_000_000)
    if st != 200:
        return [], [{"url": url, "status": st}]
    try:
        kind, entries = parse_sitemap(body)
    except ET.ParseError as e:
        return [], [{"url": url, "error": f"XML invalide : {e}"}]
    if kind == "urlset":
        return entries[:cap], []
    urls, errors = [], []
    if depth >= 2:
        return urls, errors
    for e in entries:
        sub, err = load_sitemap(e["loc"], depth + 1, cap)
        urls += sub
        errors += err
    return urls[:cap], errors


def cmd_sitemap(args):
    url = args.url
    if not url.lower().endswith((".xml", ".xml.gz")):
        url = origin(url) + "/sitemap-index.xml"
    entries, errors = load_sitemap(url)
    if not entries and errors and errors[0].get("status") == 404 and "sitemap-index" in url:
        entries, errors = load_sitemap(origin(url) + "/sitemap.xml")
    langs = {}
    for e in entries:
        for hl, _ in e["alternates"]:
            langs[hl] = langs.get(hl, 0) + 1
    locs = [e["loc"] for e in entries]
    return 0, {
        "url": url,
        "urls": len(entries),
        "with_lastmod": sum(1 for e in entries if e["lastmod"]),
        "lastmod_distinct": len({e["lastmod"] for e in entries if e["lastmod"]}),
        "with_hreflang": sum(1 for e in entries if e["alternates"]),
        "hreflang_values": langs,
        "duplicates": len(locs) - len(set(locs)),
        "no_trailing_slash": sum(1 for u in locs if not urllib.parse.urlsplit(u).path.endswith("/")
                                  and "." not in urllib.parse.urlsplit(u).path.rsplit("/", 1)[-1]),
        "errors": errors,
        "sample": locs[:5],
    }


# --------------------------------------------------------------------------- page
class PageParser(HTMLParser):
    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.title = ""
        self.meta = {}
        self.links = []
        self.alternates = []
        self.canonical = None
        self.lang = None
        self.h1, self.jsonld = [], []
        self.text, self.paras = [], []
        self._stack, self._buf, self._skip = [], [], 0
        self.has_time = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "meta" and (a.get("name") or a.get("property")):
            self.meta[(a.get("name") or a.get("property")).lower()] = a.get("content", "")
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical = a.get("href")
            elif rel == "alternate" and a.get("hreflang"):
                self.alternates.append((a["hreflang"], a.get("href")))
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "time":
            self.has_time = True
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            self._buf = []
            self._ld = a.get("type") == "application/ld+json"
        if tag in ("title", "h1", "p"):
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            if tag == "script" and getattr(self, "_ld", False):
                self.jsonld.append("".join(self._buf))
                self._ld = False
            self._skip = max(0, self._skip - 1)
            self._buf = []
        elif tag == "title":
            self.title = "".join(self._buf).strip()
        elif tag == "h1":
            self.h1.append(" ".join("".join(self._buf).split()))
        elif tag == "p":
            t = " ".join("".join(self._buf).split())
            if t:
                self.paras.append(t)
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data):
        self._buf.append(data)
        if not self._skip:
            self.text.append(data)


def jsonld_types(blocks):
    types, ids, same_as, errors = [], 0, 0, 0
    def walk(o):
        nonlocal ids, same_as
        if isinstance(o, list):
            for i in o:
                walk(i)
        elif isinstance(o, dict):
            t = o.get("@type")
            if t:
                types.extend(t if isinstance(t, list) else [t])
            if "@id" in o:
                ids += 1
            if "sameAs" in o:
                same_as += 1
            for v in o.values():
                walk(v)
    for b in blocks:
        try:
            walk(json.loads(b))
        except (ValueError, TypeError):
            errors += 1
    return {"types": sorted(set(types)), "with_id": ids, "with_sameas": same_as, "invalid_blocks": errors}


def analyse_html(html: str, url: str, ignore: tuple = ()) -> dict:
    p = PageParser(url)
    p.feed(html)
    words = len(re.findall(r"\w+", " ".join(p.text)))
    host = urllib.parse.urlsplit(url).netloc
    internal, no_slash, examples = 0, 0, []
    for h in p.links:
        u = urllib.parse.urlsplit(urllib.parse.urljoin(url, h))
        if u.netloc != host or u.scheme not in ("http", "https"):
            continue
        internal += 1
        last = u.path.rsplit("/", 1)[-1]
        if u.path and not u.path.endswith("/") and "." not in last and not u.path.startswith(ignore):
            no_slash += 1
            if len(examples) < 3 and u.path not in examples:
                examples.append(u.path)
    desc = p.meta.get("description", "")
    first = next((x for x in p.paras if len(x.split()) >= 12), "")
    issues = []
    if not p.title:
        issues.append("titre absent")
    elif len(p.title) > 65:
        issues.append(f"titre long ({len(p.title)} caractères)")
    if not desc:
        issues.append("meta description absente")
    elif len(desc) > 160:
        issues.append(f"description longue ({len(desc)} caractères)")
    if not p.canonical:
        issues.append("canonical absent")
    if len(p.h1) != 1:
        issues.append(f"{len(p.h1)} balises h1")
    if words < 300:
        issues.append(f"contenu mince ({words} mots visibles)")
    if no_slash:
        issues.append(f"{no_slash} liens internes sans slash final (redirection probable)")
    ld = jsonld_types(p.jsonld)
    if not ld["types"]:
        issues.append("aucune donnée structurée")
    if "noindex" in p.meta.get("robots", "").lower():
        issues.append("noindex")
    return {
        "url": url, "lang": p.lang, "title": p.title, "title_len": len(p.title),
        "description_len": len(desc), "canonical": p.canonical,
        "canonical_matches": bool(p.canonical) and urllib.parse.urljoin(url, p.canonical).rstrip("/") == url.rstrip("/"),
        "robots_meta": p.meta.get("robots"), "h1": p.h1, "visible_words": words,
        "hreflang": len(p.alternates), "jsonld": ld, "internal_links": internal,
        "internal_links_without_slash": no_slash, "no_slash_examples": examples, "has_time_element": p.has_time,
        "first_paragraph_words": len(first.split()), "og_image": bool(p.meta.get("og:image")),
        "issues": issues,
    }


def cmd_page(args):
    st, headers, body, final = fetch(args.url, follow=True)
    if st == 0:
        return 4, {"error": body.decode(errors="replace"), "url": args.url}
    out = analyse_html(body.decode("utf-8", errors="replace"), final, tuple(args.ignore_prefix or ()))
    out["status"] = st
    out["x_robots_tag"] = headers.get("x-robots-tag")
    if final != args.url:
        out["redirected_from"] = args.url
    return 0, out


def cmd_bots(args):
    res, base = {}, None
    for name, (ua, role) in AI_BOTS.items():
        st, headers, body, _ = fetch(args.url, ua=ua)
        res[name] = {"status": st, "role": role, "x_robots_tag": headers.get("x-robots-tag")}
        if st == 200 and base is None:
            base = len(body)
        if st == 200 and base and abs(len(body) - base) > base * 0.5:
            res[name]["note"] = "taille de réponse très différente : contenu servi différemment aux robots ?"
    if all(r["status"] == 0 for r in res.values()):
        return 4, {"error": "réseau inaccessible", "url": args.url}
    refused = [n for n, r in res.items() if r["status"] not in (200, 301, 302, 308)]
    return 0, {"url": args.url, "results": res, "refused": refused}


def cmd_crawl(args):
    entries, errors = load_sitemap(origin(args.url) + "/sitemap-index.xml")
    if not entries:
        entries, errors = load_sitemap(origin(args.url) + "/sitemap.xml")
    if not entries:
        return 0, {"error": "aucun sitemap lisible", "details": errors}
    step = max(1, len(entries) // args.max)
    sample = [e["loc"] for e in entries[::step]][: args.max]
    pages, titles, issues = [], {}, {}
    for u in sample:
        st, _, body, final = fetch(u, follow=True)
        if st != 200:
            pages.append({"url": u, "status": st})
            issues.setdefault(f"statut {st}", []).append(u)
            continue
        r = analyse_html(body.decode("utf-8", errors="replace"), final, tuple(args.ignore_prefix or ()))
        titles.setdefault(r["title"], []).append(u)
        for i in r["issues"]:
            issues.setdefault(re.sub(r"\d+", "N", i), []).append(u)
        pages.append({"url": u, "words": r["visible_words"], "title_len": r["title_len"], "issues": r["issues"]})
    dups = {t: us for t, us in titles.items() if t and len(us) > 1}
    return 0, {
        "sitemap_urls": len(entries), "sampled": len(sample),
        "issues_summary": {k: len(v) for k, v in sorted(issues.items(), key=lambda kv: -len(kv[1]))},
        "issues_examples": {k: v[:3] for k, v in issues.items()},
        "duplicate_titles": dups, "pages": pages,
    }


def cmd_doctor(_):
    ok = sys.version_info >= (3, 8)
    st, _, _, _ = fetch("https://example.com/")
    return (0 if ok else 1), {"python": sys.version.split()[0], "python_ok": ok, "network": st == 200, "dependencies": "aucune (stdlib)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    for name in ("robots", "sitemap", "page", "bots", "crawl"):
        p = sub.add_parser(name)
        p.add_argument("url")
        if name in ("page", "crawl"):
            p.add_argument("--ignore-prefix", action="append", help="préfixe de chemin à ignorer pour le contrôle du slash final (ex. /app/ : routes d'une application)")
        if name == "robots":
            p.add_argument("--path", action="append", help="chemin à tester pour chaque robot (répétable)")
        if name == "crawl":
            p.add_argument("--max", type=int, default=40)
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    fn = {"doctor": cmd_doctor, "robots": cmd_robots, "sitemap": cmd_sitemap,
          "page": cmd_page, "bots": cmd_bots, "crawl": cmd_crawl}[args.cmd]
    try:
        code, out = fn(args)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
