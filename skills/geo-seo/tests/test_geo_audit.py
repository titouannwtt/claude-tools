import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import geo_audit as g  # noqa: E402

ROBOTS = """
User-agent: *
Disallow: /app/
Allow: /app/sitemap-convert.xml

User-agent: GPTBot
Allow: /
Disallow: /app/
Allow: /app/sitemap-convert.xml

User-agent: Bytespider
Disallow: /

Sitemap: https://exemple.org/sitemap-index.xml
"""

SITEMAP = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
<url><loc>https://exemple.org/fr/a/</loc><lastmod>2026-10-10</lastmod>
<xhtml:link rel="alternate" hreflang="fr" href="https://exemple.org/fr/a/"/>
<xhtml:link rel="alternate" hreflang="en" href="https://exemple.org/a/"/></url>
<url><loc>https://exemple.org/b</loc></url>
</urlset>"""

HTML = """<!doctype html><html lang="fr"><head><title>Accordeur en ligne</title>
<meta name="description" content="Un accordeur gratuit.">
<link rel="canonical" href="https://exemple.org/fr/a/">
<link rel="alternate" hreflang="en" href="https://exemple.org/a/">
<script type="application/ld+json">{"@graph":[{"@type":"Organization","@id":"#o","sameAs":["https://x.org"]},{"@type":"WebPage"}]}</script>
<script>var x = "pas du texte visible";</script></head>
<body><h1>Accordeur</h1><p>Un accordeur en ligne qui entend la guitare, la basse et le ukulélé, sans installer d'application ni créer de compte.</p>
<time datetime="2026-10-10">10 octobre</time>
<a href="/fr/b">sans slash</a><a href="/fr/c/">avec slash</a><a href="/file.pdf">pdf</a><a href="https://autre.org/x">externe</a>
</body></html>"""


class RobotsTests(unittest.TestCase):
    def setUp(self):
        self.groups, self.sitemaps = g.parse_robots(ROBOTS)

    def test_sitemaps(self):
        self.assertEqual(self.sitemaps, ["https://exemple.org/sitemap-index.xml"])

    def test_disallow_and_exception(self):
        self.assertFalse(g.robots_allows(self.groups, "ClaudeBot", "/app/x"))
        self.assertTrue(g.robots_allows(self.groups, "ClaudeBot", "/app/sitemap-convert.xml"))

    def test_specific_group(self):
        self.assertTrue(g.robots_allows(self.groups, "GPTBot", "/blog/"))
        self.assertFalse(g.robots_allows(self.groups, "Bytespider", "/"))


class SitemapTests(unittest.TestCase):
    def test_urlset(self):
        kind, entries = g.parse_sitemap(SITEMAP)
        self.assertEqual(kind, "urlset")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["lastmod"], "2026-10-10")
        self.assertEqual(len(entries[0]["alternates"]), 2)
        self.assertIsNone(entries[1]["lastmod"])

    def test_index(self):
        xml = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://e.org/s0.xml</loc></sitemap></sitemapindex>'
        kind, entries = g.parse_sitemap(xml)
        self.assertEqual((kind, entries[0]["loc"]), ("index", "https://e.org/s0.xml"))


class PageTests(unittest.TestCase):
    def setUp(self):
        self.r = g.analyse_html(HTML, "https://exemple.org/fr/a/")

    def test_fields(self):
        self.assertEqual(self.r["title"], "Accordeur en ligne")
        self.assertEqual(self.r["lang"], "fr")
        self.assertTrue(self.r["canonical_matches"])
        self.assertEqual(self.r["h1"], ["Accordeur"])
        self.assertTrue(self.r["has_time_element"])
        self.assertEqual(self.r["hreflang"], 1)

    def test_links(self):
        self.assertEqual(self.r["internal_links"], 3)
        self.assertEqual(self.r["internal_links_without_slash"], 1)

    def test_jsonld(self):
        ld = self.r["jsonld"]
        self.assertIn("Organization", ld["types"])
        self.assertEqual(ld["with_id"], 1)
        self.assertEqual(ld["with_sameas"], 1)

    def test_visible_text_without_script(self):
        self.assertLess(self.r["visible_words"], 60)
        self.assertTrue(any("thin content" in i for i in self.r["issues"]))

    def test_cli_args(self):
        self.assertEqual(g.main(["page"]), 2)


if __name__ == "__main__":
    unittest.main()


class SoumissionTests(unittest.TestCase):
    def test_jwt_assertion(self):
        import base64
        import json as j
        import gsc_submit as s
        a = s.build_assertion({"client_email": "sa@x.iam", "token_uri": "https://t"}, 1000, lambda d: b"SIG")  # check-repo: ignore (fake test address)
        h, c, sig = a.split(".")
        pad = lambda x: x + "=" * (-len(x) % 4)
        self.assertEqual(j.loads(base64.urlsafe_b64decode(pad(h)))["alg"], "RS256")
        cl = j.loads(base64.urlsafe_b64decode(pad(c)))
        self.assertEqual((cl["iss"], cl["iat"], cl["exp"]), ("sa@x.iam", 1000, 4600))  # check-repo: ignore (fake test address)
        self.assertEqual(base64.urlsafe_b64decode(pad(sig)), b"SIG")

    def test_indexnow_sitemap(self):
        import indexnow as n
        self.assertEqual(n.urls_from_sitemap("<url><loc> https://e.org/a/ </loc></url><loc>https://e.org/b/</loc>"),
                         ["https://e.org/a/", "https://e.org/b/"])

    def test_missing_configuration(self):
        import indexnow as n
        old = os.environ.pop("INDEXNOW_KEY", None)
        try:
            self.assertEqual(n.main(["--host", "e.org", "--url", "https://e.org/a/"]), 2)
        finally:
            if old:
                os.environ["INDEXNOW_KEY"] = old
