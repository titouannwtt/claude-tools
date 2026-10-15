import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "promo.py"
sys.path.insert(0, str(SCRIPT.parent))
import promo  # noqa: E402

TODAY = date(2026, 10, 15)
NAMES = promo.merchant_names("Notion", "notion.so")

DDG_HTML = """<html><body>
<div class="result results_links"><h2 class="result__title">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fblog.example.org%2Fnotion-tips&amp;rut=abc">Notion tips</a></h2>
<a class="result__snippet" href="x">Use code <b>NOTIONFR15</b> for 15% off Notion at checkout.</a></div>
<div class="result result--ad"><a class="result__a" href="//duckduckgo.com/y.js?ad_domain=x">Ad</a></div>
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.dealabs.com%2Fbons-plans%2Fnotion">Dealabs Notion</a>
<a class="result__snippet" href="y">Code promo NOTION50 pour 50% de reduction sur Notion</a></div>
</body></html>"""

BING_HTML = """<html><body><ol id="b_results">
<li class="b_algo"><h2><a href="https://forum.example.net/t/1">Notion discount thread</a></h2>
<div class="b_caption"><p>The Notion promo code WELCOME30 gives 30% off for new users</p></div></li>
<li class="b_ad"><h2><a href="https://ads.example.com/">Ad</a></h2><p>promo code ADCODE99</p></li>
</ol></body></html>"""

HN_JSON = json.dumps({"hits": [
    {"objectID": "111", "title": "Ask HN: Notion discounts?", "created_at": "2026-09-20T10:00:00Z",
     "story_text": None, "comment_text": None},
    {"objectID": "222", "story_title": "Ask HN: Notion discounts?", "created_at": "2026-10-01T08:00:00Z",
     "comment_text": "<p>Notion gives a student plan, also try code <i>HNSAVE25</i> for 25% off.</p>"}]})

YT_ENTRIES = [
    {"id": "abc123def45", "title": "Notion code promo 2026", "channel": "Creator One",
     "url": "https://www.youtube.com/watch?v=abc123def45",
     "description": "Utilise le code NOTIONFR15 pour 15% de reduction sur Notion"},
    {"id": "zzz123def45", "title": "Notion avis", "channel": "Creator Two",
     "url": "https://www.youtube.com/watch?v=zzz123def45",
     "description": "Mon code promo Notion : NOTIONFR15 (15% de reduction)"},
    {"id": "off00000000", "title": "Cooking pasta", "channel": "Chef", "url": "https://www.youtube.com/watch?v=off00000000",
     "description": "Use code PASTA20 for 20% off"},
]

ROBOTS = "User-agent: *\nDisallow: /partners\n"
PRICING = ("<html><head><script>var x='CODE0000'</script></head><body><h1>Pricing</h1>"
           "<p>Save 20% with annual billing.</p><p>Free trial for 14 days.</p>"
           "<p>Use code OFFICIAL10 for 10% off your first order.</p></body></html>")
STUDENTS = "<html><body><h1>Students</h1><p>Students and educators get the Plus plan for free.</p></body></html>"


def fake_http(routes):
    """http_get replacement: routes maps a URL substring to (status, text) or an exception."""
    calls = []

    def get(url, timeout=promo.TIMEOUT):
        calls.append(url)
        for fragment, answer in routes.items():
            if fragment in url:
                if isinstance(answer, Exception):
                    raise answer
                return promo.Response(answer[0], answer[1], answer[2] if len(answer) > 2 else url)
        return promo.Response(404, "", url)

    get.calls = calls
    return get


def opts(**kwargs):
    base = dict(merchant="Notion", domain=None, product="", lang="en", max=10, no_youtube=True, no_web=True,
                no_hn=True, github=False)
    base.update(kwargs)
    return SimpleNamespace(**base)


class PromoCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(promo, "HOST_DELAY", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_find(self, routes, ytdlp=None, **kwargs):
        ytdlp = ytdlp or (lambda query, count: [])
        with mock.patch.object(promo, "http_get", fake_http(routes)), \
                mock.patch.object(promo, "run_ytdlp", ytdlp):
            return promo.run_find(opts(**kwargs), today=TODAY)


class ExtractionTests(PromoCase):
    def codes(self, text, names=NAMES):
        return [m["code"] for m in promo.extract_from_text(text, names)]

    def test_positive_cases(self):
        self.assertEqual(self.codes("Use code SAVE10 at checkout"), ["SAVE10"])
        self.assertEqual(self.codes("Utilise le code NOTION20 pour une reduction"), ["NOTION20"])
        self.assertEqual(self.codes("Code promo : BIENVENUE pour 15 % de reduction"), ["BIENVENUE"])
        self.assertEqual(self.codes("use STUDENT-2X to get 20% off"), ["STUDENT-2X"])
        self.assertEqual(self.codes("code_createur: MY_CODE7"), ["MY_CODE7"])

    def test_length_bounds(self):
        self.assertEqual(self.codes("use code AB1 now"), [])
        self.assertEqual(self.codes("use code AB12 now"), ["AB12"])
        self.assertEqual(self.codes("use code " + "A1" * 10 + " now"), ["A1" * 10])
        self.assertEqual(self.codes("use code " + "A1" * 11 + " now"), [])
        self.assertEqual(self.codes("promo code 123456"), [])

    def test_requires_a_trigger_nearby(self):
        self.assertEqual(self.codes("Meeting room ZX99 booked"), [])
        far = "use code " + "x" * 70 + " SAVE10"
        self.assertEqual(self.codes(far), [])

    def test_rejections_are_counted(self):
        counts = Counter()
        samples = ["Use code https://shop.example.com/?code=ABC123", "promo #SUMMER20", "promo @DEAL42",
                   "promo code FREE", "promo code NOTION", "promo at 12:30PM", "promo code 1080P"]
        for text in samples:
            self.assertEqual(promo.extract_from_text(text, NAMES, counts), [], text)
        for reason in ("url", "hashtag", "handle", "stopword", "merchant_name", "timestamp", "unit"):
            self.assertGreaterEqual(counts[reason], 1, reason)

    def test_year_rejects_only_pure_years(self):
        self.assertTrue(promo.YEAR_RE.match("2026"))
        self.assertTrue(promo.YEAR_RE.match("1999"))
        for code in ("BF2025", "CM2025", "NY2026"):
            self.assertFalse(promo.YEAR_RE.match(code), code)
            self.assertEqual(self.codes("use code %s today" % code), [code])
        counts = Counter()
        self.assertEqual(promo.extract_from_text("promo code FREE SALE TODAY", NAMES, counts), [])
        self.assertGreaterEqual(counts["stopword"], 3)

    def test_letters_only_token_needs_direct_context(self):
        self.assertEqual(self.codes("Get 20% off with ANNUAL billing"), [])
        self.assertEqual(self.codes("code: WELCOME"), ["WELCOME"])

    def test_discount_parsing(self):
        def discount(text):
            return promo.extract_from_text(text, NAMES)[0]["discount"]

        self.assertEqual(discount("code SAVE10 for 20% off")["label"], "20 %")
        self.assertEqual(discount("code SAVE10 gives 10 € de reduction"),
                         {"type": "amount", "value": 10, "currency": "EUR", "label": "10 EUR"})
        self.assertEqual(discount("code SAVE10: $15 off")["currency"], "USD")
        self.assertEqual(discount("code SAVE10 = 2 months free")["type"], "free_month")
        self.assertEqual(discount("code SAVE10 gives 1 mois offert")["value"], 1)
        # a price is not a discount
        self.assertIsNone(discount("code SAVE10, plan from $12 per month"))
        self.assertIsNone(discount("code SAVE10 only"))

    def test_condition_parsing(self):
        found = promo.extract_from_text("Use code SAVE10, nouveaux clients, sur abonnement annuel, minimum 50 €",
                                        NAMES)[0]["conditions"]
        self.assertEqual(found, ["new customers only", "annual plan", "minimum spend", "subscription only"])
        english = promo.extract_from_text("Code SAVE10 for new customers on the first order", NAMES)
        self.assertEqual(english[0]["conditions"], ["new customers only"])

    def test_code_of_another_product_is_dropped_with_an_anchor(self):
        text = "Notion is great. " + "filler " * 50 + "Other tool: use code OTHER50 for 50% off"
        counts = Counter()
        self.assertEqual(promo.extract_from_text(text, NAMES, counts, anchor="notion"), [])
        self.assertEqual(counts["unrelated_product"], 1)
        near = "Notion plus: use code NOTION50 for 50% off"
        self.assertEqual([m["code"] for m in promo.extract_from_text(near, NAMES, anchor="notion")], ["NOTION50"])
        by_title = promo.extract_from_text("Use code LONGER50 now", NAMES, anchor="notion", title="Notion deal")
        self.assertEqual(len(by_title), 1)

    def test_excerpt_contains_code_and_is_short(self):
        text = "intro " * 40 + "use code SAVE10 now " + "outro " * 40
        mention = promo.extract_from_text(text, NAMES)[0]
        self.assertIn("SAVE10", mention["excerpt"])
        self.assertLessEqual(len(mention["excerpt"]), promo.EXCERPT_LENGTH)

    def test_verbatim_rule(self):
        self.assertTrue(promo.is_verbatim("SAVE10", "use code SAVE10"))
        self.assertFalse(promo.is_verbatim("SAVE11", "use code SAVE10"))
        self.assertFalse(promo.is_verbatim("", "anything"))
        counts = Counter()
        with mock.patch.object(promo, "is_verbatim", return_value=False):
            self.assertEqual(promo.extract_from_text("use code SAVE10", NAMES, counts), [])
        self.assertEqual(counts["not_verbatim"], 1)


class BlocklistTests(PromoCase):
    def test_domains(self):
        for url in ("https://www.dealabs.com/x", "https://fr.retailmenot.com/view/notion", "https://igraal.com/n",
                    "https://www.groupon.fr/coupons", "https://ma-reduc.com/notion"):
            self.assertEqual(promo.blocked_reason(url), "aggregator", url)

    def test_url_patterns(self):
        self.assertEqual(promo.blocked_reason("https://random-site.example/code-promo/notion"), "aggregator")
        self.assertEqual(promo.blocked_reason("https://random-site.example/coupons/notion"), "aggregator")
        self.assertEqual(promo.blocked_reason("https://notioncoupons.example/"), "aggregator")

    def test_allowed(self):
        self.assertIsNone(promo.blocked_reason("https://www.reddit.com/r/Notion/comments/1/promo-code/"))
        self.assertIsNone(promo.blocked_reason("https://www.youtube.com/watch?v=abc"))
        self.assertIsNone(promo.blocked_reason("https://www.notion.so/pricing"))
        self.assertIsNone(promo.blocked_reason("https://www.example.com/promo-code", "example.com"))

    def test_official_domain_does_not_unblock_the_blocklist(self):
        self.assertEqual(promo.blocked_reason("https://dealabs.com/x", "dealabs.com"), "aggregator")

    def test_aggregator_result_is_dropped_and_counted(self):
        routes = {"duckduckgo": (200, DDG_HTML)}
        result, code = self.run_find(routes, no_web=False)
        self.assertEqual(code, promo.EXIT_OK)
        self.assertEqual([c["code"] for c in result["codes"]], ["NOTIONFR15"])
        self.assertEqual(result["excluded"]["aggregator"], 1)


class ParserTests(PromoCase):
    def test_ddg(self):
        results = promo.parse_ddg(DDG_HTML)
        self.assertEqual(len(results), 2)  # the ad is dropped
        self.assertEqual(results[0]["url"], "https://blog.example.org/notion-tips")
        self.assertIn("NOTIONFR15", results[0]["snippet"])

    def test_bing(self):
        results = promo.parse_bing(BING_HTML)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://forum.example.net/t/1")
        self.assertIn("WELCOME30", results[0]["snippet"])

    def test_bing_redirect(self):
        import base64
        target = base64.urlsafe_b64encode(b"https://example.org/a").decode().rstrip("=")
        self.assertEqual(promo.bing_target("https://www.bing.com/ck/a?u=a1" + target), "https://example.org/a")

    def test_html_to_text_skips_scripts(self):
        text = promo.html_to_text(PRICING)
        self.assertNotIn("CODE0000", text)
        self.assertIn("OFFICIAL10", text)


class RankingTests(PromoCase):
    def mention(self, code, discount, conditions=(), source_type="web", url="https://a.example/1", date_=None,
                channel=None):
        source = {"type": source_type, "url": url, "title": "t", "date": date_, "excerpt": "use code %s" % code}
        if channel:
            source["channel"] = channel
        return {"code": code, "discount": discount, "conditions": list(conditions), "source": source}

    def pct(self, value):
        return {"type": "percent", "value": value, "label": "%d %%" % value}

    def test_scoring_parts(self):
        ranked = promo.rank_mentions([self.mention("AAAA1", self.pct(20), source_type="official",
                                                   url="https://notion.so/p", date_="2026-10-10")], TODAY, 10)
        parts = ranked[0]["score_parts"]
        self.assertEqual(parts, {"discount": 16.0, "sources": 10, "type": 20, "recency": 10, "penalty": 0})
        self.assertEqual(ranked[0]["score"], 56.0)

    def test_percent_is_capped_at_50(self):
        self.assertEqual(promo.discount_points(self.pct(90)), promo.discount_points(self.pct(50)))
        self.assertEqual(promo.discount_points(self.pct(50)), 40.0)

    def test_order_best_first(self):
        mentions = [
            self.mention("LOW10", self.pct(10), url="https://a.example/1"),
            self.mention("TOP30", self.pct(30), source_type="creator", url="https://youtube.com/watch?v=1",
                         channel="One", date_="2026-10-01"),
            self.mention("TOP30", self.pct(30), source_type="creator", url="https://youtube.com/watch?v=2",
                         channel="Two"),
            self.mention("NEWC50", self.pct(50), ["new customers only", "annual plan"], url="https://b.example/1"),
            self.mention("NODISC1", None, url="https://c.example/1"),
        ]
        ranked = promo.rank_mentions(mentions, TODAY, 10)
        self.assertEqual([r["code"] for r in ranked], ["TOP30", "NEWC50", "LOW10", "NODISC1"])
        scores = [r["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(ranked[3]["score"], 10.0)  # 10 (one source) + 5 (web) - 5 (unknown discount)

    def test_youtube_channels_are_distinct_sources_and_domains_are_not(self):
        same_domain = [self.mention("DOM10", self.pct(10), url="https://a.example/%d" % i) for i in range(3)]
        channels = [self.mention("YT10", self.pct(10), source_type="creator",
                                 url="https://youtube.com/watch?v=%d" % i, channel="Channel %d" % i)
                    for i in range(3)]
        ranked = {r["code"]: r for r in promo.rank_mentions(same_domain + channels, TODAY, 10)}
        self.assertEqual(ranked["DOM10"]["source_count"], 1)
        self.assertEqual(ranked["YT10"]["source_count"], 3)
        self.assertEqual(ranked["YT10"]["score_parts"]["sources"], 30)

    def test_tie_break_is_alphabetical_and_limit_applies(self):
        mentions = [self.mention(code, self.pct(10), url="https://%s.example/" % code.lower())
                    for code in ("BBBB1", "AAAA1", "CCCC1")]
        self.assertEqual([r["code"] for r in promo.rank_mentions(mentions, TODAY, 2)], ["AAAA1", "BBBB1"])

    def test_recency_points(self):
        self.assertEqual(promo.recency_points(date(2026, 10, 1), TODAY), 10)
        self.assertEqual(promo.recency_points(date(2026, 6, 1), TODAY), 6)
        self.assertEqual(promo.recency_points(date(2020, 1, 1), TODAY), 0)
        self.assertEqual(promo.recency_points(None, TODAY), 0)

    def test_summary(self):
        ranked = promo.rank_mentions([self.mention("AAAA1", self.pct(20), source_type="creator",
                                                   url="https://youtube.com/watch?v=1", channel="X")], TODAY, 10)
        self.assertEqual(promo.build_summary(ranked), ["1. AAAA1: 20 % (creator, 1 source)"])

    def test_first_seen_is_the_oldest_known_date(self):
        ranked = promo.rank_mentions([self.mention("AAAA1", self.pct(5), url="https://a.example/1", date_="2026-09-01"),
                                      self.mention("AAAA1", self.pct(5), url="https://b.example/1", date_="2026-08-01")],
                                     TODAY, 10)
        self.assertEqual(ranked[0]["first_seen"], "2026-08-01")


class FindTests(PromoCase):
    ROUTES = {
        "html.duckduckgo.com": (200, DDG_HTML),
        "hn.algolia.com": (200, HN_JSON),
    }

    def ytdlp(self, query, count):
        return YT_ENTRIES

    def test_full_run_ranks_codes_with_sources_and_statuses(self):
        result, code = self.run_find(self.ROUTES, ytdlp=self.ytdlp, no_web=False, no_hn=False, no_youtube=False,
                                     lang="fr")
        self.assertEqual(code, promo.EXIT_OK)
        top = result["codes"][0]
        self.assertEqual(top["code"], "NOTIONFR15")
        self.assertEqual(top["discount"]["label"], "15 %")
        self.assertGreaterEqual(top["source_count"], 3)  # 2 YouTube channels + 1 web domain
        self.assertTrue(all("NOTIONFR15" in s["excerpt"] for s in top["sources"]))
        self.assertIn("HNSAVE25", [c["code"] for c in result["codes"]])
        self.assertNotIn("PASTA20", [c["code"] for c in result["codes"]])  # off topic video
        self.assertEqual(result["excluded"]["off_topic"], 1)
        self.assertEqual(result["sources_status"]["youtube"]["status"], "ok")
        self.assertEqual(result["sources_status"]["hn"]["status"], "ok")
        self.assertEqual(result["sources_status"]["duckduckgo"]["status"], "ok")
        self.assertEqual(result["sources_status"]["bing"]["status"], "skipped")
        self.assertEqual(result["summary"][0].split(":")[0], "1. NOTIONFR15")
        self.assertIn("code promo", result["queries"]["web"][0])
        hn = [s for c in result["codes"] if c["code"] == "HNSAVE25" for s in c["sources"]][0]
        self.assertEqual((hn["type"], hn["date"]), ("forum", "2026-10-01"))

    def test_source_failure_is_recorded_with_exit_0(self):
        routes = {"html.duckduckgo.com": (403, "denied"), "www.bing.com": (200, BING_HTML),
                  "hn.algolia.com": promo.FetchError("timeout")}
        result, code = self.run_find(routes, no_web=False, no_hn=False)
        self.assertEqual(code, promo.EXIT_OK)
        status = result["sources_status"]
        self.assertEqual(status["duckduckgo"]["status"], "blocked-403")
        self.assertEqual(status["bing"]["status"], "ok")
        self.assertEqual(status["hn"]["status"], "error")
        self.assertEqual([c["code"] for c in result["codes"]], ["WELCOME30"])

    def test_blocked_engine_is_not_retried(self):
        routes = {"html.duckduckgo.com": (202, "<html>anomaly-modal</html>"), "www.bing.com": (200, "<html></html>")}
        http = fake_http(routes)
        with mock.patch.object(promo, "http_get", http):
            result, code = promo.run_find(opts(no_web=False), today=TODAY)
        self.assertEqual(result["sources_status"]["duckduckgo"]["status"], "captcha")
        self.assertEqual(len([u for u in http.calls if "duckduckgo" in u]), 1)
        self.assertEqual(code, promo.EXIT_ALL_FAILED if result["sources_status"]["bing"]["status"] != "ok"
                         else promo.EXIT_NO_CODE)

    def test_exit_7_when_every_source_fails(self):
        routes = {"duckduckgo": (403, ""), "bing.com": promo.FetchError("down"), "hn.algolia.com": (500, "")}

        def failing(query, count):
            raise promo.FetchError("Sign in to confirm you're not a bot")

        result, code = self.run_find(routes, ytdlp=failing, no_web=False, no_hn=False, no_youtube=False)
        self.assertEqual(code, promo.EXIT_ALL_FAILED)
        self.assertEqual(result["sources_status"]["youtube"]["status"], "captcha")
        self.assertEqual(result["codes"], [])

    def test_exit_4_when_nothing_found(self):
        result, code = self.run_find({"hn.algolia.com": (200, json.dumps({"hits": []}))}, no_hn=False)
        self.assertEqual(code, promo.EXIT_NO_CODE)
        self.assertEqual(result["sources_status"]["hn"]["status"], "ok")

    def test_missing_ytdlp_does_not_stop_the_other_sources(self):
        def missing(query, count):
            raise promo.MissingDependency("yt-dlp not found")

        result, code = self.run_find(self.ROUTES, ytdlp=missing, no_web=False, no_youtube=False)
        self.assertEqual(code, promo.EXIT_OK)
        self.assertEqual(result["sources_status"]["youtube"]["status"], "skipped")
        self.assertTrue(result["warnings"])
        result, code = self.run_find({"duckduckgo": (200, "<html><body>nothing</body></html>"),
                                      "bing.com": (200, "<html></html>")}, ytdlp=missing, no_web=False,
                                     no_youtube=False)
        self.assertEqual(code, promo.EXIT_MISSING)

    def test_official_pages_respect_robots_and_report_offers(self):
        routes = {"/robots.txt": (200, ROBOTS), "/pricing": (200, PRICING), "/students": (200, STUDENTS),
                  "/partners": (200, "<p>Use code PARTNER10 for 10% off</p>")}
        http = fake_http(routes)
        with mock.patch.object(promo, "http_get", http):
            result, code = promo.run_find(opts(domain="www.notion.so"), today=TODAY)
        self.assertEqual(code, promo.EXIT_OK)
        self.assertFalse([u for u in http.calls if u.endswith("/partners")])
        self.assertEqual([c["code"] for c in result["codes"]], ["OFFICIAL10"])
        self.assertEqual(result["codes"][0]["sources"][0]["type"], "official")
        kinds = {o["kind"] for o in result["official_offers"]}
        self.assertEqual(kinds, {"student", "annual", "trial"})
        self.assertEqual(result["sources_status"]["official"]["status"], "ok")

    def test_collaboration_invite_is_not_a_referral_offer(self):
        offers = promo.detect_offers("https://notion.so/pricing", "Invite friends to collaborate on projects.")
        self.assertEqual([o["kind"] for o in offers], [])
        offers = promo.detect_offers("https://notion.so/referral", "Refer a friend and get a credit.")
        self.assertEqual([o["kind"] for o in offers], ["referral"])

    def test_request_budget(self):
        http = fake_http({"duckduckgo": (200, DDG_HTML)})
        with mock.patch.object(promo, "http_get", http):
            client = promo.Client(max_requests=2)
            result, _ = promo.run_find(opts(no_web=False, lang="fr"), client=client, today=TODAY)
        self.assertEqual(len(http.calls), 2)
        self.assertEqual(result["requests"], 2)

    def test_usage_errors(self):
        with self.assertRaises(promo.UsageError):
            promo.run_find(opts(merchant="  "))
        with self.assertRaises(promo.UsageError):
            promo.run_find(opts(domain="not a domain"))
        with self.assertRaises(promo.UsageError):
            promo.run_find(opts())  # every source disabled

    def test_queries(self):
        fr = promo.build_queries("Notion", "", "fr")
        self.assertEqual(fr["web"][0], "Notion code promo")
        self.assertIn("Notion promo code", fr["web"])
        self.assertIn("Notion code créateur", fr["web"])
        en = promo.build_queries("Notion", "AI", "en")
        self.assertEqual(en["web"][0], "Notion AI promo code")
        self.assertFalse([q for q in en["web"] if "code promo" in q])


class CliTests(PromoCase):
    def call(self, argv, routes=None):
        out = io.StringIO()
        with mock.patch.object(promo, "http_get", fake_http(routes or {})), contextlib.redirect_stdout(out):
            code = promo.main(argv)
        return code, json.loads(out.getvalue())

    def write(self, folder, name, content):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def test_extract_then_rank_merges_and_reranks(self):
        with tempfile.TemporaryDirectory() as folder:
            find_json = self.write(folder, "find.json", json.dumps(self.find_output()))
            page = self.write(folder, "page.txt", "Reddit: I use code NOTION20 for 20% off on Notion, works great")
            code, extracted = self.call(["extract", "--text", page, "--url", "https://www.reddit.com/r/Notion/c/1",
                                         "--merchant", "Notion", "--date", "2026-10-12"])
            self.assertEqual(code, 0)
            self.assertEqual(extracted["codes"][0]["sources"][0]["type"], "forum")
            extra = self.write(folder, "extra.json", json.dumps(extracted))
            code, ranked = self.call(["rank", "--input", find_json, extra])
            self.assertEqual(code, 0)
            by_code = {c["code"]: c for c in ranked["codes"]}
            self.assertEqual(by_code["NOTION20"]["source_count"], 2)
            self.assertGreater(by_code["NOTION20"]["score"], by_code["OLDCODE1"]["score"])
            self.assertEqual(ranked["codes"][0]["code"], "NOTION20")
            self.assertEqual(ranked["summary"][0].split(":")[0], "1. NOTION20")

    def find_output(self):
        source = {"type": "web", "url": "https://blog.example.org/a", "title": "A", "date": None,
                  "excerpt": "Use code NOTION20 for 20% off"}
        other = {"type": "web", "url": "https://blog.example.org/b", "title": "B", "date": None,
                 "excerpt": "Old code OLDCODE1 gives 5% off"}
        return {"merchant": "Notion", "merchant_domain": "notion.so", "codes": [
            {"code": "NOTION20", "discount": {"type": "percent", "value": 20, "label": "20 %"}, "conditions": [],
             "sources": [source]},
            {"code": "OLDCODE1", "discount": {"type": "percent", "value": 5, "label": "5 %"}, "conditions": [],
             "sources": [other]}],
            "sources_status": {"hn": {"status": "ok", "items": 1}}, "excluded": {"stopword": 2}, "queries": {"web": ["q"]},
            "official_offers": [{"kind": "trial", "url": "https://notion.so/pricing", "text": "14 days free"}]}

    def test_rank_drops_a_code_absent_from_its_source_excerpt(self):
        data = self.find_output()
        data["codes"][0]["sources"][0]["excerpt"] = "nothing to see here"
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "find.json", json.dumps(data))
            code, ranked = self.call(["rank", "--input", path])
        self.assertEqual([c["code"] for c in ranked["codes"]], ["OLDCODE1"])
        self.assertEqual(ranked["excluded"]["not_verbatim"], 1)
        self.assertEqual(ranked["excluded"]["stopword"], 2)
        self.assertEqual(ranked["official_offers"][0]["kind"], "trial")

    def test_rank_drops_aggregator_sources(self):
        data = self.find_output()
        data["codes"][0]["sources"][0]["url"] = "https://www.dealabs.com/x"
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "find.json", json.dumps(data))
            _, ranked = self.call(["rank", "--input", path])
        self.assertEqual(ranked["excluded"]["aggregator"], 1)

    def test_extract_blocked_url_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "page.txt", "Use code NOTION20 for 20% off")
            code, result = self.call(["extract", "--text", page, "--url", "https://www.retailmenot.com/view/notion",
                                      "--merchant", "Notion"])
            self.assertEqual(code, promo.EXIT_NO_CODE)
            self.assertEqual(result["excluded"]["aggregator"], 1)
            code, result = self.call(["extract", "--text", page + ".missing", "--url", "https://example.org/",
                                      "--merchant", "Notion"])
            self.assertEqual(code, promo.EXIT_USAGE)
            code, result = self.call(["extract", "--text", page, "--url", "not-a-url", "--merchant", "Notion"])
            self.assertEqual(code, promo.EXIT_USAGE)

    def test_extract_html_page(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "page.html", "<html><body><p>Example: use code <b>SAVE10</b> for 10% off</p></body></html>")
            code, result = self.call(["extract", "--text", page, "--url", "https://example.org/x",
                                      "--merchant", "Example"])
        self.assertEqual(code, 0)
        self.assertEqual(result["codes"][0]["code"], "SAVE10")

    def test_usage_error_is_json_with_exit_2(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            promo.main(["find"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_find_cli_prints_one_json_object(self):
        routes = {"hn.algolia.com": (200, HN_JSON)}
        code, result = self.call(["find", "Notion", "--no-web", "--no-youtube"], routes)
        self.assertEqual(code, 0)
        self.assertEqual(result["codes"][0]["code"], "HNSAVE25")

    def test_doctor(self):
        routes = {"duckduckgo": (200, "ok"), "bing.com": (200, "ok"), "hn.algolia": (200, "{}"),
                  "youtube.com": (200, "ok")}
        with mock.patch.object(promo, "ytdlp_path", return_value=None):
            code, result = self.call(["doctor"], routes)
        self.assertEqual(code, promo.EXIT_MISSING)
        self.assertFalse(result["yt_dlp"]["found"])
        self.assertIn("pip install", result["yt_dlp"]["hint"])
        self.assertEqual(result["sources"]["hn"]["status"], "ok")
        with mock.patch.object(promo, "ytdlp_path", return_value=None):
            code, _ = self.call(["doctor"], {"duckduckgo": (403, ""), "bing.com": (403, ""), "hn.algolia": (500, ""),
                                             "youtube.com": (500, "")})
        self.assertEqual(code, promo.EXIT_ALL_FAILED)


class ReviewFixTests(PromoCase):
    """One group of tests per defect of the independent review."""

    def call(self, argv, routes=None):
        out = io.StringIO()
        with mock.patch.object(promo, "http_get", fake_http(routes or {})), contextlib.redirect_stdout(out):
            try:
                code = promo.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, json.loads(out.getvalue())

    def write(self, folder, name, content):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def source(self, url, type_="web", code="SAVE20", excerpt=None):
        return {"type": type_, "url": url, "title": "t", "date": None,
                "excerpt": excerpt if excerpt is not None else "use code %s for 20%% off" % code}

    def find_json(self, entries, domain="notion.so", **extra):
        data = {"merchant": "Notion", "merchant_domain": domain, "codes": entries, "excluded": {},
                "sources_status": {}, "queries": {}, "official_offers": []}
        data.update(extra)
        return data

    def entry(self, code, *sources):
        return {"code": code, "discount": {"type": "percent", "value": 20, "label": "20 %"}, "conditions": [],
                "sources": list(sources)}

    def rank(self, *documents, extra_args=()):
        with tempfile.TemporaryDirectory() as folder:
            paths = [self.write(folder, "f%d.json" % i, doc) for i, doc in enumerate(documents)]
            return self.call(["rank", "--input"] + paths + list(extra_args))

    # 1. yt-dlp isolation
    def test_ytdlp_argv_ignores_config_cookies_and_proxy(self):
        argv = promo.ytdlp_argv("/bin/yt-dlp", "notion promo code", 5)
        self.assertEqual(argv[:2], ["/bin/yt-dlp", "--ignore-config"])
        self.assertIn("--no-cookies-from-browser", argv)
        self.assertIn("--no-cookies", argv)
        self.assertEqual(argv[argv.index("--proxy") + 1], "")
        self.assertEqual(argv[-1], "ytsearch5:notion promo code")

    def test_run_ytdlp_launches_that_argv(self):
        done = SimpleNamespace(returncode=0, stdout=json.dumps({"id": "x"}) + "\n", stderr="")
        with mock.patch.object(promo, "ytdlp_path", return_value="/bin/yt-dlp"), \
                mock.patch.object(promo.subprocess, "run", return_value=done) as run:
            entries = promo.run_ytdlp("q", 3)
        self.assertEqual(run.call_args[0][0], promo.ytdlp_argv("/bin/yt-dlp", "q", 3))
        self.assertEqual(entries[0]["id"], "x")

    def test_http_get_ignores_proxy_environment(self):
        handlers = []
        real = promo.urllib.request.build_opener

        def spy(*args):
            handlers.extend(args)
            return real(*args)

        with mock.patch.object(promo.urllib.request, "build_opener", spy):
            with self.assertRaises(promo.FetchError):
                promo.http_get("http://127.0.0.1:9/", timeout=1)
        self.assertEqual(handlers[0].proxies, {})

    # 2. rank recomputes from evidence
    def test_rank_ignores_official_claim_off_the_merchant_domain(self):
        entry = self.entry("SAVE20", self.source("https://evil.example/page", "official"),
                           self.source("https://www.notion.so/pricing", "web"))
        code, ranked = self.rank(self.find_json([entry]))
        self.assertEqual(code, 0)
        types = {s["url"]: s["type"] for s in ranked["codes"][0]["sources"]}
        self.assertEqual(types, {"https://evil.example/page": "web", "https://www.notion.so/pricing": "official"})

    def test_rank_official_claim_does_not_bypass_aggregator_patterns(self):
        entry = self.entry("SAVE20", self.source("https://random-site.example/code-promo/notion", "official"))
        code, ranked = self.rank(self.find_json([entry]))
        self.assertEqual(code, promo.EXIT_NO_CODE)
        self.assertEqual(ranked["excluded"]["aggregator"], 1)
        entry = self.entry("SAVE20", self.source("https://www.dealabs.com/x", "official"))
        _, ranked = self.rank(self.find_json([entry], domain="dealabs.com"))
        self.assertEqual(ranked["excluded"]["aggregator"], 1)

    def test_rank_domain_comes_from_the_option_or_the_first_file_only(self):
        entry = self.entry("SAVE20", self.source("https://www.notion.so/pricing", "official"))
        _, ranked = self.rank(self.find_json([entry], domain=None), extra_args=["--domain", "notion.so"])
        self.assertEqual(ranked["codes"][0]["sources"][0]["type"], "official")
        _, ranked = self.rank(self.find_json([entry], domain=None))
        self.assertEqual(ranked["codes"][0]["sources"][0]["type"], "web")
        hostile = self.find_json([self.entry("SAVE20", self.source("https://evil.example/x", "official"))],
                                 domain="evil.example")
        _, ranked = self.rank(self.find_json([], domain="notion.so"), hostile)
        self.assertEqual(ranked["codes"][0]["sources"][0]["type"], "web")

    def test_rank_verbatim_is_case_insensitive_and_checked_per_source(self):
        good = self.source("https://a.example/1", excerpt="Use code Thomas20 now")
        bad = self.source("https://b.example/1", excerpt="nothing here")
        _, ranked = self.rank(self.find_json([self.entry("THOMAS20", good, bad)]))
        self.assertEqual([s["url"] for s in ranked["codes"][0]["sources"]], ["https://a.example/1"])
        self.assertEqual(ranked["excluded"]["not_verbatim"], 1)

    def test_rank_offers_must_be_on_the_merchant_domain(self):
        offers = [{"kind": "trial", "url": "https://www.notion.so/pricing", "text": "14 days free"},
                  {"kind": "student", "url": "https://evil.example/students", "text": "free"}]
        _, ranked = self.rank(self.find_json([], official_offers=offers))
        self.assertEqual([o["kind"] for o in ranked["official_offers"]], ["trial"])
        self.assertEqual(ranked["excluded"]["offer_not_official"], 1)

    def test_rank_malformed_input_is_a_usage_error_never_a_traceback(self):
        good = self.entry("SAVE20", self.source("https://a.example/1"))

        def mutate(change):
            entry = json.loads(json.dumps(good))
            change(entry)
            return self.find_json([entry])

        cases = {
            "codes not a list": self.find_json("oops"),
            "entry not an object": self.find_json(["SAVE20"]),
            "code not a string": mutate(lambda e: e.update(code=5)),
            "code shape": mutate(lambda e: e.update(code="a b")),
            "sources not a list": mutate(lambda e: e.update(sources="x")),
            "source not an object": mutate(lambda e: e.update(sources=["x"])),
            "url missing": mutate(lambda e: e["sources"][0].pop("url")),
            "url scheme": mutate(lambda e: e["sources"][0].update(url="ftp://x.example/")),
            "excerpt not a string": mutate(lambda e: e["sources"][0].update(excerpt=[1])),
            "type unknown": mutate(lambda e: e["sources"][0].update(type="admin")),
            "type not a string": mutate(lambda e: e["sources"][0].update(type=3)),
            "discount not an object": mutate(lambda e: e.update(discount="20%")),
            "discount kind": mutate(lambda e: e["discount"].update(type="cashback")),
            "discount value": mutate(lambda e: e["discount"].update(value="20")),
            "discount range": mutate(lambda e: e["discount"].update(value=900)),
            "discount bool": mutate(lambda e: e["discount"].update(value=True)),
            "conditions": mutate(lambda e: e.update(conditions="new")),
            "excluded": self.find_json([], excluded=[1]),
            "excluded count": self.find_json([], excluded={"x": "many"}),
            "sources_status": self.find_json([], sources_status=[]),
            "warnings": self.find_json([], warnings=[1]),
            "merchant_domain": self.find_json([], domain=7),
            "offers": self.find_json([], official_offers={}),
            "offer kind": self.find_json([], official_offers=[{"kind": "x", "url": "https://a.b/", "text": "t"}]),
        }
        for name, document in cases.items():
            code, result = self.rank(document)
            self.assertEqual(code, promo.EXIT_USAGE, name)
            self.assertIn("error", result, name)
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "list.json", "[1, 2]")
            self.assertEqual(self.call(["rank", "--input", path])[0], promo.EXIT_USAGE)

    # 3. redirects
    def test_official_page_redirected_off_domain_is_not_official(self):
        page = "<p>Notion: use code REDIR10 for 10% off. Free trial for 14 days.</p>"
        routes = {"/robots.txt": (404, ""), "/pricing": (200, page, "https://other.example/landing")}
        result, code = self.run_find(routes, domain="notion.so")
        self.assertEqual(code, promo.EXIT_OK)
        source = result["codes"][0]["sources"][0]
        self.assertEqual((source["type"], source["url"]), ("web", "https://other.example/landing"))
        self.assertEqual(result["official_offers"], [])

    def test_official_page_redirected_to_an_aggregator_is_dropped(self):
        page = "<p>Notion: use code REDIR10 for 10% off.</p>"
        routes = {"/robots.txt": (404, ""), "/pricing": (200, page, "https://www.dealabs.com/bons-plans/notion")}
        result, code = self.run_find(routes, domain="notion.so")
        self.assertEqual(code, promo.EXIT_NO_CODE)
        self.assertEqual(result["excluded"]["aggregator"], 1)

    def test_redirect_inside_the_merchant_domain_stays_official(self):
        page = "<p>Use code INSIDE10 for 10% off.</p>"
        routes = {"/robots.txt": (404, ""), "/pricing": (200, page, "https://www.notion.so/en/pricing")}
        result, _ = self.run_find(routes, domain="notion.so")
        self.assertEqual(result["codes"][0]["sources"][0]["type"], "official")
        self.assertEqual(result["codes"][0]["sources"][0]["url"], "https://www.notion.so/en/pricing")

    def test_http_get_reports_the_final_url(self):
        class Opened:
            status = 200
            headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

            def read(self, n):
                return b"ok"

            def geturl(self):
                return "https://final.example/"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        opener = SimpleNamespace(open=lambda request, timeout: Opened())
        with mock.patch.object(promo.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(promo.http_get("https://start.example/").url, "https://final.example/")

    # 4. extract applies the merchant anchor
    def test_extract_requires_a_merchant(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "p.txt", "Use code SAVE10 for 10% off")
            code, result = self.call(["extract", "--text", page, "--url", "https://example.org/x"])
            self.assertEqual(code, promo.EXIT_USAGE)
            self.assertIn("error", result)
            code, result = self.call(["extract", "--text", page, "--url", "https://example.org/x",
                                      "--merchant", "  "])
            self.assertEqual(code, promo.EXIT_USAGE)

    def test_extract_keeps_only_codes_near_the_merchant_name(self):
        text = ("Notion Plus: use code NOTION15 for 15% off. " + "filler words " * 40 +
                "Other tool: use code OTHER50 for 50% off.")
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "p.txt", text)
            code, result = self.call(["extract", "--text", page, "--url", "https://forum.example.org/t/1",
                                      "--merchant", "Notion", "--title", "Notion deals"])
        self.assertEqual(code, 0)
        self.assertEqual([c["code"] for c in result["codes"]], ["NOTION15"])
        self.assertEqual(result["excluded"]["unrelated_product"], 1)

    def test_extract_title_counts_only_when_the_body_never_names_the_merchant(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "p.txt", "Use code PLAIN15 for 15% off")
            _, result = self.call(["extract", "--text", page, "--url", "https://forum.example.org/t/1",
                                   "--merchant", "Notion", "--title", "Notion deals"])
            self.assertEqual([c["code"] for c in result["codes"]], ["PLAIN15"])
            code, result = self.call(["extract", "--text", page, "--url", "https://forum.example.org/t/1",
                                      "--merchant", "Notion"])
            self.assertEqual(code, promo.EXIT_NO_CODE)

    def test_extract_official_type_needs_the_merchant_domain(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "p.txt", "Use code PLAIN15 for 15% off")
            _, result = self.call(["extract", "--text", page, "--url", "https://www.notion.so/pricing",
                                   "--merchant", "Notion", "--domain", "notion.so"])
            self.assertEqual(result["codes"][0]["sources"][0]["type"], "official")
            code, result = self.call(["extract", "--text", page, "--url", "https://example.org/x",
                                      "--merchant", "Notion", "--type", "official", "--title", "Notion"])
            self.assertEqual(result["codes"][0]["sources"][0]["type"], "web")

    # 5/6. false positives
    def test_digit_token_near_percent_needs_a_code_or_use_word(self):
        counts = Counter()
        self.assertEqual(promo.extract_from_text("Enjoy 20% off XYZ123 today", NAMES, counts), [])
        self.assertEqual(promo.extract_from_text("Big discount, 30% off sitewide, SOC2 ready", NAMES, counts), [])
        self.assertGreaterEqual(counts["weak_context"], 2)
        self.assertEqual([m["code"] for m in promo.extract_from_text("use XYZ123 for 20% off", NAMES)], ["XYZ123"])
        self.assertEqual([m["code"] for m in promo.extract_from_text("utilise XYZ123 pour 20% de reduction", NAMES)],
                         ["XYZ123"])

    def test_new_stopwords(self):
        for word in ("EXPIRED", "INVALID", "ENDED", "VALID", "TOKEN", "KEY", "API", "SECRET", "ID", "URL", "SOC2",
                     "ISO", "GDPR", "RGPD", "HTTP", "JSON"):
            self.assertIn(word, promo.STOPWORDS, word)
        counts = Counter()
        for word in ("EXPIRED", "INVALID", "ENDED", "VALID", "GDPR", "RGPD", "SOC2"):
            self.assertEqual(promo.extract_from_text("promo code %s" % word, NAMES, counts), [], word)

    def test_environment_variable_names_are_rejected(self):
        counts = Counter()
        for token in ("NOTION_TOKEN", "STRIPE_KEY", "MY_SECRET", "USER_ID", "BASE_URL", "AWS_API"):
            self.assertEqual(promo.extract_from_text("promo code %s" % token, NAMES, counts), [], token)
        self.assertGreaterEqual(counts["env_var"], 5)  # USER_ID is caught earlier as a stopword pair
        self.assertEqual([m["code"] for m in promo.extract_from_text("promo code MY_CODE7", NAMES)], ["MY_CODE7"])

    def test_model_like_tokens_need_an_adjacent_trigger_word(self):
        counts = Counter()
        self.assertEqual(promo.extract_from_text("promo: new GPT-4O model", NAMES, counts), [])
        self.assertEqual(promo.extract_from_text("promo news on RTX4090 cards", NAMES, counts), [])
        self.assertEqual(counts["model_like"], 2)
        self.assertEqual([m["code"] for m in promo.extract_from_text("use code GPT4O today", NAMES)], ["GPT4O"])
        self.assertEqual([m["code"] for m in promo.extract_from_text("promo code: AB12", NAMES)], ["AB12"])

    # 7. blocklist by brand label
    def test_blocklist_matches_the_brand_on_any_tld(self):
        for url in ("https://www.retailmenot.fr/x", "https://groupon.de/coupons", "https://dealabs.net/",
                    "https://www.couponbirds.co.uk/notion", "https://fr.ma-reduc.fr/notion", "https://igraal.es/",
                    "https://www.vouchercodes.com/notion", "https://wethrift.co/notion"):
            self.assertEqual(promo.blocked_reason(url), "aggregator", url)
        self.assertEqual(promo.blocked_reason("https://offers.com/x"), "aggregator")  # explicit list
        for url in ("https://offers.io/", "https://pepper.io/", "https://savings.bank/", "https://www.notion.so/"):
            self.assertIsNone(promo.blocked_reason(url), url)

    # 8. lowercase and mixed case codes
    def test_lowercase_codes_after_a_code_word_are_kept_as_written(self):
        self.assertEqual([m["code"] for m in promo.extract_from_text("use code thomas20 now", NAMES)], ["thomas20"])
        self.assertEqual([m["code"] for m in promo.extract_from_text("Code: Thomas20 for 10% off", NAMES)],
                         ["Thomas20"])
        self.assertEqual([m["code"] for m in promo.extract_from_text("utilise le code createur15", NAMES)],
                         ["createur15"])
        for text in ("use code thomas now", "take thomas20 for 20% off", "use code the best"):
            self.assertEqual(promo.extract_from_text(text, NAMES), [], text)

    def test_case_variants_are_one_code_shown_as_most_often_written(self):
        def mention(code, number):
            return {"code": code, "discount": None, "conditions": [],
                    "source": {"type": "web", "url": "https://s%d.example/" % number, "title": "", "date": None,
                               "excerpt": "use code %s" % code}}

        ranked = promo.rank_mentions([mention("thomas20", 1), mention("THOMAS20", 2), mention("thomas20", 3)], TODAY)
        self.assertEqual(len(ranked), 1)
        self.assertEqual((ranked[0]["code"], ranked[0]["source_count"]), ("thomas20", 3))

    # 9. one budget for every call
    def test_ytdlp_and_gh_share_the_request_budget(self):
        yt_calls = []

        def ytdlp(query, count):
            yt_calls.append(query)
            return []

        http = fake_http({"hn.algolia.com": (200, HN_JSON)})
        client = promo.Client(max_requests=3)
        with mock.patch.object(promo, "http_get", http), mock.patch.object(promo, "run_ytdlp", ytdlp), \
                mock.patch.object(promo, "run_gh", side_effect=AssertionError("budget spent")), \
                mock.patch.object(promo.shutil, "which", return_value="/bin/gh"):
            result, _ = promo.run_find(opts(no_hn=False, no_youtube=False, github=True, lang="fr"), client=client,
                                       today=TODAY)
        self.assertEqual((len(http.calls), len(yt_calls)), (2, 1))
        self.assertEqual(client.count, 3)
        self.assertEqual(result["requests"], 3)
        self.assertEqual(result["sources_status"]["github"]["status"], "skipped")
        self.assertIn("budget", result["sources_status"]["github"]["detail"])

    def test_requests_reports_the_true_total(self):
        yt_calls = []
        http = fake_http({"html.duckduckgo.com": (200, DDG_HTML), "hn.algolia.com": (200, HN_JSON)})
        client = promo.Client()
        with mock.patch.object(promo, "http_get", http), \
                mock.patch.object(promo, "run_ytdlp", lambda q, c: yt_calls.append(q) or []), \
                mock.patch.object(promo, "run_gh", return_value=[]), mock.patch.object(promo.shutil, "which",
                                                                                   return_value="/bin/gh"):
            result, _ = promo.run_find(opts(no_web=False, no_hn=False, no_youtube=False, github=True, lang="fr"),
                                       client=client, today=TODAY)
        self.assertEqual(result["requests"], len(http.calls) + len(yt_calls) + 1)
        self.assertLessEqual(result["requests"], promo.MAX_REQUESTS)

    def test_cap_holds_across_all_sources(self):
        http = fake_http({"duckduckgo": (200, DDG_HTML), "hn.algolia.com": (200, HN_JSON),
                          "/robots.txt": (404, ""), "/pricing": (200, PRICING)})
        with mock.patch.object(promo, "http_get", http), mock.patch.object(promo, "run_ytdlp", lambda q, c: []):
            result, _ = promo.run_find(opts(no_web=False, no_hn=False, no_youtube=False, domain="notion.so",
                                            lang="fr"), client=promo.Client(max_requests=promo.MAX_REQUESTS),
                                       today=TODAY)
        self.assertLessEqual(result["requests"], promo.MAX_REQUESTS)

    def test_ytdlp_calls_are_paced_per_host(self):
        client = promo.Client()
        with mock.patch.object(promo, "HOST_DELAY", 1.0), mock.patch.object(promo.time, "sleep") as sleep:
            client.call("www.youtube.com", lambda: None)
            client.call("www.youtube.com", lambda: None)
            client.call("api.github.com", lambda: None)
        self.assertEqual(sleep.call_count, 1)
        self.assertGreater(sleep.call_args[0][0], 0.5)

    # 10. HTML separators
    def test_html_text_separates_cells_and_inline_elements(self):
        for markup in ("<table><tr><td>Code</td><td>SAVE20</td></tr></table>",
                       "<span>Code</span><span>SAVE20</span>", "<dl><dt>Code</dt><dd>SAVE20</dd></dl>",
                       "<button>Code</button><label>SAVE20</label>", "<li>Code</li><li>SAVE20</li>",
                       "<th>Code</th><th>SAVE20</th>", "<section>Code</section><section>SAVE20</section>"):
            text = promo.html_to_text(markup)
            self.assertIn("SAVE20", text.split(), markup)
            self.assertNotIn("CodeSAVE20", text, markup)
        self.assertEqual([m["code"] for m in promo.extract_from_text(
            promo.html_to_text("<span>Use code</span><span>SAVE20</span>"), NAMES)], ["SAVE20"])

    # 11. robots.txt policy
    def test_robots_unavailable_policy(self):
        page = "<p>Use code PLAIN15 for 10% off</p>"
        for status, allowed in ((404, True), (410, True), (400, True), (401, False), (403, False), (429, False),
                                (500, False), (503, False)):
            http = fake_http({"/robots.txt": (status, ""), "/pricing": (200, page)})
            with mock.patch.object(promo, "http_get", http):
                result, _ = promo.run_find(opts(domain="notion.so"), today=TODAY)
            fetched_pages = [u for u in http.calls if not u.endswith("/robots.txt")]
            self.assertEqual(bool(fetched_pages), allowed, status)
            self.assertEqual(result["sources_status"]["official"]["status"] == "ok", allowed, status)

    def test_robots_network_error_disallows_everything(self):
        http = fake_http({"/robots.txt": promo.FetchError("timeout"), "/pricing": (200, "<p>x</p>")})
        with mock.patch.object(promo, "http_get", http):
            result, _ = promo.run_find(opts(domain="notion.so"), today=TODAY)
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(result["sources_status"]["official"]["status"], "error")

    # 12. --max and candidates
    def test_max_is_validated_in_every_command(self):
        with tempfile.TemporaryDirectory() as folder:
            page = self.write(folder, "p.txt", "Notion: use code SAVE10 for 10% off")
            doc = self.write(folder, "f.json", self.find_json([]))
            for argv in (["find", "Notion", "--no-web", "--no-youtube", "--max", "0"],
                         ["extract", "--text", page, "--url", "https://a.example/", "--merchant", "Notion",
                          "--max", "0"],
                         ["rank", "--input", doc, "--max", "0"],
                         ["rank", "--input", doc, "--max", "-3"], ["rank", "--input", doc, "--max", "x"]):
                code, result = self.call(argv)
                self.assertEqual(code, promo.EXIT_USAGE, argv)
                self.assertIn("--max", result["error"])
        for function, kwargs in ((promo.run_extract, {"text": "x", "url": "https://a.example/", "merchant": "N",
                                                       "domain": None, "type": None, "title": "", "date": "",
                                                       "max": 0}),
                                 (promo.run_rank, {"input": [], "domain": None, "max": 0})):
            with self.assertRaises(promo.UsageError):
                function(SimpleNamespace(**kwargs))

    def test_find_keeps_every_candidate_and_every_source(self):
        mentions = []
        for number in range(7):
            mentions.append({"code": "BIGONE", "discount": None, "conditions": [],
                             "source": {"type": "web", "url": "https://s%d.example/" % number, "title": "",
                                        "date": None, "excerpt": "use code BIGONE"}})
        mentions.append({"code": "SMALL1", "discount": None, "conditions": [],
                         "source": {"type": "web", "url": "https://t.example/", "title": "", "date": None,
                                    "excerpt": "use code SMALL1"}})
        result = {}
        codes = promo.finish(result, mentions, 1, TODAY, Counter())
        self.assertEqual(len(codes), 1)
        self.assertEqual(len(codes[0]["sources"]), promo.MAX_SOURCES_PER_CODE)
        self.assertEqual([c["code"] for c in result["candidates"]], ["BIGONE", "SMALL1"])
        self.assertEqual(len(result["candidates"][0]["sources"]), 7)

    def test_rank_confirms_a_candidate_beyond_the_top_n(self):
        weak = self.entry("WEAK10", self.source("https://w.example/1", code="WEAK10"))
        strong = self.entry("STRONG50", self.source("https://s.example/1", code="STRONG50"))
        strong["discount"] = {"type": "percent", "value": 50, "label": "50 %"}
        find = self.find_json([strong], candidates=[strong, weak])
        with tempfile.TemporaryDirectory() as folder:
            find_path = self.write(folder, "find.json", find)
            page = self.write(folder, "page.txt", "Notion: use code WEAK10 for 20% off, works")
            _, extracted = self.call(["extract", "--text", page, "--url", "https://forum.example.org/t/9",
                                      "--merchant", "Notion", "--date", "2026-10-10"])
            extra = self.write(folder, "extra.json", extracted)
            code, ranked = self.call(["rank", "--input", find_path, extra, "--max", "5"])
        self.assertEqual(code, 0)
        by_code = {c["code"]: c for c in ranked["codes"]}
        self.assertEqual(set(by_code), {"STRONG50", "WEAK10"})
        self.assertEqual(by_code["WEAK10"]["source_count"], 2)
        self.assertEqual(len(ranked["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
