# 01. Research verdicts: what is proven, probable, overrated or folklore

Every common claim about GEO, with a verdict, the explanation and the source. Starting point: the research note
of the jam-jam.org campaign (`handoff/GEO-2026-10/RECHERCHE.md`, 10 October 2026), corrected and completed on
14 October 2026 by re-reading the primary sources. Several points of the original note had changed or were
imprecise: they are listed in §9.

## Verdict scale

| Verdict | Meaning |
|---|---|
| **Proven** | Official documentation from the publisher concerned, or a reproducible controlled study |
| **Probable** | Converging correlations or a single solid study, without causal demonstration |
| **Overrated** | True in part, but the expected effect on AI visibility is much lower than its reputation |
| **Folklore** | Contradicted by documentation or measurements, or without any basis |
| **Unverified** | Reported, but the primary source could not be consulted (see §10) |

Usage rule: never present a "probable" as a "proven" in a client deliverable. Say "measured correlation" and
cite the study.

## 1. Market and behavior

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Ranking first on Google guarantees being cited by assistants | Folklore | Assistants have their own indexes and sources. Even for AI Overviews, only 38% of cited URLs are also in the top 10 for the same query (March 2026, after the move to Gemini 3 and the multiplication of sub-queries) | https://ahrefs.com/blog/ai-overview-citations-top-10/ |
| AI Overviews mostly cite the top 10 | Outdated | It was 76% in July 2025; 38% in March 2026. Sub-queries ("query fan-out") open other results | https://ahrefs.com/blog/search-rankings-ai-citations/ then the previous link |
| AI summaries reduce clicks | Proven | Pew (900 US adults, March 2025): 8% of visits click a classic result with an AI summary, 15% without; 1% click a link in the summary | https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/ |
| Assistants often cite without a link | Proven | Across more than 31,000 brand mentions, a link appears in only 10.7% of AI Overviews mentions, 16.8% of Gemini, 26.1% of Copilot and 51.6% of Perplexity | https://ahrefs.com/blog/ai-citations-vs-impressions-study |
| ChatGPT launches advertising | Proven (fact) | OpenAI documentation describes a dedicated robot (OAI-AdsBot) that validates pages submitted as ads in ChatGPT. Not relevant to organic search | https://platform.openai.com/docs/bots |
| Assistant answers are stable | Folklore | Answers vary from one run to the next; repeat each question (see `07-measurement.md`). No controlled study consulted: a method conclusion, not quantified | Method |

## 2. Content

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Statistics, quotations and sources increase visibility in generative answers | Probable | Princeton GEO study (KDD 2024): "Cite Sources", "Quotation Addition" and "Statistics Addition" give +30 to 40% relative on the position-adjusted word count metric and +15 to 30% on subjective impression. Caveats: a generative search engine built by the authors (GEO-bench benchmark) and a test on Perplexity; the effect varies by domain; "Cite Sources" gives +115.1% to sources ranked 5th but -30.3% to sources ranked 1st | https://arxiv.org/abs/2311.09735 |
| Keyword stuffing helps | Proven ineffective | Same study: "Keyword Stuffing" does no better than the baseline | https://arxiv.org/abs/2311.09735 |
| A direct 40-60 word answer at the top of the page helps being cited | Probable, not demonstrated | No controlled test of this precise format was found. Argument: engines retrieve passages. Google says it does not require splitting. Zero cost and a benefit for the reader, so applied (see `04`) | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| Cutting content into small pieces for AIs | Folklore (for Google) | Google: no "chunking" requirement; its systems understand several topics on one page. Self-contained sections remain good writing | Same guide |
| Rewriting content specifically for AIs | Folklore (for Google) | Google: unnecessary, its systems understand synonyms; no need to cover every long-tail variant | Same guide |
| There is an ideal page length | Folklore | "There is no ideal length" (Google) | Same guide |
| Unique content, drawn from first-hand experience, is what matters most in the long run | Proven (official position) | Google distinguishes "non-commodity" content (its own point of view) from content that rewords what exists, and places it above the other advice | Same guide |
| Creating one page per query variant to weigh on AI answers | Proven harmful | Falls under the "scaled content abuse" policy; a large number of pages does not make a site better | Same guide |
| Recent, dated content is favored | Probable | Google says it uses `lastmod` if it is "consistently and verifiably accurate". Corollary: a wrong date is a risk (see `03` §2) | https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap |
| Tables and lists are more citable | Probable, not demonstrated | Consistent with passage extraction; no controlled study consulted | Method |
| A FAQ improves AI visibility | Overrated | Standalone question/answer pairs are easy to extract, but Google no longer shows the rich result (see §3). Keep the visible block for the reader, do not oversell it | See §3 |

