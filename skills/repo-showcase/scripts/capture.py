"""repo-showcase capture: doctor, shoot, demo, preview, social (Python 3.9, Playwright imported lazily).

Commands (registered in the dispatcher showcase.py, each prints one JSON object):
  doctor                       tools found, what they enable, install hints (exit 5 if even the audit is impossible)
  shoot <url> --out DIR        screenshots per route, width and theme, optional browser or phone frame, optional dev server
  demo <url> --steps FILE --out FILE   scripted walkthrough recorded by Playwright, converted by ffmpeg to GIF, WebP or MP4
  preview <repo>               static README checks (links, images, anchors, SVG lint) and a render close to GitHub's
  social <repo> --source FILE  1280x640 image for the repository social preview (uploaded by hand in the web UI)

Playwright: on the Mac it lives in ~/.venvs/site-design; if the import fails the script re-executes itself with
that interpreter (disabled by REPO_SHOWCASE_NO_REEXEC=1). The preview uses `gh api markdown` (mode=markdown, the
same renderer as the file view) and github-markdown-css from a CDN, with a small builtin fallback stylesheet.
static_readme_checks(repo, file) is also used by ready.py.

Exit codes: 0 ok; 2 usage; 4 blocking README problems; 5 missing dependency; 7 URL or server unreachable.
"""
import base64
import concurrent.futures
import contextlib
import html
import importlib.util
import json
import os
import platform
import posixpath
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_FINDINGS, EXIT_MISSING, EXIT_NETWORK, EXIT_OK, EXIT_USAGE, Failure,  # noqa: E402
                    git_version, print_json, repo_root, run, state_dir, tracked_files)

VENV_PYTHON = Path.home() / ".venvs" / "site-design" / "bin" / "python"
ENTRY_SCRIPTS = ("showcase.py", "capture.py")
PLAYWRIGHT_HINT = ("python3 -m venv ~/.venvs/site-design && ~/.venvs/site-design/bin/pip install playwright && "
                   "~/.venvs/site-design/bin/playwright install chromium (Debian: pip install playwright && "
                   "playwright install --with-deps chromium)")
SCREENSHOT_WARN_BYTES = 1500000
DEMO_WARN_BYTES = 5000000
IMAGE_WARN_BYTES = 1000000
IMAGE_BLOCK_BYTES = 10000000
SOCIAL_MAX_BYTES = 1000000
MOBILE_MAX_WIDTH = 480
MARKDOWN_CSS_URL = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown-%s.css"
SOCIAL_INSTRUCTION = "Upload it in the repository Settings > General > Social preview (GitHub has no API for it)"
FIRST_VISUAL_MAX_LINE = 15
THEMES = ("light", "dark")

# ---------------------------------------------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------------------------------------------


def first_line(error):
    return (str(error).strip().splitlines() or [""])[0][:300]


def should_reexec(argv0, prefix, env, venv_python):
    """True when a Playwright import failed in the dispatcher or this script and the site-design venv can take over."""
    return (Path(venv_python).exists() and Path(argv0).name in ENTRY_SCRIPTS
            and Path(prefix).resolve() != Path(venv_python).parents[1].resolve()
            and not env.get("REPO_SHOWCASE_NO_REEXEC"))


def load_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        if should_reexec(sys.argv[0], sys.prefix, os.environ, VENV_PYTHON):
            os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)
        raise Failure(EXIT_MISSING, "playwright not found: " + PLAYWRIGHT_HINT)


def launch_chromium(pw):
    try:
        return pw.chromium.launch()
    except Exception as error:  # noqa: BLE001
        if "Executable doesn't exist" in str(error):
            raise Failure(EXIT_MISSING, "Chromium missing: playwright install chromium")
        raise


