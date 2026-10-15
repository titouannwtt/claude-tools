---
name: promo-codes
description: Find publicly shared promo codes for a merchant and rank them from best to worst, so the user can try them by hand. Use before a purchase, a subscription or a transaction, when the page has a promo code field, or when the user asks for a discount, a coupon or a cheaper price.
---

# promo-codes

Objective: give the user a short list of public, fixed promo codes for a merchant, best first. The codes are **only listed, never tested**: the user tries them.
The script searches, extracts and ranks (zero model tokens). Your role: run it, add what it cannot reach (Reddit, X), present the result.

## Commands

Script: `~/.claude/skills/promo-codes/scripts/promo.py`. One JSON object on stdout.

1. **Check the setup**: `python3 <script> doctor`
2. **Search**: `python3 <script> find "<merchant>" --domain example.com --lang fr --max 10`
   - `--domain` also reads the official pages (`/pricing`, `/students`, `/education`, `/referral`, `/partners`, robots.txt respected) and reports non-code offers (student, annual, referral, trial). Pass it whenever you know the site.
   - `--lang fr|en`: language of the queries (English is always included). `--product "<plan>"` narrows the queries.
   - `--no-youtube`, `--no-web`, `--no-hn` switch a source off; `--github` adds public GitHub issues (off by default).
3. **Add a page you found yourself**: `python3 <script> extract --text <file> --url <url> --merchant "<merchant>" [--title "<page title>"] [--date YYYY-MM-DD] > extra1.json` (`--merchant` is required: only codes near the merchant name are kept).
4. **Merge and rerank**: `python3 <script> rank --input find.json extra1.json extra2.json [--domain example.com]`

Save the `find` output to a file (`> find.json`) to be able to rerank it. Read `summary`, `codes`, `official_offers` and `sources_status` from it: the `candidates` field (every code with every source) is only there for `rank`. `rank` rechecks everything from the evidence (blocklist on every URL, code present in each excerpt, `official` only for the merchant domain) and exits 2 on a malformed file.

## Your complement (Reddit and X)

Reddit and X are blocked without a key, so the script does not query them. After `find`:
1. Run 2 to 4 WebSearch queries, e.g. `site:reddit.com "<merchant>" promo code`, `site:x.com "<merchant>" code promo`, `"<merchant>" discount code`.
2. For each relevant page, save its text to a file and run `extract`. The verbatim rule still applies: a code is kept only if it appears in the text of a known URL. Never type a code by hand into a JSON file.
3. Run `rank` with the `find` output and every `extract` output. The final list comes from the script, not from you.

## Present the result

In the user's language, a numbered list, best first (use `summary` and `codes`):
- the code, the discount, the condition (new customers, annual plan, minimum), the source link and its date if known;
- then the `official_offers` (student, annual, referral, trial) that need no code;
- say the codes are public and untested, and to try them in this order; the first one that the site accepts is enough;
- if `codes` is empty, say so plainly and show the official offers. Never invent a code.

## Exclusions (rules, not preferences)

- No coupon aggregator (Dealabs, RetailMeNot, Radins, ma-reduc, iGraal, Poulpeo, CouponBirds, Groupon coupons, Wethrift, Knoji, dealspotr, coupons.com, savings.com, Honey, Capital One Shopping...). The blocklist is `BLOCKED_DOMAINS` in the script, plus URL patterns (`code-promo`, `coupon`...). Do not read them through WebSearch either.
- No generated or brute-forced code, no leaked internal or developer test code, no code obtained through a security flaw.
- No bypass of a block: no cookies, no proxy, no CAPTCHA solving. A blocked source is reported in `sources_status`, then left alone.
- Never ask for or handle the user's payment data or account credentials. Entering the code on the site is up to the user.

## Exit codes and reaction

| Code | Meaning | Action |
|---|---|---|
| 0 | Codes found | Present them (see above). Check `sources_status` and `warnings` for degraded sources. |
| 4 | No code found | Say so, show `official_offers`, try the Reddit and X complement, suggest `--lang` or `--product` once. |
| 2 | Invalid usage (empty merchant, bad domain, unreadable file) | Fix the arguments from the `error` field. |
| 5 | Missing dependency (yt-dlp absent, nothing found) | `brew install yt-dlp` or `pip install -U yt-dlp`, rerun. Without it, the other sources still ran. |
| 7 | Every source failed (network down, blocks) | Read `sources_status`. Do not retry in a loop: report it, wait, or use the WebSearch complement alone. |
| 1 | Unexpected error | Read the message, fix the script (see Repair). |

`sources_status` values: `ok`, `blocked-403`, `blocked-429`, `captcha`, `error`, `skipped`. A `captcha` or `blocked` source is not retried.

## Limits

- At most about 25 calls per run (HTTP, yt-dlp and gh share the budget, `requests` gives the total), 1 s between two calls to the same host, 10 s timeouts. yt-dlp runs without user config, cookies or proxy.
- robots.txt: 401, 403, 429, 5xx or unreachable means no official page is read; other 4xx means no restriction.
- YouTube: only titles and the start of descriptions (no per-video fetch, which YouTube blocks). Dates are rarely known, so recency counts for little.
- Ranking (module docstring of the script): discount, number of independent sources, source type, recency, minus conditions. A high score is not a guarantee that the code works.

## Repair

If the script fails without an expected code (1), or if an output is inconsistent:
1. Read the full error message.
2. Fix the script in `<claude-tools>/skills/promo-codes/scripts/promo.py` (the symbolic link points to it), and run `python3 -m unittest discover -s tests` in the skill's folder.
3. Rerun the command. Two attempts at most, then report the problem to the user with the exact message.

A search engine that changes its HTML shows up as `ok` with `no result parsed` in `detail`: fix `parse_ddg` or `parse_bing`.
