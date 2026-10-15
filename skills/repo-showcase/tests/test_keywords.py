import gzip
import io
import json
import math
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

import repofixtures as fx

import common
import inventory
import keywords

_env = None


def setUpModule():
    global _env
    _env = fx.isolate()


def tearDownModule():
    _env.stop_and_clean()


def query_of(args):
    """The q=... parameter of a gh api call."""
    return next(a[2:] for a in args if a.startswith("q="))


class FakeNet:
    """Replacement for the gh and HTTP helpers: canned answers, every request recorded as one string."""

    def __init__(self, fail=(), meta=None, quota=297):
        self.requests, self.fail, self.quota, self.siblings = [], tuple(fail), quota, []
        self.meta = meta if meta is not None else {"visibility": "PUBLIC", "description": None, "topics": [],
                                                  "parent": None}
        self.similar = [
            {"full_name": "big/chords", "stargazers_count": 5000, "description": "Chord detection for ukulele players",
             "topics": ["chord-detection", "music", "audio-analysis"]},
            {"full_name": "small/chords", "stargazers_count": 3, "description": "Ukulele chord detection tool",
             "topics": ["music", "ukulele"]},
            {"full_name": "generic/ml", "stargazers_count": 90000, "description": "Machine learning for everything",
             "topics": ["speech-recognition", "text-to-speech", "ukulele-only-by-accident"]},
            {"full_name": "acme-corp/chordly", "stargazers_count": 99999, "description": "self",
             "topics": ["itself-only"]},
            {"full_name": "up/stream", "stargazers_count": 70000, "description": "Chord detection for ukulele players",
             "topics": ["parent-only"]},
        ]

    def owner_repos(self, owner):
        self.requests.append("owner repos " + owner)
        return list(self.siblings)

    def repo_meta(self, slug):
        self.requests.append("repo view " + slug)
        return self.meta

    def gh(self, args):
        self.requests.append("gh " + " ".join(args))
        if "gh" in self.fail:
            raise common.Failure(common.EXIT_NETWORK, "gh api failed: boom")
        query = query_of(args)
        if args[1] == "search/topics":
            return {"items": [{"name": "chord-detection", "curated": True}, {"name": "Bad_Name"},
                              {"name": "music-theory"}]}
        if query.startswith("topic:"):
            return {"total_count": {"topic:music": 12000, "topic:chord-detection": 40}.get(query, 7), "items": []}
        return {"total_count": len(self.similar), "items": self.similar}

    def http(self, url, headers=None):
        self.requests.append("http " + url + " " + json.dumps(headers or {}))
        for name in self.fail:
            if name in url:
                raise common.Failure(common.EXIT_NETWORK, "%s: timed out" % name)
        if "npmjs" in url:
            return {"objects": [{"package": {"keywords": ["chord", "Music Theory"]}},
                                {"package": {"keywords": ["chord"]}}]}
        if "crates.io/api/v1/crates?" in url:
            return {"crates": [{"name": "chordy"}]}
        if "crates.io/api/v1/crates/" in url:
            return {"crate": {"keywords": ["audio", "chord"]}, "categories": [{"slug": "multimedia-audio"}]}
        if "stackexchange" in url:
            self.quota -= 1
            return {"items": [{"name": "chord-diagram", "count": 175}], "quota_remaining": self.quota}
        if "duckduckgo" in url:
            return ["x", ["chord detection app", "chord detection from audio", "unrelated thing"]]
        raise AssertionError("unexpected url " + url)

    def patch(self):
        patches = [mock.patch.object(keywords, "_gh", self.gh), mock.patch.object(keywords, "_http_json", self.http),
                   mock.patch.object(keywords, "_repo_meta", self.repo_meta),
                   mock.patch.object(keywords, "_owner_repos", self.owner_repos),
                   mock.patch.object(keywords, "PACE_INTERVAL", 0), mock.patch.object(keywords, "HTTP_INTERVAL", 0),
                   mock.patch.object(keywords, "CRATES_INTERVAL", 0)]
        for patcher in patches:
            patcher.start()
        return lambda: [p.stop() for p in patches]


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def repo(self, files, name="proj", origin=None):
        repo = fx.make_repo(self.tmp, name, origin)
        repo.commit("initial", files)
        return repo

    def net(self, **kwargs):
        net = FakeNet(**kwargs)
        self.addCleanup(net.patch())
        return net

    def run_cmd(self, repo, *argv):
        """(exit code, parsed JSON); a Failure becomes its exit code with None, as the dispatcher would print."""
        try:
            return fx.run_cli(keywords, ["keywords", str(repo.path)] + list(argv))
        except common.Failure as failure:
            self.failure = str(failure)
            return failure.code, None


CHORD_README = ("# Chordly\n\nChord detection for ukulele players.\n\n## Features\n\n## Tuner and metronome\n\n"
                "Chordly listens to your ukulele and names the chord you play, in real time, with no account.\n\n"
                "## Install\n\nRun it.\n")


