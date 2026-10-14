# README skeleton for a public API examples repository

Use: a public GitHub repository that contains runnable examples of a public API (see `../06-off-site.md`, §5). Replace
the brackets. The README content is in English (the language of coding assistants and developers).

## Parameters

| Parameter | Content | Example (Jam Jam) |
|---|---|---|
| `[NAME]` | product name | Jam Jam |
| `[SITE]` | site address | `https://jam-jam.org/` |
| `[API_BASE]` | API base address | `https://jam-jam.org/api/v1` |
| `[OPENAPI]` | OpenAPI contract address | `https://jam-jam.org/api/v1/openapi.json` |
| `[DOCS]` | documentation page | `https://jam-jam.org/developers/` |
| `[FUNCTION]` | what the API does, in one sentence | "converts music files, links and text into chord sheets, PDF, MIDI or MusicXML" |
| `[KEY_PREFIX]` | start of an API key (never a real key) | `jj_live_` |
| `[KEY_VARIABLE]` | environment variable name | `JAM_JAM_API_KEY` |
| `[MCP_PACKAGE]` | MCP server package name, if published | `@jam-jam/convert-mcp` |
| `[TERMS]` | terms of use address | `https://jam-jam.org/terms/` |

## Checks before publishing

1. No real key anywhere (files, Git history, output examples). A `.env.example` with a fake key; `.env` in
   `.gitignore`.
2. No song lyrics, no protected title or excerpt: the example files are public domain or created for the repository.
3. Every format identifier or route is checked against the OpenAPI contract AND run once.
4. The MCP package cited is really published in the package registry; the legal page addresses answer 200.
5. The quotas in the table are those of the site's pricing page (no figure copied from an old document).
6. MIT (or Apache-2.0) license, and a sentence specifying that the license covers the examples, not the service.
7. Then: add the repository to the `Organization`'s `sameAs`, to the site's developer page and, if the item exists, to
   Wikidata (P1324).

## Repository structure

```
[name]-api-examples/
  README.md
  LICENSE
  .env.example
  samples/public-domain-sample.[ext]
  curl/
    01-list-formats.sh  02-convert-file.sh  03-follow-job-sse.sh
    04-poll-job.sh      05-download-result.sh  06-usage.sh
  javascript/           (Node 20+, native fetch, no dependency)
    package.json  list-formats.mjs  convert-file.mjs  convert-url.mjs  follow-events.mjs
  python/               (Python 3.10+, requests)
    requirements.txt  list_formats.py  convert_file.py  convert_url.py  usage.py
  mcp/
    claude_desktop_config.json
```

GitHub description: `Examples for the [NAME] REST API: [FUNCTION].` Topics to adapt (campaign: `music`, `chords`,
`chordpro`, `musicxml`, `midi`, `pdf`, `rest-api`, `openapi`, `songbook`). Website field: `[DOCS]`.

## README.md (skeleton to paste)

````markdown
# [NAME] API examples

Runnable examples for the [[NAME]]([SITE]) REST API.

The API [FUNCTION]. It is the same engine as the [NAME] app.

- Base URL: `[API_BASE]`
- OpenAPI contract: [`[OPENAPI]`]([OPENAPI])
- Documentation: [[DOCS]]([DOCS])

## Get an API key

1. Create a free [NAME] account at [[SITE]]([SITE]).
2. In the app, open **Settings, API keys** and create a key.
3. The key starts with `[KEY_PREFIX]` and is shown once. Copy it into `.env`:

```sh
cp .env.example .env
# then edit .env
```

Up to [N] keys per account, revocable at any time. Never commit a real key.

## Quotas

| Caller | Limit |
|---|---|
| Anonymous (no key) | [N] per [PERIOD] |
| Free account | [N] per [PERIOD] |
| Paid plan | [N] per [PERIOD] |

The exact balance is returned by `GET /me/usage` and in the `X-Quota-*` headers of every response that
consumes quota.

## Endpoints

| Method | Path | Scope | What it does |
|---|---|---|---|
| GET | `/formats` | none | List input and output formats |
| POST | `/jobs` | `[scope:write]` | Submit a job (file upload or JSON with a URL) |
| GET | `/jobs/{id}` | `[scope:read]` | Job status (poll) |
| GET | `/jobs/{id}/events` | `[scope:read]` | Job progress as Server-Sent Events |
| GET | `/jobs/{id}/result` | `[scope:read]` | Download the result file |
| DELETE | `/jobs/{id}` | `[scope:write]` | Cancel a job |
| GET | `/me/usage` | `[scope:read]` | Quota balance and scopes |

