# Keywords

Run `keywords <repo> --save` before writing the README. It proposes a short, sourced list for the GitHub topics, the
description and the README. The list is a starting point: the agent checks it with WebSearch and the user validates it.

## Sources and limits

| Source | Gives | Limit |
|---|---|---|
| Repository itself | description, topics, README headings and intro, `package.json` / `pyproject.toml` / `Cargo.toml` keywords, languages, `--seed` | seeds only |
| Similar repositories (GitHub search with the strongest seed pairs, by stars) | topics people use on comparable projects, weighted by log(1 + stars) and by overlap; a repository sharing fewer than 2 seed terms is dropped and listed in `similar_repos_dropped` | search API: 30 requests a minute, paced, `--max-search` (default 25) |
| GitHub topic search and `topic:<t>` count | topic names, `repo_count` (repositories using it) | `repo_count` is a density, not a popularity; only the best candidates are counted |
| npm (JS/TS) or crates.io (Rust) | package keywords and categories | PyPI search is disabled, so Python gets neither; crates.io needs a User-Agent and 1 request a second |
| Stack Exchange tags | vocabulary of questions | 300 requests a day without a key; stops under 10 left |
| DuckDuckGo suggestions | phrases for description and README | unofficial; a failure never blocks. Google autocomplete is not used: its terms forbid automated access |

GitHub repository search matches the name, description and topics by default, the README only with `in:readme`.
There is no published ranking formula: do not promise a position.

## Seeds and brands

Existing topics, `--seed` terms and multi-word domain phrases are the strongest seeds; similar-repository queries
are the strongest seed pairs plus a `topic:a topic:b` query from the two best existing topics. Brand names are weak:
the repository name, the owner, the owner's other repositories, "by X" in the description, and headings naming a
product of the owner. They never seed a query and are never proposed (`brand: true`; they can stay "covered").
Generic single words (bot, fork, tool, app, data, code, countries, languages) never start a search. The owner's own
repositories and starless forks are not "similar"; the upstream (fork parent or `upstream` remote) is similar but not
an independent source. `missing` needs `independent_sources` of at least 2.

## Scoring (0 to 100)

Sources count (30), similar-repository weight (30), seed relevance (25), log of `repo_count` (15, left out and rescaled
when not fetched). A topic almost nobody uses scores lower: people do not browse it. Details in the module docstring of
`scripts/keywords.py`. Each keyword lists its `sources` with evidence, so every term can be justified.

## Placement

- **Topics**: 10 to 15 slugs, best first, 20 at most counting the existing ones. A slug is lowercase letters, digits and
  hyphens, up to 50 characters. Cover the language, the framework, the domain and the use case. Keep the existing relevant ones.
- **Description**: one sentence that says what it is and for whom, the key phrase in the first 60 characters or so, no
  repeated word, under about 350 characters (the exact limit is not verified; the usual advice is far shorter).
- **README**: the H1 tagline and the first paragraph carry the two or three main terms; the other terms appear in
  natural headings. `missing` lists high-score terms absent from the description, the topics and the README.
- **For AI assistants** (GEO research, https://arxiv.org/abs/2311.09735 ): a clear first sentence, concrete sourced figures,
  honest comparisons. Keyword stuffing does not help: keep the list short. Never a keyword block, never hidden text.

## Privacy

Only generic seed terms are sent to GitHub search, npm, crates.io, Stack Exchange and DuckDuckGo. The repository
name, the owner, file names (private or internal repositories), git config and e-mails never leave the machine; terms
containing them are dropped. The output says `"privacy": "generic terms only"` and lists every `queries` sent.
`--no-remote` makes no network call at all.

## References

- Searching for repositories: https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories
- Topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
- Generative engine optimization: https://arxiv.org/abs/2311.09735