class TermsTest(unittest.TestCase):
    def test_extract_drops_stopwords_numbers_and_short_words(self):
        terms = keywords.extract_terms("The 2024 guide to AI chord detection, for ukulele players")
        self.assertIn("chord detection", terms)
        self.assertIn("ukulele players", terms)
        self.assertNotIn("the", terms)
        self.assertNotIn("ai", terms)
        self.assertNotIn("2024", terms)
        self.assertNotIn("detection for", terms)  # a stopword ends the pair

    def test_noise_words_only_when_asked(self):
        self.assertNotIn("install", keywords.extract_terms("Install and usage", noise=True))
        self.assertIn("install", keywords.extract_terms("Install and usage"))

    def test_topic_slug_validation(self):
        self.assertEqual(keywords.topic_slug("Chord Detection"), "chord-detection")
        self.assertEqual(keywords.topic_slug("a" * 50), "a" * 50)
        self.assertIsNone(keywords.topic_slug("a" * 51))
        self.assertIsNone(keywords.topic_slug("c++"))
        self.assertIsNone(keywords.topic_slug(""))
        self.assertEqual(keywords.topic_slug("front_end -- tools"), "front-end-tools")
        for slug in ("a", "0day", "x" * 50, "web-app"):
            self.assertTrue(keywords.TOPIC_RE.match(slug), slug)
        for slug in ("-a", "A", "a_b", "a b", "a" * 51, "café"):
            self.assertFalse(keywords.TOPIC_RE.match(slug), slug)

    def test_toml_keywords_with_and_without_tomllib(self):
        text = '[project]\nname = "x"\nkeywords = [\n  "chord detection",\n  \'ukulele\',\n]\n[tool.other]\nkeywords = ["no"]\n'
        self.assertEqual(keywords.toml_keywords(text, "project"), ["chord detection", "ukulele"])
        with mock.patch.dict(sys.modules, {"tomllib": None}):  # Python 3.9 path: the small regex
            self.assertEqual(keywords.toml_keywords(text, "project"), ["chord detection", "ukulele"])
            self.assertEqual(keywords.toml_keywords('[package]\nkeywords = ["audio", "midi"]\n', "package"),
                             ["audio", "midi"])
            self.assertEqual(keywords.toml_keywords(text, "package"), [])


class SeedsTest(Case):
    def test_seeds_from_every_local_source(self):
        repo = self.repo({
            "README.md": CHORD_README,
            "package.json": json.dumps({"name": "chordly", "keywords": ["Chord Detection", "ukulele"]}),
            "pyproject.toml": '[project]\nname = "chordly"\nkeywords = ["audio-analysis"]\n',
            "Cargo.toml": '[package]\nname = "chordly"\nkeywords = ["music-theory"]\n',
            "src/main.py": "print('hi')\n" * 20})
        files = inventory.tracked_present(repo.path)
        inv = inventory.collect(repo.path, remote=False)
        meta = {"description": "Detect guitar chords live", "topics": ["audio-tools"]}
        seeds, text = keywords.collect_seeds(repo.path, files, inv, meta, ["--extra seed"], [])
        origins = {k: e["origins"] for k, e in seeds.terms.items()}
        self.assertIn("topics", origins["audio tools"])
        self.assertIn("description", origins["guitar chords"])
        self.assertIn("package.json", origins["chord detection"])
        self.assertIn("pyproject.toml", origins["audio analysis"])
        self.assertIn("Cargo.toml", origins["music theory"])
        self.assertIn("readme-heading", origins["tuner"])
        self.assertIn("readme-heading", origins["chordly"])
        self.assertIn("--seed", origins["extra seed"])
        self.assertIn("language", origins["python"])
        self.assertNotIn("features", origins)       # section names are noise
        self.assertNotIn("install", origins)
        self.assertIn("ukulele", text.lower())

    def test_intro_paragraph_skips_html_and_badges(self):
        text = ('<p align="center"><img src="x.svg" alt="banner"></p>\n\n[![ci](https://x/y.svg)](https://x)\n\n'
                "## What is this?\n\nChordly is a free chord detector for ukulele players and singers.\n")
        headings, intro = keywords.readme_parts(text)
        self.assertEqual(headings, ["What is this?"])
        self.assertTrue(intro.startswith("Chordly is a free chord detector"))

    def test_no_seed_is_a_usage_error(self):
        repo = self.repo({"data.bin": b"\0\1\2"})
        self.net()
        code, _ = self.run_cmd(repo)
        self.assertEqual(code, common.EXIT_USAGE)
        self.assertIn("--seed", self.failure)


class ScoringTest(unittest.TestCase):
    def cand(self, key, sources=(), sim=0.0, count=None):
        cand = keywords.Candidate(key)
        for source in sources:
            cand.add(source, "ev")
        cand.sim_weight, cand.repo_count = sim, count
        return cand

    def test_more_sources_and_similar_weight_rank_first(self):
        weak = self.cand("weak", ["duckduckgo"])
        mid = self.cand("mid", ["github-topics", "stackexchange"])
        top = self.cand("top", ["seed:topics", "github-similar", "github-topics", "npm"], sim=9.0)
        ranked = keywords.score_candidates([weak, mid, top], {"top": 1.0})
        self.assertEqual([c.key for c in ranked], ["top", "mid", "weak"])
        self.assertTrue(all(0 <= c.score <= 100 for c in ranked))

    def test_seed_relevance_counts(self):
        near = self.cand("chord", ["github-topics"])
        far = self.cand("unrelated", ["github-topics"])
        ranked = keywords.score_candidates([far, near], {"chord": 1.0})
        self.assertEqual(ranked[0].key, "chord")

    def test_repo_count_is_a_log_bonus_and_optional(self):
        base = self.cand("a", ["github-topics"], count=None)
        dense = self.cand("b", ["github-topics"], count=100000)
        keywords.score_candidates([base, dense], {})
        self.assertGreater(dense.score, 0)
        self.assertNotEqual(base.score, dense.score)
        with_count = self.cand("c", ["seed:topics"], count=10)
        without = self.cand("d", ["seed:topics"], count=None)
        keywords.score_candidates([with_count, without], {"c": 1.0, "d": 1.0})
        self.assertLess(with_count.score, without.score)  # a topic almost nobody uses is less findable

    def test_seed_origins_count_as_one_source(self):
        cand = self.cand("x", ["seed:topics", "seed:description", "seed:readme-intro"])
        self.assertEqual(cand.groups(), {"seed"})


