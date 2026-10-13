# 01. Verdicts de recherche : ce qui est prouvé, probable, surestimé ou folklore

Chaque affirmation courante sur le GEO, avec un verdict, l'explication et la source. Point de départ : la
note de recherche de la campagne jam-jam.org (`handoff/GEO-2026-10/RECHERCHE.md`, 10 octobre 2026),
corrigée et complétée le 14 octobre 2026 en relisant les sources primaires. Plusieurs points de la note
d'origine ont changé ou étaient imprécis : ils sont listés au §9.

## Échelle des verdicts

| Verdict | Sens |
|---|---|
| **Prouvé** | Documentation officielle de l'éditeur concerné, ou étude contrôlée reproductible |
| **Probable** | Corrélations convergentes ou étude unique solide, sans démonstration causale |
| **Surestimé** | Vrai en partie, mais l'effet attendu sur la visibilité IA est très inférieur à sa réputation |
| **Folklore** | Contredit par la documentation ou les mesures, ou sans aucune base |
| **Non vérifié** | Rapporté, mais la source primaire n'a pas pu être consultée (voir §10) |

Règle d'usage : ne jamais présenter un « probable » comme un « prouvé » dans un livrable client. Dire
« corrélation mesurée » et citer l'étude.

## 1. Marché et comportement

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Être premier sur Google garantit d'être cité par les assistants | Folklore | Les assistants ont leurs index et leurs sources. Même pour les AI Overviews, 38 % seulement des URL citées sont aussi dans le top 10 de la même requête (mars 2026, après le passage à Gemini 3 et à la multiplication des sous-requêtes) | https://ahrefs.com/blog/ai-overview-citations-top-10/ |
| Les AI Overviews citent surtout le top 10 | Dépassé | C'était 76 % en juillet 2025 ; 38 % en mars 2026. Les sous-requêtes (« query fan-out ») ouvrent d'autres résultats | https://ahrefs.com/blog/search-rankings-ai-citations/ puis lien précédent |
| Les résumés IA réduisent les clics | Prouvé | Pew (900 adultes américains, mars 2025) : 8 % des visites cliquent un résultat classique avec résumé IA, 15 % sans ; 1 % cliquent un lien du résumé | https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/ |
| Les assistants citent souvent sans lien | Prouvé | Sur plus de 31 000 mentions d'une marque, un lien n'apparaît que dans 10,7 % des mentions AI Overviews, 16,8 % Gemini, 26,1 % Copilot et 51,6 % Perplexity | https://ahrefs.com/blog/ai-citations-vs-impressions-study |
| ChatGPT lance de la publicité | Prouvé (fait) | La documentation OpenAI décrit un robot dédié (OAI-AdsBot) qui valide les pages soumises comme publicités dans ChatGPT. Sans objet pour le référencement naturel | https://platform.openai.com/docs/bots |
| Les réponses des assistants sont stables | Folklore | Les réponses varient d'une exécution à l'autre ; répéter chaque question (voir `07-mesure.md`). Aucune étude contrôlée consultée : conclusion de méthode, non chiffrée | Méthode |