## 3. Structured data

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| JSON-LD is "served on a silver platter" to AIs | Overrated | Google: "no particular schema.org to add" for AI Overviews and AI Mode, and "over-investing in structured data" appears among the myths. A public test (February 2026) showed that ChatGPT and Perplexity read JSON-LD, even invalid, as page text | https://developers.google.com/search/docs/appearance/ai-features ; https://www.seroundtable.com/chatgpt-perplexity-structured-data-text-40862.html |
| JSON-LD remains useful for Google | Proven | Eligible for rich results; entity (name, logo, `sameAs` documented for Organization) | https://developers.google.com/search/docs/appearance/structured-data/organization |
| HowTo rich results | Proven removed | Mobile removed in August 2023, desktop on 13 September 2023: display type deprecated | https://developers.google.com/search/blog/2023/08/howto-faq-changes |
| FAQ rich results | Proven removed | Restricted in August 2023 to official government and health sites; display stopped on 7 May 2026 and the documentation was withdrawn in June 2026. The markup remains harmless, but extending it no longer has any justification on Google's side | https://developers.google.com/search/updates (entries of 8 May and 15 June 2026) |
| An entity graph linked by `@id` (Organization, WebSite, WebPage) helps assistants identify the brand | Probable | Removes ambiguity for engines that exploit markup (Google, Bing); for LLMs, it is just one more text. Low cost, so applied | Practice; see `03` §6 |
| Bing uses markup for its generative answers | Unverified | Statement by a Bing official reported in 2025; the primary source could not be consulted | Unverified |

## 4. Files and tags dedicated to AI

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| llms.txt gets the site cited | Overrated | Google: its systems do not use them and do not take them into account, either positively or negatively (added 15 June 2026). Ahrefs (137,000 domains, May 2026): 28% publish an llms.txt, 97% of these files received no request, 96% of requests come from robots, 19.5% from named AI robots (GPTBot first, then a coding agent), and no AI robot looks for an unpublished file | https://ahrefs.com/de/blog/llmstxt-study/ ; https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| Can llms.txt harm? | Unlikely | The same study flags a risk: actors probe these files for instruction injection; an outdated file misleads. Hence: generated at build time, factual content, no instructions | Same study |
| A dedicated robots.txt for AIs is needed | Proven useful for control | Each publisher documents its tokens and their independence (training, index, on-demand visit). A site with no blocking has nothing to add; a site behind a CDN must check its per-robot rules | https://platform.openai.com/docs/bots ; https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler ; https://docs.perplexity.ai/guides/bots |
| Blocking GPTBot prevents appearing in ChatGPT | Folklore | "Each setting is independent": you can allow OAI-SearchBot and block GPTBot. Only OAI-SearchBot governs search | https://platform.openai.com/docs/bots |
| Google-Extended removes you from AI Overviews | Folklore | Token without its own user-agent; governs Gemini training and grounding outside Search; no effect on Search. To limit display in Search: `nosnippet`, `max-snippet`, `noindex` | https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers ; https://developers.google.com/search/docs/appearance/ai-features |
| On-demand robots respect robots.txt | Folklore | OpenAI (ChatGPT-User) and Perplexity (Perplexity-User) state that the rules may not apply; Meta states that its on-demand fetcher may bypass some rules (text read truncated). To control: WAF rules | Publishers' documentation |
| AI robots execute JavaScript | Folklore (except Google and Apple) | December 2024 measurement: OpenAI, Anthropic, Meta, ByteDance, Perplexity and CCBot do not render JavaScript; Gemini (via Googlebot) and Applebot do. A robot may download a JS file without executing it | https://vercel.com/blog/the-rise-of-the-ai-crawler |
| The CDN can block AI robots by default | Proven (fact) | Cloudflare announced in July 2025 a default block, which can be lifted; it also published in August 2025 observations of undeclared crawling attributed to Perplexity | https://www.cloudflare.com/press/press-releases/2025/cloudflare-just-changed-how-ai-crawlers-scrape-the-internet-at-large/ ; https://blog.cloudflare.com/perplexity-is-using-stealth-undeclared-crawlers-to-evade-website-no-crawl-directives/ |