def png_size(path):
    """(width, height) read from the PNG header, or None."""
    try:
        with open(str(path), "rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if head[:8] != b"\x89PNG\r\n\x1a\n" or len(head) < 24:
        return None
    return struct.unpack(">II", head[16:24])


def file_entry(path, **extra):
    path = Path(path)
    size = png_size(path)
    entry = {"path": str(path), "bytes": path.stat().st_size, "pixels": "%dx%d" % size if size else None}
    entry.update(extra)
    return entry


def parse_int_list(text, name):
    try:
        values = [int(part) for part in text.split(",") if part.strip()]
    except ValueError:
        values = []
    if not values or any(value < 100 or value > 4000 for value in values):
        raise Failure(EXIT_USAGE, "%s expects comma-separated integers between 100 and 4000" % name)
    return values


def parse_themes(text):
    themes = [part.strip() for part in text.split(",") if part.strip()]
    if not themes or any(theme not in THEMES for theme in themes):
        raise Failure(EXIT_USAGE, "--themes expects light, dark or light,dark")
    return themes


def viewport_options(width, theme, scale=1.0):
    """new_context options: 390-style widths are phones (touch, mobile, 844 high), others desktops (900 high)."""
    mobile = width <= MOBILE_MAX_WIDTH
    options = {"viewport": {"width": width, "height": 844 if mobile else 900}, "color_scheme": theme,
               "device_scale_factor": scale}
    if mobile:
        options.update(is_mobile=True, has_touch=True)
    return options


def route_slug(route):
    """File name part of a route: '/' -> 'home', '/pricing/pro?x=1' -> 'pricing-pro-x-1'."""
    parsed = urlparse(route)
    text = (parsed.path + ("?" + parsed.query if parsed.query else "")) if parsed.scheme else route
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "home"


def join_url(base, route):
    """Absolute URL for a route; '/' keeps the base URL as given (it may carry a path)."""
    if urlparse(route).scheme in ("http", "https"):
        return route
    if route in ("", "/"):
        return base
    return urljoin(base, route)


# ---------------------------------------------------------------------------------------------------------------
# Dev server (--serve)
# ---------------------------------------------------------------------------------------------------------------


def url_status(url, timeout=2.0):
    """HTTP status of a GET (redirects followed, no proxy), or None if nothing answers."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url), timeout=timeout) as response:
            return response.status
    except HTTPError as error:
        error.close()
        return error.code
    except Exception:  # noqa: BLE001
        return None


def log_tail(log, lines=20):
    try:
        log.flush()
        log.seek(0)
        data = log.read()[-20000:]
    except (OSError, ValueError):
        return ""
    return "\n".join(data.decode("utf-8", "replace").splitlines()[-lines:])


def wait_for_url(url, timeout, proc=None, log=None, interval=0.25):
    """Poll url until it answers 200-399. Failure(EXIT_NETWORK) with the server's last output otherwise."""
    deadline = time.time() + timeout
    while True:
        status = url_status(url)
        if status is not None and 200 <= status < 400:
            return status
        if proc is not None and proc.poll() is not None:
            raise Failure(EXIT_NETWORK, "server exited with code %s before answering; last output:\n%s"
                          % (proc.returncode, log_tail(log) if log else ""))
        if time.time() >= deadline:
            raise Failure(EXIT_NETWORK, "server not up at %s after %ss (last status: %s); last output:\n%s"
                          % (url, timeout, status, log_tail(log) if log else ""))
        time.sleep(interval)


def signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_group(proc, grace=5.0):
    """SIGTERM the whole process group of proc, SIGKILL whatever is still alive after the grace delay."""
    pgid = proc.pid
    signal_group(pgid, signal.SIGTERM)
    deadline = time.time() + grace
    while time.time() < deadline:
        proc.poll()
        if not signal_group(pgid, 0):
            return
        time.sleep(0.05)
    signal_group(pgid, signal.SIGKILL)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


@contextlib.contextmanager
def dev_server(command, cwd, url, timeout=120, grace=5.0):
    """Run command (shlex split, no shell) in its own process group until the block ends. No command: no-op."""
    if not command:
        yield None
        return
    log = tempfile.TemporaryFile()
    try:
        argv = shlex.split(command)
        if not argv:
            raise Failure(EXIT_USAGE, "--serve is empty")
        try:
            proc = subprocess.Popen(argv, cwd=cwd or None, stdin=subprocess.DEVNULL, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        except (FileNotFoundError, NotADirectoryError) as error:
            raise Failure(EXIT_MISSING, "cannot start the server: %s" % first_line(error))
        try:
            wait_for_url(url, timeout, proc, log)
            yield proc
        finally:
            stop_group(proc, grace)
    finally:
        log.close()


# ---------------------------------------------------------------------------------------------------------------
# Window frames for screenshots
# ---------------------------------------------------------------------------------------------------------------

FRAME_COLORS = {
    "light": {"bar": "#f1f3f4", "addr": "#ffffff", "text": "#5f6368", "line": "#d0d7de", "shadow": "rgba(31,35,40,.30)",
              "bezel": "#1f2328", "page": "#ffffff"},
    "dark": {"bar": "#202124", "addr": "#35363a", "text": "#9aa0a6", "line": "#3c4043", "shadow": "rgba(0,0,0,.70)",
             "bezel": "#2d333b", "page": "#0d1117"},
}
FRAME_CSS = """
html,body{margin:0;background:transparent}
#stage{display:inline-block;padding:56px 56px 80px;background:transparent}
img{display:block}
.win{overflow:hidden;border-radius:12px;background:%(page)s;
 box-shadow:0 0 0 1px %(line)s,0 28px 60px -14px %(shadow)s,0 12px 24px -12px %(shadow)s}
.bar{display:flex;align-items:center;height:40px;padding:0 14px;box-sizing:border-box;background:%(bar)s;
 border-bottom:1px solid %(line)s}
.dots{display:flex;gap:8px;width:62px}
.dots i{display:block;width:12px;height:12px;border-radius:50%%}
.addr{flex:1;margin-right:62px;height:26px;padding:0 14px;border-radius:7px;background:%(addr)s;color:%(text)s;
 font:13px/26px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;text-align:center;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.phone{padding:14px;border-radius:54px;background:%(bezel)s;
 box-shadow:0 0 0 2px %(line)s,0 28px 60px -14px %(shadow)s,0 12px 24px -12px %(shadow)s}
.screen{position:relative;overflow:hidden;border-radius:40px;background:%(page)s}
.notch{position:absolute;top:10px;left:50%%;width:92px;height:24px;margin-left:-46px;border-radius:12px;
 background:%(bezel)s;z-index:2}
"""


def address_label(url):
    """Host and path shown in the fake address bar."""
    parsed = urlparse(url)
    text = (parsed.netloc + parsed.path) if parsed.netloc else url
    return text.rstrip("/") if parsed.path in ("", "/") else text


def frame_html(image_uri, kind, theme, label, width, height):
    """Self-contained HTML of a screenshot inside a browser window or a phone bezel (transparent page)."""
    colors = FRAME_COLORS[theme]
    size = 'width="%g" height="%g"' % (width, height)
    if kind == "browser":
        body = ('<div class="win"><div class="bar"><span class="dots"><i style="background:#ff5f57"></i>'
                '<i style="background:#febc2e"></i><i style="background:#28c840"></i></span>'
                '<span class="addr">%s</span></div><img src="%s" %s></div>'
                % (html.escape(label), image_uri, size))
    elif kind == "phone":
        body = '<div class="phone"><div class="screen"><i class="notch"></i><img src="%s" %s></div></div>' % (
            image_uri, size)
    else:
        raise Failure(EXIT_USAGE, "unknown frame: %s" % kind)
    return ('<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<div id="stage">%s</div></body></html>' % (FRAME_CSS % colors, body))


def frame_png(browser, source, target, kind, theme, url, scale):
    """Write target: source PNG inside a frame, transparent background, same pixel density."""
    size = png_size(source)
    if not size:
        raise Failure(EXIT_USAGE, "cannot frame a file that is not a PNG: %s" % source)
    width, height = size[0] / scale, size[1] / scale
    uri = "data:image/png;base64," + base64.b64encode(Path(source).read_bytes()).decode("ascii")
    page_html = frame_html(uri, kind, theme, address_label(url), width, height)
    context = browser.new_context(viewport={"width": int(width) + 200, "height": int(height) + 260},
                                  device_scale_factor=scale, color_scheme=theme)
    try:
        page = context.new_page()
        page.set_content(page_html)
        page.locator("#stage").screenshot(path=str(target), omit_background=True)
    finally:
        context.close()


# ---------------------------------------------------------------------------------------------------------------
# shoot
# ---------------------------------------------------------------------------------------------------------------


def open_page(page, target, wait_for, delay, warnings):
    """Load target and wait for the page to settle; Failure(EXIT_NETWORK) if it cannot be loaded."""
    try:
        response = page.goto(target, wait_until="load", timeout=30000)
    except Exception as error:  # noqa: BLE001
        raise Failure(EXIT_NETWORK, "page unreachable: %s (%s)" % (target, first_line(error)))
    if response is not None and response.status >= 400:
        warnings.append("%s answered HTTP %d" % (target, response.status))
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:  # noqa: BLE001
        pass
    if wait_for:
        try:
            page.wait_for_selector(wait_for, timeout=15000)
        except Exception:  # noqa: BLE001
            warnings.append("%s: selector %s did not appear within 15 s" % (target, wait_for))
    if delay:
        page.wait_for_timeout(delay)


def shoot(url, out, routes, widths, themes, full_page=False, selector=None, wait_for=None, delay=300, scale=2.0,
          frame="none"):
    """Screenshots of every route at every width and theme. Returns {"files": [...], "warnings": [...]}."""
    if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
        raise Failure(EXIT_USAGE, "http(s) URL expected: %s" % url)
    sync_playwright = load_playwright()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files, warnings = [], []
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            for theme in themes:
                for width in widths:
                    context = browser.new_context(**viewport_options(width, theme, scale))
                    try:
                        for route in routes:
                            target = join_url(url, route)
                            page = context.new_page()
                            open_page(page, target, wait_for, delay, warnings)
                            path = out / ("%s-%d-%s.png" % (route_slug(route), width, theme))
                            if selector:
                                locator = page.locator(selector).first
                                try:
                                    locator.screenshot(path=str(path), timeout=15000)
                                except Exception as error:  # noqa: BLE001
                                    raise Failure(EXIT_USAGE, "selector %s not capturable on %s: %s"
                                                  % (selector, target, first_line(error)))
                            else:
                                page.screenshot(path=str(path), full_page=full_page)
                            page.close()
                            files.append(file_entry(path, route=route, width=width, theme=theme, framed=False))
                            if frame != "none":
                                framed = path.with_name(path.stem + "-framed.png")
                                frame_png(browser, path, framed, frame, theme, target, scale)
                                files.append(file_entry(framed, route=route, width=width, theme=theme, framed=True))
                    finally:
                        context.close()
        finally:
            browser.close()
    for entry in files:
        if entry["bytes"] > SCREENSHOT_WARN_BYTES:
            warnings.append("%s is %.1f MB (over 1.5 MB): use --scale 1, fewer pixels or --selector"
                            % (entry["path"], entry["bytes"] / 1e6))
    return {"files": files, "warnings": warnings}


# ---------------------------------------------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------------------------------------------

STEP_SHAPES = {
    "goto": "a path or URL string",
    "click": "a CSS selector string",
    "fill": '["css", "text"]',
    "type": '["css", "text"] or ["css", "text", delay_ms]',
    "press": 'a key name such as "Enter"',
    "scroll": "a number of pixels (positive scrolls down)",
    "hover": "a CSS selector string",
    "wait": "a delay in milliseconds",
    "wait_for": "a CSS selector string",
}
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('__showcase_cursor')) return;
    const d = document.createElement('div');
    d.id = '__showcase_cursor';
    d.style.cssText = 'position:fixed;z-index:2147483647;width:20px;height:20px;border-radius:50%;' +
      'background:rgba(255,90,60,.55);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);' +
      'pointer-events:none;left:-60px;top:-60px;transform:translate(-50%,-50%);transition:left .1s,top .1s';
    document.documentElement.appendChild(d);
    document.addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_steps(steps):
    """Check the steps list, return [(name, value)]. Failure(EXIT_USAGE) on the first invalid step."""
    if not isinstance(steps, list) or not steps:
        raise Failure(EXIT_USAGE, "steps must be a non-empty JSON list")
    checked = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict) or len(step) != 1:
            raise Failure(EXIT_USAGE, "step %d: expected an object with exactly one key" % index)
        name, value = next(iter(step.items()))
        if name not in STEP_SHAPES:
            raise Failure(EXIT_USAGE, "step %d: unknown step '%s' (known: %s)" % (index, name, ", ".join(STEP_SHAPES)))
        ok = False
        if name in ("goto", "click", "press", "hover", "wait_for"):
            ok = isinstance(value, str) and bool(value.strip())
        elif name == "fill":
            ok = isinstance(value, list) and len(value) == 2 and all(isinstance(item, str) for item in value)
        elif name == "type":
            ok = (isinstance(value, list) and len(value) in (2, 3) and isinstance(value[0], str)
                  and isinstance(value[1], str) and (len(value) == 2 or (is_number(value[2]) and value[2] >= 0)))
        elif name in ("scroll", "wait"):
            ok = is_number(value) and (name == "scroll" or value >= 0)
        if not ok:
            raise Failure(EXIT_USAGE, "step %d: '%s' expects %s" % (index, name, STEP_SHAPES[name]))
        checked.append((name, value))
    return checked


