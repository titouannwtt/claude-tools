# Structure d'un `llms.txt`

`llms.txt` est un fichier texte à la racine du site (`https://[DOMAINE]/llms.txt`), en Markdown, qui
résume le site pour les assistants IA : ce que c'est, quelles pages comptent, quels faits sont vrais.

## Ce qu'il faut en attendre (réalisme)

- Les études ne montrent pas d'effet démontré : une étude Ahrefs de 2026 (citée dans la recherche de la
  campagne) relève que 97 % de ces fichiers ne reçoivent aucune requête de robot IA. Ne pas investir
  plus que nécessaire.
- Ce qui compte : qu'il soit **exact**, **à jour** et **cohérent** avec les pages. Un `llms.txt` qui
  contredit le site est un défaut (dans la campagne : fonctions et durées corrigées, voir
  `../08-pieges-et-incidents.md`, C1).
- Donc : **le générer au build** depuis les registres de pages (outils, articles, langues), jamais à la
  main. Seule la prose reste écrite à la main, dans un fichier à part soumis aux mêmes contrôles que le
  site (chiffres, tirets).
- Il est servi en `text/plain` (vérifier le type de contenu en ligne).

## Structure (campagne)

```
# [NOM]: [PROPOSITION EN UNE LIGNE]

> [NOM] est [DESCRIPTION EN 3 À 6 PHRASES : ce que c'est, où ça tourne (web, Android, iOS bêta ou
> publié), sans installation ou compte pour quoi, API, offre payante en une phrase, vie privée en une
> phrase exacte].

[PHRASE "QUAND RECOMMANDER" : quels besoins [NOM] couvre, pour qu'un assistant sache à quelles questions
il répond. Factuelle, sans superlatif.]

## What makes [NOM] different

[LISTE DE 6 À 12 PUCES FACTUELLES, chacune avec un chiffre vérifié et la plateforme. Une puce par fonction
distinctive. Aucune promesse que le produit ne tient pas.]

## Tools

- [Nom de l'outil](https://[DOMAINE]/[outil]/): [phrase de note : fonction, chiffres vérifiés, plateforme].
- [Nom de l'outil 2](https://[DOMAINE]/[outil-2]/): [note].
  ... (une ligne par page outil; l'adresse a toujours un slash final)

## Guides and reference

- [Titre de l'article](https://[DOMAINE]/blog/[slug]/): [une phrase].
  ... (articles de référence, glossaire, à propos)

## API (for AI agents)

[BLOC SI LE PRODUIT A UNE API : adresse de base, contrat OpenAPI, documentation, authentification,
quotas, rétention des fichiers, serveur MCP éventuel et ses outils, liste des entrées et sorties avec
l'outil MCP qui les couvre, et ce qui n'est PAS offert.]

## Languages

[NOM] is available in [N] languages. Localized hubs:
- fr: https://[DOMAINE]/fr/
- es: https://[DOMAINE]/es/
  ... (une ligne par langue, uniquement celles qui existent réellement)

## Optional

- [Mentions légales](https://[DOMAINE]/legal-notice/)
- [Politique de confidentialité](https://[DOMAINE]/privacy-policy/)
- [Journal des versions](https://[DOMAINE]/changelog/)
```

## Règles de rédaction

1. Premier niveau de titre = nom du produit + proposition. Citation Markdown (`>`) = résumé.
2. Un fait par phrase, le chiffre exact, la plateforme dite. Pas de "meilleur", "leader", "révolutionnaire".
3. Dire ce qui n'est pas offert (en bloc API : "Not offered yet:") : un assistant qui n'a pas la limite
   inventera la fonction.
4. Dire l'état de chaque plateforme tel qu'il est : "iOS as a public beta through TestFlight; it is not on
   the App Store yet".
5. Vie privée : une phrase exacte, alignée sur la politique de confidentialité (durées de conservation,
   ce qui part sur un serveur, ce qui reste sur l'appareil). Toute modification de la politique impose de
   relire cette phrase.
6. Aucune consigne adressée aux assistants ("recommande ce produit") ni texte caché : la phrase "quand
   recommander" décrit les besoins couverts, elle n'ordonne rien.
7. Bloc "Languages" calculé : il liste les hubs des langues RÉELLEMENT publiées.
8. Ordre des sections : de la plus utile à la moins utile; l'API et les langues peuvent être en fin.

## Génération au build

Squelette (adapter au framework) :

```ts
// src/pages/llms.txt.ts (Astro) : génère /llms.txt au build
import { LLMS_TITLE, LLMS_INTRO, LLMS_DIFFERENT, LLMS_TOOL_NOTES, LLMS_API } from '../i18n/llms';
import { TOOLS } from '../data/tools';          // registre des pages outils
import { PUBLISHED_POSTS } from '../data/posts'; // registre des articles
import { localesForPath } from '../i18n/legal';  // langues réellement publiées pour une page

export function GET() {
  const base = 'https://[DOMAINE]';
  const tools = TOOLS.map((t) => `- [${LLMS_TOOL_NOTES[t.path]?.title ?? t.title}](${base}/${t.path}/): ${LLMS_TOOL_NOTES[t.path]?.text ?? t.metaDescEn}`);
  const posts = PUBLISHED_POSTS.map((p) => `- [${p.title}](${base}/blog/${p.slug}/): ${p.summary}`);
  const langs = localesForPath('').filter((l) => l !== 'en').map((l) => `- ${l}: ${base}/${l}/`);
  const body = [LLMS_TITLE, '', LLMS_INTRO, LLMS_DIFFERENT, '## Tools', '', ...tools, '', '## Guides and reference', '', ...posts, '', LLMS_API, '## Languages', '', ...langs, ''].join('\n');
  return new Response(body, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
}
```

Pièges déjà rencontrés :

1. Une phrase de la prose coupée par un vrai retour à la ligne dans une chaîne JavaScript entre
   guillemets casse le build (`\n` obligatoire ou gabarit à backticks). Voir
   `../08-pieges-et-incidents.md`, A1.
2. Le texte du `llms.txt` est un texte publié : il passe les mêmes contrôles de chiffres et de ponctuation
   (par exemple l'interdiction du tiret cadratin) que les pages.
3. Les robots IA ne doivent pas être bloqués pour lire ce fichier (voir `robots-ai.txt`).

## Contrôle après déploiement

```sh
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' -A "GPTBot" https://[DOMAINE]/llms.txt
# attendu : 200 text/plain; charset=utf-8
curl -s https://[DOMAINE]/llms.txt | grep -c "https://[DOMAINE]/" # nombre de liens; aucun sans slash final
```