## 2. Contenu

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Statistiques, citations et sources augmentent la visibilité dans les réponses génératives | Probable | Étude Princeton GEO (KDD 2024) : « Cite Sources », « Quotation Addition » et « Statistics Addition » donnent +30 à 40 % relatifs sur la métrique de mots positionnés et +15 à 30 % sur l'impression subjective. Réserves : moteur génératif de recherche construit par les auteurs (banc GEO-bench) et un test sur Perplexity ; l'effet varie par domaine ; « Cite Sources » donne +115,1 % aux sources classées 5es mais -30,3 % aux sources classées 1res | https://arxiv.org/abs/2311.09735 |
| Le bourrage de mots-clés aide | Prouvé inefficace | Même étude : « Keyword Stuffing » ne fait pas mieux que la base de comparaison | https://arxiv.org/abs/2311.09735 |
| Une réponse directe de 40 à 60 mots en tête de page aide à être cité | Probable, non démontré | Aucun test contrôlé du format précis n'a été trouvé. Argument : les moteurs récupèrent des passages. Google dit ne pas exiger de découpage. Coût nul et bénéfice lecteur, donc appliqué (voir `04`) | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| Découper le contenu en petits morceaux pour les IA | Folklore (pour Google) | Google : aucune exigence de « chunking », ses systèmes comprennent plusieurs sujets sur une page. Des sections autonomes restent de la bonne rédaction | Même guide |
| Réécrire le contenu spécialement pour les IA | Folklore (pour Google) | Google : inutile, les systèmes comprennent les synonymes ; pas besoin de couvrir chaque variante longue traîne | Même guide |
| Il existe une longueur de page idéale | Folklore | « Il n'y a pas de longueur idéale » (Google) | Même guide |
| Le contenu unique, issu d'une expérience propre, est ce qui compte le plus à long terme | Prouvé (position officielle) | Google distingue contenu « non banal » (point de vue propre) du contenu qui reformule l'existant, et le place au-dessus des autres conseils | Même guide |
| Créer une page par variante de requête pour peser sur les réponses IA | Prouvé nuisible | Relève de la politique « scaled content abuse » ; une grande quantité de pages ne rend pas un site meilleur | Même guide |
| Le contenu récent et daté est favorisé | Probable | Google dit utiliser `lastmod` s'il est « constamment et vérifiablement exact ». Corollaire : une date fausse est un risque (voir `03` §2) | https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap |
| Les tableaux et listes sont plus citables | Probable, non démontré | Cohérent avec l'extraction de passages ; aucune étude contrôlée consultée | Méthode |
| Une FAQ améliore la visibilité IA | Surestimé | Les paires question/réponse autonomes sont faciles à extraire, mais Google ne montre plus le résultat enrichi (voir §3). Garder le bloc visible pour le lecteur, ne pas le survendre | Voir §3 |

## 3. Données structurées

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Le JSON-LD est « servi sur un plateau » aux IA | Surestimé | Google : « aucun schema.org particulier à ajouter » pour les AI Overviews et l'AI Mode, et « surinvestir dans les données structurées » figure dans les mythes. Un test public (février 2026) a montré que ChatGPT et Perplexity lisent un JSON-LD, même invalide, comme du texte de la page | https://developers.google.com/search/docs/appearance/ai-features ; https://www.seroundtable.com/chatgpt-perplexity-structured-data-text-40862.html |
| Le JSON-LD reste utile pour Google | Prouvé | Résultats enrichis éligibles, entité (nom, logo, `sameAs` documentés pour Organization) | https://developers.google.com/search/docs/appearance/structured-data/organization |
| Les résultats enrichis HowTo | Prouvé supprimés | Mobile retiré en août 2023, desktop le 13 septembre 2023 : type d'affichage déprécié | https://developers.google.com/search/blog/2023/08/howto-faq-changes |
| Les résultats enrichis FAQ | Prouvé supprimés | Restreints en août 2023 aux sites officiels d'administration et de santé ; l'affichage a cessé le 7 mai 2026 et la documentation a été retirée en juin 2026. Le balisage reste inoffensif, mais l'étendre n'a plus de justification côté Google | https://developers.google.com/search/updates (entrées du 8 mai et du 15 juin 2026) |
| Un graphe d'entité relié par `@id` (Organization, WebSite, WebPage) aide les assistants à identifier la marque | Probable | Lève l'ambiguïté pour les moteurs qui exploitent le balisage (Google, Bing) ; pour les LLM, ce n'est qu'un texte de plus. Coût faible, donc appliqué | Pratique ; voir `03` §6 |
| Bing utilise le balisage pour ses réponses génératives | Non vérifié | Déclaration d'un responsable Bing rapportée en 2025 ; la source primaire n'a pas pu être consultée | Non vérifié |