def load_steps(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise Failure(EXIT_USAGE, "cannot read steps file: %s" % first_line(error))
    except ValueError as error:
        raise Failure(EXIT_USAGE, "steps file is not valid JSON: %s" % first_line(error))
    return validate_steps(data)


def ffmpeg_args(src, dst, fmt, fps=12, width=960, trim_start=0.0):
    """ffmpeg command converting the recorded video to gif, webp or mp4."""
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if trim_start and trim_start > 0:
        command += ["-ss", "%g" % trim_start]
    command += ["-i", str(src)]
    if fmt == "gif":
        filters = ("fps=%d,scale=%d:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];"
                   "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" % (fps, width))
        command += ["-vf", filters, "-loop", "0"]
    elif fmt == "webp":
        command += ["-vf", "fps=%d,scale=%d:-1:flags=lanczos" % (fps, width), "-c:v", "libwebp", "-lossless", "0",
                    "-q:v", "70", "-loop", "0", "-an"]
    elif fmt == "mp4":
        command += ["-vf", "fps=%d,scale=%d:-2:flags=lanczos" % (fps, width - width % 2), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
    else:
        raise Failure(EXIT_USAGE, "unknown format: %s" % fmt)
    return command + [str(dst)]


def ffmpeg_encoders():
    result = run(["ffmpeg", "-hide_banner", "-encoders"], check=False, timeout=30)
    names = set()
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.match(r"^[VAS][A-Z.]{5}$", parts[0]):
            names.add(parts[1])
    return names


def media_duration(path):
    """Duration in seconds read from `ffmpeg -i`, or None (webm recordings often have no duration)."""
    result = run(["ffmpeg", "-hide_banner", "-i", str(path)], check=False, timeout=30)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr.decode("utf-8", "replace"))
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)) if match else None


def parse_viewport(text):
    match = re.match(r"^(\d{3,4})x(\d{3,4})$", text.strip())
    if not match:
        raise Failure(EXIT_USAGE, "--viewport expects WIDTHxHEIGHT, e.g. 1280x800")
    return int(match.group(1)), int(match.group(2))


def run_step(page, name, value, base, cursor):
    def approach(selector):
        if not cursor:
            return
        box = page.locator(selector).first.bounding_box(timeout=15000)
        if box:
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
            page.wait_for_timeout(150)

    if name == "goto":
        page.goto(join_url(base, value), wait_until="load", timeout=30000)
    elif name == "click":
        approach(value)
        page.click(value, timeout=15000)
    elif name == "hover":
        approach(value)
        page.hover(value, timeout=15000)
    elif name == "fill":
        page.fill(value[0], value[1], timeout=15000)
    elif name == "type":
        page.type(value[0], value[1], delay=value[2] if len(value) == 3 else 60, timeout=15000)
    elif name == "press":
        page.keyboard.press(value)
    elif name == "scroll":
        page.evaluate("y => window.scrollBy({top: y, behavior: 'smooth'})", value)
        page.wait_for_timeout(700)
    elif name == "wait":
        page.wait_for_timeout(value)
    elif name == "wait_for":
        page.wait_for_selector(value, timeout=15000)


def record_walkthrough(url, steps, viewport, theme, cursor, tmp_dir):
    """Run the steps in a recording context; returns (webm path, seconds elapsed)."""
    sync_playwright = load_playwright()
    started = time.time()
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                          record_video_dir=str(tmp_dir),
                                          record_video_size={"width": viewport[0], "height": viewport[1]},
                                          color_scheme=theme)
            try:
                if cursor:
                    context.add_init_script(CURSOR_JS)
                page = context.new_page()
                video = page.video
                try:
                    page.goto(url, wait_until="load", timeout=30000)
                except Exception as error:  # noqa: BLE001
                    raise Failure(EXIT_NETWORK, "page unreachable: %s (%s)" % (url, first_line(error)))
                for number, (name, value) in enumerate(steps, 1):
                    try:
                        run_step(page, name, value, url, cursor)
                    except Failure:
                        raise
                    except Exception as error:  # noqa: BLE001
                        raise Failure(EXIT_FINDINGS, "step %d (%s %s) failed: %s"
                                      % (number, name, json.dumps(value, ensure_ascii=False)[:80], first_line(error)))
                page.wait_for_timeout(600)
            finally:
                context.close()
            video_path = video.path()
        finally:
            browser.close()
    return Path(video_path), time.time() - started


def demo(url, steps, out, viewport=(1280, 800), width=960, fps=12, fmt="gif", trim_start=0.5, theme="light",
         cursor=True):
    if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
        raise Failure(EXIT_USAGE, "http(s) URL expected: %s" % url)
    if not shutil.which("ffmpeg"):
        raise Failure(EXIT_MISSING, "ffmpeg not found: brew install ffmpeg (Debian: apt install ffmpeg)")
    if fmt == "webp" and "libwebp" not in ffmpeg_encoders():
        raise Failure(EXIT_MISSING, "this ffmpeg has no libwebp encoder: use --format gif, or install an ffmpeg "
                                    "built with libwebp")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    warnings, notes = [], []
    if out.suffix.lower().lstrip(".") != fmt:
        warnings.append("output name %s does not end with .%s" % (out.name, fmt))
    with tempfile.TemporaryDirectory(prefix="showcase-demo-") as tmp:
        video, elapsed = record_walkthrough(url, steps, viewport, theme, cursor, tmp)
        run(ffmpeg_args(video, out, fmt, fps, width, trim_start), timeout=600)
    duration = media_duration(out)
    if duration is None:
        duration = max(0.0, elapsed - trim_start)
    size = out.stat().st_size
    if size > DEMO_WARN_BYTES:
        warnings.append("%.1f MB is over the 5 MB comfort threshold: lower --fps (8-10), --width (720-800) or "
                        "shorten the steps" % (size / 1e6))
    if fmt == "mp4":
        notes.append("An mp4 renders as a video player only when uploaded through the GitHub web editor (drag and "
                     "drop into an issue, PR or README edit); a relative mp4 path committed in the repo is shown as "
                     "a plain link (unverified). Prefer GIF or WebP for a README.")
    return {"path": str(out), "format": fmt, "bytes": size, "duration_s": round(duration, 2),
            "frames_estimate": int(round(duration * fps)), "width": width, "fps": fps, "warnings": warnings,
            "notes": notes}