class PacerTest(unittest.TestCase):
    def test_interval_and_cap(self):
        now, slept = [100.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        pacer = keywords.Pacer(2.1, cap=3, sleep=sleep, clock=lambda: now[0])
        self.assertTrue(pacer.acquire())
        self.assertEqual(slept, [])
        now[0] += 0.5
        self.assertTrue(pacer.acquire())
        self.assertAlmostEqual(slept[0], 1.6)
        self.assertTrue(pacer.acquire())
        self.assertFalse(pacer.acquire())
        self.assertEqual(pacer.used, 3)

    def test_default_interval_is_below_the_search_rate_limit(self):
        self.assertGreaterEqual(keywords.PACE_INTERVAL, 2.0)  # 30 requests a minute


class RunTest(Case):
    FILES = {"README.md": CHORD_README, "package.json": json.dumps({"name": "c", "keywords": ["ukulele"]})}

    def test_full_run_shape(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        net = self.net(meta={"visibility": "PUBLIC", "description": "Chord detection for ukulele",
                             "topics": ["ukulele"], "parent": "up/stream"})
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        self.assertEqual(data["privacy"], "generic terms only")
        self.assertFalse(data["private"])
        self.assertTrue(data["keywords"])
        scores = [k["score"] for k in data["keywords"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for item in data["keywords"]:
            self.assertEqual(set(item), {"term", "score", "brand", "independent_sources", "sources", "as_topic",
                                         "repo_count", "covered"})
            self.assertEqual(set(item["covered"]), {"description", "topics", "readme"})
            self.assertTrue(item["as_topic"] is None or keywords.TOPIC_RE.match(item["as_topic"]))
            self.assertTrue(all(set(s) == {"source", "evidence"} for s in item["sources"]))
        by_term = {k["term"]: k for k in data["keywords"]}
        top = by_term["chord detection"]
        self.assertEqual(top["as_topic"], "chord-detection")
        self.assertEqual(top["repo_count"], 40)
        self.assertTrue(top["covered"]["description"] and top["covered"]["readme"])
        self.assertFalse(top["covered"]["topics"])
        self.assertTrue(by_term["ukulele"]["covered"]["topics"])
        # npm is used (package.json), crates is not; phrases from DuckDuckGo are not topics
        self.assertIn("npm", data["calls"])
        self.assertNotIn("crates", data["calls"])
        phrase = by_term["chord detection app"]
        self.assertIsNone(phrase["as_topic"])
        self.assertEqual({s["source"] for s in phrase["sources"]}, {"duckduckgo"})
        self.assertNotIn("unrelated thing", by_term)
        # the repository itself is not "similar"; its upstream parent is, but brings no independent source
        names = [r["full_name"] for r in data["similar_repos"]]
        self.assertEqual(names[:2], ["up/stream", "big/chords"])
        self.assertNotIn("acme-corp/chordly", names)
        self.assertEqual(by_term["parent only"]["independent_sources"], 0)
        self.assertNotIn("parent only", data["placement"]["missing"])
        placement = data["placement"]
        self.assertIn("ukulele", placement["topics"])           # existing relevant topic kept
        self.assertTrue(all(keywords.TOPIC_RE.match(t) for t in placement["topics"]))
        self.assertLessEqual(len(placement["topics"]), 20)
        self.assertTrue(2 <= len(placement["description_phrases"]) <= 3)
        self.assertTrue(3 <= len(placement["readme_terms"]) <= 6)
        self.assertEqual(data["calls"]["github-repo"], 1)
        self.assertTrue(any("Accept: application/vnd.github+json" in r for r in net.requests if r.startswith("gh ")))
        for request in net.requests:
            if "crates.io" in request:
                self.assertIn("repo-showcase-keywords", request)
        duck = [r for r in net.requests if "duckduckgo" in r][0]
        self.assertIn("Mozilla/5.0", duck)

    def test_similar_topics_are_weighted_by_stars(self):
        net = self.net()
        run = keywords.Run(25)
        pool = keywords.Pool(lambda key: False)
        seeds = {"chord detection": 1.0, "ukulele": 1.0, "audio analysis": 1.0, "metronome": 1.0}
        found, dropped = keywords.from_similar(run, pool, ["chord detection"], {"acme-corp/chordly", "up/stream"},
                                               seeds)
        self.assertEqual([r["full_name"] for r in found], ["big/chords", "small/chords"])  # by stars
        self.assertEqual([r["full_name"] for r in dropped], ["generic/ml"])
        cands = pool.items
        # overlap: big/chords 3 seed terms, small/chords 2: its contribution is scaled by 2/3
        self.assertAlmostEqual(cands["chord detection"].sim_weight, math.log1p(5000))
        self.assertAlmostEqual(cands["music"].sim_weight, math.log1p(5000) + math.log1p(3) * 2 / 3)
        self.assertAlmostEqual(cands["ukulele"].sim_weight, math.log1p(3) * 2 / 3)
        self.assertNotIn("speech recognition", cands)
        self.assertNotIn("itself only", cands)  # the repository itself and its fork parent are excluded
        self.assertNotIn("parent only", cands)
        ranked = keywords.score_candidates(list(cands.values()), {})
        self.assertEqual(ranked[0].key, "music")
        self.assertEqual(len(net.requests), 1)

    def test_rust_project_uses_crates_not_npm(self):
        repo = self.repo({"Cargo.toml": '[package]\nname = "x"\nkeywords = ["audio"]\n',
                          "src/main.rs": "fn main() {}\n" * 5,
                          "README.md": "# X\n\nAudio chord tool for guitar players everywhere.\n"})
        net = self.net()
        _, data = self.run_cmd(repo)
        self.assertIn("crates", data["calls"])
        self.assertEqual(data["calls"]["crates"], 2)  # one search, one crate detail
        self.assertNotIn("npm", data["calls"])
        self.assertIn("multimedia audio", {k["term"] for k in data["keywords"]})
        self.assertIn("audio", [k["term"] for k in data["keywords"]])
        self.assertTrue(any("crates.io" in r for r in net.requests))

    def test_python_project_queries_neither_registry(self):
        repo = self.repo({"main.py": "x = 1\n" * 10, "README.md": CHORD_README})
        self.net()
        _, data = self.run_cmd(repo)
        self.assertNotIn("npm", data["calls"])
        self.assertNotIn("crates", data["calls"])
        self.assertNotIn("pypi", " ".join(q["source"] for q in data["queries"]))

    def test_no_remote_makes_zero_calls(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        boom = mock.Mock(side_effect=AssertionError("network call with --no-remote"))
        with mock.patch.object(keywords, "_gh", boom), mock.patch.object(keywords, "_http_json", boom), \
                mock.patch.object(keywords, "_repo_meta", boom), mock.patch.object(keywords, "_owner_repos", boom), \
                mock.patch("urllib.request.urlopen", boom), mock.patch("subprocess.run", wraps=__import__("subprocess").run) as sub:
            code, data = self.run_cmd(repo, "--no-remote")
        self.assertEqual(code, 0)
        boom.assert_not_called()
        self.assertFalse(any("gh" == c.args[0][0] for c in sub.call_args_list if c.args))
        self.assertEqual(data["calls"], {})
        self.assertEqual(data["queries"], [])
        self.assertFalse(data["remote"])
        self.assertTrue(data["seeds"])
        self.assertTrue(data["keywords"])

    def test_private_repository_sends_generic_terms_only(self):
        files = dict(self.FILES, **{
            "README.md": "# Secret Tool\n\nSecret Tool by Acme Corp detects ukulele chords for the payroll team.\n"
                         "\n## Roadmap Q4\n\nUkulele chords again and again, ukulele chords everywhere.\n",
            "roadmap-q4-plan.md": "plan\n", "payroll-export.py": "x = 1\n"})
        repo = self.repo(files, origin="https://github.com/acme-corp/secret-tool.git")
        net = self.net(meta={"visibility": "PRIVATE", "description": "Secret Tool for the Acme Corp payroll team",
                             "topics": ["secret-tool", "ukulele"], "parent": None})
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        self.assertTrue(data["private"])
        self.assertEqual(data["privacy"], "generic terms only")
        sent = [r for r in net.requests if not r.startswith(("repo view", "owner repos"))]
        self.assertTrue(sent)
        blob = " ".join(sent).lower()
        for secret in ("secret", "acme", "roadmap", "payroll-export", "noreply", "tester", "@"):
            self.assertNotIn(secret, blob)
        for item in data["queries"]:
            self.assertNotIn("secret", item["query"])
        self.assertNotIn("secret tool", {k["term"] for k in data["keywords"]})
        self.assertNotIn("secret-tool", data["placement"]["topics"])

    def test_failing_source_is_recorded_and_exit_is_zero(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        self.net(fail=["duckduckgo", "stackexchange"])
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        self.assertIn("duckduckgo", data["errors"])
        self.assertIn("stackexchange", data["errors"])
        self.assertIn("timed out", data["errors"]["duckduckgo"][0])
        self.assertNotIn("github-similar", data["errors"])
        self.assertTrue(data["keywords"])

    def test_github_down_but_other_sources_answer(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        self.net(fail=["gh"])
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        self.assertIn("github-similar", data["errors"])
        self.assertIn("stackexchange", data["calls"])

    def test_exit_7_when_nothing_answers(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        self.net(fail=["gh", "npmjs", "stackexchange", "duckduckgo"])
        with mock.patch.object(keywords, "_repo_meta", return_value=None):
            code, _ = self.run_cmd(repo)
        self.assertEqual(code, common.EXIT_NETWORK)
        self.assertIn("no source answered", self.failure)

    def test_rate_limit_stops_further_github_calls(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        net = self.net()

        def limited(args):
            net.requests.append("gh " + " ".join(args))
            raise common.Failure(common.EXIT_NETWORK, "gh api failed: API rate limit exceeded (HTTP 403)")

        with mock.patch.object(keywords, "_gh", limited):
            code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        self.assertEqual(sum(1 for r in net.requests if r.startswith("gh ")), 1)

    def test_max_search_caps_github_search_calls(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        net = self.net()
        code, data = self.run_cmd(repo, "--max-search", "3")
        self.assertEqual(code, 0)
        searches = [r for r in net.requests if r.startswith("gh api search/")]
        self.assertEqual(len(searches), 3)
        self.assertTrue(any("--max-search 3" in n for n in data["notes"]))
        net = self.net()
        _, data = self.run_cmd(repo)
        self.assertLessEqual(len([r for r in net.requests if r.startswith("gh api search/")]), 25)

    def test_stack_exchange_stops_on_low_quota(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        net = self.net(quota=10)
        _, data = self.run_cmd(repo)
        self.assertEqual(data["calls"]["stackexchange"], 1)
        self.assertIn("quota", data["errors"]["stackexchange"][0])

    def test_save_writes_mode_600(self):
        repo = self.repo(self.FILES, origin="https://github.com/acme-corp/chordly.git")
        self.net()
        code, data = self.run_cmd(repo, "--save")
        self.assertEqual(code, 0)
        path = data["saved"]
        self.assertTrue(path.endswith("repo-showcase/keywords.json"))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["keywords"], data["keywords"])
        os.chmod(path, 0o644)
        self.run_cmd(repo, "--save")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertIsNone(self.run_cmd(repo)[1]["saved"])

    def test_seed_option_feeds_queries(self):
        repo = self.repo({"README.md": "# X\n"}, origin="https://github.com/acme-corp/chordly.git")
        net = self.net()
        code, data = self.run_cmd(repo, "--seed", "Ear Training", "--seed", "solfege")
        self.assertEqual(code, 0)
        self.assertIn("ear training", {s["term"] for s in data["seeds"]})
        self.assertTrue(any("ear training" in r for r in net.requests))


class SimilarFilterTest(Case):
    def repo_item(self, name, stars, topics, description):
        return {"full_name": name, "stargazers_count": stars, "topics": topics, "description": description}

    def run_similar(self, items, seeds, own=()):
        run = keywords.Run(25)
        pool = keywords.Pool(lambda key: False)
        with mock.patch.object(keywords, "_gh", lambda args: {"items": items}), \
                mock.patch.object(keywords, "PACE_INTERVAL", 0):
            kept, dropped = keywords.from_similar(run, pool, ["q"], set(own), seeds)
        return kept, dropped, pool

    SEEDS = {"chord detection": 1.0, "ukulele": 1.0, "beat tracking": 1.0, "drum kits": 1.0}

    def test_needs_two_distinct_seed_terms_with_four_seeds_or_more(self):
        items = [self.repo_item("big/generic", 100000, ["speech-recognition", "audio"], "ML for ukulele and more"),
                 self.repo_item("small/on-topic", 10, ["chord-detection", "ukulele"], "Beat tracking too")]
        kept, dropped, pool = self.run_similar(items, self.SEEDS)
        self.assertEqual([r["full_name"] for r in kept], ["small/on-topic"])
        self.assertEqual(kept[0]["overlap"], 3)
        self.assertEqual([r["full_name"] for r in dropped], ["big/generic"])
        self.assertIn("shares 1 seed term (ukulele), 2 needed", dropped[0]["reason"])
        self.assertNotIn("speech recognition", pool.items)       # a dropped repository adds no topic
        self.assertIn("chord detection", pool.items)

    def test_one_seed_term_is_enough_below_four_seeds(self):
        items = [self.repo_item("a/b", 5, ["ukulele"], "x"), self.repo_item("c/d", 5, ["other"], "y")]
        kept, dropped, _ = self.run_similar(items, {"ukulele": 1.0, "tuner": 1.0})
        self.assertEqual([r["full_name"] for r in kept], ["a/b"])
        self.assertIn("0 seed terms (none), 1 needed", dropped[0]["reason"])

    def test_a_term_inside_a_longer_matched_term_counts_once(self):
        seeds = {"speech": 1.0, "speech recognition": 1.0, "ukulele": 1.0, "chord": 1.0}
        item = self.repo_item("a/b", 5, ["speech-recognition"], "")
        terms, weight = keywords.seed_overlap(dict(item), seeds)
        self.assertEqual(terms, ["speech recognition"])
        kept, dropped, _ = self.run_similar([item], seeds)
        self.assertEqual((len(kept), len(dropped)), (0, 1))   # one hit is not enough with four seeds

    def test_contribution_is_scaled_by_relative_overlap(self):
        items = [self.repo_item("a/full", 100, ["x-one"], "chord detection ukulele beat tracking drum kits"),
                 self.repo_item("b/half", 100, ["x-two"], "chord detection ukulele")]
        _, _, pool = self.run_similar(items, self.SEEDS)
        self.assertAlmostEqual(pool.items["x one"].sim_weight, math.log1p(100))
        self.assertAlmostEqual(pool.items["x two"].sim_weight, math.log1p(100) * 2 / 4)

    def test_seed_pairs_are_strong_distinct_and_short(self):
        pool = ["chord detection", "ukulele", "beat tracking", "drum kits", "chord", "audio"]
        pairs = keywords.seed_pairs(pool)
        self.assertEqual(pairs[0], ("chord detection", "ukulele"))
        self.assertLessEqual(len(pairs), 3)
        for first, second in pairs:
            self.assertLessEqual(len((first + " " + second).split()), 3)
            self.assertFalse(set(first.split()) & set(second.split()))
        self.assertNotIn(("chord detection", "chord"), pairs)
        self.assertEqual(keywords.seed_pairs(["only one"]), [])

    def test_strongest_seeds_rank_first(self):
        seeds = keywords.Seeds()
        seeds.add("generic thing", "readme-intro")
        seeds.add("audio", "description")
        seeds.add("chord detection", "description")
        seeds.terms["audio"]["freq"] = 0
        seeds.terms["chord detection"]["freq"] = 8
        seeds.add("python", "language")
        self.assertEqual(seeds.query_pool(), ["chord detection", "audio", "generic thing"])

    def test_end_to_end_queries_are_pairs_and_dropped_repos_are_reported(self):
        repo = self.repo(RunTest.FILES, origin="https://github.com/acme-corp/chordly.git")
        self.net(meta={"visibility": "PUBLIC", "description": "Chord detection for ukulele", "topics": ["ukulele"],
                       "parent": "up/stream"})
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        similar_queries = [q["query"] for q in data["queries"] if q["source"] == "github-similar"]
        self.assertGreaterEqual(len(similar_queries), 2)
        self.assertTrue(all(len(q.split()) >= 2 for q in similar_queries))
        dropped = data["similar_repos_dropped"]
        self.assertEqual([d["full_name"] for d in dropped], ["generic/ml"])
        self.assertEqual(set(dropped[0]), {"full_name", "stars", "reason"})
        self.assertNotIn("generic/ml", [r["full_name"] for r in data["similar_repos"]])
        terms = {k["term"] for k in data["keywords"]}
        self.assertFalse({"speech recognition", "text to speech"} & terms)
        self.assertTrue(all(r["overlap"] >= 2 for r in data["similar_repos"]))


class SeedQualityTest(Case):
    """Existing topics and domain phrases lead; brands and generic words never seed a query."""

    DESC = "Production-grade Freqtrade fork for algorithmic trading on Hyperliquid. Maintained by Freqtrade France."
    TOPICS = ["algorithmic-trading", "hyperliquid", "freqtrade", "hyperopt", "freqtrade-fork", "python"]
    README = ("# Freqtrade Ultimate\n\nA fork of freqtrade for algorithmic trading, a bot for hyperliquid.\n\n"
              "## FreqUI Ultimate\n\nThe dashboard.\n\n## Learn algorithmic trading\n\nText.\n")

    def seeds(self, siblings=("frequi-ultimate", "docs")):
        repo = self.repo({"README.md": self.README, "main.py": "x = 1\n" * 10}, name="freqtrade-ultimate",
                         origin="https://github.com/titouannwtt/freqtrade-ultimate.git")
        files = inventory.tracked_present(repo.path)
        inv = inventory.collect(repo.path, remote=False)
        meta = {"description": self.DESC, "topics": self.TOPICS}
        protected = {keywords.term_key(t) for t in self.TOPICS}
        brand = keywords.build_brand("freqtrade-ultimate", "titouannwtt", list(siblings), self.DESC, protected)
        seeds, _ = keywords.collect_seeds(repo.path, files, inv, meta, [], [], brand)
        return repo, seeds, brand

    def test_topics_and_phrases_are_the_strongest_seeds(self):
        _, seeds, _ = self.seeds()
        pool = seeds.query_pool()
        self.assertEqual(pool[0], "algorithmic trading")  # topic, phrase, in description, headings and intro
        topics_first = [k for k in pool[:5]]
        self.assertTrue(all({"topics"} & set(seeds.terms[k]["origins"]) for k in topics_first), topics_first)
        self.assertGreater(seeds.strength("hyperliquid"), seeds.strength("production grade"))
        self.assertLess(seeds.strength("freqtrade fork"), seeds.strength("freqtrade"))  # a vague phrase ranks lower
        pairs = keywords.seed_pairs(pool)
        self.assertEqual(pairs[0][0], "algorithmic trading")
        self.assertTrue(all(a in pool[:8] and b in pool[:8] for a, b in pairs))

    def test_topic_qualifier_query_uses_existing_topics(self):
        _, seeds, _ = self.seeds()
        query = seeds.topic_query()
        self.assertEqual(query, "topic:algorithmic-trading topic:freqtrade")
        only_one = keywords.Seeds()
        only_one.add("chords", "topics")
        only_one.add("music", "description")
        self.assertIsNone(only_one.topic_query())

    def test_brand_names_are_found_and_kept_out_of_queries(self):
        _, seeds, brand = self.seeds()
        self.assertTrue(brand.matches("freqtrade france"))         # "Maintained by Freqtrade France"
        self.assertTrue(brand.matches("france"))
        self.assertTrue(brand.matches("freqtrade ultimate"))        # repository name
        self.assertTrue(brand.matches("titouannwtt"))               # owner
        self.assertTrue(brand.matches("frequi ultimate"))           # sibling repository
        self.assertFalse(brand.matches("freqtrade"))                # chosen as a topic: a normal term
        self.assertFalse(brand.matches("docs"))                     # generic sibling name
        long_name = keywords.build_brand("x", "y", ["freqtrade-france-strategies-simple-vwap"], "", set())
        self.assertNotIn("freqtrade france strategies simple vwap", long_name.phrases)  # a description, not a brand
        self.assertFalse(long_name.matches("france strategies"))
        pool = seeds.query_pool()
        for term in ("freqtrade france", "france", "frequi ultimate", "frequi", "freqtrade ultimate"):
            self.assertNotIn(term, pool)
        self.assertTrue(seeds.terms["frequi"]["brand"])             # product-name heading taints its words
        self.assertTrue(seeds.terms["frequi ultimate"]["brand"])
        self.assertFalse(seeds.terms["freqtrade"]["brand"])
        self.assertFalse(seeds.terms["algorithmic trading"]["brand"])  # same heading words elsewhere stay normal
        self.assertNotIn("frequi", seeds.word_weights())

    def test_generic_single_words_never_seed_a_query(self):
        _, seeds, _ = self.seeds()
        pool = seeds.query_pool()
        for word in ("bot", "fork", "france", "python", "ultimate", "production"):
            self.assertNotIn(word, pool)
        self.assertTrue(keywords.is_generic("bot") and keywords.is_generic("tool"))
        self.assertTrue(keywords.is_generic("france") and keywords.is_generic("english"))
        self.assertFalse(keywords.is_generic("trading bot"))   # inside a phrase it is fine
        self.assertFalse(keywords.is_generic("hyperliquid"))
        self.assertIn("freqtrade fork", seeds.terms)           # kept as a term, a topic of the repository

    def run_end_to_end(self, **net_args):
        repo, _, _ = self.seeds()
        net = self.net(meta={"visibility": "PUBLIC", "description": self.DESC, "topics": self.TOPICS, "parent": None},
                       **net_args)
        net.siblings = ["frequi-ultimate", "docs", "freqtrade-ultimate"]
        code, data = self.run_cmd(repo)
        self.assertEqual(code, 0)
        return net, data

    def test_end_to_end_queries(self):
        net, data = self.run_end_to_end()
        queries = [(q["source"], q["query"]) for q in data["queries"]]
        similar = [q for s_, q in queries if s_ == "github-similar"]
        self.assertTrue(any(q.startswith("topic:") and q.count("topic:") == 2 for q in similar), similar)
        self.assertTrue(any("algorithmic trading" in q for q in similar), similar)
        spoken = " ".join(q for _, q in queries).lower()
        for banned in ("france", "frequi", "ultimate", "titouannwtt"):
            self.assertNotIn(banned, spoken)
        for source, query in queries:
            if source in ("github-topics", "stackexchange", "duckduckgo"):
                self.assertNotIn(query, ("bot", "fork", "france", "python", "tool"))
        self.assertIn("frequi ultimate", data["brand_names"])
        self.assertEqual(data["calls"]["github-owner"], 1)

    def test_brand_terms_stay_covered_but_are_never_proposed(self):
        net, data = self.run_end_to_end()
        by_term = {k["term"]: k for k in data["keywords"]}
        brand_terms = [k for k in data["keywords"] if k["brand"]]
        self.assertIn("freqtrade france", by_term)
        self.assertTrue(by_term["freqtrade france"]["brand"])
        self.assertTrue(by_term["freqtrade france"]["covered"]["description"])
        placement = data["placement"]
        proposed = set(placement["missing"]) | set(placement["readme_terms"]) | set(placement["description_phrases"])
        for item in brand_terms:
            self.assertNotIn(item["term"], proposed)
            self.assertNotIn(item["as_topic"], placement["topics_new"])
        for generic in ("bot", "fork", "france"):
            self.assertNotIn(generic, proposed)


class SimilarExclusionTest(Case):
    SEEDS = {"chord detection": 1.0, "ukulele": 1.0, "beat tracking": 1.0, "drum kits": 1.0}

    def item(self, name, stars, topics, fork=False):
        return {"full_name": name, "stargazers_count": stars, "topics": topics, "fork": fork,
                "description": "chord detection ukulele"}

    def run_similar(self, items, owner=None, parents=()):
        run = keywords.Run(25)
        pool = keywords.Pool(lambda key: False)
        with mock.patch.object(keywords, "_gh", lambda args: {"items": items}), \
                mock.patch.object(keywords, "PACE_INTERVAL", 0):
            kept, dropped = keywords.from_similar(run, pool, ["q"], {"me/self"}, self.SEEDS, owner, parents)
        return kept, dropped, pool

    def test_owner_repositories_are_excluded(self):
        items = [self.item("Me/other-project", 900, ["mine"]), self.item("me/self", 5, ["x"]),
                 self.item("third/party", 10, ["theirs"])]
        kept, dropped, pool = self.run_similar(items, owner="me")
        self.assertEqual([r["full_name"] for r in kept], ["third/party"])
        self.assertNotIn("mine", pool.items)
        self.assertEqual(dropped, [])

    def test_zero_star_forks_are_excluded_starred_forks_kept(self):
        items = [self.item("a/fork-none", 0, ["noise"], fork=True), self.item("b/fork-liked", 40, ["liked"], fork=True),
                 self.item("c/plain-none", 0, ["plain"], fork=False)]
        kept, _, pool = self.run_similar(items)
        self.assertEqual({r["full_name"] for r in kept}, {"b/fork-liked", "c/plain-none"})
        self.assertNotIn("noise", pool.items)

    def test_upstream_is_similar_but_not_an_independent_source(self):
        items = [self.item("up/stream", 90000, ["upstream-only", "shared"]),
                 self.item("other/one", 8000, ["shared"])]
        kept, _, pool = self.run_similar(items, parents=["Up/Stream"])
        self.assertEqual([r["full_name"] for r in kept], ["up/stream", "other/one"])
        up_only, shared = pool.items["upstream only"], pool.items["shared"]
        self.assertGreater(up_only.sim_weight, 0)                 # still similar: it counts for the score
        self.assertEqual(up_only.sim_other, [])
        self.assertEqual(up_only.independent(), 0)
        self.assertEqual(shared.sim_other, ["other/one"])         # 8000 stars: heavy enough alone
        self.assertEqual(shared.independent(), 1)

    def test_upstream_remote_slug(self):
        repo = self.repo({"a.txt": "x"}, origin="https://github.com/me/mine.git")
        self.assertIsNone(keywords._upstream_slug(repo.path))
        repo.git("remote", "add", "upstream", "https://github.com/freqtrade/freqtrade.git")
        self.assertEqual(keywords._upstream_slug(repo.path), "freqtrade/freqtrade")


class MissingSourcesTest(unittest.TestCase):
    def cand(self, sources=(), others=(), weight=0.0):
        cand = keywords.Candidate("term")
        for source in sources:
            cand.add(source, "ev")
        cand.sim_other, cand.sim_other_weight = list(others), weight
        return cand

    def test_single_light_similar_repo_is_not_a_source(self):
        light = self.cand(["github-similar"], ["a/b"], weight=2.0)
        self.assertEqual(light.independent(), 0)
        heavy = self.cand(["github-similar"], ["a/b"], weight=keywords.SIM_MIN_WEIGHT + 0.1)
        self.assertEqual(heavy.independent(), 1)
        two = self.cand(["github-similar"], ["a/b", "c/d"], weight=1.0)
        self.assertEqual(two.independent(), 1)

    def test_seed_words_do_not_count(self):
        self.assertEqual(self.cand(["seed:topics", "seed:description"]).independent(), 0)
        self.assertEqual(self.cand(["github-topics", "stackexchange", "npm", "crates"]).independent(), 3)

    def keyword(self, term, independent, score=60.0, **flags):
        item = {"term": term, "score": score, "as_topic": keywords.topic_slug(term), "independent_sources": independent,
                "covered": {"description": False, "topics": False, "readme": False}}
        item.update(flags)
        return item

    def test_missing_needs_two_independent_sources_and_a_real_term(self):
        ranked = [self.keyword("single source", 1), self.keyword("two sources", 2), self.keyword("echarts", 3),
                  self.keyword("vendor name", 3, brand=True), self.keyword("bot", 3),
                  self.keyword("covered one", 3)]
        ranked[-1]["covered"]["readme"] = True
        placement = keywords.place(ranked, [])
        self.assertEqual(placement["missing"], ["two sources", "echarts"])
        self.assertNotIn("vendor-name", placement["topics_new"])
        self.assertNotIn("bot", placement["topics_new"])
        self.assertIn("single-source", placement["topics_new"])   # a weak topic can still be proposed, not "missing"


class PlacementTest(unittest.TestCase):
    def ranked(self, count, start=90.0):
        return [{"term": "term%d alpha" % i, "score": start - i, "as_topic": "term%d-alpha" % i,
                 "covered": {"description": False, "topics": False, "readme": False}} for i in range(count)]

    def test_topics_between_ten_and_fifteen_best_first(self):
        placement = keywords.place(self.ranked(30), [])
        self.assertEqual(len(placement["topics"]), 15)
        self.assertEqual(placement["topics"][0], "term0-alpha")

    def test_low_scores_stop_at_ten(self):
        placement = keywords.place(self.ranked(30, start=29.0), [])
        self.assertEqual(len(placement["topics"]), 10)

    def test_never_more_than_twenty_with_existing_topics(self):
        existing = ["old%d" % i for i in range(16)]
        placement = keywords.place(self.ranked(30), existing)
        self.assertLessEqual(len(placement["topics"]) + len([t for t in existing if t not in placement["topics"]]), 20)

    def test_relevant_existing_topic_kept_irrelevant_not_proposed(self):
        ranked = self.ranked(12)
        ranked.append({"term": "legacy", "score": 25.0, "as_topic": "legacy",
                       "covered": {"description": False, "topics": True, "readme": False}})
        ranked.append({"term": "stale", "score": 5.0, "as_topic": "stale",
                       "covered": {"description": False, "topics": True, "readme": False}})
        placement = keywords.place(ranked, ["legacy", "stale"])
        self.assertIn("legacy", placement["topics"])
        self.assertNotIn("legacy", placement["topics_new"])
        self.assertNotIn("stale", placement["topics"])

    def test_missing_lists_high_scores_absent_everywhere(self):
        ranked = self.ranked(3)
        ranked[1]["covered"]["readme"] = True
        placement = keywords.place(ranked, [])
        self.assertEqual(placement["missing"], ["term0 alpha", "term2 alpha"])

    def test_description_phrases_do_not_repeat_words(self):
        ranked = [{"term": t, "score": s, "as_topic": None, "covered": {"description": False, "topics": False,
                                                                       "readme": False}}
                  for t, s in (("chord detection", 90), ("chord recognition", 80), ("ukulele tuner", 70),
                               ("live audio", 60), ("audio tools", 50))]
        phrases = keywords.place(ranked, [])["description_phrases"]
        self.assertEqual(phrases, ["chord detection", "ukulele tuner", "live audio"])


class WarningsTest(unittest.TestCase):
    def test_description_and_topics_warnings(self):
        text = "Chord detector and chord finder. " + "x" * 340
        warnings = keywords.description_warnings(text, ["t%d" % i for i in range(21)])
        self.assertTrue(any("about 350" in w for w in warnings))
        self.assertTrue(any("repeated words" in w and "chord" in w for w in warnings))
        self.assertTrue(any("21 topics" in w for w in warnings))
        self.assertEqual(keywords.description_warnings("A short chord detector for players", []), [])


class HttpTest(unittest.TestCase):
    def fake_response(self, payload):
        response = io.BytesIO(payload)
        response.__enter__ = lambda self_: self_
        response.__exit__ = lambda *a: False
        return response

    def test_gzip_response_is_decompressed(self):
        body = gzip.compress(json.dumps({"items": [1]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=self.fake_response(body)) as opened:
            self.assertEqual(keywords._http_json("https://api.stackexchange.com/x"), {"items": [1]})
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), keywords.UA)
        self.assertEqual(opened.call_args.kwargs["timeout"], 10)

    def test_errors_become_failures(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            with self.assertRaises(common.Failure) as raised:
                keywords._http_json("https://example.org/x")
        self.assertEqual(raised.exception.code, common.EXIT_NETWORK)
        with mock.patch("urllib.request.urlopen", return_value=self.fake_response(b"<html>")):
            with self.assertRaises(common.Failure):
                keywords._http_json("https://example.org/x")


class DispatcherTest(unittest.TestCase):
    def test_registered_in_showcase(self):
        import showcase
        self.assertIn("keywords", showcase.MODULES)
        args = showcase.build_parser().parse_args(["keywords", ".", "--seed", "a", "--seed", "b", "--no-remote"])
        self.assertEqual((args.seed, args.no_remote, args.max_search, args.save), (["a", "b"], True, 25, False))


if __name__ == "__main__":
    unittest.main()
