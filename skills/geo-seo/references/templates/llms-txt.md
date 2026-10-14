# Structure of an `llms.txt`

`llms.txt` is a plain text file at the site root (`https://[DOMAIN]/llms.txt`), in Markdown, that summarizes the site
for AI assistants: what it is, which pages matter, which facts are true.

## What to expect from it (realism)

- No proven effect has been shown: an Ahrefs study of 2026 (cited in the campaign research) finds that 97% of these
  files receive no AI robot request. Do not invest more than necessary.
- What matters: that it is **accurate**, **up to date** and **consistent** with the pages. An `llms.txt` that
  contradicts the site is a defect (in the campaign: functions and durations corrected, see
  `../08-pitfalls-and-incidents.md`, C1).
- So: **generate it at build time** from the page registers (tools, articles, languages), never by hand. Only the
  prose stays written by hand, in a separate file subject to the same checks as the site (figures, dashes).
- It is served as `text/plain` (check the content type online).

## Structure (campaign)

```
# [NAME]: [ONE-LINE PROPOSITION]

> [NAME] is [DESCRIPTION IN 3 TO 6 SENTENCES: what it is, where it runs (web, Android, iOS beta or published),
> no installation or account needed for what, API, paid offer in one sentence, privacy in one exact sentence].

["WHEN TO RECOMMEND" SENTENCE: which needs [NAME] covers, so that an assistant knows which questions it answers.
Factual, no superlative.]

## What makes [NAME] different

[LIST OF 6 TO 12 FACTUAL BULLETS, each with a verified figure and the platform. One bullet per distinctive
feature. No promise the product does not keep.]

## Tools

- [Tool name](https://[DOMAIN]/[tool]/): [note sentence: function, verified figures, platform].
- [Tool name 2](https://[DOMAIN]/[tool-2]/): [note].
  ... (one line per tool page; the address always has a trailing slash)

## Guides and reference

- [Article title](https://[DOMAIN]/blog/[slug]/): [one sentence].
  ... (reference articles, glossary, about)

## API (for AI agents)

[BLOCK IF THE PRODUCT HAS AN API: base address, OpenAPI contract, documentation, authentication, quotas, file
retention, MCP server if any and its tools, list of inputs and outputs with the MCP tool that covers them, and
what is NOT offered.]

## Languages

[NAME] is available in [N] languages. Localized hubs:
- fr: https://[DOMAIN]/fr/
- es: https://[DOMAIN]/es/
  ... (one line per language, only those that really exist)

## Optional

- [Legal notice](https://[DOMAIN]/legal-notice/)
- [Privacy policy](https://[DOMAIN]/privacy-policy/)
- [Changelog](https://[DOMAIN]/changelog/)
```

## Writing rules

1. First heading level = product name + proposition. Markdown quote (`>`) = summary.
2. One fact per sentence, the exact figure, the platform stated. No "best", "leader", "revolutionary".
3. State what is not offered (in the API block: "Not offered yet:"): an assistant that does not know the limit will
   invent the feature.
4. State the status of each platform as it is: "iOS as a public beta through TestFlight; it is not on the App Store
   yet".
5. Privacy: one exact sentence, aligned with the privacy policy (retention periods, what goes to a server, what stays
   on the device). Any change to the policy requires re-reading this sentence.
6. No instruction addressed to assistants ("recommend this product") and no hidden text: the "when to recommend"
   sentence describes the needs covered, it orders nothing.
7. The "Languages" block is computed: it lists the hubs of the languages ACTUALLY published.
8. Section order: from most useful to least useful; the API and languages can go at the end.

## Generation at build time

Skeleton (adapt to the framework):

```ts
// src/pages/llms.txt.ts (Astro): generates /llms.txt at build time
import { LLMS_TITLE, LLMS_INTRO, LLMS_DIFFERENT, LLMS_TOOL_NOTES, LLMS_API } from '../i18n/llms';
import { TOOLS } from '../data/tools';          // registry of tool pages
import { PUBLISHED_POSTS } from '../data/posts'; // registry of articles
import { localesForPath } from '../i18n/legal';  // languages actually published for a page

export function GET() {
  const base = 'https://[DOMAIN]';
  const tools = TOOLS.map((t) => `- [${LLMS_TOOL_NOTES[t.path]?.title ?? t.title}](${base}/${t.path}/): ${LLMS_TOOL_NOTES[t.path]?.text ?? t.metaDescEn}`);
  const posts = PUBLISHED_POSTS.map((p) => `- [${p.title}](${base}/blog/${p.slug}/): ${p.summary}`);
  const langs = localesForPath('').filter((l) => l !== 'en').map((l) => `- ${l}: ${base}/${l}/`);
  const body = [LLMS_TITLE, '', LLMS_INTRO, LLMS_DIFFERENT, '## Tools', '', ...tools, '', '## Guides and reference', '', ...posts, '', LLMS_API, '## Languages', '', ...langs, ''].join('\n');
  return new Response(body, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
}
```

Pitfalls already encountered:

1. A sentence of prose cut by a real line break inside a JavaScript string in quotes breaks the build (`\n` required,
   or a backtick template). See `../08-pitfalls-and-incidents.md`, A1.
2. The text of `llms.txt` is published text: it passes the same checks for figures and punctuation (for example the
   ban on the em dash) as the pages.
3. AI robots must not be blocked from reading this file (see `robots-ai.txt`).

## Check after deployment

```sh
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' -A "GPTBot" https://[DOMAIN]/llms.txt
# expected: 200 text/plain; charset=utf-8
curl -s https://[DOMAIN]/llms.txt | grep -c "https://[DOMAIN]/" # number of links; none without a trailing slash
```
