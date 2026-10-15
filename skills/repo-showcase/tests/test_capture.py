import argparse
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import capture  # noqa: E402
from common import (EXIT_FINDINGS, EXIT_MISSING, EXIT_NETWORK, EXIT_OK, EXIT_USAGE, Failure)  # noqa: E402


def chromium_available():
    if importlib.util.find_spec("playwright") is None:
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
            return True
    except Exception:  # noqa: BLE001
        return False


HAS_BROWSER = chromium_available()
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_repo(files):
    """Temporary git repository with the given {relative path: text or bytes}, files added to the index."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return tmp, root


def run_cli(argv):
    """Parse argv with the module's own subparsers, run the handler, return (exit code, JSON object)."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    capture.add_commands(sub)
    args = parser.parse_args(argv)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            code = args.func(args)
        except Failure as failure:
            capture.print_json({"ok": False, "error": str(failure)})
            code = failure.code
    return code, json.loads(buffer.getvalue())


SVG_OK = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#08f"/>'
          '</svg>')
SVG_ANIMATED = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 40"><style>@keyframes grow{from{width:0}'
                'to{width:100px}}.bar{animation:grow 1s forwards}@media (prefers-reduced-motion:reduce){.bar{'
                'animation:none}}</style><rect class="bar" width="100" height="20" fill="#08f"/></svg>')


class SlugTest(unittest.TestCase):
    def test_basic_rules(self):
        self.assertEqual(capture.heading_slug("Hello, World!"), "hello-world")
        self.assertEqual(capture.heading_slug("Snake_case and kebab-case"), "snake_case-and-kebab-case")
        self.assertEqual(capture.heading_slug("Install `npm`"), "install-npm")
        self.assertEqual(capture.heading_slug("A [link](https://example.com) here"), "a-link-here")
        self.assertEqual(capture.heading_slug("What's new?"), "whats-new")
        self.assertEqual(capture.heading_slug("Café menu"), "café-menu")

    def test_emoji_leaves_a_leading_hyphen(self):
        self.assertEqual(capture.heading_slug("\U0001F680 Features"), "-features")
        self.assertEqual(capture.heading_slug(":rocket: Features"), "-features")

    def test_duplicates_get_a_counter(self):
        slugs = capture.slugs_with_duplicates(["Usage", "Other", "Usage", "Usage"])
        self.assertEqual(slugs, ["usage", "other", "usage-1", "usage-2"])

    def test_heading_finder_sees_atx_setext_and_html(self):
        text = "# One\n\nTwo\n===\n\n<h2 align=\"center\">Three <b>x</b></h2>\n\n## Four ##\n"
        found = [raw for _, raw in capture.find_headings(capture.mask_blocks(text))]
        self.assertEqual(found, ["One", "Two", "Three <b>x</b>", "Four"])

    def test_code_fences_are_ignored(self):
        text = "# Real\n```\n# not a heading\n[x](missing.png)\n```\n"
        masked = capture.mask_blocks(text)
        self.assertEqual([raw for _, raw in capture.find_headings(masked)], ["Real"])
        self.assertEqual(masked.count("\n"), text.count("\n"))


class ReferenceTest(unittest.TestCase):
    def targets(self, text):
        refs, ids, undefined = capture.extract_references(capture.mask_blocks(text))
        return sorted((ref["kind"], ref["target"]) for ref in refs), ids, undefined

    def test_markdown_links_and_images(self):
        refs, _, _ = self.targets("![alt](a.png) and [text](b.md \"title\") and [![badge](c.svg)](https://x.io/y)\n")
        self.assertIn(("image", "a.png"), refs)
        self.assertIn(("image", "c.svg"), refs)
        self.assertIn(("link", "b.md"), refs)
        self.assertIn(("link", "https://x.io/y"), refs)

    def test_html_tags_and_picture(self):
        text = ('<picture><source media="(prefers-color-scheme: dark)" srcset="dark.svg">'
                '<img src="light.svg" alt="x"></picture>\n<a href="#usage" id="top">go</a> <a name="old"></a>\n'
                '<img srcset="a.png 1x, b.png 2x">')
        refs, ids, _ = self.targets(text)
        self.assertIn(("source", "dark.svg"), refs)
        self.assertIn(("image", "light.svg"), refs)
        self.assertIn(("source", "a.png"), refs)
        self.assertIn(("source", "b.png"), refs)
        self.assertIn(("link", "#usage"), refs)
        self.assertEqual(ids, {"top", "old"})

    def test_reference_style(self):
        text = "See [docs][d] and ![shot][s] and [missing][nope].\n\n[d]: docs/guide.md\n[s]: <img/shot.png>\n"
        refs, _, undefined = self.targets(text)
        self.assertIn(("link", "docs/guide.md"), refs)
        self.assertIn(("image", "img/shot.png"), refs)
        self.assertEqual([label for label, _ in undefined], ["nope"])

    def test_inline_code_is_ignored(self):
        refs, _, _ = self.targets("Use `![x](nowhere.png)` and ``[y](nothing.md)`` in text\n")
        self.assertEqual(refs, [])

    def test_classify(self):
        self.assertEqual(capture.classify_target("#Usage")[0], "anchor")
        self.assertEqual(capture.classify_target("https://x.io")[0], "external")
        self.assertEqual(capture.classify_target("//cdn.x.io/a.png")[0], "external")
        self.assertEqual(capture.classify_target("mailto:a@b.c")[0], "other")
        self.assertEqual(capture.classify_target("docs/a.md#x")[0], "local")