# ---------------------------------------------------------------------------------------------------------------
# Static README checks
# ---------------------------------------------------------------------------------------------------------------

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
HTML_HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.I | re.S)
TARGET = r"(<[^>\n]*>|(?:[^\s()]|\([^\s()]*\))+)"
MD_IMAGE_RE = re.compile(r"!\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*" + TARGET)
MD_LINK_RE = re.compile(r"(?<!!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*" + TARGET)
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]\n^][^\]\n]*)\]:[ \t]*(<[^>\n]*>|\S+)", re.M)
REF_USE_RE = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\[([^\]\n]*)\]")
AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")
HTML_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+))")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
BADGE_RE = re.compile(r"shields\.io|badgen\.net|badge|travis-ci|codecov\.io|coveralls|img\.youtube", re.I)
SVG_ANIMATION_RE = re.compile(r"<animate\b|<animateTransform\b|<animateMotion\b|<set\b|@keyframes", re.I)


def mask_blocks(text):
    """Blank fenced code blocks and HTML comments, keeping the line numbers."""
    lines, fence = [], None
    for line in text.split("\n"):
        match = FENCE_RE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) \
                    and not line.strip().strip(fence[0]):
                fence = None
            lines.append("")
        elif match:
            fence = match.group(1)
            lines.append("")
        else:
            lines.append(line)
    masked = "\n".join(lines)
    return re.sub(r"<!--.*?-->", lambda found: "\n" * found.group(0).count("\n"), masked, flags=re.S)


def mask_inline_code(text):
    return re.sub(r"(`+)(.+?)\1", lambda found: re.sub(r"[^\n]", " ", found.group(0)), text, flags=re.S)


def heading_plain(text):
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("*", "")
    text = re.sub(r"(?<!\w)_+([^_]+?)_+(?!\w)", r"\1", text)
    text = re.sub(r":[a-z0-9_+-]+:", "\u2605", text)  # a shortcode becomes an emoji, dropped later like any symbol
    return text.strip()


def heading_slug(text):
    """GitHub anchor of a heading: lowercase, punctuation dropped except - and _, spaces become hyphens."""
    lowered = heading_plain(text).lower()
    return "".join(char for char in lowered if char.isalnum() or char in "-_ ").replace(" ", "-")


def slugs_with_duplicates(texts):
    """Anchors of the headings in document order; the repeats get -1, -2..."""
    seen, slugs = {}, []
    for text in texts:
        slug = heading_slug(text)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        slugs.append(slug if count == 0 else "%s-%d" % (slug, count))
    return slugs


def find_headings(masked):
    """[(offset, raw text)] for ATX, setext and HTML headings, in document order."""
    found, lines, pos = [], masked.split("\n"), 0
    starts = []
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    for index, line in enumerate(lines):
        match = ATX_RE.match(line)
        if match and match.group(1):
            found.append((starts[index], match.group(1)))
        elif index > 0 and SETEXT_RE.match(line):
            prev = lines[index - 1].strip()
            if prev and not prev.startswith(("#", ">", "|", "-", "*", "+", "<", "=")) \
                    and not re.match(r"^\d+[.)]\s", prev):
                found.append((starts[index - 1], prev))
    for match in HTML_HEADING_RE.finditer(masked):
        found.append((match.start(), match.group(2)))
    return sorted(found)


def parse_attrs(raw):
    attrs = {}
    for match in ATTR_RE.finditer(raw):
        value = next(group for group in match.groups()[1:] if group is not None)
        attrs.setdefault(match.group(1).lower(), html.unescape(value))
    return attrs


def srcset_urls(value):
    urls = []
    for part in value.split(","):
        token = part.strip().split(" ")[0] if part.strip() else ""
        if token and not token.startswith("data:"):
            urls.append(token)
    return urls


def extract_references(masked):
    """Targets found in the Markdown and inline HTML: [{kind, target, line}] plus the explicit anchor ids.

    kind: image (shown), source (picture/video alternatives), link, media (video, audio).
    """
    text = mask_inline_code(masked)

    def line_of(pos):
        return text.count("\n", 0, pos) + 1

    refs, ids = [], set()
    for match in MD_IMAGE_RE.finditer(text):
        refs.append({"kind": "image", "target": match.group(1).strip("<>"), "line": line_of(match.start())})
    for match in MD_LINK_RE.finditer(text):
        refs.append({"kind": "link", "target": match.group(1).strip("<>"), "line": line_of(match.start())})
    for match in AUTOLINK_RE.finditer(text):
        refs.append({"kind": "link", "target": match.group(1), "line": line_of(match.start())})
    defs = {}
    for match in REF_DEF_RE.finditer(text):
        label = " ".join(match.group(1).lower().split())
        defs[label] = (match.group(2).strip("<>"), line_of(match.start()))
    image_labels, undefined = set(), []
    for match in REF_USE_RE.finditer(text):
        label = " ".join((match.group(3) or match.group(2)).lower().split())
        if label not in defs:
            undefined.append((label, line_of(match.start())))
        elif match.group(1):
            image_labels.add(label)
    for label, (target, line) in defs.items():
        refs.append({"kind": "image" if label in image_labels else "link", "target": target, "line": line})
    for match in HTML_TAG_RE.finditer(text):
        tag, attrs = match.group(1).lower(), parse_attrs(match.group(2))
        line = line_of(match.start())
        for key in ("id", "name"):
            if attrs.get(key):
                ids.add(attrs[key].lower())
        if tag == "img" and attrs.get("src"):
            refs.append({"kind": "image", "target": attrs["src"], "line": line})
        if tag in ("img", "source") and attrs.get("srcset"):
            for url in srcset_urls(attrs["srcset"]):
                refs.append({"kind": "source", "target": url, "line": line})
        if tag == "source" and attrs.get("src"):
            refs.append({"kind": "source", "target": attrs["src"], "line": line})
        if tag in ("video", "audio") and attrs.get("src"):
            refs.append({"kind": "media", "target": attrs["src"], "line": line})
        if tag == "video" and attrs.get("poster"):
            refs.append({"kind": "image", "target": attrs["poster"], "line": line})
        if tag == "a" and attrs.get("href"):
            refs.append({"kind": "link", "target": attrs["href"], "line": line})
    return refs, ids, undefined


def classify_target(target):
    """(kind, value): anchor (fragment), external (http, https, //), other (mailto, data...), local (path), empty."""
    value = html.unescape(target.strip())
    if not value:
        return "empty", value
    if value.startswith("#"):
        return "anchor", value[1:]
    if value.startswith("//") or SCHEME_RE.match(value):
        return ("external" if re.match(r"^(https?:)?//", value, re.I) else "other"), value
    return "local", value


def lint_svg(text, name="image.svg"):
    """(blocking, warnings) for an SVG used through <img>: no script, no external resource, motion preferences."""
    blocking, warnings = [], []
    if re.search(r"<script\b", text, re.I):
        blocking.append("%s: contains <script (scripts never run inside <img>, remove it)" % name)
    if re.search(r"<[^>]*\son[a-z]+\s*=", text, re.I):
        blocking.append("%s: contains an on*= event attribute (never runs inside <img>, remove it)" % name)
    external = (r"(?:xlink:)?href\s*=\s*[\"']\s*https?:", r"\bsrc\s*=\s*[\"']\s*https?:",
                r"url\(\s*[\"']?\s*https?:", r"@import\s+(?:url\(\s*)?[\"']?\s*https?:")
    if any(re.search(pattern, text, re.I) for pattern in external):
        blocking.append("%s: references an external http(s) resource (it will not load inside <img>, inline it)"
                        % name)
    if re.search(r"<foreignObject\b", text, re.I):
        warnings.append("%s: <foreignObject> is rendered inconsistently across browsers" % name)
    if re.search(r"@font-face", text, re.I):
        warnings.append("%s: @font-face cannot load fonts inside <img>, the fallback font will be used" % name)
    root = re.search(r"<svg\b[^>]*>", text, re.I | re.S)
    if root and not re.search(r"\bviewBox\s*=", root.group(0)):
        warnings.append("%s: the root <svg> has no viewBox (it will not scale on mobile)" % name)
    if SVG_ANIMATION_RE.search(text) and not re.search(r"prefers-reduced-motion", text, re.I):
        warnings.append("%s: animation without a prefers-reduced-motion media query" % name)
    return blocking, warnings