## 5. URL, sitemap, robots.txt

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Two URLs for one page (with and without slash) split signals | Proven (principle), observed locally | Google recommends reducing duplicate content and setting a canonical. Local measurement: `/accordeur-basse` (no slash) position 62.7, `/accordeur-basse/` position 40.7, and the tool page showing "Redirect error" in Search Console for the URL without slash | Google doc (duplicate content); campaign audit |
| Google uses `lastmod` | Proven, conditional | Used if consistently and verifiably accurate; a footer update does not count. `priority` and `changefreq` are ignored | https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap |
| Sitemap limits | Proven | 50,000 URLs or 50 MB uncompressed per file; sitemap index allowed | Same page |
| A `Disallow` covering a subfolder also blocks the sitemap placed inside it | Proven | Google applies the most specific rule; in case of conflict, the least restrictive one. In the campaign, `Disallow: /app/` blocked `/app/sitemap-convert.xml`: Search Console error since 17 September, `Allow` rule added 10 October | https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt |
| `User-agent` groups add up | Folklore | Only one group is valid for a robot (the most specific); specific groups and the `*` group are not merged. Any `Allow` exception must therefore be repeated in each group | Same page |
| `urllib.robotparser` (Python) applies the same logic as Google | Folklore | It applies the first matching rule in file order, without `*` or `$` in paths. Do not use it to audit; use "longest rule, Allow on a tie" (RFC 9309) | Local test on Python 3.9: `Disallow: /app/` followed by `Allow: /app/convert` refuses `/app/convert/x` (Google allows it, longest rule); `Disallow: /*.pdf$` is not applied. To be re-checked on other versions |
| The Indexing API speeds up indexing of any page | Folklore | Reserved for `JobPosting` and `BroadcastEvent` pages (in `VideoObject`); every submission goes through an anti-spam check; a sitemap remains recommended. The campaign abandoned this use (412 tool URLs submitted before) | https://developers.google.com/search/apis/indexing-api/v3/quickstart |
| Submitting sitemaps via the Search Console API | Proven | `PUT https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, scope `webmasters` (write) | https://developers.google.com/webmaster-tools/v1/sitemaps/submit |
| IndexNow also notifies Google | Folklore | Participating engines listed by the protocol: Bing, Naver, Seznam, Yandex, Yep, Amazon. Google is not among them. Key of 8 to 128 characters, up to 10,000 URLs per submission | https://www.indexnow.org/documentation ; https://www.indexnow.org/faq |
| IndexNow speeds up discovery by Bing | Probable | That is its purpose; no independent measured gain consulted | Protocol |

## 6. Hreflang and languages

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Language variants must reference each other | Proven | Each version lists all the others, including itself, with `x-default`. An English page at the root without `/en/` is valid | Google documentation on localized versions (not re-opened on 14 October: prior knowledge) |
| Different codes between sitemap and pages lose the signal | Proven (local finding) | The 380 conversion pages used `pt-BR` while the rest of the site used `pt` | Campaign audit |
| Translating into ten languages multiplies traffic | Probable, to be qualified | Over 90 days, the English root gets 311 clicks out of 8,725 impressions, French 171 out of 5,397, Korean 6 out of 188: the small languages weigh little, but face little competition | The site's Search Console (see `05-multilingual.md`) |

## 7. Entity and off-site presence

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Brand mentions count more than links | Probable (correlation) | 75,000 brands: web mentions 0.664, inbound links 0.218, brand anchors 0.527, brand search volume 0.392. Correlation with visibility in AI Overviews, not causation | https://ahrefs.com/blog/ai-overview-brand-correlation/ |
| YouTube is the most correlated signal | Probable | YouTube mentions about 0.737 (ChatGPT, AI Mode, AI Overviews), ahead of web mentions at 0.66 to 0.71; YouTube accounts for 18.2% of cited URLs that are not in the top 100 results for the query | https://ahrefs.com/blog/ai-brand-visibility-correlations/ ; https://ahrefs.com/blog/ai-overview-citations-top-10/ |
| Wikipedia and Reddit dominate ChatGPT citations | Probable, unstable | Semrush observed a sharp drop in these citations in September 2025; the cause is debated (a change of Google parameter or a concern about source balance) | https://www.semrush.com/blog/most-cited-domains-ai/ |
| Fabricating mentions (fake accounts, fake reviews) | Proven harmful | Google advises against inauthentic mentions and tightens its rule on undisclosed incentivized reviews (July 2026); Reddit and Wikipedia sanction self-promotion | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide ; https://developers.google.com/search/updates |
| Wikidata and the knowledge graph help being recognized as an entity | Unverified | Reasonable, no primary source consulted. Campaign condition: create an entry only after an independent source | Unverified |
| Positioning on a coherent niche | Probable | Less competition and a clear entity; in the campaign, pages for rare instruments (guitalele position 8, mandolin, violin, cello positions 9 to 13) are the ones ranking. Local observation | The site's Search Console |

## 8. Measurement

| Claim | Verdict | Explanation | Source |
|---|---|---|---|
| Search Console measures Google's AI features | Proven | "Generative AI" performance report in Search Console; AI Overviews are counted in the standard performance report | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| A site must be included in Search Console's AI features to be eligible | Proven | Condition cited by Google's guide, in addition to being indexed and eligible with a snippet | Same guide |
| Third-party "GEO score" tools reflect Google's internal ranking | Folklore | Google: no third-party tool has access to its internal ranking or AI systems | Same guide |
| A monthly question panel gives a usable signal | Probable | Provided each question is repeated (at least three times, five recommended), conditions are fixed, and the brand is never named in the question. Directional signal, not a precise measurement | `07-measurement.md` |

## 9. Corrections to the original note

1. **AI Overviews and top 10**: "mostly cite the top 10" becomes "76% in July 2025, 38% in March 2026".
2. **Clicks after an AI answer**: the 8% figure concerns clicks on a classic result when a summary is present
   (15% without). The click on a link in the summary is 1%.
3. **FAQ**: the note said "rich results reserved for government and health sites since 2023". Since 7 May 2026,
   they no longer appear at all. The campaign kept the FAQPage markup and the visible block; it did not extend
   them (plan v2 decision: "kept, not extended").
4. **JavaScript**: "no AI robot executes JavaScript" is too strong. Googlebot (therefore Gemini and AI Overviews)
   and Applebot execute it. The reasoning remains valid for OpenAI, Anthropic, Meta, ByteDance, Perplexity and
   CCBot.
5. **Ahrefs study URL on mentions**: the address cited in the original note points to the study on links in
   mentions. The study of 75,000 brands is https://ahrefs.com/blog/ai-overview-brand-correlation/ .
6. **Google's guide (15 May 2026)**: the original note did not know it. It contradicts three very widespread
   practices (llms.txt, chunking, searching for mentions) and confirms that fundamental SEO remains the basis.
   The campaign kept an answer block at the top and self-contained sections, because they also serve the other
   assistants and the readers, without expecting an effect at Google.
7. **Robots**: the note listed 13 tokens. Current documentation adds MistralAI-Index, Amzn-SearchBot, Amzn-User,
   Meta-ExternalFetcher and OAI-AdsBot (see `00-overview.md` §4).

## 10. What could not be verified

- The OpenAI help page on ChatGPT search requires JavaScript; the claim "ChatGPT partly relies on Bing" rests on
  third-party analyses and on the wording "third-party search providers".
- Claude's external search provider (often attributed to Brave Search) is not documented by Anthropic.
- The statement of a Bing official on the use of markup by its generative models.
- Google's hreflang pages were not re-opened on 14 October 2026; the reciprocity principle has been stable for
  years.
- Wikidata and the knowledge graph as an entity lever: no primary source consulted.
- Meta's exact text on bypassing robots.txt via Meta-ExternalFetcher (page consulted truncated) and Perplexity's
  response to Cloudflare's observations.
- Any robustness of Ahrefs' correlations outside their own dataset (proprietary datasets not accessible).
- No measured result from the campaign itself at the time of writing (deployment of 10 October 2026).
