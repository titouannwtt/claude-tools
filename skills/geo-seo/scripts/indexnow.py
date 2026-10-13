#!/usr/bin/env python3
"""indexnow.py : notifie Bing, Yandex, Naver et Seznam (et donc la recherche de ChatGPT, qui s'appuie
sur Bing) des URL nouvelles ou modifiées. Google n'utilise pas IndexNow : pour lui, sitemap + lastmod.

    INDEXNOW_KEY=<clé de 8 à 128 caractères hexadécimaux>   (valeur locale, dans local.env)
    python3 indexnow.py --host exemple.org --sitemap https://exemple.org/sitemap-0.xml [--dry-run]
    python3 indexnow.py --host exemple.org --url https://exemple.org/a/ --url https://exemple.org/b/

Prérequis : le fichier https://<host>/<clé>.txt doit contenir exactement la clé (le script le vérifie).
Codes de sortie : 0 succès (HTTP 200 ou 202), 2 configuration invalide, 4 réseau, 1 refus.
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
        print(json.dumps({"error": "INDEXNOW_KEY absente ou invalide (voir local.env)"}))
        return 2
    try:
        urls = list(args.url)
        for sm in args.sitemap:
            urls += urls_from_sitemap(get(sm))
        urls = sorted({u for u in urls if re.match(r"https?://" + re.escape(args.host) + r"[/:]", u + "/")})
        if not urls:
            print(json.dumps({"error": "aucune URL à soumettre pour cet hôte"}))
            return 2
        key_url = f"https://{args.host}/{key}.txt"
        try:
            if get(key_url).strip() != key:
                print(json.dumps({"error": f"{key_url} ne contient pas la clé"}))
                return 2
        except urllib.error.HTTPError as e:
            print(json.dumps({"error": f"{key_url} répond {e.code} : publier le fichier de clé d'abord"}))
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
        print(json.dumps({"error": f"réseau : {e}"}))
        return 4


if __name__ == "__main__":
    sys.exit(main())