## 4. Fichiers et balises dédiés aux IA

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| llms.txt fait citer le site | Surestimé | Google : ses systèmes ne les utilisent pas et n'en tiennent compte ni en bien ni en mal (ajout du 15 juin 2026). Ahrefs (137 000 domaines, mai 2026) : 28 % publient un llms.txt, 97 % de ces fichiers n'ont reçu aucune requête, 96 % des requêtes viennent de robots, 19,5 % de robots IA nommés (GPTBot en tête, puis un agent de code) et aucun robot IA ne cherche un fichier non publié | https://ahrefs.com/de/blog/llmstxt-study/ ; https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| llms.txt peut-il nuire | Peu probable | Le même article signale un risque : des acteurs sondent ces fichiers pour de l'injection de consignes ; un fichier périmé induit en erreur. D'où : généré au build, contenu factuel, aucune consigne | Même étude |
| Il faut un robots.txt dédié aux IA | Prouvé utile pour le contrôle | Chaque éditeur documente ses jetons et leur indépendance (entraînement, index, visite à la demande). Un site sans blocage n'a rien à ajouter ; un site derrière un CDN doit vérifier ses règles par robot | https://platform.openai.com/docs/bots ; https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler ; https://docs.perplexity.ai/guides/bots |
| Bloquer GPTBot empêche d'apparaître dans ChatGPT | Folklore | « Chaque réglage est indépendant » : on peut autoriser OAI-SearchBot et interdire GPTBot. Seul OAI-SearchBot gouverne la recherche | https://platform.openai.com/docs/bots |
| Google-Extended retire des AI Overviews | Folklore | Jeton sans user-agent propre ; gouverne l'entraînement de Gemini et le grounding hors Search ; sans effet sur Search. Pour limiter l'affichage dans Search : `nosnippet`, `max-snippet`, `noindex` | https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers ; https://developers.google.com/search/docs/appearance/ai-features |
| Les robots à la demande respectent robots.txt | Folklore | OpenAI (ChatGPT-User) et Perplexity (Perplexity-User) indiquent que les règles peuvent ne pas s'appliquer ; Meta indique que son récupérateur à la demande peut contourner certaines règles (texte consulté tronqué). Pour contrôler : règles WAF | Documentations des éditeurs |
| Les robots IA exécutent JavaScript | Folklore (sauf Google et Apple) | Mesure de décembre 2024 : OpenAI, Anthropic, Meta, ByteDance, Perplexity et CCBot ne rendent pas JavaScript ; Gemini (via Googlebot) et Applebot le font. Un robot peut télécharger un fichier JS sans l'exécuter | https://vercel.com/blog/the-rise-of-the-ai-crawler |
| Le CDN peut bloquer les robots IA par défaut | Prouvé (fait) | Cloudflare a annoncé en juillet 2025 un blocage par défaut, levable ; il a aussi publié en août 2025 des observations de crawl non déclaré attribué à Perplexity | https://www.cloudflare.com/press/press-releases/2025/cloudflare-just-changed-how-ai-crawlers-scrape-the-internet-at-large/ ; https://blog.cloudflare.com/perplexity-is-using-stealth-undeclared-crawlers-to-evade-website-no-crawl-directives/ |

## 5. URL, sitemap, robots.txt

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Deux URL pour une page (avec et sans slash) divisent les signaux | Prouvé (principe), observé localement | Google recommande de réduire le contenu dupliqué et de fixer un canonical. Mesure locale : `/accordeur-basse` (sans slash) position 62,7, `/accordeur-basse/` position 40,7, et page de l'outil en « Redirect error » dans Search Console pour l'URL sans slash | Doc Google (duplicate content) ; audit de la campagne |
| `lastmod` est utilisé par Google | Prouvé, sous condition | Utilisé si exact de façon constante et vérifiable ; une mise à jour du pied de page ne compte pas. `priority` et `changefreq` sont ignorés | https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap |
| Limites d'un sitemap | Prouvé | 50 000 URL ou 50 Mo non compressés par fichier ; index de sitemaps autorisé | Même page |
| Un `Disallow` couvrant un sous-dossier bloque aussi le sitemap placé dedans | Prouvé | Google applique la règle la plus spécifique ; en cas de conflit la moins restrictive. Dans la campagne, `Disallow: /app/` bloquait `/app/sitemap-convert.xml` : erreur Search Console depuis le 17/09, règle `Allow` ajoutée le 10/10 | https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt |
| Les groupes `User-agent` se cumulent | Folklore | Un seul groupe est valable pour un robot (le plus spécifique) ; groupes spécifiques et groupe `*` ne sont pas fusionnés. Toute exception `Allow` doit donc être répétée dans chaque groupe | Même page |
| `urllib.robotparser` (Python) applique la même logique que Google | Folklore | Il applique la première règle correspondante dans l'ordre du fichier, sans `*` ni `$` dans les chemins. Ne pas s'en servir pour auditer ; utiliser « règle la plus longue, Allow à égalité » (RFC 9309) | Test local sur Python 3.9 : `Disallow: /app/` suivi de `Allow: /app/convert` refuse `/app/convert/x` (Google l'autorise, règle la plus longue) ; `Disallow: /*.pdf$` n'est pas appliqué. À revérifier sur d'autres versions |
| L'API Indexing accélère l'indexation de n'importe quelle page | Folklore | Réservée aux pages `JobPosting` et `BroadcastEvent` (dans `VideoObject`) ; toute soumission passe un contrôle anti-spam ; un sitemap reste recommandé. La campagne a abandonné cet usage (412 URL d'outils soumises avant) | https://developers.google.com/search/apis/indexing-api/v3/quickstart |
| Soumettre les sitemaps par l'API Search Console | Prouvé | `PUT https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, scope `webmasters` (écriture) | https://developers.google.com/webmaster-tools/v1/sitemaps/submit |
| IndexNow prévient aussi Google | Folklore | Moteurs participants listés par le protocole : Bing, Naver, Seznam, Yandex, Yep, Amazon. Google n'y figure pas. Clé de 8 à 128 caractères, jusqu'à 10 000 URL par envoi | https://www.indexnow.org/documentation ; https://www.indexnow.org/faq |
| IndexNow accélère la découverte par Bing | Probable | C'est son objet ; aucun gain chiffré indépendant consulté | Protocole |