def exact_case_exists(root, candidate):
    """(exists, case_ok): walk the path part by part, as GitHub (case sensitive) would."""
    if not os.path.exists(candidate):
        return False, False
    try:
        rel = os.path.relpath(candidate, root)
    except ValueError:
        return True, True
    if rel.startswith(".."):
        return True, True
    current = root
    for part in [piece for piece in rel.split(os.sep) if piece not in ("", ".")]:
        try:
            if part not in os.listdir(current):
                return True, False
        except OSError:
            return True, True
        current = os.path.join(current, part)
    return True, True


def word_count(masked):
    text = re.sub(r"<[^>]+>", " ", masked)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\]\([^)]*\)", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return len(re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", text))


def analyze_readme(repo, file="README.md"):
    """Static analysis; returns (result, external links as [(line, url)])."""
    repo = Path(repo).resolve()
    path = repo / file
    blocking, warnings, externals = [], [], []
    stats = {"lines": 0, "words": 0, "reading_minutes": 0.0, "images": 0, "headings": 0, "links": 0,
             "first_visual_line": None}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ({"ok": False, "blocking": ["%s not found" % file], "warnings": [], "stats": stats}, [])
    masked = mask_blocks(text)
    refs, ids, undefined = extract_references(masked)
    headings = find_headings(masked)
    anchors = {slug for slug in slugs_with_duplicates([raw for _, raw in headings])} | ids
    readme_dir = path.parent
    try:
        tracked = set(tracked_files(repo))
    except Failure:
        tracked = None
    tracked_dirs = {posixpath.dirname(name) for name in tracked or ()}
    for name in list(tracked_dirs):
        while name:
            name = posixpath.dirname(name)
            tracked_dirs.add(name)
    seen, svg_done, size_done = set(), set(), set()
    first_visual = None
    for label, line in undefined:
        warnings.append("%s:%d: reference link '%s' has no definition" % (file, line, label))
    for ref in refs:
        kind, value = classify_target(ref["target"])
        where = "%s:%d" % (file, ref["line"])
        if ref["kind"] == "image":
            stats["images"] += 1
        if ref["kind"] == "image" and kind != "empty" and first_visual is None and not BADGE_RE.search(value):
            first_visual = ref["line"]
        if ref["kind"] == "link" and kind == "external" and value.startswith(("http://", "https://")):
            externals.append((ref["line"], value))
        if ref["kind"] == "link":
            stats["links"] += 1
        key = (ref["kind"], kind, value, ref["line"])
        if key in seen:
            continue
        seen.add(key)
        if kind == "anchor":
            fragment = unquote(value).lower()
            if fragment and fragment != "top" and not fragment.startswith(("fn-", "fnref-", "user-content-")) \
                    and fragment not in anchors:
                warnings.append("%s: anchor '#%s' matches no heading or id" % (where, value))
        elif kind == "local":
            rel = unquote(re.split(r"[?#]", value, maxsplit=1)[0])
            if not rel:
                continue
            base = str(repo) if rel.startswith("/") else str(readme_dir)
            candidate = os.path.normpath(os.path.join(base, rel.lstrip("/")))
            inside = candidate == str(repo) or candidate.startswith(str(repo) + os.sep)
            exists, case_ok = exact_case_exists(str(repo), candidate)
            if not exists or not inside:
                blocking.append("%s: missing file for %s '%s'" % (where, ref["kind"], rel))
                continue
            if not case_ok:
                blocking.append("%s: '%s' differs in case from the file on disk (GitHub is case sensitive)"
                                % (where, rel))
                continue
            relpath = os.path.relpath(candidate, str(repo)).replace(os.sep, "/")
            if tracked is not None and relpath not in tracked and relpath not in tracked_dirs:
                warnings.append("%s: '%s' is not tracked by git (it will be missing on GitHub until committed)"
                                % (where, relpath))
            if os.path.isfile(candidate) and ref["kind"] in ("image", "source") and candidate not in size_done:
                size_done.add(candidate)
                size = os.path.getsize(candidate)
                if size > IMAGE_BLOCK_BYTES:
                    blocking.append("%s: image '%s' is %.1f MB (over 10 MB)" % (where, relpath, size / 1e6))
                elif size > IMAGE_WARN_BYTES:
                    warnings.append("%s: image '%s' is %.1f MB (over 1 MB, compress or resize)"
                                    % (where, relpath, size / 1e6))
            if candidate.lower().endswith(".svg") and os.path.isfile(candidate) and candidate not in svg_done \
                    and ref["kind"] in ("image", "source"):
                svg_done.add(candidate)
                svg_text = Path(candidate).read_text(encoding="utf-8", errors="replace")
                svg_blocking, svg_warnings = lint_svg(svg_text, relpath)
                blocking += svg_blocking
                warnings += svg_warnings
    seen_urls = set()
    unique_externals = []
    for line, url in externals:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_externals.append((line, url))
    words = word_count(masked)
    stats.update(lines=len(text.splitlines()), words=words, reading_minutes=round(words / 230.0, 1),
                 headings=len(headings), first_visual_line=first_visual)
    if first_visual is None:
        warnings.append("%s: no image, screenshot or GIF (badges excluded): a visual in the first %d lines "
                        "makes the README easier to scan" % (file, FIRST_VISUAL_MAX_LINE))
    elif first_visual > FIRST_VISUAL_MAX_LINE:
        warnings.append("%s:%d: first visual is after line %d" % (file, first_visual, FIRST_VISUAL_MAX_LINE))
    blocking = list(dict.fromkeys(blocking))
    warnings = list(dict.fromkeys(warnings))
    return ({"ok": not blocking, "blocking": blocking, "warnings": warnings, "stats": stats},
            unique_externals)


def static_readme_checks(repo, file="README.md"):
    """{"ok", "blocking", "warnings", "stats"}: missing local targets and unsafe SVG block, the rest warns."""
    return analyze_readme(repo, file)[0]


def check_one_link(url, timeout=10):
    """(status or None, error text): HEAD first, GET if HEAD fails or is refused."""
    headers = {"User-Agent": "Mozilla/5.0 (repo-showcase link check)"}
    last_status, last_error = None, ""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, ""
        except HTTPError as error:
            error.close()
            last_status, last_error = error.code, "HTTP %d" % error.code
        except Exception as error:  # noqa: BLE001
            last_status, last_error = None, first_line(error) or type(error).__name__
    return last_status, last_error


UNVERIFIABLE_STATUS = (401, 403, 429, 999)


def check_links(urls, timeout=10, workers=8):
    """{"checked", "failed": [{url, error}], "unverified": [url]}: the sites that block bots are not failures."""
    result = {"checked": len(urls), "failed": [], "unverified": []}
    if not urls:
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda url: check_one_link(url, timeout), urls))
    for url, (status, error) in zip(urls, outcomes):
        if error == "":
            continue
        if status in UNVERIFIABLE_STATUS:
            result["unverified"].append(url)
        else:
            result["failed"].append({"url": url, "error": error})
    return result


# ---------------------------------------------------------------------------------------------------------------
# Render of the README
# ---------------------------------------------------------------------------------------------------------------

