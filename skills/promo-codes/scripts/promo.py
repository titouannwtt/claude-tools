#!/usr/bin/env python3
"""Find publicly shared, fixed promo codes for a merchant and rank them from most to least interesting.

Commands (one JSON object on stdout):
  doctor                       dependencies and reachability of every source.
  find <merchant> [options]    query the sources, extract codes, rank them.
  extract --text FILE --url U --merchant M   extract codes from a page text saved by the agent (Reddit, X...).
  rank --input F [F ...]       merge a `find` JSON with `extract` outputs and rerank.

`find` also prints `candidates` (every code with every source): `rank` reads them, so a code outside the top N
can be confirmed later. `rank` trusts nothing in its inputs: it rechecks the blocklist on every URL, requires the
code in each excerpt (case-insensitive), accepts the type `official` only for the merchant domain (`--domain`, or
the `merchant_domain` of the first file) and exits 2 on any malformed value.

Sources without key: yt-dlp search (video titles and descriptions; no user config, cookies or proxy), DuckDuckGo
HTML then Bing as fallback, HN Algolia, the merchant's official pages (robots.txt respected: 401/403/429/5xx or
unreachable disallows everything, other 4xx allows; final URL after redirects decides the type), GitHub issues
(opt-in, `--github`). About 25 calls at most per run, yt-dlp and gh included, 1 s between calls to the same host.
Reddit and X are not queried here (blocked without key): the agent searches them and feeds `extract`.

Rules (the codes are only listed, never tested):
- A code is kept only if it appears verbatim in a source text whose URL is known (no invented code).
- Never used: coupon aggregators (BLOCKED_DOMAINS and AGGREGATOR_* patterns, editable below), generated or
  brute-forced codes, leaked internal or test codes, flaws, cookies, proxies, CAPTCHA solving.

Extraction: a token of 4 to 20 characters (letters and digits, at most one hyphen or underscore, at least one
letter) found at most 60 characters after or 30 before a trigger word (code, coupon, promo, discount, off, %...)
and with a code or use word (code, coupon, promo, use, utilise...) within 40 characters.
Rejected: tokens inside URLs, hashtags, handles, timestamps, pure years, units, STOPWORDS, environment variable
names (API_KEY...), the merchant name, and model-like names (GPT4O, RTX4090) unless a code or use word is adjacent.
A token without digit must directly follow "code", "coupon", "promo"... (e.g. "code promo : WELCOME").
Lowercase or mixed case codes (with a digit) are accepted only right after such a word and kept as written.
With a merchant name (always, for `extract`), a code must be within 200 characters of the name; a title naming the
merchant is enough only when the body never does.

Ranking (deterministic), score = discount + sources + type + recency - conditions, floor 0:
  discount   percent capped at 50 -> 0.8 pt per %, up to 40; fixed amount: min(2 x amount, 30) % equivalent;
             free month 24 pts.
  sources    10 pts per independent source, up to 30. Independent = distinct registrable domain;
             each YouTube channel counts as its own source.
  type       best source type: official 20, creator video 15, forum or HN 10, generic web 5.
  recency    most recent dated source: <=30 d 10, <=90 d 8, <=180 d 6, <=1 y 4, <=2 y 2, else 0 (unknown 0).
  conditions new customers only -5, annual plan or minimum spend -5, unknown discount -5.
Ties: more sources first, then alphabetical.

Dependencies: Python standard library; yt-dlp (optional, YouTube source). Python 3.9 compatible.
Exit codes: 0 codes found; 1 unexpected error; 2 invalid usage; 4 no code found;
5 missing dependency (yt-dlp absent, and nothing found); 7 every source failed.
"""
import argparse
import base64
import html
import http.client
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter, namedtuple
from datetime import date, datetime
from html.parser import HTMLParser

EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, EXIT_NO_CODE, EXIT_MISSING, EXIT_ALL_FAILED = 0, 1, 2, 4, 5, 7

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 10
MAX_REQUESTS = 25
HOST_DELAY = 1.0
MAX_BYTES = 600000
YTDLP_TIMEOUT = 45
OFFICIAL_PATHS = ("/pricing", "/students", "/education", "/referral", "/partners")

# Editable blocklist: coupon aggregators and cashback/deal sites, matched on the registrable domain.
BLOCKED_DOMAINS = frozenset("""
dealabs.com retailmenot.com radins.com ma-reduc.com igraal.com poulpeo.com couponbirds.com groupon.com
groupon.fr wethrift.com knoji.com dealspotr.com coupons.com savings.com joinhoney.com capitaloneshopping.com
couponfollow.com slickdeals.net hotukdeals.com mydealz.de pepper.com vouchercodes.co.uk myvouchercodes.co.uk
cuponation.fr simplycodes.com promocodes.com offers.com dealnews.com couponcabin.com couponannie.com
promocodewatch.com
""".split())
# Brand labels (second-level label, any TLD): retailmenot.*, groupon.*... Generic words match the listed domain only.
GENERIC_BRAND_LABELS = frozenset(["offers", "savings", "coupons", "pepper"])
BLOCKED_BRANDS = frozenset(d.split(".")[0] for d in BLOCKED_DOMAINS) - GENERIC_BRAND_LABELS
# Aggregator patterns, applied to hosts and paths outside the official domain and outside discussion platforms.
AGGREGATOR_HOST_RE = re.compile(
    r"coupon|codepromo|code-promo|codes-promo|promocode|promo-code|discountcode|vouchercode|cuponation|bonsplans")
AGGREGATOR_PATH_RE = re.compile(
    r"(?:^|/)[^/?#]*(?:coupon|code-?promo|codes-?promo|promo-?codes?|discount-?codes?|voucher)[^/?#]*(?=/|$|\?|#)",
    re.I)
PLATFORM_DOMAINS = frozenset("""
reddit.com ycombinator.com youtube.com youtu.be x.com twitter.com github.com stackexchange.com
stackoverflow.com quora.com tiktok.com instagram.com facebook.com
""".split())
FORUM_DOMAINS = frozenset("""
reddit.com ycombinator.com x.com twitter.com stackexchange.com stackoverflow.com quora.com tiktok.com
instagram.com facebook.com discord.com
""".split())
CREATOR_DOMAINS = frozenset(["youtube.com", "youtu.be"])

# Common words in capitals that are not codes (editable).
STOPWORDS = frozenset("""
FREE OFF SALE CODE CODES PROMO PROMOS NEW LINK LINKS HTTP HTTPS WWW USA EUR USD GBP VPN AND THE FOR WITH YOU YOUR
NOW SAVE BEST DEAL DEALS TODAY NOT ALL HOW WHAT GET USE USED USING FROM THIS THAT THESE THEM THEN THAN WILL
WHEN WHERE WHICH WHO WHY ARE WAS HAS HAVE HAD CAN OUR OUT ANY MORE MOST ONLY OVER ONE TWO NEW NEWS INFO
DISCOUNT DISCOUNTS COUPON COUPONS VOUCHER SALES OFFER OFFERS OFFRE OFFRES PRICE PRICES PRICING PLAN PLANS PLUS PRO
PREMIUM BASIC TEAM TEAMS BUSINESS ENTERPRISE STUDENT STUDENTS EDUCATION ANNUAL ANNUALLY YEARLY MONTHLY MONTH MONTHS
YEAR YEARS WEEK DAY DAYS TRIAL FIRST ORDER ORDERS CUSTOMER CUSTOMERS USER USERS CHECKOUT ONLINE OFFICIAL REVIEW
REVIEWS TUTORIAL GUIDE TIPS TIPS LIVE VIDEO VIDEOS SHORTS SHORT PART FULL VERSION UPDATE SUBSCRIBE SUBSCRIBER
SUBSCRIBERS CHANNEL LIKE COMMENT EXPIRED INVALID ENDED VALID TOKEN TOKENS KEY KEYS SECRET ID URL SOC2 ISO GDPR RGPD
JSON XML YAML ISO27001 CSV SHARE AFFILIATE SPONSOR SPONSORED AD ADS WORLD
POUR AVEC SANS DANS CHEZ VOTRE VOTRES NOTRE NOUS VOUS MOIS GRATUIT GRATUITE GRATUITS REDUC REDUCTION REMISE
REMISES RABAIS OFFERT OFFERTS ABONNEMENT ANNUEL CLIENT CLIENTS COMMANDE ACHAT PROMOTION PROMOTIONS CREATEUR
BONNE ANNEE TOUS TOUT TOUTE TOUTES CETTE CELA LIEN DESCRIPTION PRIX
HTML CSS API PDF FAQ SEO CEO CTO SAAS IOS MACOS LINUX WINDOWS ANDROID IPHONE IPAD CHATGPT GPT OPENAI GOOGLE
H264 H265 HTML5 CSS3 IPV4 IPV6 UTF8 SHA256 WEBP JPEG JPG PNG GIF MP3 MP4 WIFI
JAN FEB MAR APR MAY JUN JUL AUG SEP SEPT OCT NOV DEC JANV FEVR AVRIL JUIN JUIL AOUT SEPT NOVEMBRE DECEMBRE
""".split())