## Quick start (curl)

```sh
# 1. List formats (no key needed)
curl [API_BASE]/formats

# 2. Submit a file
curl -X POST [API_BASE]/jobs \
  -H "Authorization: Bearer $[KEY_VARIABLE]" \
  -F file=@samples/public-domain-sample.[ext] \
  -F inputFormat=[INPUT_FORMAT] \
  -F output=[OUTPUT_FORMAT]

# 3. Follow progress (Server-Sent Events)
curl -N -H "Authorization: Bearer $[KEY_VARIABLE]" \
  [API_BASE]/jobs/<job_id>/events

# 4. Download the result
curl -H "Authorization: Bearer $[KEY_VARIABLE]" \
  -OJ [API_BASE]/jobs/<job_id>/result
```

## JavaScript (Node 20+, no dependency)

```js
const API = '[API_BASE]';
const headers = { Authorization: `Bearer ${process.env.[KEY_VARIABLE]}` };

const res = await fetch(`${API}/jobs`, {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://example.com/my-document', output: '[OUTPUT_FORMAT]' }),
});
let job = await res.json();

while (!['done', 'failed', 'cancelled'].includes(job.phase)) {
  await new Promise((r) => setTimeout(r, (job.etaS ?? 2) * 1000));
  job = await (await fetch(`${API}/jobs/${job.id}`, { headers })).json();
}

if (job.phase === 'done') {
  const result = await (await fetch(`${API}/jobs/${job.id}/result`, { headers })).arrayBuffer();
  console.log('result bytes:', result.byteLength);
} else {
  console.error('failed:', job.problem);
}
```

## Python (3.10+)

```python
import os, time, requests

API = "[API_BASE]"
HEADERS = {"Authorization": f"Bearer {os.environ['[KEY_VARIABLE]']}"}

job = requests.post(f"{API}/jobs", headers=HEADERS,
                    json={"url": "https://example.com/my-document", "output": "[OUTPUT_FORMAT]"})
job.raise_for_status()
job = job.json()

while job["phase"] not in ("done", "failed", "cancelled"):
    time.sleep(job.get("etaS", 2))
    job = requests.get(f"{API}/jobs/{job['id']}", headers=HEADERS).json()

if job["phase"] == "done":
    data = requests.get(f"{API}/jobs/{job['id']}/result", headers=HEADERS)
    print("result bytes:", len(data.content))
else:
    print("failed:", job.get("problem"))
```

## Use it from an AI agent (MCP)

```json
{
  "mcpServers": {
    "[name]": {
      "command": "npx",
      "args": ["-y", "[MCP_PACKAGE]"],
      "env": { "[KEY_VARIABLE]": "[KEY_PREFIX]xxxxxxxxxxxxxxxx" }
    }
  }
}
```

Tools exposed: `[tool_1]`, `[tool_2]`, `[tool_3]` (list them with one line each). Compatible with MCP
clients such as Claude Desktop, Claude Code and Cursor.

## Errors and retention

Every error is an `application/problem+json` object (RFC 9457). Uploaded files and results are deleted
[N] hours after the job is created; fetching a result after that returns `410 Gone`.

| Status | Meaning | What to do |
|---|---|---|
| 400 | invalid input or format | check `GET /formats` |
| 401 | missing or invalid key | check the `Authorization` header |
| 403 | key lacks the scope | create a key with the right scope |
| 410 | result deleted | submit the job again |
| 413 | file too large | see the limits returned by `GET /formats` |
| 429 | quota exceeded | read `GET /me/usage` and the `X-Quota-*` headers |

## Rights

Only convert content you have the right to use. The sample in `samples/` is in the public domain.

## License

The examples in this repository are released under the MIT License. The [NAME] API and service are
governed by the [[NAME] terms]([TERMS]).
````

## Notes

- The error codes in the table are usual examples: replace them with those of the real OpenAPI contract, without
  inventing any.
- Keep the README short: the full documentation stays on the site (`[DOCS]`) and the repository links to it.
- An unmaintained repository harms the entity: plan a review at each contract change (format, quota, route) and a
  last-verified date in the README.