FALLBACK_CSS = {
    "light": ".markdown-body{color:#1f2328;font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,"
             "sans-serif;word-wrap:break-word}.markdown-body a{color:#0969da}.markdown-body h1,.markdown-body h2{"
             "border-bottom:1px solid #d1d9e0;padding-bottom:.3em}.markdown-body code,.markdown-body pre{background:"
             "#f6f8fa;border-radius:6px}.markdown-body pre{padding:16px;overflow:auto}.markdown-body code{padding:"
             ".2em .4em;font-size:85%}.markdown-body img{max-width:100%}.markdown-body table{border-collapse:collapse}"
             ".markdown-body td,.markdown-body th{border:1px solid #d1d9e0;padding:6px 13px}",
    "dark": ".markdown-body{color:#f0f6fc;font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,"
            "sans-serif;word-wrap:break-word}.markdown-body a{color:#4493f8}.markdown-body h1,.markdown-body h2{"
            "border-bottom:1px solid #3d444d;padding-bottom:.3em}.markdown-body code,.markdown-body pre{background:"
            "#151b23;border-radius:6px}.markdown-body pre{padding:16px;overflow:auto}.markdown-body code{padding:"
            ".2em .4em;font-size:85%}.markdown-body img{max-width:100%}.markdown-body table{border-collapse:collapse}"
            ".markdown-body td,.markdown-body th{border:1px solid #3d444d;padding:6px 13px}",
}
PAGE_BACKGROUNDS = {"light": "#ffffff", "dark": "#0d1117"}
PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="@@BASE@@">
<style>@@CSS@@</style>
<style>
html,body{margin:0;background:@@BG@@}
.markdown-body{box-sizing:border-box;max-width:880px;margin:0 auto;padding:32px}
@media (max-width:480px){.markdown-body{padding:16px}}
</style></head>
<body><article class="markdown-body">@@BODY@@</article></body></html>
"""


def fetch_css(theme, timeout=8):
    """(css, source): github-markdown-css from the CDN, or the builtin fallback if the fetch fails."""
    url = MARKDOWN_CSS_URL % theme
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            css = response.read().decode("utf-8")
        if ".markdown-body" in css:
            return css, url
    except Exception:  # noqa: BLE001
        pass
    return FALLBACK_CSS[theme], "builtin fallback"


def render_markdown_html(readme_path):
    """HTML of the README from `gh api markdown` (mode=markdown, like the file view). Failure if gh cannot."""
    result = run(["gh", "api", "markdown", "-f", "mode=markdown", "-F", "text=@%s" % readme_path], check=False,
                 timeout=60)
    if result.returncode != 0:
        raise Failure(EXIT_NETWORK, "gh api markdown failed: %s"
                      % (first_line(result.stderr.decode("utf-8", "replace")) or "exit code %d" % result.returncode))
    body = result.stdout.decode("utf-8", "replace")
    if not body.strip():
        raise Failure(EXIT_NETWORK, "gh api markdown returned nothing")
    return body


def build_preview_page(body, css, theme, base_url, repo_url):
    """Standalone page: GitHub's HTML in an 880 px article. Root-relative src (/img.png) point to the repo root."""
    body = re.sub(r"""\b(src|srcset)=(["'])/(?!/)""", lambda found: "%s=%s%s" % (found.group(1), found.group(2), repo_url),
                  body)
    return (PAGE_TEMPLATE.replace("@@BASE@@", html.escape(base_url, quote=True)).replace("@@CSS@@", css)
            .replace("@@BG@@", PAGE_BACKGROUNDS[theme]).replace("@@BODY@@", body))


WAIT_IMAGES_JS = """() => Promise.all(Array.from(document.images).map(img => img.complete ? 0 :
  new Promise(resolve => { img.onload = img.onerror = resolve; setTimeout(resolve, 8000); })))"""


def render_preview(body, repo, readme_dir, out, widths, themes):
    """Screenshots of the rendered README. Returns the render section of the preview output."""
    sync_playwright = load_playwright()
    base_url = Path(readme_dir).as_uri() + "/"
    repo_url = Path(repo).as_uri() + "/"
    has_svg = ".svg" in body.lower()
    desktop = max(widths)
    shots, pages, failed = [], [], []
    css_sources = {}
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            for theme in themes:
                css, source = fetch_css(theme)
                css_sources[theme] = source
                page_file = Path(out) / ("preview-%s.html" % theme)
                page_file.write_text(build_preview_page(body, css, theme, base_url, repo_url), encoding="utf-8")
                pages.append(str(page_file))
                for width in widths:
                    context = browser.new_context(**viewport_options(width, theme, 1))
                    try:
                        page = context.new_page()
                        page.on("requestfailed", lambda request: failed.append(request.url)
                                if request.resource_type == "image" else None)
                        page.goto(page_file.as_uri(), wait_until="load", timeout=30000)
                        try:
                            page.evaluate(WAIT_IMAGES_JS)
                        except Exception:  # noqa: BLE001
                            pass
                        page.wait_for_timeout(1500 if has_svg else 200)
                        full = Path(out) / ("readme-%d-%s.png" % (width, theme))
                        page.screenshot(path=str(full), full_page=True)
                        shots.append(file_entry(full, kind="full", width=width, theme=theme))
                        if width == desktop:
                            fold = Path(out) / ("readme-fold-%s.png" % theme)
                            page.screenshot(path=str(fold), clip={"x": 0, "y": 0, "width": width, "height": 900})
                            shots.append(file_entry(fold, kind="fold", width=width, theme=theme))
                    finally:
                        context.close()
        finally:
            browser.close()
    return {"screenshots": shots, "pages": pages, "css": css_sources,
            "failed_images": sorted(set(failed))}


def preview(repo, file, out, widths, themes, static_only, links):
    root = repo_root(repo)
    out = Path(out) if out else state_dir(root) / "preview"
    out.mkdir(parents=True, exist_ok=True)
    static, externals = analyze_readme(root, file)
    result = {"ok": static["ok"], "repo": str(root), "file": file, "out": str(out), "static": static}
    if links:
        link_result = check_links([url for _, url in externals])
        result["link_check"] = link_result
        for item in link_result["failed"]:
            static["warnings"].append("external link not reachable: %s (%s)" % (item["url"], item["error"]))
    if static_only:
        result["render"] = {"skipped": "--static-only"}
        return result, (EXIT_OK if static["ok"] else EXIT_FINDINGS)
    readme = root / file
    try:
        body = render_markdown_html(readme)
    except Failure as failure:
        result["render"] = {"skipped": str(failure)}
        return result, (EXIT_OK if static["ok"] else EXIT_FINDINGS)
    result["render"] = render_preview(body, root, readme.parent, out, widths, themes)
    return result, (EXIT_OK if static["ok"] else EXIT_FINDINGS)


# ---------------------------------------------------------------------------------------------------------------
# social
# ---------------------------------------------------------------------------------------------------------------

BG_RE = re.compile(r"^[#\w(),.% -]{1,40}$")


def social_html(source_uri, bg, fit):
    """Page of exactly 1280x640 showing the source image (SVG or bitmap) on the background."""
    if not BG_RE.match(bg):
        raise Failure(EXIT_USAGE, "--bg expects a CSS color such as #0d1117")
    if fit not in ("contain", "cover"):
        raise Failure(EXIT_USAGE, "--fit expects contain or cover")
    return ('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1280px;height:640px;'
            'overflow:hidden;background:%s}img{display:block;width:1280px;height:640px;object-fit:%s}</style></head>'
            '<body><img src="%s"></body></html>' % (bg, fit, html.escape(source_uri, quote=True)))