TRIGGER_RE = re.compile(
    r"code|coupon|promo|voucher|discount|\boff\b|r[eé]duction|remise|rabais|%|parrain|referral|offre|cr[eé]ateur",
    re.I)
DIRECT_RE = re.compile(
    r"(?:codes?|coupon|promo|promotion|voucher|cr[eé]ateur|referral|parrainage)\s*"
    r"(?:(?:is|est|=|:|->|→|-|–|\"|“|'|«|\*|\(|\[)\s*)*$", re.I)
USE_DIRECT_RE = re.compile(
    r"(?:\buse|utilis\w*|\bavec|\bwith|\benter|\bentrez)\s+(?:(?:the|le|mon|my)\s+)?[\"\u201c'\u00ab]?$", re.I)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
TOKEN_RE = re.compile(r"(?<![\w-])([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)?)(?!\w|-\w|\.[A-Za-z])")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")  # pure years only: BF2025, CM2025, NY2026 stay candidates
STRONG_TRIGGER_RE = re.compile(r"code|coupon|promo|voucher|\buse\b|utilis\w*|parrain|referral|cr[eé]ateur", re.I)
STRONG_WINDOW = 40
ENV_WORDS = frozenset(["TOKEN", "KEY", "SECRET", "ID", "URL", "PASSWORD", "PASS", "PWD", "API"])
MODEL_RE = re.compile(r"^(?:[A-Z]{1,3}-?\d{1,4}[A-Z]{0,2}|(?:GPT|CLAUDE|GEMINI|LLAMA|MISTRAL|QWEN|IPHONE|IPAD|PIXEL|GALAXY)-?\d+[A-Z0-9.]*)$")
UNIT_RE = re.compile(r"^\d+(?:GB|MB|TB|KB|K|M|P|X|MS|H|S|FPS|GHZ|MHZ|PX|PM|AM|USD|EUR|GBP|PCT|HZ)$")
WINDOW_AFTER_TRIGGER = 60
WINDOW_BEFORE_TRIGGER = 30
RELATED_WINDOW = 200

PERCENT_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d)?) ?(?:%|percent\b|pour ?cent\b)", re.I)
AMOUNT_RE = re.compile(
    r"(?<![\d.,])(\d+(?:[.,]\d+)?) ?(€|\$|£|euros?\b|dollars?\b)"
    r"|(€|\$|£) ?(\d+(?:[.,]\d+)?)", re.I)
FREE_MONTH_RE = re.compile(
    r"(?:(\d+|one|un|deux|two) )?(?:months? free|free months?|mois (?:offerts?|gratuits?))", re.I)
OFF_CONTEXT_RE = re.compile(
    r"off\b|discount|r[eé]duction|remise|rabais|de moins|moins|offert|gratuit|free|rebate|saving|[eé]conomi", re.I)
NUMBER_WORDS = {"one": 1, "un": 1, "deux": 2, "two": 2}
CURRENCIES = {"€": "EUR", "euro": "EUR", "euros": "EUR", "$": "USD", "dollar": "USD", "dollars": "USD",
              "£": "GBP"}

CONDITION_RULES = (
    ("new customers only", re.compile(
        r"new (?:customers?|users?|members?|subscribers?)|first (?:order|purchase)|first[- ]time|"
        r"nouveaux? (?:clients?|utilisateurs?|abonn)|premi[eè]re? (?:commande|achat)", re.I)),
    ("annual plan", re.compile(r"annual|yearly|annuel|par an|per year|12 months", re.I)),
    ("minimum spend", re.compile(
        r"minimum|min\.? (?:spend|order)|[aà] partir de \d+|dès \d+|orders? over|d'au moins", re.I)),
    ("subscription only", re.compile(r"sur abonnement|subscriptions? only|abonnements? uniquement", re.I)),
)
CONDITION_WINDOW = 150

OFFER_RULES = (
    ("student", re.compile(r"student|étudiant|etudiant|academic|education|éducation|universit", re.I)),
    ("annual", re.compile(r"annual|yearly|annuel|par an|per year|billed annually", re.I)),
    ("referral", re.compile(r"referral|refer a friend|refer friends|parrain", re.I)),
    ("trial", re.compile(r"free trial|essai gratuit|try (?:it )?free|days? free|jours? gratuits?|-day trial", re.I)),
)
SAVING_HINT_RE = re.compile(r"%|save|saving|[eé]conomi|months? free|mois (?:offerts?|gratuits?)|\bfree\b", re.I)

SOURCE_TYPE_POINTS = {"official": 20, "creator": 15, "forum": 10, "web": 5}
TYPE_ORDER = {"official": 0, "creator": 1, "forum": 2, "web": 3}
MAX_SOURCES_PER_CODE = 5
EXCERPT_LENGTH = 160

CAPTCHA_MARKERS = ("anomaly-modal", "unusual traffic", "turing/captcha", "Verify you are human",
                   "Just a moment", "cf-chl", "challenge-platform", "g-recaptcha", "h-captcha")

Response = namedtuple("Response", "status text url")


class FetchError(Exception):
    """Network failure (timeout, DNS, TLS): the source is recorded as `error`."""


class BudgetExceeded(Exception):
    """The per-run request budget is spent: the remaining sources are skipped."""


class MissingDependency(Exception):
    pass


class UsageError(Exception):
    pass


# --------------------------------------------------------------------------------------------- network

def http_get(url, timeout=TIMEOUT):
    """GET with a browser-like User-Agent, no cookies, no proxy (environment proxies ignored).

    HTTP errors are returned, not raised. The returned URL is the final one, after redirects.
    """
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8,fr;q=0.6",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    final = url
    try:
        with opener.open(request, timeout=timeout) as response:
            status, body, charset = response.status, response.read(MAX_BYTES), response.headers.get_content_charset()
            final = response.geturl() or url
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(MAX_BYTES)
        except Exception:  # noqa: BLE001 - an unreadable error body is not worth a failure
            body = b""
        status, charset, final = exc.code, None, exc.geturl() or url
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        raise FetchError("%s: %s" % (type(exc).__name__, getattr(exc, "reason", exc)))
    return Response(status, body.decode(charset or "utf-8", errors="replace"), final)


