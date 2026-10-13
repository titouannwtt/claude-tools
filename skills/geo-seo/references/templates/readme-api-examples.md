# Squelette de README pour un dépôt public d'exemples d'API

Usage : dépôt GitHub public qui contient des exemples exécutables d'une API publique (voir
`../06-hors-site.md`, §5). Remplacez les crochets. Le contenu du README est en anglais (langue des
assistants de code et des développeurs), le reste de ce fichier en français.

## Paramètres

| Paramètre | Contenu | Exemple (Jam Jam) |
|---|---|---|
| `[NOM]` | nom du produit | Jam Jam |
| `[SITE]` | adresse du site | `https://jam-jam.org/` |
| `[API_BASE]` | adresse de base de l'API | `https://jam-jam.org/api/v1` |
| `[OPENAPI]` | adresse du contrat OpenAPI | `https://jam-jam.org/api/v1/openapi.json` |
| `[DOCS]` | page de documentation | `https://jam-jam.org/developers/` |
| `[FONCTION]` | ce que fait l'API en une phrase | "converts music files, links and text into chord sheets, PDF, MIDI or MusicXML" |
| `[PREFIXE_CLE]` | début d'une clé d'API (jamais une vraie clé) | `jj_live_` |
| `[VARIABLE_CLE]` | nom de la variable d'environnement | `JAM_JAM_API_KEY` |
| `[PAQUET_MCP]` | nom du paquet du serveur MCP, si publié | `@jam-jam/convert-mcp` |
| `[CGU]` | adresse des conditions d'utilisation | `https://jam-jam.org/terms/` |

## Vérifications avant publication

1. Aucune vraie clé nulle part (fichiers, historique Git, exemples de sortie). Un `.env.example` avec une
   clé fictive; `.env` dans `.gitignore`.
2. Aucune parole de chanson, aucun titre ou extrait protégé : les fichiers d'exemple sont du domaine public
   ou créés pour le dépôt.
3. Chaque identifiant de format ou de route est vérifié contre le contrat OpenAPI ET exécuté une fois.
4. Le paquet MCP cité est réellement publié sur le registre de paquets; les adresses des pages légales
   répondent 200.
5. Les quotas du tableau sont ceux de la page de tarifs du site (pas de chiffre recopié d'un ancien
   document).
6. Licence MIT (ou Apache-2.0) et phrase précisant que la licence couvre les exemples, pas le service.
7. Ensuite : ajouter le dépôt au `sameAs` de l'`Organization`, à la page développeurs du site et, si
   l'élément existe, à Wikidata (P1324).

## Structure du dépôt

```
[nom]-api-examples/
  README.md
  LICENSE
  .env.example
  samples/public-domain-sample.[ext]
  curl/
    01-list-formats.sh  02-convert-file.sh  03-follow-job-sse.sh
    04-poll-job.sh      05-download-result.sh  06-usage.sh
  javascript/           (Node 20+, fetch natif, aucune dépendance)
    package.json  list-formats.mjs  convert-file.mjs  convert-url.mjs  follow-events.mjs
  python/               (Python 3.10+, requests)
    requirements.txt  list_formats.py  convert_file.py  convert_url.py  usage.py
  mcp/
    claude_desktop_config.json
```

Description GitHub : `Examples for the [NOM] REST API: [FONCTION].` Topics à adapter (campagne :
`music`, `chords`, `chordpro`, `musicxml`, `midi`, `pdf`, `rest-api`, `openapi`, `songbook`). Champ site :
`[DOCS]`.

## README.md (squelette à coller)

````markdown
# [NOM] API examples

Runnable examples for the [[NOM]]([SITE]) REST API.

The API [FONCTION]. It is the same engine as the [NOM] app.

- Base URL: `[API_BASE]`
- OpenAPI contract: [`[OPENAPI]`]([OPENAPI])
- Documentation: [[DOCS]]([DOCS])

## Get an API key

1. Create a free [NOM] account at [[SITE]]([SITE]).
2. In the app, open **Settings, API keys** and create a key.
3. The key starts with `[PREFIXE_CLE]` and is shown once. Copy it into `.env`:

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
  -H "Authorization: Bearer $[VARIABLE_CLE]" \
  -F file=@samples/public-domain-sample.[ext] \
  -F inputFormat=[INPUT_FORMAT] \
  -F output=[OUTPUT_FORMAT]

# 3. Follow progress (Server-Sent Events)
curl -N -H "Authorization: Bearer $[VARIABLE_CLE]" \
  [API_BASE]/jobs/<job_id>/events

# 4. Download the result
curl -H "Authorization: Bearer $[VARIABLE_CLE]" \
  -OJ [API_BASE]/jobs/<job_id>/result
```

## JavaScript (Node 20+, no dependency)

```js
const API = '[API_BASE]';
const headers = { Authorization: `Bearer ${process.env.[VARIABLE_CLE]}` };

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
HEADERS = {"Authorization": f"Bearer {os.environ['[VARIABLE_CLE]']}"}

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
    "[nom]": {
      "command": "npx",
      "args": ["-y", "[PAQUET_MCP]"],
      "env": { "[VARIABLE_CLE]": "[PREFIXE_CLE]xxxxxxxxxxxxxxxx" }
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

The examples in this repository are released under the MIT License. The [NOM] API and service are
governed by the [[NOM] terms]([CGU]).
````

## Notes

- Les codes d'erreur du tableau sont des exemples usuels : remplacez-les par ceux du contrat OpenAPI
  réel, sans en inventer.
- Gardez le README court : la documentation complète reste sur le site (`[DOCS]`) et le dépôt la cite.
- Un dépôt qui n'est pas maintenu nuit à l'entité : prévoir une revue à chaque changement de contrat
  (format, quota, route) et une date de dernière vérification dans le README.