## 6. Hreflang et langues

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Les variantes de langue doivent se référencer mutuellement | Prouvé | Chaque version liste toutes les autres, elle-même incluse, avec `x-default`. Une page anglaise à la racine sans `/en/` est valide | Documentation Google sur les versions localisées (non rouverte le 14/10 : connaissance antérieure) |
| Des codes différents entre sitemap et pages perdent le signal | Prouvé (constat local) | Les 380 pages de conversion utilisaient `pt-BR` quand le reste du site utilisait `pt` | Audit de la campagne |
| Traduire en dix langues multiplie le trafic | Probable, à nuancer | Sur 90 jours, la racine anglaise donne 311 clics sur 8 725 impressions, le français 171 sur 5 397, le coréen 6 sur 188 : les petites langues pèsent peu, mais sont peu concurrencées | Search Console du site (voir `05-multilingue.md`) |

## 7. Entité et présence hors site

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Les mentions de marque comptent plus que les liens | Probable (corrélation) | 75 000 marques : mentions web 0,664, liens entrants 0,218, ancres de marque 0,527, volume de recherche de la marque 0,392. Corrélation avec la visibilité dans les AI Overviews, pas causalité | https://ahrefs.com/blog/ai-overview-brand-correlation/ |
| YouTube est le signal le plus corrélé | Probable | Mentions YouTube environ 0,737 (ChatGPT, AI Mode, AI Overviews) devant les mentions web 0,66 à 0,71 ; YouTube représente 18,2 % des URL citées qui ne sont pas dans les 100 premiers résultats de la requête | https://ahrefs.com/blog/ai-brand-visibility-correlations/ ; https://ahrefs.com/blog/ai-overview-citations-top-10/ |
| Wikipedia et Reddit dominent les citations de ChatGPT | Probable, instable | Semrush a observé une chute brutale de ces citations en septembre 2025 ; cause débattue (changement de paramètre de Google ou souci d'équilibre des sources) | https://www.semrush.com/blog/most-cited-domains-ai/ |
| Fabriquer des mentions (faux comptes, faux avis) | Prouvé nuisible | Google déconseille les mentions inauthentiques et durcit sa règle sur les avis incités non déclarés (juillet 2026) ; Reddit et Wikipedia sanctionnent l'autopromotion | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide ; https://developers.google.com/search/updates |
| Wikidata et le graphe de connaissances aident à être reconnu comme entité | Non vérifié | Raisonnable, aucune source primaire consultée. Condition de la campagne : ne créer une entrée qu'après une source indépendante | Non vérifié |
| Se positionner sur une niche cohérente | Probable | Moins de concurrence et entité nette ; dans la campagne, les pages d'instruments rares (guitalélé position 8, mandoline, violon, violoncelle positions 9 à 13) sont celles qui se classent. Observation locale | Search Console du site |

## 8. Mesure

| Affirmation | Verdict | Explication | Source |
|---|---|---|---|
| Search Console mesure les fonctions IA de Google | Prouvé | Rapport de performance « IA générative » dans Search Console ; les AI Overviews sont comptés dans le rapport de performance ordinaire | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide |
| Un site doit être inclus dans les fonctions IA de Search Console pour y être éligible | Prouvé | Condition citée par le guide de Google, en plus d'être indexé et éligible avec extrait | Même guide |
| Les outils tiers de « score GEO » reflètent le classement interne de Google | Folklore | Google : aucun outil tiers n'a accès à ses systèmes internes de classement ou d'IA | Même guide |
| Un panel de questions mensuel donne un signal exploitable | Probable | À condition de répéter chaque question (au moins trois fois, cinq recommandé), de fixer les conditions et de ne jamais nommer la marque dans la question. Signal directionnel, pas mesure précise | `07-mesure.md` |

## 9. Corrections apportées à la note d'origine

1. **AI Overviews et top 10** : « citent surtout le top 10 » devient « 76 % en juillet 2025, 38 % en mars 2026 ».
2. **Clics après une réponse IA** : le chiffre de 8 % concerne les clics sur un résultat classique en présence
   d'un résumé (15 % sans). Le clic sur un lien du résumé est de 1 %.
3. **FAQ** : la note disait « résultats enrichis réservés aux sites gouvernementaux et de santé depuis 2023 ».
   Depuis le 7 mai 2026, ils ne s'affichent plus du tout. La campagne a conservé le balisage FAQPage et le
   bloc visible ; elle ne l'a pas étendu (décision du plan v2 : « conservés, non étendus »).
4. **JavaScript** : « aucun robot IA n'exécute JavaScript » est trop fort. Googlebot (donc Gemini et les
   AI Overviews) et Applebot l'exécutent. Le raisonnement reste valable pour OpenAI, Anthropic, Meta,
   ByteDance, Perplexity et CCBot.