class Client:
    """One budget for every outgoing call (HTTP, yt-dlp, gh) and politeness: HOST_DELAY s between calls per host."""

    def __init__(self, max_requests=MAX_REQUESTS):
        self.max_requests = max_requests
        self.count = 0
        self.last = {}

    def call(self, host, function, *args):
        """Run function(*args) as one request to `host`, after the budget check and the pacing."""
        if self.count >= self.max_requests:
            raise BudgetExceeded()
        wait = HOST_DELAY - (time.monotonic() - self.last.get(host, -1e9))
        if wait > 0 and HOST_DELAY:
            time.sleep(wait)
        self.count += 1
        try:
            return function(*args)
        finally:
            self.last[host] = time.monotonic()

    def get(self, url):
        return self.call(urllib.parse.urlparse(url).netloc, http_get, url)


def classify_response(response):
    """State of a fetch: ok, captcha, blocked-403, blocked-429 or error."""
    status, text = response.status, response.text or ""
    if status == 200:
        return "ok"
    if status == 202:
        return "captcha"
    if status in (403, 429, 503) and any(marker in text for marker in CAPTCHA_MARKERS):
        return "captcha"
    if status in (403, 429):
        return "blocked-%d" % status
    return "error"


Fetched = namedtuple("Fetched", "state text detail url status")


def fetch_full(client, url):
    """One GET with its outcome (state, text, detail, final URL, HTTP status); never raises."""
    try:
        response = client.get(url)
    except BudgetExceeded:
        return Fetched("skipped", "", "request budget reached", url, None)
    except FetchError as exc:
        return Fetched("error", "", str(exc), url, None)
    state = classify_response(response)
    detail = "" if state == "ok" else "HTTP %d" % response.status
    return Fetched(state, response.text, detail, response.url or url, response.status)


def fetch(client, url):
    """(state, text, detail) for one GET; never raises."""
    outcome = fetch_full(client, url)
    return outcome.state, outcome.text, outcome.detail


# --------------------------------------------------------------------------------------------- helpers

def squeeze(text):
    return re.sub(r"\s+", " ", text or "").strip()


def clip(text, length):
    text = squeeze(text)
    return text if len(text) <= length else text[:length - 1].rstrip() + "..."


def host_of(url):
    return (urllib.parse.urlparse(url).hostname or "").lower()


def registrable_domain(host):
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if len(labels[-1]) == 2 and labels[-2] in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def normalize_domain(value):
    value = (value or "").strip().lower()
    value = re.sub(r"^[a-z]+://", "", value).split("/")[0]
    if value.startswith("www."):
        value = value[4:]
    if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", value):
        raise UsageError("invalid domain: %s" % value)
    return value


def parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for pattern, fmt in ((r"^\d{4}-\d{2}-\d{2}", "%Y-%m-%d"), (r"^\d{8}$", "%Y%m%d")):
        match = re.match(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(0), fmt).date()
            except ValueError:
                return None
    return None


def iso(value):
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def blocked_reason(url, official_domain=None):
    """'aggregator' if the URL belongs to a coupon aggregator (blocklist or URL pattern), else None."""
    host = host_of(url)
    if not host:
        return None
    domain = registrable_domain(host)
    if domain in BLOCKED_DOMAINS or host in BLOCKED_DOMAINS or domain.split(".")[0] in BLOCKED_BRANDS:
        return "aggregator"
    if official_domain and domain == registrable_domain(official_domain):
        return None
    if domain in PLATFORM_DOMAINS:
        return None
    if AGGREGATOR_HOST_RE.search(host):
        return "aggregator"
    if AGGREGATOR_PATH_RE.search(urllib.parse.urlparse(url).path or ""):
        return "aggregator"
    return None


def classify_url(url, official_domain=None):
    """Source type of a web result: official, creator, forum or web."""
    domain = registrable_domain(host_of(url))
    if official_domain and domain == registrable_domain(official_domain):
        return "official"
    if domain in CREATOR_DOMAINS:
        return "creator"
    if domain in FORUM_DOMAINS or re.search(r"(^|\.)forums?\.", host_of(url)):
        return "forum"
    return "web"


def merchant_names(merchant, domain=None):
    """Normalized names a token must not equal: the merchant, its words of 3+ letters, the domain label."""
    def norm(value):
        return re.sub(r"[^a-z0-9]", "", value.lower())

    names = {norm(merchant)}
    names.update(norm(word) for word in re.split(r"\s+", merchant) if len(norm(word)) >= 3)
    if domain:
        names.add(norm(domain.split(".")[0]))
    names.discard("")
    return names


def mentions_merchant(text, url, names, merchant):
    haystack = re.sub(r"[^a-z0-9]", "", ("%s %s" % (text, url)).lower())
    full = re.sub(r"[^a-z0-9]", "", merchant.lower())
    return (bool(full) and full in haystack) or any(len(name) >= 4 and name in haystack for name in names)


# --------------------------------------------------------------------------------------------- extraction

def is_verbatim(code, text):
    return bool(code) and code in (text or "")


def window_has_trigger(triggers, start, end):
    for t_start, t_end in triggers:
        if t_end <= start and start - t_end <= WINDOW_AFTER_TRIGGER:
            return True
        if t_start >= end and t_start - end <= WINDOW_BEFORE_TRIGGER:
            return True
    return False


def strong_trigger_near(triggers, start, end):
    """A code or use word (code, coupon, promo, use, utilise...) within STRONG_WINDOW characters."""
    return any((t_end <= start and start - t_end <= STRONG_WINDOW) or (t_start >= end and t_start - end <= STRONG_WINDOW)
               for t_start, t_end in triggers)


def rejection_reason(token, text, start, end, spans, names):
    """Why a token near a trigger is not a code (None if it is a candidate)."""
    previous = text[start - 1] if start else ""
    upper = token.upper()
    if any(s <= start < e for s, e in spans) or (previous and previous in "/=?&"):
        return "url"
    if previous == "#":
        return "hashtag"
    if previous == "@":
        return "handle"
    after = text[end:end + 2]
    if (previous == ":" and start >= 2 and text[start - 2].isdigit()) or re.match(r":\d", after):
        return "timestamp"
    if YEAR_RE.match(token):
        return "year"
    if UNIT_RE.match(upper):
        return "unit"
    if all(part in STOPWORDS for part in re.split(r"[-_]", upper)):
        return "stopword"
    if "_" in token and any(part in ENV_WORDS for part in upper.split("_")):
        return "env_var"
    if re.sub(r"[^a-z0-9]", "", token.lower()) in names:
        return "merchant_name"
    before = text[max(0, start - 30):start]
    direct = DIRECT_RE.search(before) is not None
    has_digit = any(char.isdigit() for char in token)
    if token != upper and not (direct and has_digit):
        return "weak_context"  # lowercase or mixed case: only "use code thomas20" style
    if not direct and not USE_DIRECT_RE.search(before) and MODEL_RE.match(upper):
        return "model_like"
    if not direct and not has_digit:
        return "weak_context"
    return None


def make_discount(kind, value, currency=None):
    value = int(value) if float(value).is_integer() else value
    if kind == "percent":
        return {"type": "percent", "value": value, "label": "%s %%" % value}
    if kind == "amount":
        return {"type": "amount", "value": value, "currency": currency, "label": "%s %s" % (value, currency)}
    return {"type": "free_month", "value": value, "label": "%s free month%s" % (value, "s" if value > 1 else "")}


