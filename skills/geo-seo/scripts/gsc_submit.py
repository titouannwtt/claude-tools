#!/usr/bin/env python3
"""gsc_submit.py: submits sitemaps to Google Search Console (Webmasters API v3).

Standard library + `openssl` (RS256 signature of the JWT). No secret in the repo:

    GSC_SERVICE_ACCOUNT=/path/to/service-account.json   (local value, in local.env)
    python3 gsc_submit.py --property sc-domain:example.org \
        --sitemap https://example.org/sitemap-index.xml [--sitemap ...] [--dry-run]

The service account must be added as an owner of the Search Console property. Scope
`webmasters` (write): `webmasters.readonly` cannot submit.
Exit codes: 0 success, 2 invalid arguments or configuration, 4 network, 1 API failure.
Does NOT use the Google Indexing API: it is reserved for job postings and live streams.
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
    ap.add_argument("--property", required=True, help="e.g. sc-domain:example.org or https://example.org/")
    ap.add_argument("--sitemap", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        for sm in args.sitemap:
            print(json.dumps({"dry_run": True, "would_submit": sm, "property": args.property}))
        return 0
    path = os.environ.get("GSC_SERVICE_ACCOUNT")
    if not path or not os.path.isfile(path):
        print(json.dumps({"error": "GSC_SERVICE_ACCOUNT missing or not found (see local.env)"}))
        return 2
    with open(path, encoding="utf-8") as fh:
        sa = json.load(fh)
    assertion = build_assertion(sa, int(time.time()), openssl_signer(sa["private_key"]))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": assertion}).encode()
    try:
        st, raw = http("POST", sa["token_uri"], {"Content-Type": "application/x-www-form-urlencoded"}, body)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"network: {e}"}))
        return 4
    if st != 200:
        print(json.dumps({"error": "token rejected", "status": st, "detail": raw.decode()[:200]}))
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