5. **URL de l'étude Ahrefs sur les mentions** : l'adresse citée dans la note d'origine renvoie à l'étude sur
   les liens dans les mentions. L'étude des 75 000 marques est
   https://ahrefs.com/blog/ai-overview-brand-correlation/ .
6. **Guide de Google (15 mai 2026)** : la note d'origine ne le connaissait pas. Il contredit trois pratiques
   très répandues (llms.txt, découpage en morceaux, recherche de mentions) et confirme que le SEO
   fondamental reste la base. La campagne a gardé un bloc de réponse en tête et des sections autonomes,
   parce que cela sert aussi les autres assistants et les lecteurs, sans en attendre d'effet chez Google.
7. **Robots** : la note listait 13 jetons. Les documentations actuelles ajoutent MistralAI-Index,
   Amzn-SearchBot, Amzn-User, Meta-ExternalFetcher et OAI-AdsBot (voir `00-vue-ensemble.md` §4).

## 10. Ce qui n'a pas pu être vérifié

- La page d'aide OpenAI sur ChatGPT search exige JavaScript ; l'affirmation « ChatGPT s'appuie en partie sur
  Bing » repose sur des analyses tierces et sur la formule « fournisseurs tiers de recherche ».
- Le fournisseur de recherche externe de Claude (souvent attribué à Brave Search) n'est pas documenté par
  Anthropic.
- La déclaration d'un responsable de Bing sur l'usage du balisage par ses modèles génératifs.
- Les pages hreflang de Google n'ont pas été rouvertes le 14 octobre 2026 ; le principe de réciprocité est
  stable depuis des années.
- Wikidata et le graphe de connaissances comme levier d'entité : aucune source primaire consultée.
- Le texte exact de Meta sur le contournement de robots.txt par Meta-ExternalFetcher (page consultée
  tronquée) et la réponse de Perplexity aux observations de Cloudflare.
- Toute robustesse des corrélations d'Ahrefs hors de leur propre jeu de données (jeux propriétaires non
  accessibles).
- Aucun résultat mesuré de la campagne elle-même à la date de rédaction (déploiement du 10 octobre 2026).
