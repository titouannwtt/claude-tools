#!/usr/bin/env python3
"""indexnow.py: notifies Bing, Yandex, Naver and Seznam (and therefore ChatGPT search, which relies
on Bing) of new or modified URLs. Google does not use IndexNow: for it, sitemap + lastmod.

    INDEXNOW_KEY=<key of 8 to 128 hexadecimal characters>   (local value, in local.env)
    python3 indexnow.py --host example.org --sitemap https://example.org/sitemap-0.xml [--dry-run]
    python3 indexnow.py --host example.org --url https://example.org/a/ --url https://example.org/b/

Prerequisite: the file https://<host>/<key>.txt must contain exactly the key (the script checks it).
Exit codes: 0 success (HTTP 200 or 202), 2 invalid configuration, 4 network, 1 rejected.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.indexnow.org/IndexNow"


def urls_from_sitemap(xml: str):
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "indexnow-script/1.0"}), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True)
    ap.add_argument("--sitemap", action="append", default=[])
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    key = os.environ.get("INDEXNOW_KEY", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
        print(json.dumps({"error": "INDEXNOW_KEY missing or invalid (see local.env)"}))
        return 2
    try:
        urls = list(args.url)
        for sm in args.sitemap:
            urls += urls_from_sitemap(get(sm))
        urls = sorted({u for u in urls if re.match(r"https?://" + re.escape(args.host) + r"[/:]", u + "/")})
        if not urls:
            print(json.dumps({"error": "no URL to submit for this host"}))
            return 2
        key_url = f"https://{args.host}/{key}.txt"
        try:
            if get(key_url).strip() != key:
                print(json.dumps({"error": f"{key_url} does not contain the key"}))
                return 2
        except urllib.error.HTTPError as e:
            print(json.dumps({"error": f"{key_url} returns {e.code}: publish the key file first"}))
            return 2
        if args.dry_run:
            print(json.dumps({"dry_run": True, "urls": len(urls), "sample": urls[:3]}))
            return 0
        sent, code = 0, 0
        for i in range(0, len(urls), 9000):
            chunk = urls[i:i + 9000]
            body = json.dumps({"host": args.host, "key": key, "keyLocation": key_url, "urlList": chunk}).encode()
            req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                         headers={"Content-Type": "application/json; charset=utf-8"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    st = r.status
            except urllib.error.HTTPError as e:
                st = e.code
            if st in (200, 202):
                sent += len(chunk)
            else:
                code = 1
                print(json.dumps({"failed_chunk": i // 9000, "status": st}))
        print(json.dumps({"submitted": sent, "total": len(urls)}))
        return code
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"network: {e}"}))
        return 4


if __name__ == "__main__":
    sys.exit(main())