class SvgLintTest(unittest.TestCase):
    def lint(self, text):
        return capture.lint_svg(text, "x.svg")

    def test_clean_svg(self):
        self.assertEqual(self.lint(SVG_OK), ([], []))
        self.assertEqual(self.lint(SVG_ANIMATED), ([], []))

    def test_script_and_events_block(self):
        self.assertTrue(self.lint('<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>')[0])
        self.assertTrue(self.lint('<svg viewBox="0 0 1 1"><rect onclick="x()"/></svg>')[0])
        self.assertTrue(self.lint('<svg viewBox="0 0 1 1"><rect onload = "x()"/></svg>')[0])

    def test_external_resources_block(self):
        for body in ('<image href="https://x.io/a.png"/>', '<image xlink:href="http://x.io/a.png"/>',
                     '<rect style="fill:url(https://x.io/p)"/>', '<style>@import url(https://x.io/f.css);</style>',
                     '<style>@import "https://x.io/f.css";</style>'):
            blocking, _ = self.lint('<svg viewBox="0 0 1 1">%s</svg>' % body)
            self.assertTrue(blocking, body)

    def test_namespace_and_local_urls_are_fine(self):
        text = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                'viewBox="0 0 1 1"><defs><linearGradient id="g"/></defs><rect fill="url(#g)"/>'
                '<use xlink:href="#g"/></svg>')
        self.assertEqual(self.lint(text), ([], []))

    def test_warnings(self):
        _, warnings = self.lint('<svg><foreignObject/></svg>')
        self.assertEqual(len(warnings), 2)  # foreignObject and missing viewBox
        _, warnings = self.lint('<svg viewBox="0 0 1 1"><style>@font-face{font-family:x}</style></svg>')
        self.assertEqual(len(warnings), 1)
        for animation in ('<animate attributeName="x"/>', '<animateTransform/>', '<animateMotion/>', '<set/>',
                          '<style>@keyframes a{}</style>'):
            _, warnings = self.lint('<svg viewBox="0 0 1 1">%s</svg>' % animation)
            self.assertTrue(any("prefers-reduced-motion" in warning for warning in warnings), animation)