def find_discount(text, start, end):
    """Stated discount near the token: the closest one that is described as a reduction (not a price)."""
    low, high = max(0, start - 100), min(len(text), end + 100)
    zone = text[low:high]
    found = []
    for match in PERCENT_RE.finditer(zone):
        value = float(match.group(1).replace(",", "."))
        if 0 < value <= 100:
            found.append((match.start(), match.end(), "percent", value, None))
    for match in AMOUNT_RE.finditer(zone):
        raw = match.group(1) or match.group(4)
        unit = (match.group(2) or match.group(3)).lower()
        value = float(raw.replace(",", "."))
        if value > 0:
            found.append((match.start(), match.end(), "amount", value, CURRENCIES.get(unit, "EUR")))
    for match in FREE_MONTH_RE.finditer(zone):
        raw = (match.group(1) or "1").lower()
        value = NUMBER_WORDS.get(raw) or int(raw)
        found.append((match.start(), match.end(), "free_month", value, None))
    middle = start - low
    best = None
    for f_start, f_end, kind, value, currency in found:
        around = zone[max(0, f_start - 25):f_end + 25]
        described = kind == "free_month" or OFF_CONTEXT_RE.search(around) is not None
        if kind == "amount" and not described:
            continue
        distance = min(abs(f_start - middle), abs(f_end - middle))
        key = (0 if described else 1, distance)
        if best is None or key < best[0]:
            best = (key, kind, value, currency)
    if best is None:
        return None
    return make_discount(best[1], best[2], best[3])


def find_conditions(text, start, end):
    zone = text[max(0, start - CONDITION_WINDOW):end + CONDITION_WINDOW]
    return [label for label, pattern in CONDITION_RULES if pattern.search(zone)]


def make_excerpt(text, start, end):
    first = max(0, start - 60)
    last = min(len(text), first + EXCERPT_LENGTH)
    if end > last:
        first, last = max(0, end - EXCERPT_LENGTH), end
    return text[first:last].strip()


def squash(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def related_to_anchor(text, title, anchor, start, end):
    """Is the code about the merchant? The name must be within RELATED_WINDOW characters of the code.

    If the body never names the merchant (truncated descriptions), a title that names it is enough.
    """
    if squash(text[max(0, start - RELATED_WINDOW):end + RELATED_WINDOW]).find(anchor) >= 0:
        return True
    squeezed_title = squeeze(title)
    body = text.replace(squeezed_title, "", 1) if squeezed_title else text
    return anchor in squash(squeezed_title) and anchor not in squash(body)


def extract_from_text(text, names, excluded=None, anchor=None, title=""):
    """Mentions {code, discount, conditions, excerpt} found in a text, each code once. Counts rejections.

    With `anchor` (the merchant name, squashed), a code is kept only if the name is near it (see
    related_to_anchor): otherwise it belongs to another product mentioned in the same text.
    Codes are written as found; lowercase or mixed case is only accepted right after a code word.
    """
    excluded = excluded if excluded is not None else Counter()
    text = squeeze(text)
    spans = [match.span() for match in URL_RE.finditer(text)]
    triggers = [match.span() for match in TRIGGER_RE.finditer(text)]
    strong = [match.span() for match in STRONG_TRIGGER_RE.finditer(text)]
    found = {}
    for match in TOKEN_RE.finditer(text):
        token, (start, end) = match.group(1), match.span(1)
        if not 4 <= len(token) <= 20 or not any(char.isalpha() for char in token):
            continue
        if token != token.upper() and not any(char.isdigit() for char in token):
            continue  # an ordinary lowercase word
        outside = [t for t in triggers if t[1] <= start or t[0] >= end]
        if not window_has_trigger(outside, start, end):
            continue
        if not strong_trigger_near([t for t in strong if t[1] <= start or t[0] >= end], start, end):
            excluded["weak_context"] += 1  # near "%" or "off" only: no code or use word close enough
            continue
        reason = rejection_reason(token, text, start, end, spans, names)
        if reason:
            excluded[reason] += 1
            continue
        if anchor and not related_to_anchor(text, title, anchor, start, end):
            excluded["unrelated_product"] += 1
            continue
        if not is_verbatim(token, text):  # defensive: the rule holds for every code returned
            excluded["not_verbatim"] += 1
            continue
        discount = find_discount(text, start, end)
        key = token.upper()
        if key in found:
            if found[key]["discount"] is None and discount:
                found[key]["discount"] = discount
            continue
        found[key] = {"code": token, "discount": discount, "conditions": find_conditions(text, start, end),
                      "excerpt": make_excerpt(text, start, end)}
    return list(found.values())


# --------------------------------------------------------------------------------------------- ranking

def discount_points(discount):
    if not discount:
        return 0.0
    kind, value = discount["type"], discount["value"]
    if kind == "percent":
        return min(value, 50) * 0.8
    if kind == "amount":
        return min(value * 2, 30) * 0.8
    return 24.0


def recency_points(when, today):
    if not when:
        return 0
    age = max(0, (today - when).days)
    for limit, points in ((30, 10), (90, 8), (180, 6), (365, 4), (730, 2)):
        if age <= limit:
            return points
    return 0


def source_key(source):
    if source.get("channel"):
        return "youtube:" + source["channel"].lower()
    return registrable_domain(host_of(source["url"]))


def pick_discount(discounts):
    counts = Counter(json.dumps(d, sort_keys=True) for d in discounts if d)
    if not counts:
        return None
    best = max(counts, key=lambda k: (counts[k], discount_points(json.loads(k)), k))
    return json.loads(best)


def score_code(discount, conditions, sources, today):
    keys = {source_key(s) for s in sources}
    best_type = max((SOURCE_TYPE_POINTS.get(s["type"], 5) for s in sources), default=0)
    dates = [parse_date(s.get("date")) for s in sources]
    dates = [d for d in dates if d]
    penalty = 0
    if "new customers only" in conditions:
        penalty += 5
    if "annual plan" in conditions or "minimum spend" in conditions:
        penalty += 5
    if not discount:
        penalty += 5
    parts = {"discount": round(discount_points(discount), 1), "sources": min(len(keys) * 10, 30),
             "type": best_type, "recency": recency_points(max(dates) if dates else None, today),
             "penalty": -penalty}
    return round(max(0.0, sum(parts.values())), 1), parts


def rank_mentions(mentions, today, limit=None):
    """Aggregate mentions {code, discount, conditions, source} by code (case-insensitive) and rank them.

    Entries keep every source; the code is shown as most often written.
    """
    grouped = {}
    for mention in mentions:
        grouped.setdefault(mention["code"].upper(), []).append(mention)
    ranked = []
    for items in grouped.values():
        written = Counter(item["code"] for item in items)
        code = sorted(written.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
        sources, seen = [], set()
        for item in items:
            if item["source"]["url"] not in seen:
                seen.add(item["source"]["url"])
                sources.append(item["source"])
        discount = pick_discount([item["discount"] for item in items])
        conditions = sorted({label for item in items for label in item["conditions"]})
        score, parts = score_code(discount, conditions, sources, today)
        dates = sorted(d for d in (iso(s.get("date")) for s in sources) if d)
        ordered = sorted(sources, key=lambda s: (TYPE_ORDER.get(s["type"], 9), s["url"]))
        ranked.append({"code": code, "score": score, "discount": discount, "conditions": conditions,
                       "sources": ordered, "source_count": len({source_key(s) for s in sources}),
                       "first_seen": dates[0] if dates else None, "score_parts": parts})
    ranked.sort(key=lambda r: (-r["score"], -r["source_count"], r["code"].upper(), r["code"]))
    return ranked[:limit] if limit else ranked


def build_summary(codes):
    lines = []
    for index, entry in enumerate(codes, 1):
        label = entry["discount"]["label"] if entry["discount"] else "discount unknown"
        best = min((s["type"] for s in entry["sources"]), key=lambda t: TYPE_ORDER.get(t, 9))
        count = entry["source_count"]
        lines.append("%d. %s: %s (%s, %d source%s)" % (index, entry["code"], label, best, count,
                                                      "" if count == 1 else "s"))
    return lines


SOURCE_FIELDS = ("type", "url", "title", "date", "excerpt", "channel")
DISCOUNT_LIMITS = {"percent": 100, "amount": 10000, "free_month": 24}
CONDITION_LABELS = frozenset(label for label, _ in CONDITION_RULES)
OFFER_KINDS = frozenset(kind for kind, _ in OFFER_RULES)
CODE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{2,18})[A-Za-z0-9]$")


def malformed(where, message):
    return UsageError("%s: %s" % (where, message))


def need(value, kind, where, what, optional=False):
    """Type check of one JSON value read by `rank`; a wrong type is a usage error, never a TypeError."""
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, kind):
        raise malformed(where, "%s must be %s" % (what, kind.__name__ if isinstance(kind, type) else "a number"))
    return value


