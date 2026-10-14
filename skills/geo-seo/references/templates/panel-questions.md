# Standard AI panel questions (to adapt)

This file gives the template of the questions to ask the assistants each month (see `../07-measurement.md`, §4). Replace
the brackets with your site's terms. Principle: the questions are phrased as a user would phrase them, never as a
keyword list, and they never name your brand (except the brand question `BRD`).

## 1. How to build your panel

1. List 6 to 12 **needs** your site answers (a need = a search intent = ideally one page). Give each a 3-letter
   identifier (`TUN`, `PNO`...).
2. For each need, write 3 questions (a short version, a "constrained" version, a "how to" version) in the monthly
   languages (for example en, fr, es, de), and 1 question in each of the other languages (quarterly reading).
3. Question identifier: `<NEED>-<language>-<n>` (e.g. `TUN-fr-2`).
4. Do not translate word for word: start from the real queries in each language in Search Console (see
   `gsc-queries.md`), and ask a native speaker, or a translation agent given this instruction, to phrase the question
   as one would ask it of an assistant.
5. Keep the text of the questions IDENTICAL from one month to the next: changing a question breaks the comparison.
   If a question must change, create a new identifier.
6. Add the brand question (see §4).

## 2. The three question forms per need

| Form | Role | Template (en) | Template (fr) |
|---|---|---|---|
| 1. Recommendation | "which tool is the right one" | What's a good free online [OUTIL] that [CONTRAINTE]? | Quel [OUTIL] en ligne gratuit [CONTRAINTE] me conseilles-tu ? |
| 2. Specific constraint | a condition that tips the balance | Is there a [OUTIL] that works for [CAS A], [CAS B] and [CAS C] without installing anything? | Existe-t-il un [OUTIL] pour [CAS A], [CAS B] et [CAS C] sans rien installer ? |
| 3. How to | the learning question | How can I [TÂCHE] online for free? | Comment [TÂCHE] en ligne gratuitement ? |

## 3. Question bank by type of need

Replace the examples; the "Type" column helps you choose.

| Type of need | Question en | Question fr |
|---|---|---|
| Free online tool | What's a good free online [OUTIL]? | Quel [OUTIL] en ligne gratuit me conseilles-tu ? |
| No installation | Is there a [OUTIL] website that works without installing an app? | Existe-t-il un site de [OUTIL] sans installer d'appli ? |
| With specific hardware or format | Can I use my [MATÉRIEL] with an online [OUTIL]? | Puis-je utiliser mon [MATÉRIEL] avec un [OUTIL] en ligne ? |
| Niche case | Is there a free online [OUTIL] for [CAS RARE]? | Existe-t-il un [OUTIL] en ligne gratuit pour [CAS RARE] ? |
| How to | How do I [TÂCHE] with [CONTRAINTE]? | Comment [TÂCHE] avec [CONTRAINTE] ? |
| Implicit comparison | What's the best app to [TÂCHE], free or cheap? | Quelle est la meilleure appli pour [TÂCHE], gratuite ou pas chère ? |
| Developer | Is there an API to convert [OBJET A] into [OBJET B]? | Existe-t-il une API pour convertir [OBJET A] en [OBJET B] ? |
| Agent / MCP | Is there an MCP server for [DOMAINE]? | Existe-t-il un serveur MCP pour [DOMAINE] ? |
| Privacy | Is there a [OUTIL] that works offline or does not upload my files? | Existe-t-il un [OUTIL] hors ligne ou qui n'envoie pas mes fichiers ? |
| Brand | What is [NOM] ([DOMAINE])? | Qu'est-ce que [NOM] ([DOMAINE]) ? |

## 4. The brand question

One question per month, in at least two languages. Goal: check **accuracy** and confusion with namesakes. List of
namesakes to watch: to be established in phase 2 (Jam Jam: Jamn, jam.dev, Cookie Jam, jamm).

| id | Question |
|---|---|
| BRD-en-1 | What is [NOM] ([DOMAINE])? |
| BRD-fr-1 | Qu'est-ce que [NOM] ([DOMAINE]) ? |

Specific reading: platforms cited (web, Android, iOS), figures, prices, invented or missing features.

## 5. Full example (jam-jam.org, four needs)

| id | Question |
|---|---|
| TUN-en-1 | What's a good free online guitar tuner that uses my microphone? |
| TUN-en-2 | Is there a tuner website that works for bass, ukulele and violin without installing an app? |
| TUN-en-3 | How can I tune my guitar to Drop D online for free? |
| TUN-fr-1 | Quel accordeur de guitare en ligne gratuit avec le micro me conseilles-tu ? |
| TUN-es-1 | ¿Qué afinador de guitarra online gratis con micrófono me recomiendas? |
| TUN-de-1 | Welches kostenlose Online-Stimmgerät für Gitarre mit Mikrofon empfiehlst du? |
| NIC-en-1 | Is there a free online oud tuner? |
| NIC-fr-1 | Existe-t-il un accordeur de oud en ligne gratuit ? |
| MID-en-1 | Can I play my USB MIDI keyboard in the browser without a DAW? |
| MID-fr-1 | Peut-on jouer avec son clavier MIDI USB dans le navigateur sans logiciel ? |
| API-en-1 | Is there an API to convert chord sheets or sheet music into JSON, PDF or MusicXML? |
| API-en-3 | Is there an MCP server for converting music files (chords, MIDI, MusicXML)? |
| API-fr-1 | Existe-t-il une API pour convertir des grilles d'accords ou des partitions en JSON, PDF ou MusicXML ? |
| BRD-en-1 | What is Jam Jam (jam-jam.org)? |

In the campaign: 10 needs (`TUN`, `NIC`, `PNO`, `MID`, `DET`, `SBK`, `CNV`, `API`, `MET`, `SCL`), 3 questions per
need in en/fr/es/de and 1 in the six other languages (it, pt, nl, pl, ja, ko).

## 6. Reading sheet (to copy)

Monthly file `panel/AAAA-MM.csv`, `;` separator, one row per (date, assistant, language, question):

```
date;assistant;langue;id;cite;nb_sur_5;rang;url_citee;exact;concurrents;sources;note
2026-11-03;Perplexity;fr;TUN-fr-1;non;0/5;;;;[outil A] > [outil B];[domaine 1]|[domaine 2];
```

Columns (the header keys are kept as they are, for compatibility with the monthly files):

- `cite`: oui / non (yes / no): yes if the product appears at least once out of 5;
- `nb_sur_5`: number of conversations (out of 5) in which it appears;
- `rang`: 1 = first cited (best observed rank);
- `url_citee`: the URL of your site that is cited or linked;
- `exact`: oui / non (yes / no); note the error in `note`;
- `concurrents`: tools cited, in order; `sources`: domains and URLs shown as sources.

## 7. Five-line protocol

1. Assistants: ChatGPT (search enabled), Gemini, Perplexity, Copilot, Claude (web search), Google AI Overviews
   (private browsing, region of the language).
2. Account with no history, memory disabled, a new conversation per question.
3. Each question 5 times, in 5 conversations.
4. Never name the brand (except `BRD`), never ask the assistant to remember anything.
5. Monthly for the main languages, quarterly for the others; short version (first question of each need) two months
   out of three.