class StaticChecksTest(unittest.TestCase):
    def check(self, files, readme="README.md"):
        tmp, root = make_repo(files)
        self.addCleanup(tmp.cleanup)
        return capture.static_readme_checks(root, readme)

    def test_clean_readme(self):
        readme = ("# Title\n\n![demo](docs/demo.svg)\n\nText with a [section](#usage) link.\n\n## Usage\n\nGo.\n"
                  "[guide](docs/guide.md#top)\n")
        result = self.check({"README.md": readme, "docs/demo.svg": SVG_OK, "docs/guide.md": "# Guide\n"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["blocking"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["stats"]["first_visual_line"], 3)
        self.assertEqual(result["stats"]["headings"], 2)
        self.assertEqual(result["stats"]["images"], 1)
        self.assertEqual(set(result), {"ok", "blocking", "warnings", "stats"})

    def test_missing_files_block(self):
        readme = ("# T\n\n![a](missing.png)\n\n<img src=\"nope/b.png\">\n\n[x](gone.md)\n\n"
                  "<picture><source srcset=\"no-dark.svg\"><img src=\"ok.svg\"></picture>\n")
        result = self.check({"README.md": readme, "ok.svg": SVG_OK})
        self.assertFalse(result["ok"])
        text = "\n".join(result["blocking"])
        for name in ("missing.png", "nope/b.png", "gone.md", "no-dark.svg"):
            self.assertIn(name, text)
        self.assertNotIn("ok.svg", text)

    def test_query_fragment_absolute_and_directory_targets(self):
        readme = "![a](img/a.png?raw=true)\n[b](docs/b.md#sec)\n![c](/img/a.png)\n[d](docs/)\n[e](img%2Fa.png)\n"
        files = {"README.md": readme, "img/a.png": b"\x89PNG", "docs/b.md": "# b\n"}
        result = self.check(files)
        self.assertEqual(result["blocking"], [], result)

    def test_resolution_is_from_the_readme_folder(self):
        files = {"sub/README.md": "![a](a.png)\n![b](../b.png)\n", "sub/a.png": b"x", "b.png": b"y"}
        result = self.check(files, "sub/README.md")
        self.assertEqual(result["blocking"], [], result)
        files = {"sub/README.md": "![a](a.png)\n", "a.png": b"x"}
        self.assertFalse(self.check(files, "sub/README.md")["ok"])

    def test_outside_the_repository_is_missing(self):
        result = self.check({"README.md": "![a](../../../../etc/hosts)\n"})
        self.assertFalse(result["ok"])

    def test_case_difference_blocks(self):
        result = self.check({"README.md": "![a](docs/logo.svg)\n", "docs/Logo.svg": SVG_OK})
        self.assertFalse(result["ok"])

    def test_anchors(self):
        readme = ("# Top\n\n[ok](#getting-started) [dup](#usage-1) [bad](#nowhere) [id](#custom) [enc](#Getting%20x)\n\n"
                  "## Getting started\n\n## Usage\n\n## Usage\n\n<a id=\"custom\"></a>\n")
        result = self.check({"README.md": readme})
        warnings = "\n".join(result["warnings"])
        self.assertIn("#nowhere", warnings)
        self.assertNotIn("#getting-started", warnings)
        self.assertNotIn("#usage-1", warnings)
        self.assertNotIn("#custom", warnings)
        self.assertTrue(result["ok"])

    def test_image_sizes(self):
        files = {"README.md": "![a](a.png)\n![b](b.png)\n![c](c.png)\n", "a.png": b"x" * 1200000,
                 "b.png": b"x" * 10500000, "c.png": b"x" * 100}
        result = self.check(files)
        self.assertTrue(any("a.png" in warning and "over 1 MB" in warning for warning in result["warnings"]))
        self.assertTrue(any("b.png" in item for item in result["blocking"]))
        self.assertFalse(any("c.png" in item for item in result["blocking"] + result["warnings"]))

    def test_svg_lint_runs_on_referenced_svgs(self):
        bad = '<svg viewBox="0 0 1 1"><script>1</script></svg>'
        result = self.check({"README.md": "![a](a.svg)\n", "a.svg": bad})
        self.assertFalse(result["ok"])
        self.assertTrue(any("a.svg" in item and "<script" in item for item in result["blocking"]))

    def test_no_visual_warning_and_badges_do_not_count(self):
        readme = "# T\n\n![build](https://img.shields.io/badge/a-b-green)\n\n" + "text\n" * 30
        result = self.check({"README.md": readme})
        self.assertIsNone(result["stats"]["first_visual_line"])
        self.assertTrue(any("no image" in warning for warning in result["warnings"]))

    def test_late_visual_warns(self):
        readme = "# T\n" + "text\n" * 20 + "![a](a.svg)\n"
        result = self.check({"README.md": readme, "a.svg": SVG_OK})
        self.assertEqual(result["stats"]["first_visual_line"], 22)
        self.assertTrue(any("first visual" in warning for warning in result["warnings"]))

    def test_untracked_file_warns(self):
        tmp, root = make_repo({"README.md": "![a](a.svg)\n"})
        self.addCleanup(tmp.cleanup)
        (root / "a.svg").write_text(SVG_OK)
        result = capture.static_readme_checks(root)
        self.assertTrue(result["ok"])
        self.assertTrue(any("not tracked" in warning for warning in result["warnings"]))

    def test_stats(self):
        readme = "# Title\n\n" + "word " * 460 + "\n\n```\ncode words here\n```\n"
        result = self.check({"README.md": readme})
        stats = result["stats"]
        self.assertEqual(stats["words"], 461)
        self.assertEqual(stats["reading_minutes"], 2.0)
        self.assertEqual(stats["lines"], 7)

    def test_missing_readme(self):
        result = self.check({"other.md": "x"})
        self.assertFalse(result["ok"])
        self.assertIn("README.md not found", result["blocking"][0])


class LinkCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(405 if self.path == "/head-refused" else self.status())
                self.end_headers()

            def do_GET(self):
                self.send_response(self.status())
                self.end_headers()

            def status(self):
                return {"/gone": 404, "/blocked": 403}.get(self.path, 200)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_check_links(self):
        base = "http://127.0.0.1:%d" % self.port
        urls = [base + "/ok", base + "/head-refused", base + "/gone", base + "/blocked",
                "http://127.0.0.1:%d/closed" % free_port()]
        result = capture.check_links(urls, timeout=3)
        failed = sorted(item["url"] for item in result["failed"])
        self.assertEqual(failed, sorted([base + "/gone", urls[-1]]))
        self.assertEqual(result["unverified"], [base + "/blocked"])
        self.assertEqual(result["checked"], 5)


class FfmpegArgsTest(unittest.TestCase):
    def test_gif(self):
        command = capture.ffmpeg_args("in.webm", "out.gif", "gif", fps=10, width=800, trim_start=0.5)
        self.assertEqual(command[0], "ffmpeg")
        self.assertLess(command.index("-ss"), command.index("-i"))
        self.assertEqual(command[command.index("-ss") + 1], "0.5")
        vf = command[command.index("-vf") + 1]
        self.assertEqual(vf, "fps=10,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];"
                             "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
        self.assertEqual(command[command.index("-loop") + 1], "0")
        self.assertEqual(command[-1], "out.gif")

    def test_webp(self):
        command = capture.ffmpeg_args("in.webm", "out.webp", "webp", fps=12, width=960, trim_start=0)
        self.assertNotIn("-ss", command)
        for token in ("libwebp", "-lossless", "-q:v", "-loop", "-an"):
            self.assertIn(token, command)
        self.assertEqual(command[command.index("-lossless") + 1], "0")
        self.assertEqual(command[command.index("-q:v") + 1], "70")
        self.assertEqual(command[-1], "out.webp")

    def test_mp4(self):
        command = capture.ffmpeg_args("in.webm", "out.mp4", "mp4", fps=24, width=961, trim_start=1)
        for token in ("libx264", "yuv420p", "+faststart", "-an"):
            self.assertIn(token, command)
        self.assertIn("scale=960:-2:flags=lanczos", command[command.index("-vf") + 1])

    def test_unknown_format(self):
        with self.assertRaises(Failure) as caught:
            capture.ffmpeg_args("a", "b", "avi")
        self.assertEqual(caught.exception.code, EXIT_USAGE)


class StepsTest(unittest.TestCase):
    def test_valid_steps(self):
        steps = [{"goto": "/pricing"}, {"click": "button.buy"}, {"fill": ["#q", "hello"]},
                 {"type": ["#q", "hello"]}, {"type": ["#q", "hello", 80]}, {"press": "Enter"}, {"scroll": 600},
                 {"scroll": -200}, {"hover": "a"}, {"wait": 800}, {"wait_for": ".done"}]
        checked = capture.validate_steps(steps)
        self.assertEqual(len(checked), len(steps))
        self.assertEqual(checked[0], ("goto", "/pricing"))

    def test_invalid_steps(self):
        bad = [[], {}, [{"jump": "x"}], [{"goto": 3}], [{"click": ""}], [{"fill": ["only-one"]}],
               [{"type": ["a", "b", "slow"]}], [{"scroll": "down"}], [{"wait": -5}], [{"wait": True}],
               [{"goto": "/", "click": "a"}], ["goto"]]
        for steps in bad:
            with self.assertRaises(Failure, msg=str(steps)) as caught:
                capture.validate_steps(steps)
            self.assertEqual(caught.exception.code, EXIT_USAGE)

    def test_unknown_step_is_named(self):
        with self.assertRaises(Failure) as caught:
            capture.validate_steps([{"goto": "/"}, {"swipe": "left"}])
        self.assertIn("step 2", str(caught.exception))
        self.assertIn("swipe", str(caught.exception))

    def test_load_steps_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json")
            for path in (bad, Path(tmp) / "absent.json"):
                with self.assertRaises(Failure) as caught:
                    capture.load_steps(path)
                self.assertEqual(caught.exception.code, EXIT_USAGE)


class SmallHelpersTest(unittest.TestCase):
    def test_route_slug_and_join(self):
        self.assertEqual(capture.route_slug("/"), "home")
        self.assertEqual(capture.route_slug("/pricing"), "pricing")
        self.assertEqual(capture.route_slug("/docs/Intro?x=1"), "docs-intro-x-1")
        self.assertEqual(capture.join_url("http://h:3000", "/"), "http://h:3000")
        self.assertEqual(capture.join_url("http://h:3000", "/pricing"), "http://h:3000/pricing")
        self.assertEqual(capture.join_url("http://h", "https://other/x"), "https://other/x")

    def test_viewport_options(self):
        desktop = capture.viewport_options(1440, "dark", 2)
        self.assertEqual(desktop["viewport"], {"width": 1440, "height": 900})
        self.assertEqual(desktop["color_scheme"], "dark")
        self.assertEqual(desktop["device_scale_factor"], 2)
        self.assertNotIn("is_mobile", desktop)
        phone = capture.viewport_options(390, "light", 3)
        self.assertEqual(phone["viewport"], {"width": 390, "height": 844})
        self.assertTrue(phone["is_mobile"] and phone["has_touch"])
        self.assertTrue(capture.viewport_options(480, "light")["is_mobile"])
        self.assertNotIn("is_mobile", capture.viewport_options(481, "light"))

    def test_parsers(self):
        self.assertEqual(capture.parse_int_list("1440, 390", "--widths"), [1440, 390])
        for text in ("", "abc", "50", "99999"):
            with self.assertRaises(Failure):
                capture.parse_int_list(text, "--widths")
        self.assertEqual(capture.parse_themes("dark"), ["dark"])
        with self.assertRaises(Failure):
            capture.parse_themes("light,sepia")
        self.assertEqual(capture.parse_viewport("1280x800"), (1280, 800))
        with self.assertRaises(Failure):
            capture.parse_viewport("wide")

    def test_png_size(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (30).to_bytes(4, "big") + (20).to_bytes(4, "big")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            path.write_bytes(data)
            self.assertEqual(capture.png_size(path), (30, 20))
            path.write_bytes(b"not a png at all, really not")
            self.assertIsNone(capture.png_size(path))

    def test_should_reexec(self):
        venv = Path(tempfile.mkdtemp()) / "venv" / "bin" / "python"
        venv.parent.mkdir(parents=True)
        venv.write_text("")
        self.addCleanup(shutil.rmtree, str(venv.parents[2]), True)
        other_prefix = tempfile.gettempdir()
        self.assertTrue(capture.should_reexec("/x/showcase.py", other_prefix, {}, venv))
        self.assertTrue(capture.should_reexec("capture.py", other_prefix, {}, venv))
        self.assertFalse(capture.should_reexec("/x/showcase.py", other_prefix, {"REPO_SHOWCASE_NO_REEXEC": "1"}, venv))
        self.assertFalse(capture.should_reexec("/x/showcase.py", str(venv.parents[1]), {}, venv))
        self.assertFalse(capture.should_reexec("/x/unittest/__main__.py", other_prefix, {}, venv))
        self.assertFalse(capture.should_reexec("/x/showcase.py", other_prefix, {}, venv.with_name("absent")))


class FrameHtmlTest(unittest.TestCase):
    def test_browser_frame(self):
        page = capture.frame_html("data:image/png;base64,AAAA", "browser", "light", "example.com/pricing", 720, 450)
        self.assertIn("example.com/pricing", page)
        self.assertEqual(page.count("<i style=\"background:"), 3)
        self.assertIn("border-radius:12px", page)
        self.assertIn("box-shadow", page)
        self.assertIn("background:transparent", page)
        self.assertIn('width="720" height="450"', page)
        self.assertIn("#f1f3f4", page)

    def test_dark_colors_and_escaping(self):
        page = capture.frame_html("data:,", "browser", "dark", "a.io/<b>", 100, 100)
        self.assertIn("#202124", page)
        self.assertIn("a.io/&lt;b&gt;", page)
        self.assertNotIn("<b>", page)

    def test_phone_frame(self):
        page = capture.frame_html("data:,", "phone", "dark", "x", 195, 422)
        self.assertIn('class="phone"', page)
        self.assertIn("notch", page)
        self.assertNotIn('class="bar"', page)

    def test_unknown_frame(self):
        with self.assertRaises(Failure):
            capture.frame_html("data:,", "tablet", "light", "x", 1, 1)

    def test_address_label(self):
        self.assertEqual(capture.address_label("http://localhost:5173/"), "localhost:5173")
        self.assertEqual(capture.address_label("https://site.io/pricing?x=1"), "site.io/pricing")


class PageHtmlTest(unittest.TestCase):
    def test_preview_page(self):
        page = capture.build_preview_page('<p><img src="/img/a.png"> <img src="b.png"></p>', "CSS-HERE", "dark",
                                          "file:///work/docs/", "file:///work/")
        self.assertIn('<base href="file:///work/docs/">', page)
        self.assertIn("CSS-HERE", page)
        self.assertIn("max-width:880px", page)
        self.assertIn("padding:32px", page)
        self.assertIn("padding:16px", page)
        self.assertIn("#0d1117", page)
        self.assertIn('src="file:///work/img/a.png"', page)
        self.assertIn('src="b.png"', page)

    def test_social_html(self):
        page = capture.social_html("file:///a/b.svg", "#0d1117", "cover")
        self.assertIn("object-fit:cover", page)
        self.assertIn("file:///a/b.svg", page)
        for bg, fit in (("red;}</style><script>", "contain"), ("#fff", "stretch")):
            with self.assertRaises(Failure):
                capture.social_html("file:///a.svg", bg, fit)

    def test_fallback_css_when_the_fetch_fails(self):
        with mock.patch.object(capture.urllib.request, "urlopen", side_effect=OSError("offline")):
            css, source = capture.fetch_css("dark")
        self.assertEqual(source, "builtin fallback")
        self.assertIn(".markdown-body", css)


class DoctorTest(unittest.TestCase):
    TOOLS = {"git": {"present": True, "version": "2.54.0"}, "gh": {"present": True, "version": "2.0"},
             "git-filter-repo": {"present": True, "version": "x"}, "gitleaks": {"present": False, "version": None},
             "ffmpeg": {"present": True, "version": "7", "libwebp": False}, "exiftool": {"present": False, "version": None},
             "playwright": {"present": True, "version": "1.64", "chromium": True}, "Pillow": {"present": False, "version": None},
             "cv2": {"present": False, "version": None}}

    def test_ready_for(self):
        gh = {"logged_in": True, "login": "someone", "scopes": ["repo"]}
        ready = capture.compute_ready_for(self.TOOLS, gh, (2, 54, 0))
        self.assertEqual(ready, {"audit": True, "history_rewrite": True, "github_metadata": True, "screenshots": True,
                                 "demo": True, "faces": False, "photo_metadata": True, "deep_secrets": False})
        old = capture.compute_ready_for(self.TOOLS, gh, (2, 30, 2))
        self.assertFalse(old["history_rewrite"])
        no_gh = capture.compute_ready_for(self.TOOLS, {"logged_in": False, "login": None, "scopes": []}, (2, 54, 0))
        self.assertFalse(no_gh["github_metadata"])
        tools = dict(self.TOOLS, cv2={"present": True, "version": "4"}, playwright={"present": True, "chromium": False})
        ready = capture.compute_ready_for(tools, gh, (2, 54, 0))
        self.assertTrue(ready["faces"])
        self.assertFalse(ready["screenshots"] or ready["demo"])

    def test_hints_cover_missing_tools(self):
        hints = capture.missing_hints(self.TOOLS, (2, 30, 0))
        for key in ("gitleaks", "exiftool", "Pillow", "cv2", "git_upgrade", "ffmpeg_libwebp"):
            self.assertIn(key, hints)
            self.assertEqual(set(hints[key]), {"macos", "debian"})
        self.assertNotIn("git", hints)

    def test_doctor_command(self):
        gh = {"logged_in": True, "login": "someone", "scopes": ["repo", "workflow"]}
        probe = {"present": False, "version": None, "chromium": False, "interpreter": None, "error": "none"}
        with mock.patch.object(capture, "gh_auth_info", return_value=gh), \
                mock.patch.object(capture, "probe_playwright", return_value=probe):
            code, data = run_cli(["doctor"])
        self.assertEqual(code, EXIT_OK if shutil.which("git") else EXIT_MISSING)
        self.assertTrue(data["ready_for"]["audit"])
        self.assertFalse(data["ready_for"]["screenshots"])
        self.assertIn("playwright", data["install_hints"])
        self.assertEqual(data["gh_auth"]["scopes"], ["repo", "workflow"])
        for key in ("python", "git_version", "tools", "gh_auth", "ready_for", "install_hints"):
            self.assertIn(key, data)

    def test_gh_status_parsing(self):
        text = ("github.com\n  ✓ Logged in to github.com account someone (keyring)\n  - Active account: true\n"
                "  - Token scopes: 'gist', 'read:org', 'repo'\n")
        done = subprocess.CompletedProcess([], 0, stdout=text.encode(), stderr=b"")
        who = subprocess.CompletedProcess([], 0, stdout=b"someone\n", stderr=b"")
        with mock.patch.object(capture, "run", side_effect=[done, who]):
            info = capture.gh_auth_info()
        self.assertEqual(info, {"logged_in": True, "login": "someone", "scopes": ["gist", "read:org", "repo"]})
        out = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"You are not logged into any GitHub hosts.")
        with mock.patch.object(capture, "run", return_value=out):
            self.assertFalse(capture.gh_auth_info()["logged_in"])


class ServeTest(unittest.TestCase):
    def test_wait_and_cleanup_of_the_process_group(self):
        port = free_port()
        url = "http://127.0.0.1:%d/" % port
        # sh starts the real server in the background: only a group kill stops it
        inner = "%s -m http.server %d --bind 127.0.0.1" % (shlex.quote(sys.executable), port)
        command = "sh -c %s" % shlex.quote(inner + " & wait")
        with tempfile.TemporaryDirectory() as tmp:
            with capture.dev_server(command, tmp, url, timeout=20) as proc:
                self.assertEqual(capture.url_status(url), 200)
                pgid = proc.pid
                self.assertTrue(capture.signal_group(pgid, 0))
        self.assertFalse(capture.signal_group(pgid, 0))
        self.assertIsNone(capture.url_status(url, timeout=1))

    def test_no_command_is_a_noop(self):
        with capture.dev_server(None, None, "http://127.0.0.1:9/") as proc:
            self.assertIsNone(proc)

    def test_server_that_never_answers(self):
        script = "import time; print('booting'); print('still booting', flush=True); time.sleep(60)"
        command = "%s -c %s" % (shlex.quote(sys.executable), shlex.quote(script))
        with self.assertRaises(Failure) as caught:
            with capture.dev_server(command, None, "http://127.0.0.1:%d/" % free_port(), timeout=2, grace=1):
                pass
        self.assertEqual(caught.exception.code, EXIT_NETWORK)
        self.assertIn("still booting", str(caught.exception))

    def test_server_that_exits_early(self):
        command = "%s -c %s" % (shlex.quote(sys.executable), shlex.quote("print('boom'); raise SystemExit(3)"))
        with self.assertRaises(Failure) as caught:
            with capture.dev_server(command, None, "http://127.0.0.1:%d/" % free_port(), timeout=20):
                pass
        self.assertEqual(caught.exception.code, EXIT_NETWORK)
        self.assertIn("boom", str(caught.exception))
        self.assertIn("code 3", str(caught.exception))

    def test_unknown_command(self):
        with self.assertRaises(Failure) as caught:
            with capture.dev_server("definitely-not-a-command-xyz", None, "http://127.0.0.1:9/", timeout=1):
                pass
        self.assertEqual(caught.exception.code, EXIT_MISSING)

    def test_only_the_last_20_lines_are_reported(self):
        script = "import time\nfor i in range(50): print('line', i, flush=True)\ntime.sleep(60)"
        command = "%s -c %s" % (shlex.quote(sys.executable), shlex.quote(script))
        with self.assertRaises(Failure) as caught:
            with capture.dev_server(command, None, "http://127.0.0.1:%d/" % free_port(), timeout=2, grace=1):
                pass
        message = str(caught.exception)
        self.assertIn("line 49", message)
        self.assertIn("line 30", message)
        self.assertNotIn("line 29", message)


class PageHandler(BaseHTTPRequestHandler):
    PAGE = """<!doctype html><html><head><title>Demo</title><style>
body{margin:0;font-family:sans-serif;background:#fff;color:#111}
@media (prefers-color-scheme: dark){body{background:#111;color:#eee}}
.box{padding:40px}
</style></head><body><div class="box"><h1 id="title">Hello</h1><a id="next" href="/two">next</a>
<input id="q"><div id="out"></div></div>
<script>document.getElementById('q').addEventListener('input',e=>{document.getElementById('out').textContent=e.target.value})</script>
</body></html>"""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.PAGE.encode("utf-8"))

    def log_message(self, *args):
        pass


class WebTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


@unittest.skipUnless(HAS_BROWSER, "Playwright with Chromium not available")
class ShootTest(WebTestCase):
    def test_widths_themes_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = capture.shoot(self.url, tmp, ["/", "/two"], [800, 390], ["light", "dark"], scale=1, delay=0)
            names = sorted(Path(entry["path"]).name for entry in result["files"])
            self.assertEqual(names, sorted("%s-%d-%s.png" % (slug, width, theme) for slug in ("home", "two")
                                           for width in (800, 390) for theme in ("light", "dark")))
            by_name = {Path(entry["path"]).name: entry for entry in result["files"]}
            self.assertEqual(by_name["home-800-light.png"]["pixels"], "800x900")
            self.assertEqual(by_name["home-390-light.png"]["pixels"], "390x844")
            self.assertNotEqual((Path(tmp) / "home-800-light.png").read_bytes(),
                                (Path(tmp) / "home-800-dark.png").read_bytes())
            self.assertEqual(result["warnings"], [])

    def test_scale_selector_and_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = capture.shoot(self.url, tmp, ["/"], [800], ["light"], selector="h1", scale=2, delay=0,
                                   frame="browser")
            plain, framed = result["files"]
            self.assertFalse(plain["framed"])
            self.assertTrue(framed["framed"])
            width, height = [int(part) for part in plain["pixels"].split("x")]
            self.assertLess(width, 1600)  # the h1 is narrower than the 800 px viewport at scale 2
            self.assertLess(height, 400)
            self.assertTrue(Path(framed["path"]).name.endswith("-framed.png"))
            fwidth, fheight = [int(part) for part in framed["pixels"].split("x")]
            self.assertGreater(fwidth, width)
            self.assertGreater(fheight, height)
            header = Path(framed["path"]).read_bytes()[:33]
            self.assertEqual(header[25], 6)  # color type RGBA: the shadow area is transparent

    def test_phone_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = capture.shoot(self.url, tmp, ["/"], [390], ["dark"], scale=1, delay=0, frame="phone")
            self.assertEqual(len(result["files"]), 2)
            self.assertTrue(result["files"][1]["framed"])

    def test_unreachable_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Failure) as caught:
                capture.shoot("http://127.0.0.1:%d" % free_port(), tmp, ["/"], [800], ["light"], scale=1, delay=0)
        self.assertEqual(caught.exception.code, EXIT_NETWORK)

    def test_cli_with_serve(self):
        port = free_port()
        with tempfile.TemporaryDirectory() as site, tempfile.TemporaryDirectory() as out:
            (Path(site) / "index.html").write_text(PageHandler.PAGE)
            command = "%s -m http.server %d --bind 127.0.0.1" % (shlex.quote(sys.executable), port)
            code, data = run_cli(["shoot", "http://127.0.0.1:%d/" % port, "--out", out, "--widths", "600",
                                  "--themes", "dark", "--scale", "1", "--serve", command, "--serve-cwd", site,
                                  "--delay", "0"])
            self.assertEqual(code, EXIT_OK, data)
            self.assertEqual([Path(entry["path"]).name for entry in data["files"]], ["home-600-dark.png"])
            self.assertIsNone(capture.url_status("http://127.0.0.1:%d/" % port, timeout=1))


@unittest.skipUnless(HAS_BROWSER, "Playwright with Chromium not available")
class PreviewTest(unittest.TestCase):
    README = ("# Demo project\n\n![logo](assets/logo.svg)\n\nSome text with a [link](#usage).\n\n## Usage\n\n"
              "<picture><source media=\"(prefers-color-scheme: dark)\" srcset=\"assets/logo.svg\">"
              "<img src=\"assets/logo.svg\" alt=\"logo\"></picture>\n")
    HTML = ('<h1>Demo project</h1><p><img src="assets/logo.svg" alt="logo"></p><p>Some text</p>'
            '<h2>Usage</h2><p><img src="/assets/logo.svg"> <img src="assets/missing.png"></p>')

    def make(self):
        tmp, root = make_repo({"README.md": self.README, "assets/logo.svg": SVG_ANIMATED})
        self.addCleanup(tmp.cleanup)
        return root

    def test_static_only(self):
        root = self.make()
        code, data = run_cli(["preview", str(root), "--static-only", "--out", str(root / "out")])
        self.assertEqual(code, EXIT_OK, data)
        self.assertTrue(data["static"]["ok"])
        self.assertEqual(data["render"], {"skipped": "--static-only"})
        self.assertEqual(list((root / "out").iterdir()), [])

    def test_static_blocking_gives_exit_4(self):
        tmp, root = make_repo({"README.md": "![x](gone.png)\n"})
        self.addCleanup(tmp.cleanup)
        code, data = run_cli(["preview", str(root), "--static-only"])
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertFalse(data["ok"])

    def test_render_with_mocked_gh(self):
        root = self.make()
        out = root / "out"
        with mock.patch.object(capture, "render_markdown_html", return_value=self.HTML), \
                mock.patch.object(capture, "fetch_css", side_effect=lambda theme: (capture.FALLBACK_CSS[theme], "test")):
            code, data = run_cli(["preview", str(root), "--out", str(out)])
        self.assertEqual(code, EXIT_OK, data)
        render = data["render"]
        names = sorted(Path(entry["path"]).name for entry in render["screenshots"])
        self.assertEqual(names, sorted(["readme-880-light.png", "readme-880-dark.png", "readme-390-light.png",
                                        "readme-390-dark.png", "readme-fold-light.png", "readme-fold-dark.png"]))
        sizes = {Path(entry["path"]).name: entry["pixels"] for entry in render["screenshots"]}
        self.assertEqual(sizes["readme-fold-light.png"], "880x900")
        self.assertTrue(sizes["readme-390-dark.png"].startswith("390x"))
        # the root-relative and relative SVG load from the working tree, only the missing png fails
        self.assertEqual([Path(url).name for url in render["failed_images"]], ["missing.png"])
        self.assertNotEqual((out / "readme-880-light.png").read_bytes(), (out / "readme-880-dark.png").read_bytes())

    def test_gh_failure_returns_static_result(self):
        root = self.make()
        failure = Failure(EXIT_NETWORK, "gh api markdown failed: not logged in")
        with mock.patch.object(capture, "render_markdown_html", side_effect=failure):
            code, data = run_cli(["preview", str(root), "--out", str(root / "out")])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("not logged in", data["render"]["skipped"])
        self.assertTrue(data["static"]["ok"])

    def test_gh_render_command_line(self):
        done = subprocess.CompletedProcess([], 0, stdout=b"<p>x</p>", stderr=b"")
        with mock.patch.object(capture, "run", return_value=done) as fake:
            self.assertEqual(capture.render_markdown_html(Path("/work/README.md")), "<p>x</p>")
        command = fake.call_args[0][0]
        self.assertEqual(command[:5], ["gh", "api", "markdown", "-f", "mode=markdown"])
        self.assertEqual(command[5:], ["-F", "text=@/work/README.md"])


@unittest.skipUnless(HAS_BROWSER, "Playwright with Chromium not available")
class SocialTest(unittest.TestCase):
    def test_svg_to_png(self):
        tmp, root = make_repo({"README.md": "# x\n"})
        self.addCleanup(tmp.cleanup)
        source = root / "card.svg"
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640"><rect width="1280" '
                          'height="640" fill="#123456"/><circle cx="640" cy="320" r="200" fill="#ff6600"/></svg>')
        out = root / "social.png"
        code, data = run_cli(["social", str(root), "--source", str(source), "--out", str(out), "--fit", "cover"])
        self.assertEqual(code, EXIT_OK, data)
        self.assertEqual(data["pixels"], "1280x640")
        self.assertTrue(data["under_1mb"])
        self.assertIn("Settings > General > Social preview", data["instruction"])
        self.assertEqual(capture.png_size(out), (1280, 640))

    def test_html_source_and_bad_source(self):
        tmp, root = make_repo({"README.md": "# x\n"})
        self.addCleanup(tmp.cleanup)
        page = root / "card.html"
        page.write_text("<body style='margin:0;background:#224'><h1 style='color:white'>Title</h1></body>")
        result = capture.social(root, page, root / "s.png", delay=0)
        self.assertEqual(result["pixels"], "1280x640")
        with self.assertRaises(Failure) as caught:
            capture.social(root, root / "absent.svg", root / "s.png")
        self.assertEqual(caught.exception.code, EXIT_USAGE)