def social(repo, source, out, bg="#0d1117", fit="contain", delay=1500):
    root = repo_root(repo)
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise Failure(EXIT_USAGE, "source not found: %s" % source)
    suffix = source.suffix.lower()
    if suffix not in (".svg", ".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise Failure(EXIT_USAGE, "unsupported source type: %s" % suffix)
    out = Path(out) if out else state_dir(root) / "social-preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sync_playwright = load_playwright()
    warnings, jpeg = [], None
    with tempfile.TemporaryDirectory(prefix="showcase-social-") as tmp:
        if suffix in (".html", ".htm"):
            target = source.as_uri()
        else:
            wrapper = Path(tmp) / "social.html"
            wrapper.write_text(social_html(source.as_uri(), bg, fit), encoding="utf-8")
            target = wrapper.as_uri()
        with sync_playwright() as pw:
            browser = launch_chromium(pw)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 640}, device_scale_factor=1)
                try:
                    page = context.new_page()
                    page.goto(target, wait_until="load", timeout=30000)
                    page.wait_for_timeout(delay)
                    page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1280, "height": 640})
                    if out.stat().st_size > SOCIAL_MAX_BYTES:
                        warnings.append("PNG is %.2f MB (GitHub limit 1 MB): a JPEG version was written instead"
                                        % (out.stat().st_size / 1e6))
                        jpeg_path = out.with_suffix(".jpg")
                        for quality in (90, 80, 70, 55):
                            page.screenshot(path=str(jpeg_path), type="jpeg", quality=quality,
                                            clip={"x": 0, "y": 0, "width": 1280, "height": 640})
                            if jpeg_path.stat().st_size <= SOCIAL_MAX_BYTES:
                                break
                        jpeg = jpeg_path
                finally:
                    context.close()
            finally:
                browser.close()
    result = {"path": str(out), "bytes": out.stat().st_size, "pixels": "%dx%d" % png_size(out),
              "under_1mb": out.stat().st_size <= SOCIAL_MAX_BYTES, "warnings": warnings,
              "instruction": SOCIAL_INSTRUCTION}
    if jpeg:
        result["jpeg"] = file_entry(jpeg)
        result["upload"] = str(jpeg) if jpeg.stat().st_size <= SOCIAL_MAX_BYTES else str(out)
        if jpeg.stat().st_size > SOCIAL_MAX_BYTES:
            warnings.append("JPEG is still over 1 MB: simplify the artwork (fewer gradients, no photo)")
    return result


# ---------------------------------------------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------------------------------------------

INSTALL_HINTS = {
    "git": {"macos": "brew install git", "debian": "apt install git"},
    "git_upgrade": {"macos": "brew upgrade git", "debian": "install a newer git (backports or the git-core PPA)"},
    "gh": {"macos": "brew install gh && gh auth login",
           "debian": "apt install gh (or see the GitHub CLI Linux install guide) then gh auth login"},
    "git-filter-repo": {"macos": "brew install git-filter-repo", "debian": "apt install git-filter-repo "
                                                                          "(or pip install git-filter-repo)"},
    "gitleaks": {"macos": "brew install gitleaks", "debian": "download the binary from the gitleaks GitHub releases"},
    "ffmpeg": {"macos": "brew install ffmpeg", "debian": "apt install ffmpeg"},
    "ffmpeg_libwebp": {"macos": "reinstall ffmpeg built with libwebp (GIF and MP4 do not need it)",
                       "debian": "apt install ffmpeg (the Debian build includes libwebp)"},
    "exiftool": {"macos": "brew install exiftool", "debian": "apt install libimage-exiftool-perl"},
    "playwright": {"macos": "python3 -m venv ~/.venvs/site-design && ~/.venvs/site-design/bin/pip install playwright"
                            " && ~/.venvs/site-design/bin/playwright install chromium",
                   "debian": "pip install playwright && playwright install --with-deps chromium"},
    "chromium": {"macos": "~/.venvs/site-design/bin/playwright install chromium",
                 "debian": "playwright install --with-deps chromium"},
    "Pillow": {"macos": "pip install Pillow", "debian": "apt install python3-pil (or pip install Pillow)"},
    "cv2": {"macos": "pip install opencv-python-headless", "debian": "apt install python3-opencv "
                                                                    "(or pip install opencv-python-headless)"},
    "vision": {"macos": "pip install pyobjc-framework-Vision", "debian": "not available (macOS only)"},
}
PLAYWRIGHT_PROBE = """
import json
out = {"importable": False, "version": None, "chromium": False, "error": None}
try:
    from playwright.sync_api import sync_playwright
    out["importable"] = True
    try:
        from importlib.metadata import version
        out["version"] = version("playwright")
    except Exception:
        pass
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        browser.close()
        out["chromium"] = True
except Exception as error:
    out["error"] = (str(error).strip().splitlines() or [""])[0][:200]
print(json.dumps(out))
"""


def command_version(command, pattern=r"(\d+(?:\.\d+)+)"):
    """{"present": bool, "version": str or None} for a command that prints its version."""
    try:
        result = run(command, check=False, timeout=20)
    except (Failure, subprocess.TimeoutExpired):
        return {"present": False, "version": None}
    if result.returncode != 0:
        return {"present": False, "version": None}
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    match = re.search(pattern, text)
    return {"present": True, "version": match.group(1) if match else (text.strip().splitlines() or [""])[0][:60]}


def python_module(module, dists):
    if importlib.util.find_spec(module) is None:
        return {"present": False, "version": None}
    version = None
    try:
        from importlib import metadata
        for dist in dists:
            try:
                version = metadata.version(dist)
                break
            except metadata.PackageNotFoundError:
                continue
    except ImportError:
        pass
    return {"present": True, "version": version}


