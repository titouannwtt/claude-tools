#!/usr/bin/env python3
"""Analyse du design d'un site avec Playwright : captures responsives, palette, typographie, espacements.

Commandes :
  analyze <url> [--out D] [--widths 375,768,1280] [--dark] [--use-proxy]
      écrit dans D : shot-<largeur>.png, design.json (mesures complètes), summary.md (synthèse à lire)
  doctor     vérifie Playwright et le navigateur Chromium

Le script charge la page dans un vrai navigateur (le JavaScript de la page s'exécute) puis mesure les styles
calculés des éléments visibles : le résultat décrit ce qui s'affiche, pas ce qui est écrit dans les feuilles de style.
Dépendances : playwright (pip) et `playwright install chromium`. Sur le Mac, bascule automatique vers l'environnement
~/.venvs/site-design s'il existe. Proxy : seulement avec --use-proxy (clé IPROYAL_RESIDENTIAL_URL de local.env).

Sortie : JSON sur stdout. Codes : 0 succès ; 1 erreur inattendue ; 2 URL invalide ; 4 page bloquée (403, 429) ;
5 dépendance manquante ; 7 page injoignable.
Python 3.9 compatible.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import cttools  # noqa: E402

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID, EXIT_BLOCKED, EXIT_MISSING, EXIT_NETWORK = 0, 1, 2, 4, 5, 7
VENV_PYTHON = Path.home() / ".venvs" / "site-design" / "bin" / "python"
MAX_SHOT_HEIGHT = 10000
COLOR_RE = re.compile(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+))?\s*\)")

EXTRACT_JS = r"""
() => {
  const count = (map, key) => { if (key) map[key] = (map[key] || 0) + 1; };
  const px = v => { const n = parseFloat(v); return isNaN(n) ? 0 : Math.round(n * 10) / 10; };
  const visible = el => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const hasText = el => Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
  const els = Array.from(document.querySelectorAll('body *')).filter(visible).slice(0, 3000);
  const colors = {}, backgrounds = {}, borders = {}, sizes = {}, families = {}, radii = {}, shadows = {}, spacing = {};
  let flex = 0, grid = 0;
  for (const el of els) {
    const cs = getComputedStyle(el);
    if (hasText(el)) { count(colors, cs.color); count(sizes, cs.fontSize); count(families, cs.fontFamily); }
    if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)') count(backgrounds, cs.backgroundColor);
    if (px(cs.borderTopWidth) > 0) count(borders, cs.borderTopColor);
    if (px(cs.borderTopLeftRadius) > 0) count(radii, cs.borderTopLeftRadius);
    if (cs.boxShadow && cs.boxShadow !== 'none') count(shadows, cs.boxShadow);
    if (cs.display.includes('flex')) flex++;
    if (cs.display.includes('grid')) grid++;
    for (const p of ['paddingTop', 'paddingLeft', 'marginTop', 'marginBottom', 'rowGap', 'columnGap']) {
      const v = px(cs[p]); if (v > 0) count(spacing, v + 'px');
    }
  }
  const style = el => { const cs = getComputedStyle(el); return {
    fontFamily: cs.fontFamily, fontSize: cs.fontSize, fontWeight: cs.fontWeight, lineHeight: cs.lineHeight,
    letterSpacing: cs.letterSpacing, color: cs.color, background: cs.backgroundColor, radius: cs.borderTopLeftRadius,
    padding: cs.padding, textTransform: cs.textTransform }; };
  const samples = {};
  for (const sel of ['body', 'h1', 'h2', 'h3', 'p', 'a', 'button', 'nav a', 'input', 'label', 'small', 'blockquote']) {
    const el = Array.from(document.querySelectorAll(sel)).find(visible);
    if (el) samples[sel] = style(el);
  }
  const variables = {}, breakpoints = new Set();
  let darkMode = false;
  const walk = rules => { for (const rule of rules) {
    if (rule.media) {
      const text = rule.media.mediaText || '';
      if (/prefers-color-scheme\s*:\s*dark/.test(text)) darkMode = true;
      for (const m of text.matchAll(/(min|max)-width\s*:\s*([\d.]+)(px|em|rem)/g))
        breakpoints.add(m[1] + ' ' + (m[3] === 'px' ? m[2] : m[2] * 16) + 'px');
      walk(rule.cssRules);
    } else if (rule.style && /(^|,)\s*(:root|html)\s*(,|$)/.test(rule.selectorText || '')) {
      for (const name of Array.from(rule.style)) if (name.startsWith('--'))
        variables[name] = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    } else if (rule.cssRules) walk(rule.cssRules);
  } };
  for (const sheet of Array.from(document.styleSheets)) { try { walk(sheet.cssRules); } catch (e) { /* feuille tierce */ } }
  const metaContent = n => { const m = document.querySelector('meta[name="' + n + '"], meta[property="' + n + '"]');
    return m ? m.content : null; };
  const icon = document.querySelector('link[rel~="icon"]');
  const fonts = Array.from(document.fonts).map(f => ({ family: f.family.replace(/"/g, ''), weight: f.weight,
    style: f.style, status: f.status }));
  const headings = Array.from(document.querySelectorAll('h1, h2, h3')).filter(visible).slice(0, 12)
    .map(h => h.tagName.toLowerCase() + ': ' + h.textContent.trim().replace(/\s+/g, ' ').slice(0, 80));
  const imgs = Array.from(document.images);
  return { meta: { title: document.title, lang: document.documentElement.lang || null,
      description: metaContent('description'), themeColor: metaContent('theme-color'), viewport: metaContent('viewport'),
      ogImage: metaContent('og:image'), favicon: icon ? icon.href : null },
    counts: { elements: els.length, flex, grid, images: imgs.length, imagesWithoutAlt: imgs.filter(i => !i.alt).length },
    colors, backgrounds, borders, sizes, families, radii, shadows, spacing, samples, variables,
    breakpoints: Array.from(breakpoints), darkMode, fonts, headings,
    stylesheets: Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href).slice(0, 15),
    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
    pageHeight: document.documentElement.scrollHeight };
}
"""


class Failure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def to_hex(value):
    """'rgb(10, 20, 30)' -> '#0a141e' ; avec transparence : '#0a141e80' ; autre valeur : inchangée."""
    match = COLOR_RE.search(value or "")
    if not match:
        return value
    red, green, blue = (int(match.group(i)) for i in (1, 2, 3))
    text = "#%02x%02x%02x" % (red, green, blue)
    if match.group(4) is not None and float(match.group(4)) < 1:
        text += "%02x" % round(float(match.group(4)) * 255)
    return text


def top(counter, limit=10, convert=None):
    """[{value, count}] triés par fréquence décroissante ; regroupe les valeurs identiques après conversion."""
    merged = {}
    for key, number in counter.items():
        label = convert(key) if convert else key
        merged[label] = merged.get(label, 0) + number
    ordered = sorted(merged.items(), key=lambda item: (-item[1], str(item[0])))
    return [{"value": value, "count": number} for value, number in ordered[:limit]]


def first_family(stack):
    return (stack or "").split(",")[0].strip().strip("\"'")


def summarize(raw):
    """Données brutes du navigateur -> structure lisible (palette en hex, polices, échelle de tailles)."""
    sizes = sorted(raw["sizes"].items(), key=lambda item: float(item[0].replace("px", "")))
    families = {}
    for stack, number in raw["families"].items():
        name = first_family(stack)
        families[name] = families.get(name, 0) + number
    return {
        "meta": raw["meta"],
        "counts": raw["counts"],
        "palette": {
            "text": top(raw["colors"], 8, to_hex),
            "backgrounds": top(raw["backgrounds"], 8, to_hex),
            "borders": top(raw["borders"], 5, to_hex),
        },
        "typography": {
            "families": top(families, 5),
            "sizes": [{"value": key, "count": number} for key, number in sizes],
            "samples": {sel: dict(style, color=to_hex(style["color"]), background=to_hex(style["background"]))
                        for sel, style in raw["samples"].items()},
            "fonts_loaded": sorted({"%s %s" % (f["family"], f["weight"]) for f in raw["fonts"]
                                    if f["status"] == "loaded"}),
        },
        "spacing": top(raw["spacing"], 10),
        "radii": top(raw["radii"], 5),
        "shadows": top(raw["shadows"], 3),
        "css_variables": raw["variables"],
        "breakpoints": sorted(raw["breakpoints"]),
        "dark_mode_in_css": raw["darkMode"],
        "headings": raw["headings"],
        "stylesheets": raw["stylesheets"],
    }


def render_markdown(url, summary, shots, overflow):
    lines = ["# Design de %s" % url, ""]
    meta = summary["meta"]
    lines += ["- Titre : %s" % meta.get("title"), "- Langue : %s" % meta.get("lang"),
              "- Couleur de thème : %s" % meta.get("themeColor"),
              "- Éléments visibles analysés : %d (flex %d, grid %d)" % (
                  summary["counts"]["elements"], summary["counts"]["flex"], summary["counts"]["grid"]),
              "- Images sans texte alternatif : %d sur %d" % (
                  summary["counts"]["imagesWithoutAlt"], summary["counts"]["images"]), ""]

    def row(items):
        return ", ".join("%s (%d)" % (i["value"], i["count"]) for i in items) or "aucune"
    lines += ["## Palette", "- Texte : " + row(summary["palette"]["text"]),
              "- Fonds : " + row(summary["palette"]["backgrounds"]),
              "- Bordures : " + row(summary["palette"]["borders"]), ""]
    typo = summary["typography"]
    lines += ["## Typographie", "- Familles : " + row(typo["families"]),
              "- Tailles (px, du plus petit au plus grand) : " + row(typo["sizes"]),
              "- Polices chargées : " + (", ".join(typo["fonts_loaded"]) or "aucune (polices système)"), ""]
    for sel, style in typo["samples"].items():
        lines.append("- `%s` : %s %s/%s, graisse %s, couleur %s" % (
            sel, first_family(style["fontFamily"]), style["fontSize"], style["lineHeight"], style["fontWeight"],
            style["color"]))
    lines += ["", "## Espacements, formes",
              "- Espacements les plus fréquents : " + row(summary["spacing"]),
              "- Rayons de bordure : " + row(summary["radii"]),
              "- Ombres : " + row(summary["shadows"]), ""]
    variables = summary["css_variables"]
    lines += ["## Variables CSS (%d)" % len(variables)]
    lines += ["- `%s` : %s" % (name, value) for name, value in list(variables.items())[:40]] or ["- aucune"]
    lines += ["", "## Responsive",
              "- Points de rupture dans le CSS : " + (", ".join(summary["breakpoints"]) or "aucun trouvé"),
              "- Mode sombre prévu dans le CSS : %s" % ("oui" if summary["dark_mode_in_css"] else "non")]
    lines += ["- Défilement horizontal à %s px : %s" % (width, "OUI (défaut)" if bad else "non")
              for width, bad in overflow.items()]
    lines += ["", "## Structure des titres"] + ["- " + h for h in summary["headings"]]
    lines += ["", "## Captures"] + ["- %s" % shot for shot in shots]
    return "\n".join(lines) + "\n"


def parse_proxy(url):
    """URL de proxy -> dict accepté par Playwright (server, username, password)."""
    parsed = urlparse(url)
    if not parsed.hostname:
        raise Failure(EXIT_INVALID, "adresse de proxy illisible")
    proxy = {"server": "%s://%s:%s" % (parsed.scheme or "http", parsed.hostname, parsed.port or 80)}
    if parsed.username:
        proxy["username"] = parsed.username
        proxy["password"] = parsed.password or ""
    return proxy


def load_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        if VENV_PYTHON.exists() and Path(sys.prefix) != VENV_PYTHON.parents[1] \
                and not os.environ.get("SITE_DESIGN_NO_REEXEC"):
            os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)
        raise Failure(EXIT_MISSING, "playwright introuvable : python3 -m venv ~/.venvs/site-design && "
                                    "~/.venvs/site-design/bin/pip install playwright && "
                                    "~/.venvs/site-design/bin/playwright install chromium")


def analyze(url, out_dir, widths, dark, proxy, local_env=None):
    if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
        raise Failure(EXIT_INVALID, "URL http(s) attendue : %s" % url)
    sync_playwright = load_playwright()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shots, overflow, raw = [], {}, None
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(proxy=parse_proxy(proxy) if proxy else None)
        except Exception as error:  # noqa: BLE001
            if "Executable doesn't exist" in str(error):
                raise Failure(EXIT_MISSING, "Chromium absent : playwright install chromium")
            raise
        try:
            for width in widths:
                context = browser.new_context(viewport={"width": width, "height": 900},
                                              color_scheme="dark" if dark and width == widths[-1] else "light")
                page = context.new_page()
                try:
                    response = page.goto(url, wait_until="load", timeout=30000)
                except Exception as error:  # noqa: BLE001
                    raise Failure(EXIT_NETWORK, "page injoignable : %s" % str(error).splitlines()[0])
                if response is not None and response.status in (403, 429):
                    raise Failure(EXIT_BLOCKED, "page bloquée : HTTP %d" % response.status)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(500)
                data = page.evaluate(EXTRACT_JS)
                overflow[width] = data["overflowX"]
                height = min(int(data["pageHeight"]), MAX_SHOT_HEIGHT)
                name = "shot-%d%s.png" % (width, "-dark" if dark and width == widths[-1] else "")
                page.screenshot(path=str(out / name), full_page=True,
                                clip={"x": 0, "y": 0, "width": width, "height": height})
                shots.append(name)
                if width == widths[-1]:
                    raw = data
                context.close()
        finally:
            browser.close()
    summary = summarize(raw)
    (out / "design.json").write_text(json.dumps({"url": url, "summary": summary, "overflow": overflow},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "summary.md").write_text(render_markdown(url, summary, shots, overflow), encoding="utf-8")
    return {"out": str(out), "screenshots": shots, "summary": str(out / "summary.md"),
            "design": str(out / "design.json"), "overflow_x": overflow}


def doctor():
    info = {"python": sys.version.split()[0]}
    try:
        sync_playwright = load_playwright()
        info["playwright"] = True
        with sync_playwright() as pw:
            info["chromium"] = os.path.exists(pw.chromium.executable_path)
    except Failure as failure:
        info["playwright"] = False
        info["error"] = failure.message
    info["proxy_configured"] = bool(cttools.configured_proxy())
    return info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("analyze")
    item.add_argument("url")
    item.add_argument("--out", default="./site-design")
    item.add_argument("--widths", default="375,768,1280")
    item.add_argument("--dark", action="store_true", help="capture aussi la plus grande largeur en mode sombre")
    item.add_argument("--use-proxy", action="store_true")
    item.add_argument("--local-env", default=None)
    sub.add_parser("doctor")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        else:
            try:
                widths = [int(w) for w in args.widths.split(",") if w.strip()]
            except ValueError:
                raise Failure(EXIT_INVALID, "--widths attend des entiers séparés par des virgules")
            proxy = None
            if args.use_proxy:
                proxy = cttools.configured_proxy(args.local_env)
                if not proxy:
                    raise Failure(EXIT_MISSING, "IPROYAL_RESIDENTIAL_URL absent de local.env : proxy impossible")
            result = analyze(args.url, args.out, sorted(widths), args.dark, proxy, args.local_env)
    except Failure as failure:
        print(json.dumps({"error": failure.message}, ensure_ascii=False))
        return failure.code
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"error": "erreur inattendue : %s" % error}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