@unittest.skipUnless(HAS_BROWSER and HAS_FFMPEG, "Playwright with Chromium and ffmpeg not available")
class DemoTest(WebTestCase):
    def test_gif_walkthrough(self):
        steps = capture.validate_steps([{"hover": "#next"}, {"click": "#q"}, {"type": ["#q", "hello", 30]},
                                        {"press": "Enter"}, {"scroll": 100}, {"wait": 300},
                                        {"wait_for": "#out"}])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo.gif"
            result = capture.demo(self.url, steps, out, viewport=(800, 500), width=400, fps=8, fmt="gif",
                                  trim_start=0.3)
            self.assertTrue(out.read_bytes().startswith(b"GIF8"))
            self.assertEqual(result["bytes"], out.stat().st_size)
            self.assertGreater(result["duration_s"], 1)
            self.assertGreater(result["frames_estimate"], 5)
            self.assertEqual(result["warnings"], [])

    def test_failing_step_reports_it(self):
        steps = capture.validate_steps([{"click": "#does-not-exist"}])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Failure) as caught:
                capture.record_walkthrough(self.url, steps, (600, 400), "light", False, tmp)
        self.assertEqual(caught.exception.code, EXIT_FINDINGS)
        self.assertIn("step 1", str(caught.exception))


class DemoPreconditionsTest(unittest.TestCase):
    def test_webp_without_encoder_is_missing(self):
        with mock.patch.object(capture, "ffmpeg_encoders", return_value={"libx264"}), \
                mock.patch.object(capture.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with self.assertRaises(Failure) as caught:
                capture.demo("http://127.0.0.1:9", [("wait", 1)], "x.webp", fmt="webp")
        self.assertEqual(caught.exception.code, EXIT_MISSING)

    def test_cli_rejects_a_bad_steps_file_before_any_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps = Path(tmp) / "steps.json"
            steps.write_text(json.dumps([{"swipe": "left"}]))
            with mock.patch.object(capture, "load_playwright", side_effect=AssertionError("no browser")):
                code, data = run_cli(["demo", "http://127.0.0.1:9", "--steps", str(steps),
                                      "--out", str(Path(tmp) / "d.gif")])
        self.assertEqual(code, EXIT_USAGE)
        self.assertFalse(data["ok"])

    def test_missing_playwright_message(self):
        with mock.patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            with self.assertRaises(Failure) as caught:
                capture.load_playwright()
        self.assertEqual(caught.exception.code, EXIT_MISSING)
        self.assertIn("playwright install chromium", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
