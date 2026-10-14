#!/usr/bin/env python3
"""Fetch a web page, falling back to the residential proxy if direct access is blocked.

Usage: fetch_url.py <url> [--text] [--out FILE] [--no-proxy] [--force-proxy] [--timeout S] [--max-bytes N]
  --text         extract the readable text of the HTML (without script/style tags)
  --out          write the body to a file instead of including it in the JSON
  --no-proxy     never use the proxy
  --force-proxy  go through the proxy directly (no direct attempt)
The proxy is only tried after a block (403, 429, 503, timeout) and only if it is configured
in local.env. It is not meant to bypass a login or a subscription: only an IP address block.

Output: JSON on stdout (url, status, via, content_type, bytes, text|file). Exit codes:
  0 success; 1 unexpected error; 2 invalid URL; 4 blocked even with the proxy (or proxy missing); 6 HTTP error
  other than a block (404, 500...); 7 network unreachable.
Python 3.9 compatible, standard library only.
"""
import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import cttools  # noqa: E402

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID, EXIT_BLOCKED, EXIT_HTTP, EXIT_NETWORK = 0, 1, 2, 4, 6, 7
BLOCK_STATUSES = {403, 429, 503}
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header",
              "footer", "ul", "ol", "table", "blockquote", "pre"}


class Blocked(Exception):
    pass


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html):
    parser = TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def validate_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("http(s) URL expected: %s" % url)
    return url


def request(url, proxy, timeout, max_bytes):
    """Return (status, content_type, body as bytes, charset). Raises Blocked on a block, URLError on network failure."""
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                               "Accept-Language": "fr,en;q=0.8"})
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, response.headers.get_content_type(), body[:max_bytes], charset
    except urllib.error.HTTPError as error:
        if error.code in BLOCK_STATUSES:
            raise Blocked("HTTP %d" % error.code)
        return error.code, error.headers.get_content_type() if error.headers else "", b"", "utf-8"
    except (TimeoutError, urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise Blocked("timeout")
        raise


def fetch(url, timeout, max_bytes, use_proxy_mode, local_env=None):
    """use_proxy_mode: 'auto' (fallback), 'never', 'always'. Return (response, via)."""
    proxy = cttools.configured_proxy(local_env)
    if use_proxy_mode == "always":
        if not proxy:
            raise Blocked("proxy missing from local.env")
        return request(url, proxy, timeout, max_bytes), "proxy"
    try:
        return request(url, None, timeout, max_bytes), "direct"
    except Blocked as direct_block:
        if use_proxy_mode == "never":
            raise
        if not proxy:
            raise Blocked("%s; fallback proxy not configured" % direct_block)
        return request(url, proxy, timeout, max_bytes), "proxy"


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("url")
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--out")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--no-proxy", action="store_true")
    group.add_argument("--force-proxy", action="store_true")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    return parser


def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False))
    return code


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        validate_url(args.url)
    except ValueError as error:
        return emit({"error": str(error)}, EXIT_INVALID)
    mode = "never" if args.no_proxy else "always" if args.force_proxy else "auto"
    try:
        (status, content_type, body, charset), via = fetch(args.url, args.timeout, args.max_bytes, mode)
    except Blocked as error:
        return emit({"error": "access blocked: %s" % error, "url": args.url}, EXIT_BLOCKED)
    except (urllib.error.URLError, OSError) as error:
        return emit({"error": "network unreachable: %s" % getattr(error, "reason", error), "url": args.url},
                    EXIT_NETWORK)
    payload = {"url": args.url, "status": status, "via": via, "content_type": content_type, "bytes": len(body)}
    if status >= 400:
        payload["error"] = "HTTP %d" % status
        return emit(payload, EXIT_HTTP)
    text = body.decode(charset, "replace")
    if args.text and "html" in content_type:
        text = html_to_text(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        payload["file"] = args.out
    else:
        payload["text"] = text
    return emit(payload, EXIT_OK)


if __name__ == "__main__":
    sys.exit(main())