def clean_discount(value, where):
    if value is None:
        return None
    need(value, dict, where, "discount")
    kind = value.get("type")
    if kind not in DISCOUNT_LIMITS:
        raise malformed(where, "discount.type must be percent, amount or free_month")
    amount = need(value.get("value"), (int, float), where, "discount.value")
    if not 0 < amount <= DISCOUNT_LIMITS[kind]:
        raise malformed(where, "discount.value out of range")
    currency = None
    if kind == "amount":
        currency = need(value.get("currency"), str, where, "discount.currency")
        if currency not in ("EUR", "USD", "GBP"):
            raise malformed(where, "discount.currency must be EUR, USD or GBP")
    return make_discount(kind, amount, currency)


def entry_mentions(entries, domain, excluded, where):
    """Mentions rebuilt from ranked entries (rank command), everything rechecked from the evidence.

    A source is kept only if its excerpt contains the code (case-insensitive) and its URL is not an aggregator.
    Its type is never trusted: `official` stands only if the URL belongs to the merchant domain.
    """
    need(entries, list, where, "the code list")
    mentions = []
    for index, entry in enumerate(entries):
        spot = "%s, entry %d" % (where, index)
        need(entry, dict, spot, "an entry")
        code = need(entry.get("code"), str, spot, "code")
        if not CODE_RE.match(code):
            raise malformed(spot, "code has an invalid shape")
        discount = clean_discount(entry.get("discount"), spot)
        conditions = need(entry.get("conditions", []), list, spot, "conditions")
        if not all(isinstance(label, str) for label in conditions):
            raise malformed(spot, "conditions must be a list of strings")
        conditions = [label for label in conditions if label in CONDITION_LABELS]
        sources = need(entry.get("sources"), list, spot, "sources")
        for position, source in enumerate(sources):
            place = "%s, source %d" % (spot, position)
            need(source, dict, place, "a source")
            url = need(source.get("url"), str, place, "url")
            if not re.match(r"^https?://[^\s]+$", url):
                raise malformed(place, "url must be an http(s) URL")
            excerpt = squeeze(need(source.get("excerpt"), str, place, "excerpt"))[:EXCERPT_LENGTH * 2]
            claimed = need(source.get("type"), str, place, "type", optional=True)
            if claimed is not None and claimed not in SOURCE_TYPE_POINTS:
                raise malformed(place, "type must be one of %s" % ", ".join(sorted(SOURCE_TYPE_POINTS)))
            kept = {"title": need(source.get("title"), str, place, "title", optional=True) or "",
                    "date": iso(need(source.get("date"), str, place, "date", optional=True)),
                    "channel": need(source.get("channel"), str, place, "channel", optional=True)}
            if code.lower() not in excerpt.lower():
                excluded["not_verbatim"] += 1
                continue
            if blocked_reason(url, domain):
                excluded["aggregator"] += 1
                continue
            official_ok = classify_url(url, domain) == "official"
            if claimed in (None, "official"):
                claimed = classify_url(url, domain)
            elif official_ok:
                claimed = "official"
            source_out = {"type": claimed, "url": url, "title": clip(kept["title"], 120), "date": kept["date"],
                          "excerpt": excerpt}
            if kept["channel"]:
                source_out["channel"] = kept["channel"]
            mentions.append({"code": code, "discount": discount, "conditions": conditions, "source": source_out})
    return mentions


# --------------------------------------------------------------------------------------------- queries

def build_queries(merchant, product, lang):
    base = merchant + (" " + product if product else "")
    english = ["%s promo code" % base, "%s coupon code" % base, "%s discount code reddit" % base,
               "%s referral" % base, "%s student discount" % base]
    if lang != "fr":
        return {"web": english, "youtube": english[:1], "hn": english[:2]}
    french = ["%s code promo" % base, "%s code créateur" % base]
    web = [french[0]] + english + [french[1]]
    return {"web": web, "youtube": [french[0], english[0], french[1]], "hn": english[:2]}


# --------------------------------------------------------------------------------------------- parsers

