#!/usr/bin/env python3
"""gsc_submit.py : soumet des sitemaps à Google Search Console (API Webmasters v3).

Bibliothèque standard + `openssl` (signature RS256 du JWT). Aucun secret dans le dépôt :

    GSC_SERVICE_ACCOUNT=/chemin/vers/compte-de-service.json   (valeur locale, dans local.env)
    python3 gsc_submit.py --property sc-domain:exemple.org \
        --sitemap https://exemple.org/sitemap-index.xml [--sitemap ...] [--dry-run]

Le compte de service doit être ajouté comme propriétaire de la propriété Search Console. Scope
`webmasters` (écriture) : `webmasters.readonly` ne permet pas de soumettre.
Codes de sortie : 0 succès, 2 arguments ou configuration invalides, 4 réseau, 1 échec API.
N'utilise PAS l'API Google Indexing : réservée aux offres d'emploi et aux diffusions en direct.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

SCOPE = "https://www.googleapis.com/auth/webmasters"


def b64url(b: bytes) -> bytes:
    return base64.urlsafe_b64encode(b).rstrip(b"=")


def build_assertion(sa: dict, now: int, signer) -> str:
    head = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({"iss": sa["client_email"], "scope": SCOPE, "aud": sa["token_uri"],
                                "exp": now + 3600, "iat": now}).encode())
    signing_input = head + b"." + claims
    return (signing_input + b"." + b64url(signer(signing_input))).decode()


def openssl_signer(private_key_pem: str):
    def sign(data: bytes) -> bytes:
        fd, path = tempfile.mkstemp()
        try:
            os.chmod(path, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(private_key_pem)
            return subprocess.run(["openssl", "dgst", "-sha256", "-sign", path], input=data,
                                  capture_output=True, check=True).stdout
        finally:
            os.unlink(path)
    return sign


def http(method: str, url: str, headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--property", required=True, help="ex. sc-domain:exemple.org ou https://exemple.org/")
    ap.add_argument("--sitemap", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        for sm in args.sitemap:
            print(json.dumps({"dry_run": True, "would_submit": sm, "property": args.property}))
        return 0
    path = os.environ.get("GSC_SERVICE_ACCOUNT")
    if not path or not os.path.isfile(path):
        print(json.dumps({"error": "GSC_SERVICE_ACCOUNT absent ou introuvable (voir local.env)"}))
        return 2
    with open(path, encoding="utf-8") as fh:
        sa = json.load(fh)
    assertion = build_assertion(sa, int(time.time()), openssl_signer(sa["private_key"]))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": assertion}).encode()
    try:
        st, raw = http("POST", sa["token_uri"], {"Content-Type": "application/x-www-form-urlencoded"}, body)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"réseau : {e}"}))
        return 4
    if st != 200:
        print(json.dumps({"error": "jeton refusé", "status": st, "detail": raw.decode()[:200]}))
        return 1
    auth = {"Authorization": "Bearer " + json.loads(raw)["access_token"]}
    site = urllib.parse.quote(args.property, safe="")
    code = 0
    for sm in args.sitemap:
        url = f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{urllib.parse.quote(sm, safe='')}"
        st, raw = http("PUT", url, auth)
        if st in (200, 204):
            st2, info = http("GET", url, auth)
            d = json.loads(info) if st2 == 200 else {}
            print(json.dumps({"submitted": sm, "errors": d.get("errors"), "warnings": d.get("warnings"),
                              "last_downloaded": d.get("lastDownloaded")}, ensure_ascii=False))
        else:
            code = 1
            print(json.dumps({"failed": sm, "status": st, "detail": raw.decode()[:200]}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