def probe_playwright():
    """Playwright and Chromium check, run as a child process with the interpreter that can import it."""
    interpreter = sys.executable if importlib.util.find_spec("playwright") else (
        str(VENV_PYTHON) if VENV_PYTHON.exists() else None)
    info = {"present": False, "version": None, "chromium": False, "interpreter": interpreter, "error": None}
    if not interpreter:
        info["error"] = "playwright is not importable and ~/.venvs/site-design does not exist"
        return info
    try:
        result = run([interpreter, "-c", PLAYWRIGHT_PROBE], check=False, timeout=90)
        data = json.loads(result.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
    except (Failure, subprocess.TimeoutExpired, ValueError, IndexError) as error:
        info["error"] = first_line(error) or "probe failed"
        return info
    info.update(present=data["importable"], version=data["version"], chromium=data["chromium"], error=data["error"])
    return info


def gh_auth_info():
    try:
        status = run(["gh", "auth", "status"], check=False, timeout=30)
    except Failure:
        return {"logged_in": False, "login": None, "scopes": []}
    text = (status.stdout + status.stderr).decode("utf-8", "replace")
    logged_in = "Logged in to" in text
    scopes = []
    for line in re.findall(r"Token scopes:\s*(.*)", text):
        scopes += re.findall(r"'([^']+)'", line) or [part.strip() for part in line.split(",") if part.strip()]
    login = None
    if logged_in:
        who = run(["gh", "api", "user", "--jq", ".login"], check=False, timeout=30)
        login = who.stdout.decode("utf-8", "replace").strip() or None if who.returncode == 0 else None
    return {"logged_in": logged_in, "login": login, "scopes": list(dict.fromkeys(scopes))}


def compute_ready_for(tools, gh_auth, git_ver):
    faces = tools["cv2"]["present"] or tools.get("vision", {}).get("present", False)
    screenshots = tools["playwright"]["present"] and tools["playwright"]["chromium"]
    return {
        "audit": tools["git"]["present"],
        "history_rewrite": tools["git-filter-repo"]["present"] and tuple(git_ver) >= (2, 36),
        "github_metadata": bool(gh_auth["logged_in"]),
        "screenshots": screenshots,
        "demo": screenshots and tools["ffmpeg"]["present"],
        "faces": faces,
        "photo_metadata": True,
        "deep_secrets": tools["gitleaks"]["present"],
    }


def missing_hints(tools, git_ver):
    keys = [name for name, info in tools.items() if not info["present"]]
    if tools["git"]["present"] and tuple(git_ver) < (2, 36):
        keys.append("git_upgrade")
    if tools["playwright"]["present"] and not tools["playwright"]["chromium"]:
        keys.append("chromium")
    if tools["ffmpeg"]["present"] and not tools["ffmpeg"].get("libwebp"):
        keys.append("ffmpeg_libwebp")
    if platform.system() != "Darwin":
        keys = [key for key in keys if key != "vision"]
    return {key: INSTALL_HINTS[key] for key in keys if key in INSTALL_HINTS}


def doctor_report():
    tools = {"git": command_version(["git", "--version"]),
             "gh": command_version(["gh", "--version"]),
             "git-filter-repo": command_version(["git", "filter-repo", "--version"], r"(\S+)"),
             "gitleaks": command_version(["gitleaks", "version"]),
             "ffmpeg": command_version(["ffmpeg", "-version"], r"version\s+(\S+)"),
             "exiftool": command_version(["exiftool", "-ver"])}
    tools["ffmpeg"]["libwebp"] = tools["ffmpeg"]["present"] and "libwebp" in ffmpeg_encoders()
    tools["playwright"] = probe_playwright()
    tools["Pillow"] = python_module("PIL", ["Pillow", "pillow"])
    tools["cv2"] = python_module("cv2", ["opencv-python", "opencv-python-headless", "opencv-contrib-python"])
    if platform.system() == "Darwin":
        tools["vision"] = python_module("Vision", ["pyobjc-framework-Vision"])
    git_ver = git_version() if tools["git"]["present"] else (0, 0, 0)
    gh_auth = gh_auth_info() if tools["gh"]["present"] else {"logged_in": False, "login": None, "scopes": []}
    ready = compute_ready_for(tools, gh_auth, git_ver)
    return {"ok": ready["audit"], "python": platform.python_version(), "platform": platform.system(),
            "git_version": ".".join(str(part) for part in git_ver), "tools": tools, "gh_auth": gh_auth,
            "ready_for": ready, "install_hints": missing_hints(tools, git_ver)}


# ---------------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------------


def add_serve_arguments(parser):
    parser.add_argument("--serve", default=None, metavar="CMD",
                        help="dev server command started for the capture (no shell), e.g. 'npm run dev -- --port 5173'")
    parser.add_argument("--serve-cwd", default=None, help="working folder of the server command")
    parser.add_argument("--serve-timeout", type=int, default=120, help="seconds to wait for the URL to answer")


def cmd_doctor(args):
    report = doctor_report()
    print_json(report)
    return EXIT_OK if report["ok"] else EXIT_MISSING


def cmd_shoot(args):
    widths = parse_int_list(args.widths, "--widths")
    themes = parse_themes(args.themes)
    if args.scale <= 0 or args.scale > 4:
        raise Failure(EXIT_USAGE, "--scale expects a number between 0 and 4")
    load_playwright()  # may re-exec into the Playwright venv: do it before a dev server is started
    with dev_server(args.serve, args.serve_cwd, args.url, args.serve_timeout):
        result = shoot(args.url, args.out, args.routes, widths, themes, args.full_page, args.selector, args.wait_for,
                       args.delay, args.scale, args.frame)
    result.update(ok=True, out=str(Path(args.out)))
    print_json(result)
    return EXIT_OK


def cmd_demo(args):
    steps = load_steps(args.steps)
    viewport = parse_viewport(args.viewport)
    suffix = Path(args.out).suffix.lower().lstrip(".")
    fmt = args.format or (suffix if suffix in ("gif", "webp", "mp4") else "gif")
    if not 1 <= args.fps <= 60 or not 100 <= args.width <= 3840 or args.trim_start < 0:
        raise Failure(EXIT_USAGE, "--fps must be 1-60, --width 100-3840 and --trim-start >= 0")
    load_playwright()  # may re-exec into the Playwright venv: do it before a dev server is started
    with dev_server(args.serve, args.serve_cwd, args.url, args.serve_timeout):
        result = demo(args.url, steps, args.out, viewport, args.width, args.fps, fmt, args.trim_start, args.theme,
                      not args.no_cursor)
    result["ok"] = True
    print_json(result)
    return EXIT_OK


def cmd_preview(args):
    widths = parse_int_list(args.widths, "--widths")
    themes = parse_themes(args.themes)
    result, code = preview(args.repo, args.file, args.out, widths, themes, args.static_only, args.check_links)
    print_json(result)
    return code


def cmd_social(args):
    result = social(args.repo, args.source, args.out, args.bg, args.fit)
    result["ok"] = True
    print_json(result)
    return EXIT_OK


def add_commands(subparsers):
    doctor = subparsers.add_parser("doctor", help="dependencies and what they enable")
    doctor.set_defaults(func=cmd_doctor)

    shoot_parser = subparsers.add_parser("shoot", help="screenshots of a live site or a local dev server")
    shoot_parser.add_argument("url")
    shoot_parser.add_argument("--out", required=True, help="output folder")
    shoot_parser.add_argument("--routes", nargs="+", default=["/"], metavar="ROUTE")
    shoot_parser.add_argument("--widths", default="1440,390", help="comma-separated; 480 or less is a phone")
    shoot_parser.add_argument("--themes", default="light,dark")
    shoot_parser.add_argument("--full-page", action="store_true")
    shoot_parser.add_argument("--selector", default=None, help="clip to the first element matching this CSS")
    shoot_parser.add_argument("--wait-for", default=None, help="CSS selector to wait for before the capture")
    shoot_parser.add_argument("--delay", type=int, default=300, help="extra wait in ms before the capture")
    shoot_parser.add_argument("--scale", type=float, default=2.0, help="device scale factor")
    shoot_parser.add_argument("--frame", choices=("none", "browser", "phone"), default="none")
    add_serve_arguments(shoot_parser)
    shoot_parser.set_defaults(func=cmd_shoot)

    demo_parser = subparsers.add_parser("demo", help="recorded walkthrough converted to GIF, WebP or MP4")
    demo_parser.add_argument("url")
    demo_parser.add_argument("--steps", required=True, help="JSON file: list of single-key step objects")
    demo_parser.add_argument("--out", required=True, help="output file (.gif, .webp or .mp4)")
    demo_parser.add_argument("--viewport", default="1280x800")
    demo_parser.add_argument("--width", type=int, default=960, help="width of the converted file")
    demo_parser.add_argument("--fps", type=int, default=12)
    demo_parser.add_argument("--format", choices=("gif", "webp", "mp4"), default=None,
                             help="default: from the --out extension, else gif")
    demo_parser.add_argument("--trim-start", type=float, default=0.5, help="seconds cut from the start")
    demo_parser.add_argument("--theme", choices=THEMES, default="light")
    demo_parser.add_argument("--no-cursor", action="store_true", help="do not draw a pointer in the recording")
    add_serve_arguments(demo_parser)
    demo_parser.set_defaults(func=cmd_demo)

    preview_parser = subparsers.add_parser("preview", help="README checks and render as on GitHub")
    preview_parser.add_argument("repo", nargs="?", default=".")
    preview_parser.add_argument("--file", default="README.md")
    preview_parser.add_argument("--out", default=None, help="default: <git dir>/repo-showcase/preview")
    preview_parser.add_argument("--widths", default="880,390")
    preview_parser.add_argument("--themes", default="light,dark")
    preview_parser.add_argument("--static-only", action="store_true", help="checks only, no render")
    preview_parser.add_argument("--check-links", action="store_true", help="also test the external links")
    preview_parser.set_defaults(func=cmd_preview)

    social_parser = subparsers.add_parser("social", help="1280x640 social preview image")
    social_parser.add_argument("repo", nargs="?", default=".")
    social_parser.add_argument("--source", required=True, help="SVG, HTML or image file")
    social_parser.add_argument("--out", default=None, help="default: <git dir>/repo-showcase/social-preview.png")
    social_parser.add_argument("--bg", default="#0d1117")
    social_parser.add_argument("--fit", choices=("contain", "cover"), default="contain")
    social_parser.set_defaults(func=cmd_social)


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(prog="capture.py")
    _sub = _parser.add_subparsers(dest="command", metavar="<command>")
    _sub.required = True
    add_commands(_sub)
    _args = _parser.parse_args()
    try:
        sys.exit(_args.func(_args))
    except Failure as _failure:
        print_json({"ok": False, "error": str(_failure)})
        sys.exit(_failure.code)