class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    BLOCK = {"p", "div", "li", "br", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol",
             "dl", "table", "thead", "tbody", "tfoot", "header", "footer", "nav", "main", "aside", "form", "pre",
             "blockquote", "figure", "figcaption", "hr", "option"}
    INLINE = {"td", "th", "dd", "dt", "span", "button", "label", "a", "b", "strong", "em", "i", "small", "code"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in self.INLINE:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in self.INLINE:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(markup):
    parser = TextExtractor()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:  # noqa: BLE001 - broken markup: keep what was read
        pass
    return "".join(parser.parts)


def strip_tags(markup):
    text = re.sub(r"<(?:p|br)\s*/?>", "\n", markup or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def ddg_target(href):
    """Real URL of a DuckDuckGo result (uddg redirect parameter); None for ads and internal links."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in (parsed.hostname or ""):
        values = urllib.parse.parse_qs(parsed.query).get("uddg")
        return values[0] if values else None
    return href if parsed.scheme in ("http", "https") else None


class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results, self.current, self.mode, self.mode_tag = [], None, None, None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self.current = {"title": "", "url": ddg_target(attributes.get("href", "")), "snippet": ""}
            self.results.append(self.current)
            self.mode, self.mode_tag = "title", tag
        elif self.current is not None and ("result__snippet" in classes or "result-snippet" in classes):
            self.mode, self.mode_tag = "snippet", tag

    def handle_endtag(self, tag):
        if self.mode and tag == self.mode_tag:
            self.mode = self.mode_tag = None

    def handle_data(self, data):
        if self.mode and self.current is not None:
            self.current[self.mode] += data


def parse_ddg(markup):
    parser = DDGParser()
    parser.feed(markup or "")
    return [{"title": squeeze(r["title"]), "url": r["url"], "snippet": squeeze(r["snippet"])}
            for r in parser.results if r["url"]]


def bing_target(href):
    parsed = urllib.parse.urlparse(href)
    if "bing.com" in (parsed.hostname or "") and parsed.path.startswith("/ck/"):
        value = (urllib.parse.parse_qs(parsed.query).get("u") or [""])[0]
        if value.startswith("a1"):
            try:
                padded = value[2:] + "=" * (-len(value[2:]) % 4)
                return base64.urlsafe_b64decode(padded).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return None
        return None
    return href if parsed.scheme in ("http", "https") else None


class BingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results, self.current = [], None
        self.in_h2 = self.in_title = self.in_p = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "li" and any(c in ("b_algo", "b_ad", "b_ans", "b_pag") for c in classes):
            if "b_algo" in classes:
                self.current = {"title": "", "url": None, "snippet": ""}
                self.results.append(self.current)
            else:
                self.current = None
        elif self.current is None:
            return
        elif tag == "h2":
            self.in_h2 = True
        elif tag == "a" and self.in_h2 and self.current["url"] is None:
            self.current["url"] = bing_target(attributes.get("href", ""))
            self.in_title = True
        elif tag == "p":
            self.in_p = True

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_h2 = False
        elif tag == "a":
            self.in_title = False
        elif tag == "p":
            self.in_p = False

    def handle_data(self, data):
        if self.current is None:
            return
        if self.in_title:
            self.current["title"] += data
        elif self.in_p:
            self.current["snippet"] += data + " "


def parse_bing(markup):
    parser = BingParser()
    parser.feed(markup or "")
    return [{"title": squeeze(r["title"]), "url": r["url"], "snippet": squeeze(r["snippet"])}
            for r in parser.results if r["url"]]


# --------------------------------------------------------------------------------------------- sources

def status_entry(state, items=0, detail=""):
    entry = {"status": state, "items": items}
    if detail:
        entry["detail"] = detail
    return entry


def search_web(client, queries):
    """DuckDuckGo first, Bing as fallback. Returns (statuses, docs). Stops retrying an engine once blocked."""
    engines = [("duckduckgo", "https://html.duckduckgo.com/html/?q=%s", parse_ddg),
               ("bing", "https://www.bing.com/search?q=%s", parse_bing)]
    live = {name: True for name, _, _ in engines}
    errors = Counter()
    info = {name: {"ok": 0, "items": 0, "state": None, "detail": ""} for name, _, _ in engines}
    docs = []
    for query in queries:
        for name, template, parser in engines:
            if not live[name]:
                continue
            state, text, detail = fetch(client, template % urllib.parse.quote_plus(query))
            results = parser(text) if state == "ok" else []
            if state == "ok" and not results:
                if any(marker in text for marker in CAPTCHA_MARKERS):
                    state, detail = "captcha", "challenge page"
                else:
                    detail = "no result parsed"
            if state != "ok":
                info[name]["state"], info[name]["detail"] = state, detail
                errors[name] += 1
                if state != "error" or errors[name] >= 2:
                    live[name] = False
                continue
            info[name]["ok"] += 1
            info[name]["items"] += len(results)
            if not info[name]["state"]:
                info[name]["detail"] = detail
            for result in results:
                docs.append({"url": result["url"], "title": result["title"], "date": None,
                             "text": "%s. %s" % (result["title"], result["snippet"])})
            if results:
                break  # the fallback engine is only used when the first one gave nothing
    statuses = {}
    for name, _, _ in engines:
        data = info[name]
        if data["ok"] and data["state"]:
            statuses[name] = status_entry("ok", data["items"], "stopped after %s (%s)" % (data["state"], data["detail"]))
        elif data["ok"]:
            statuses[name] = status_entry("ok", data["items"], data["detail"])
        elif data["state"]:
            statuses[name] = status_entry(data["state"], 0, data["detail"])
        else:
            statuses[name] = status_entry("skipped", 0, "not needed" if name == "bing" else "")
    return statuses, docs


def search_hn(client, queries):
    docs, ok, last = [], 0, ("skipped", "")
    for query in queries:
        url = "https://hn.algolia.com/api/v1/search?query=%s&tags=%s&hitsPerPage=20" % (
            urllib.parse.quote_plus(query), urllib.parse.quote("(story,comment)", safe="(),"))
        state, text, detail = fetch(client, url)
        if state != "ok":
            last = (state, detail)
            if state != "error":
                break
            continue
        try:
            hits = json.loads(text).get("hits", [])
        except (ValueError, AttributeError):
            last = ("error", "invalid JSON")
            continue
        ok += 1
        for hit in hits:
            body = hit.get("comment_text") or hit.get("story_text") or ""
            title = hit.get("title") or hit.get("story_title") or ""
            docs.append({"url": "https://news.ycombinator.com/item?id=%s" % hit.get("objectID"), "title": title,
                         "date": iso(hit.get("created_at")), "text": "%s. %s" % (title, strip_tags(body)),
                         "type": "forum"})
    if ok:
        return status_entry("ok", len(docs)), docs
    return status_entry(last[0], 0, last[1]), docs


def ytdlp_path():
    return shutil.which("yt-dlp")


def ytdlp_argv(binary, query, count):
    """No user config, no cookies, no proxy: a configured --cookies-from-browser or --proxy must not apply."""
    return [binary, "--ignore-config", "--no-cookies", "--no-cookies-from-browser", "--proxy", "",
            "--flat-playlist", "--dump-json", "--skip-download", "--no-warnings", "ytsearch%d:%s" % (count, query)]


def run_ytdlp(query, count):
    """Flat search results (id, title, description preview, channel). Raises MissingDependency / FetchError."""
    binary = ytdlp_path()
    if not binary:
        raise MissingDependency("yt-dlp not found: pip install -U yt-dlp (or brew install yt-dlp)")
    try:
        done = subprocess.run(ytdlp_argv(binary, query, count), capture_output=True, text=True,
                              timeout=YTDLP_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise FetchError("yt-dlp timed out")
    if done.returncode != 0 and not done.stdout.strip():
        raise FetchError((done.stderr or "yt-dlp failed").strip()[-300:])
    entries = []
    for line in done.stdout.splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def search_youtube(client, queries, count=8):
    docs, ok, last = [], 0, ("error", "")
    for query in queries:
        try:
            entries = client.call("www.youtube.com", run_ytdlp, query, count)
        except BudgetExceeded:
            last = ("skipped", "request budget reached")
            break
        except MissingDependency as exc:
            return status_entry("skipped", 0, str(exc)), [], True
        except FetchError as exc:
            message = str(exc)
            if "not a bot" in message or "Sign in" in message:
                last = ("captcha", "bot check, not bypassed")
                break
            if "429" in message:
                last = ("blocked-429", message)
                break
            if "403" in message:
                last = ("blocked-403", message)
                break
            last = ("error", message)
            continue
        ok += 1
        for entry in entries:
            video = entry.get("id") or ""
            url = entry.get("webpage_url") or entry.get("url") or (
                "https://www.youtube.com/watch?v=%s" % video if video else "")
            if not url:
                continue
            title = entry.get("title") or ""
            docs.append({"url": url, "title": title, "date": iso(entry.get("upload_date")),
                         "text": "%s. %s" % (title, entry.get("description") or ""),
                         "channel": entry.get("channel") or entry.get("uploader") or ""})
    if ok:
        return status_entry("ok", len(docs)), docs, False
    return status_entry(last[0], 0, last[1]), docs, False


def run_gh(query):
    done = subprocess.run(["gh", "api", "-X", "GET", "search/issues", "-f", "q=%s" % query, "-f", "per_page=10"],
                          capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise FetchError((done.stderr or "gh failed").strip()[-300:])
    return json.loads(done.stdout).get("items", [])


def search_github(client, merchant):
    if not shutil.which("gh"):
        return status_entry("skipped", 0, "gh not found"), []
    try:
        items = client.call("api.github.com", run_gh, "%s promo code in:title,body" % merchant)
    except BudgetExceeded:
        return status_entry("skipped", 0, "request budget reached"), []
    except (FetchError, ValueError, subprocess.TimeoutExpired) as exc:
        return status_entry("error", 0, str(exc)), []
    docs = [{"url": item["html_url"], "title": item.get("title") or "", "date": iso(item.get("created_at")),
             "text": "%s. %s" % (item.get("title") or "", item.get("body") or ""), "type": "forum"}
            for item in items if item.get("html_url")]
    return status_entry("ok", len(docs)), docs


DEDICATED_PATHS = {"/students": "student", "/education": "student", "/referral": "referral"}


def detect_offers(url, text):
    """Non-code offers found on an official page: student, annual, referral, trial."""
    offers = []
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]
    dedicated = DEDICATED_PATHS.get(urllib.parse.urlparse(url).path.rstrip("/"))
    for kind, pattern in OFFER_RULES:
        needs_hint = kind in ("student", "annual") and dedicated != kind
        hit = next((s for s in sentences if pattern.search(s) and (not needs_hint or SAVING_HINT_RE.search(s))),
                   None)
        if hit is None and dedicated == kind and sentences:
            hit = sentences[0]
        if hit:
            match = pattern.search(hit)
            offset = max(0, (match.start() if match else 0) - 50)
            offers.append({"kind": kind, "url": url, "text": clip(hit[offset:], EXCERPT_LENGTH)})
    return offers


def robots_policy(outcome):
    """(parser or None, status entry or None): robots.txt 401/403/429/5xx or unreachable disallows everything,
    any other 4xx allows everything."""
    robots = urllib.robotparser.RobotFileParser()
    if outcome.state == "ok":
        robots.parse(outcome.text.splitlines())
        return robots, None
    if outcome.state == "skipped":
        return None, status_entry("skipped", 0, outcome.detail)
    status = outcome.status
    if status in (401, 403):
        return None, status_entry("blocked-403", 0, "robots.txt HTTP %d: treated as disallow all" % status)
    if status == 429:
        return None, status_entry("blocked-429", 0, "robots.txt HTTP 429: not fetched")
    if status is not None and 400 <= status < 500:
        robots.parse([])  # robots.txt absent: no restriction
        return robots, None
    if outcome.state == "captcha":
        return None, status_entry("captcha", 0, "robots.txt: " + outcome.detail)
    return None, status_entry("error", 0, "robots.txt unavailable (%s): treated as disallow all" % outcome.detail)


def fetch_official(client, domain):
    """Official pages of the merchant, robots.txt first. Returns (status, docs, offers).

    The final URL after redirects is used: a page that left the merchant domain is not official.
    """
    base = "https://%s" % domain
    robots, refused = robots_policy(fetch_full(client, base + "/robots.txt"))
    if refused:
        return refused, [], []
    docs, offers, seen_kinds = [], [], set()
    problems = []
    for path in OFFICIAL_PATHS:
        url = base + path
        if not robots.can_fetch(USER_AGENT, url):
            continue
        outcome = fetch_full(client, url)
        if outcome.state == "skipped":
            problems.append((outcome.state, outcome.detail))
            break
        if outcome.state != "ok":
            if outcome.status != 404:
                problems.append((outcome.state, outcome.detail))
            continue
        final = outcome.url
        official = registrable_domain(host_of(final)) == registrable_domain(domain)
        text = html_to_text(outcome.text)
        docs.append({"url": final, "title": path.strip("/").capitalize(), "date": None, "text": text,
                     "type": "official" if official else classify_url(final)})
        if not official:
            continue
        for offer in detect_offers(final, text):
            if offer["kind"] not in seen_kinds:
                seen_kinds.add(offer["kind"])
                offers.append(offer)
    if docs:
        return status_entry("ok", len(docs)), docs, offers
    if problems:
        return status_entry(problems[0][0], 0, problems[0][1]), docs, offers
    return status_entry("ok", 0, "no official page found or allowed"), docs, offers


# --------------------------------------------------------------------------------------------- commands

def docs_to_mentions(docs, merchant, names, domain, excluded, check_topic=True):
    mentions, seen = [], set()
    anchor_name = squash(merchant)
    for doc in docs:
        url = doc["url"]
        if url in seen:
            continue
        seen.add(url)
        if blocked_reason(url, domain):
            excluded["aggregator"] += 1
            continue
        doc_type = doc.get("type") or classify_url(url, domain)
        if doc_type == "official" and classify_url(url, domain) != "official":
            doc_type = classify_url(url, domain)  # the final URL left the merchant domain
        if check_topic and doc_type != "official" and not mentions_merchant(doc["text"], url, names, merchant):
            excluded["off_topic"] += 1
            continue
        anchor = None if doc_type == "official" else anchor_name
        for found in extract_from_text(doc["text"], names, excluded, anchor, doc.get("title")):
            source = {"type": doc_type, "url": url, "title": clip(doc.get("title"), 120),
                      "date": doc.get("date"), "excerpt": found["excerpt"]}
            if doc.get("channel"):
                source["channel"] = doc["channel"]
            mentions.append({"code": found["code"], "discount": found["discount"],
                             "conditions": found["conditions"], "source": source})
    return mentions


def exit_for(codes, status, youtube_missing):
    attempted = [s for s in status.values() if s["status"] != "skipped"]
    if attempted and all(s["status"] != "ok" for s in attempted):
        return EXIT_ALL_FAILED
    if codes:
        return EXIT_OK
    return EXIT_MISSING if youtube_missing else EXIT_NO_CODE


def finish(result, mentions, limit, today, excluded):
    """Rank, then fill codes (top `limit`, at most MAX_SOURCES_PER_CODE sources each) and candidates (all)."""
    ranked = rank_mentions(mentions, today)
    codes = [dict(entry, sources=entry["sources"][:MAX_SOURCES_PER_CODE]) for entry in ranked[:limit]]
    result["codes"] = codes
    result["candidates"] = [{"code": e["code"], "discount": e["discount"], "conditions": e["conditions"],
                             "sources": e["sources"]} for e in ranked]
    result["excluded"] = dict(sorted(excluded.items()))
    result["summary"] = build_summary(codes)
    result["note"] = "Codes are publicly shared and untested: try them in order."
    return codes


def check_max(opts):
    if opts.max < 1:
        raise UsageError("--max must be at least 1")


def run_find(opts, client=None, today=None):
    merchant = squeeze(opts.merchant)
    if not merchant:
        raise UsageError("merchant is empty")
    check_max(opts)
    if opts.no_youtube and opts.no_web and opts.no_hn and not opts.domain and not opts.github:
        raise UsageError("every source is disabled")
    domain = normalize_domain(opts.domain) if opts.domain else None
    today = today or date.today()
    client = client or Client()
    names = merchant_names(merchant, domain)
    queries = build_queries(merchant, opts.product, opts.lang)
    excluded, status, docs, offers, warnings = Counter(), {}, [], [], []
    youtube_missing = False

    if domain:
        status["official"], found, offers = fetch_official(client, domain)
        docs += found
    else:
        status["official"] = status_entry("skipped", 0, "no --domain")
    if opts.no_hn:
        status["hn"] = status_entry("skipped", 0, "disabled")
    else:
        status["hn"], found = search_hn(client, queries["hn"])
        docs += found
    if opts.no_youtube:
        status["youtube"] = status_entry("skipped", 0, "disabled")
    else:
        status["youtube"], found, youtube_missing = search_youtube(client, queries["youtube"])
        docs += found
        if youtube_missing:
            warnings.append(status["youtube"]["detail"])
    if opts.no_web:
        status["duckduckgo"] = status_entry("skipped", 0, "disabled")
        status["bing"] = status_entry("skipped", 0, "disabled")
    else:
        found_status, found = search_web(client, queries["web"])
        status.update(found_status)
        docs += found
    if opts.github:
        status["github"], found = search_github(client, merchant)
        docs += found
    else:
        status["github"] = status_entry("skipped", 0, "off by default (--github)")

    mentions = docs_to_mentions(docs, merchant, names, domain, excluded)
    result = {"merchant": merchant, "merchant_domain": domain, "lang": opts.lang, "generated": today.isoformat(),
              "official_offers": offers, "sources_status": status, "queries": queries, "warnings": warnings,
              "requests": client.count}
    codes = finish(result, mentions, opts.max, today, excluded)
    return result, exit_for(codes, status, youtube_missing)


def run_extract(opts, today=None):
    check_max(opts)
    merchant = squeeze(opts.merchant)
    if not merchant:
        raise UsageError("--merchant is required: a code is only kept if it is near the merchant name")
    try:
        with open(opts.text, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        raise UsageError("cannot read %s: %s" % (opts.text, exc))
    if not re.match(r"^https?://[^\s]+$", opts.url or ""):
        raise UsageError("--url must be an http(s) URL")
    domain = normalize_domain(opts.domain) if opts.domain else None
    today = today or date.today()
    excluded = Counter()
    mentions = []
    if blocked_reason(opts.url, domain):
        excluded["aggregator"] += 1
    else:
        names = merchant_names(merchant, domain)
        doc_type = classify_url(opts.url, domain)  # `official` only on the merchant domain
        if opts.type and opts.type != "official" and doc_type != "official":
            doc_type = opts.type
        is_html = re.search(r"<\s*(?:html|body|div|p|span|a|li|br)\b", text, re.I) is not None
        text = html_to_text(text) if is_html else text
        anchor = None if doc_type == "official" else squash(merchant)
        for found in extract_from_text(text, names, excluded, anchor, opts.title):
            mentions.append({"code": found["code"], "discount": found["discount"],
                             "conditions": found["conditions"],
                             "source": {"type": doc_type, "url": opts.url, "title": clip(opts.title, 120),
                                        "date": iso(opts.date), "excerpt": found["excerpt"]}})
    result = {"merchant": merchant, "merchant_domain": domain, "generated": today.isoformat(),
              "official_offers": [], "sources_status": {"extract": status_entry("ok", len(mentions))},
              "queries": {}, "warnings": []}
    codes = finish(result, mentions, opts.max, today, excluded)
    return result, EXIT_OK if codes else EXIT_NO_CODE


def load_json_object(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise UsageError("cannot read %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise UsageError("%s: expected a JSON object" % path)
    return data


def clean_offers(offers, domain, excluded, where):
    """Official offers are kept only if their URL is on the merchant domain."""
    need(offers, list, where, "official_offers")
    kept = []
    for position, offer in enumerate(offers):
        place = "%s, official_offers %d" % (where, position)
        need(offer, dict, place, "an offer")
        kind = need(offer.get("kind"), str, place, "kind")
        url = need(offer.get("url"), str, place, "url")
        text = need(offer.get("text"), str, place, "text")
        if kind not in OFFER_KINDS:
            raise malformed(place, "kind must be one of %s" % ", ".join(sorted(OFFER_KINDS)))
        if not domain or classify_url(url, domain) != "official" or blocked_reason(url, domain):
            excluded["offer_not_official"] += 1
            continue
        kept.append({"kind": kind, "url": url, "text": clip(text, EXCERPT_LENGTH)})
    return kept


def run_rank(opts, today=None):
    check_max(opts)
    today = today or date.today()
    excluded, mentions = Counter(), []
    merged = {"official_offers": [], "sources_status": {}, "queries": {}, "warnings": [], "merchant": None}
    documents = [(path, load_json_object(path)) for path in opts.input]
    domain = normalize_domain(opts.domain) if opts.domain else None
    first_domain = documents[0][1].get("merchant_domain")
    if domain is None and first_domain is not None:  # only the first file (the find output) can name the domain
        domain = normalize_domain(need(first_domain, str, documents[0][0], "merchant_domain"))
    merged["merchant_domain"] = domain
    seen_offers = set()
    for path, data in documents:
        entries = data["candidates"] if "candidates" in data else data.get("codes", [])
        mentions += entry_mentions(entries, domain, excluded, path)
        counts = need(data.get("excluded", {}), dict, path, "excluded")
        for name, count in counts.items():
            if not isinstance(name, str) or isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise malformed(path, "excluded must map reasons to counts")
            excluded[name] += count
        merchant = need(data.get("merchant"), str, path, "merchant", optional=True)
        merged["merchant"] = merged["merchant"] or merchant
        queries = need(data.get("queries", {}), dict, path, "queries")
        merged["queries"] = merged["queries"] or queries
        warnings = need(data.get("warnings", []), list, path, "warnings")
        if not all(isinstance(w, str) for w in warnings):
            raise malformed(path, "warnings must be a list of strings")
        merged["warnings"] += [w for w in warnings if w not in merged["warnings"]]
        statuses = need(data.get("sources_status", {}), dict, path, "sources_status")
        for name, value in statuses.items():
            need(value, dict, path, "sources_status.%s" % name)
            merged["sources_status"].setdefault(name, value)
        for offer in clean_offers(data.get("official_offers", []), domain, excluded, path):
            key = (offer["kind"], offer["url"])
            if key not in seen_offers:
                seen_offers.add(key)
                merged["official_offers"].append(offer)
    merged["generated"] = today.isoformat()
    codes = finish(merged, mentions, opts.max, today, excluded)
    return merged, EXIT_OK if codes else EXIT_NO_CODE


def run_doctor(client=None):
    binary = ytdlp_path()
    version = None
    if binary:
        try:
            version = subprocess.run([binary, "--version"], capture_output=True, text=True,
                                     timeout=15).stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            version = None
    targets = {"duckduckgo": "https://html.duckduckgo.com/html/?q=promo",
               "bing": "https://www.bing.com/search?q=promo",
               "hn": "https://hn.algolia.com/api/v1/search?query=promo&hitsPerPage=1",
               "youtube": "https://www.youtube.com/"}
    client = client or Client(max_requests=len(targets))
    sources = {}
    for name, url in targets.items():
        state, _, detail = fetch(client, url)
        sources[name] = status_entry(state, 0, detail)
    result = {"python": sys.version.split()[0],
              "yt_dlp": {"found": bool(binary), "version": version,
                         "hint": None if binary else "pip install -U yt-dlp (or brew install yt-dlp)"},
              "gh": {"found": bool(shutil.which("gh")), "note": "only used with --github"},
              "sources": sources, "reddit_x": "not queried by the script: use WebSearch (see SKILL.md)"}
    if all(entry["status"] != "ok" for entry in sources.values()):
        return result, EXIT_ALL_FAILED
    return result, EXIT_OK if binary else EXIT_MISSING


# --------------------------------------------------------------------------------------------- CLI

def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("--max must be an integer, got %r" % value)
    if number < 1:
        raise argparse.ArgumentTypeError("--max must be at least 1")
    return number


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": message}, ensure_ascii=False))
        sys.exit(EXIT_USAGE)


def build_parser():
    parser = JsonParser(description="Find and rank publicly shared promo codes for a merchant.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=JsonParser)
    sub.add_parser("doctor", help="dependencies and reachability of the sources")
    find = sub.add_parser("find", help="search, extract and rank the codes")
    find.add_argument("merchant")
    find.add_argument("--domain", help="official domain, e.g. example.com (enables the official pages)")
    find.add_argument("--product", default="", help="product or plan, appended to the queries")
    find.add_argument("--lang", choices=("fr", "en"), default="en")
    find.add_argument("--max", type=positive_int, default=10)
    find.add_argument("--no-youtube", action="store_true")
    find.add_argument("--no-web", action="store_true")
    find.add_argument("--no-hn", action="store_true")
    find.add_argument("--github", action="store_true", help="also search public GitHub issues (off by default)")
    extract = sub.add_parser("extract", help="extract codes from a saved page text")
    extract.add_argument("--text", required=True, help="file with the page text")
    extract.add_argument("--url", required=True, help="URL the text comes from")
    extract.add_argument("--merchant", required=True, help="merchant name: only codes near it are kept")
    extract.add_argument("--domain", help="merchant domain: only pages on it can be typed official")
    extract.add_argument("--type", choices=sorted(SOURCE_TYPE_POINTS), help="source type (default: from the URL)")
    extract.add_argument("--title", default="")
    extract.add_argument("--date", default="", help="publication date, YYYY-MM-DD")
    extract.add_argument("--max", type=positive_int, default=10)
    rank = sub.add_parser("rank", help="merge find/extract outputs and rerank")
    rank.add_argument("--input", nargs="+", required=True, help="JSON files: a find output, then extract outputs")
    rank.add_argument("--domain", help="merchant domain (default: the one recorded in the first file)")
    rank.add_argument("--max", type=positive_int, default=10)
    return parser


def main(argv=None):
    opts = build_parser().parse_args(argv)
    try:
        if opts.command == "doctor":
            result, code = run_doctor()
        elif opts.command == "find":
            result, code = run_find(opts)
        elif opts.command == "extract":
            result, code = run_extract(opts)
        else:
            result, code = run_rank(opts)
    except UsageError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - last resort, reported as JSON
        print(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}, ensure_ascii=False))
        return EXIT_UNEXPECTED
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
