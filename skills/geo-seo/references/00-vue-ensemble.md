# 00. Vue d'ensemble : être recommandé par Google, Bing et les assistants IA

Ce fichier pose le cadre : ce qu'est le GEO, par quels chemins un assistant finit par nommer un site, ce
qui compte vraiment (dans quel ordre), qui sont les robots, et quels mythes écarter. Les verdicts
détaillés avec sources sont dans `01-verdicts-recherche.md`. L'exemple travaillé est la campagne menée
en octobre 2026 sur jam-jam.org (site Astro statique, 10 langues, environ 730 pages indexables).

Dernière vérification des sources citées : 14 octobre 2026. Ce qui n'a pas pu être vérifié est dit comme tel.

## 1. Ce que veut dire GEO

- **SEO** : être classé dans les moteurs (Google, Bing).
- **GEO** (Generative Engine Optimization) et **AEO** (Answer Engine Optimization) : être cité ou recommandé
  dans une réponse générée par une IA (ChatGPT, Claude, Perplexity, Gemini, Copilot, AI Overviews, DeepSeek).

Position officielle de Google, publiée le 15 mai 2026 dans son guide d'optimisation pour les fonctions
d'IA générative : « du point de vue de Google Search, optimiser pour la recherche générative, c'est
optimiser pour l'expérience de recherche, donc c'est toujours du SEO ». Les AI Overviews et l'AI Mode
s'appuient sur le classement et l'index ordinaires (récupération de pages, plus une expansion de la
requête en sous-requêtes, dite « query fan-out »). Cette position vaut pour Google ; pour les autres
assistants, la preuve est plus mince (voir `01`), mais la conclusion pratique est la même : un site rapide à
explorer, clair, factuel, cité ailleurs, a la meilleure chance partout.

Conséquence de méthode : le GEO sérieux est un SEO solide, plus trois choses propres aux assistants
(accès des robots IA, passages autonomes et citables, présence hors site). Il n'existe pas de balise
magique.

## 2. Les trois voies par lesquelles un assistant recommande un site

| Voie | Mécanisme | Délai | Ce qui l'alimente | Ce qu'on contrôle |
|---|---|---|---|---|
| 1. Mémoire du modèle | Le modèle a « lu » le site (ou ce qui se dit de lui) pendant l'entraînement | Mois, parfois un an | GPTBot, ClaudeBot, CCBot, Google-Extended, Applebot-Extended, Meta-ExternalAgent, corpus ouverts, et tout ce qui est écrit sur la marque ailleurs | Peu : autoriser les robots d'entraînement, être mentionné ailleurs |
| 2. Recherche en direct | L'assistant lance une recherche, récupère des passages de pages, les cite | Jours à semaines (indexation) | Index Google (AI Overviews, AI Mode, Gemini), Bing (Copilot, et selon les rapports ChatGPT), index propres (OAI-SearchBot, PerplexityBot, Claude-SearchBot) et visites à la demande (ChatGPT-User, Claude-User, Perplexity-User) | Beaucoup : indexation, accès, contenu citable |
| 3. Entité | L'assistant sait que « X » est tel logiciel/organisation/personne, avec tel nom, telle URL, telles plateformes | Semaines à mois | Graphe de connaissances Google, Wikidata, profils cohérents (`sameAs`), page À propos, mentions | Moyennement : identité claire, profils réels, JSON-LD relié |

Points qui structurent tout le reste :

1. **Les assistants récupèrent des passages, pas des pages.** Chaque section doit se comprendre seule
   (sujet nommé dans le titre de section, réponse dans les premières lignes, chiffres avec leur unité).
   Google dit que découper volontairement le texte n'est pas nécessaire pour lui ; c'est simplement de la
   bonne rédaction, utile aux autres moteurs et sans coût.
2. **Le HTML servi est ce qui compte.** Mesure publiée en décembre 2024 (Vercel et un cabinet d'analyse de
   rendu) : les robots d'OpenAI, Anthropic, Meta, ByteDance et Perplexity, ainsi que CCBot, n'exécutent pas
   JavaScript ; Googlebot (donc Gemini et les AI Overviews) et Applebot le font. Un site qui construit son
   texte côté client est invisible pour une partie des assistants. Sur jam-jam.org, la SPA `/app/*` est
   volontairement hors référencement et chaque outil a un « double » statique indexable.
3. **Les mentions externes comptent plus que les balises** (voir §5 et `06-hors-site.md`).
4. **Les réponses varient d'une exécution à l'autre.** Toute mesure se répète (voir `07-mesure.md`).

## 3. Ce qui compte vraiment, dans quel ordre (impact par coût)

Ordre retenu dans la campagne jam-jam.org, justifié dans `01` :

| Rang | Levier | Pourquoi | Coût | Preuve |
|---|---|---|---|---|
| 1 | Une URL par page (slash final, liens internes sans redirection) | Les signaux ne se partagent plus entre deux adresses ; économie de crawl | Faible (un helper + un contrôle bloquant) | Documentation Google (contenu dupliqué) ; mesure locale : `/accordeur-basse` position 62,7 contre `/accordeur-basse/` position 40,7 |
| 2 | Sitemap fiable : `lastmod` réel, tout déclaré, soumis | Seule voie officielle pour signaler les changements à Google ; IndexNow pour Bing | Faible | Documentation Google (`lastmod` utilisé s'il est vérifiablement exact ; `priority` et `changefreq` ignorés) |
| 3 | Accès : robots.txt sans blocage involontaire, pas de WAF qui refuse les robots IA | Un robot bloqué ne cite jamais | Faible | Documentations OpenAI, Anthropic, Perplexity |
| 4 | Titres et descriptions réécrits sur les requêtes déjà en positions 5 à 20 | Gain de clic immédiat (Google et AI Overviews) | Faible à moyen | Données Search Console du site |
| 5 | Bloc de réponse en tête, faits chiffrés vérifiés, sections autonomes | Passages citables ; faits et sources augmentent la visibilité | Moyen | Étude Princeton GEO (KDD 2024), probable |
| 6 | Entité : JSON-LD relié par `@id`, `sameAs` réels, éditeur et auteur réels, page À propos | Lever l'ambiguïté (homonymes), alimenter le graphe de connaissances | Moyen | Documentation Google (Organization), pratique |
| 7 | Pages pour les besoins sans page, articles de référence citables | Une requête sans page n'a aucune chance | Élevé | Données Search Console du site |
| 8 | Présence hors site (annuaires, YouTube, GitHub, presse, avis réels) | Corrélation la plus forte avec la visibilité IA ; c'est le plafond du site seul | Élevé, manuel | Études Ahrefs (corrélations, pas causalité) |
| 9 | Mesure : Search Console, canal « assistants IA », panel de questions | Sans mesure, on ne sait pas si ça a servi | Moyen | Méthode |
| 10 | llms.txt | Valeur quasi nulle pour la visibilité, mais gratuit s'il est généré au build | Faible | Ahrefs (137 000 domaines), Google |

Règle de décision : tant que les rangs 1 à 3 ne sont pas verts, ne rien écrire de nouveau. Un contenu
excellent derrière un sitemap muet, des doublons d'URL ou un robot bloqué ne rapporte pas.

## 4. Les robots et les moteurs

### 4.1 Trois rôles à ne pas confondre

Chaque grand acteur sépare désormais ses robots en trois rôles, contrôlables indépendamment dans
robots.txt :

- **Entraînement** : collecter du contenu pour de futurs modèles (GPTBot, ClaudeBot, Google-Extended,
  Applebot-Extended...).
- **Index de recherche** : construire l'index qui alimente les réponses avec citations (OAI-SearchBot,
  Claude-SearchBot, PerplexityBot, Bingbot, Googlebot).
- **Visite à la demande** : aller lire une page parce qu'un utilisateur l'a demandé (ChatGPT-User,
  Claude-User, Perplexity-User, MistralAI-User). Plusieurs de ces robots disent que robots.txt peut ne pas
  s'appliquer, puisque l'action vient d'un humain.

Pour être cité, il faut autoriser les deux derniers rôles. Bloquer seulement l'entraînement est un choix
légitime, sans effet sur la recherche chez OpenAI (« chaque réglage est indépendant des autres », doc
OpenAI). Dans la campagne, tous sont autorisés : l'objectif est la recommandation.

### 4.2 Tableau des robots

Légende : « Doc » = affirmé par la documentation officielle consultée le 14 octobre 2026. « Rapporté » =
vu dans la presse spécialisée ou des études tierces, non confirmé par l'éditeur. « Inconnu » = rien de
vérifié.

| Robot | Éditeur | Rôle | Ce que l'on sait | Ce qui est incertain |
|---|---|---|---|---|
| GPTBot | OpenAI | Entraînement | Doc : l'interdire exclut le contenu de l'entraînement ; IP publiées ; sans lien avec la recherche | Effet réel sur les réponses futures non mesurable |
| OAI-SearchBot | OpenAI | Index de ChatGPT search | Doc : un site qui l'interdit n'apparaît pas dans les réponses de recherche (liens de navigation possibles) ; prise en compte de robots.txt en environ 24 h ; autoriser aussi ses IP | Part de Bing contre index propre : non détaillée par OpenAI |
| ChatGPT-User | OpenAI | Visite à la demande (questions, GPT personnalisés) | Doc : robots.txt peut ne pas s'appliquer ; ne décide pas de l'apparition en recherche | Fréquence réelle |
| OAI-AdsBot | OpenAI | Contrôle des pages de publicités ChatGPT | Doc : sans lien avec le référencement naturel | Sans objet ici |
| ClaudeBot | Anthropic | Entraînement | Doc : restreindre exclut les contenus futurs de l'entraînement ; accepte `Crawl-delay` | Effet réel non mesurable |
| Claude-SearchBot | Anthropic | Index pour la recherche | Doc : le désactiver empêche l'indexation pour la recherche | Fournisseur de recherche externe éventuel non documenté |
| Claude-User | Anthropic | Visite à la demande | Doc : le désactiver peut réduire la visibilité en recherche dirigée par l'utilisateur | Fréquence réelle |
| Claude-Web | Anthropic | Ancien jeton | Absent de la page d'aide consultée ; le garder dans robots.txt ne coûte rien | Statut actuel : non vérifié |
| PerplexityBot | Perplexity | Index de recherche | Doc : sert à afficher et lier des sites dans les résultats ; pas utilisé pour entraîner des modèles de fondation ; IP publiées | Sources de recherche complémentaires non documentées |
| Perplexity-User | Perplexity | Visite à la demande | Doc : ignore généralement robots.txt car l'utilisateur a demandé la visite ; Cloudflare a publié en août 2025 des observations de crawl non déclaré | Position de Perplexity sur ces observations : non revérifiée |
| Googlebot | Google | Search, AI Overviews, AI Mode | Doc : robots.txt pour Googlebot est le contrôle ; extraits limitables par `nosnippet`, `data-nosnippet`, `max-snippet`, `noindex` ; aucune exigence particulière pour les fonctions IA | Rien |
| Google-Extended | Google | Jeton robots.txt seul (pas de user-agent propre) | Doc : gouverne l'entraînement de Gemini et le « grounding » dans Gemini Apps et Vertex ; sans effet sur l'inclusion dans Google Search ni sur le classement | Ne bloque pas les AI Overviews (erreur fréquente) |
| Bingbot | Microsoft | Index Bing | Doc Microsoft : Copilot Search est intégré à Bing (juillet 2025) | Alimentation de ChatGPT par Bing : rapportée |
| Applebot | Apple | Siri, Spotlight, Safari | Doc : ses données peuvent servir aux réponses de culture générale de Siri et de la recherche ; mesure Vercel : rend JavaScript | Étendue exacte des usages |
| Applebot-Extended | Apple | Jeton robots.txt (entraînement) | Doc : l'interdire exclut l'entraînement des modèles de fondation d'Apple ; n'empêche pas Applebot d'explorer | Rien |
| Amazonbot | Amazon | Amélioration des produits, peut entraîner des modèles Amazon | Doc : la page cite aussi Amzn-SearchBot et Amzn-User, réglables séparément | Rôle exact de chacun dans Alexa |
| Meta-ExternalAgent | Meta | Entraînement et indexation directe | Doc : crawl pour l'entraînement ou l'amélioration de produits ; Meta-ExternalFetcher fonctionne à la demande et peut contourner certaines règles (texte consulté tronqué) | Étendue exacte du contournement : à relire |
| MistralAI-User | Mistral | Visite à la demande | Doc : pas de crawl automatique, pas d'entraînement ; MistralAI-Index indexe pour la recherche Mistral, sans entraînement | La documentation nomme le produit « Vibe » |
| DuckAssistBot | DuckDuckGo | Réponses assistées en temps réel | Doc : sources citées, pas d'entraînement, prise en compte en 72 h | Rien |
| CCBot | Common Crawl | Corpus ouvert, source fréquente d'entraînement | Mesure Vercel : ne rend pas JavaScript | Liste des modèles qui s'en servent : non vérifiée |
| Bytespider | ByteDance | Collecte (entraînement) | Rapporté : gros volume, respect de robots.txt discuté | Aucune documentation officielle consultée ; non listé dans la campagne (aucune valeur attendue) |
| DeepSeek | DeepSeek | Inconnu | Aucun robot officiel documenté trouvé | Inconnu : ne rien promettre sur DeepSeek |

Remarques pratiques :

- Un robot non nommé dans robots.txt applique le groupe `*`. Nommer chaque robot sert surtout à rendre
  l'intention explicite et à résister à un CDN qui injecterait ses propres groupes.
- Test d'accès : les robots IA se vérifient par user-agent **et** par adresse IP (les éditeurs publient
  leurs plages). Un `curl` avec un faux user-agent ne prouve que la règle par user-agent (voir `02`).
- Cloudflare a annoncé en juillet 2025 un blocage des robots IA par défaut, que le propriétaire peut
  lever (communiqué de l'entreprise). Si le site est derrière un CDN ou un WAF, vérifier ses réglages de
  robots IA et ses règles par user-agent, pas seulement robots.txt.

### 4.3 Quel moteur nourrit quel assistant

| Assistant | Ce qui le nourrit | Statut |
|---|---|---|
| Google AI Overviews, AI Mode | Index Google, récupération de pages (RAG) et query fan-out | Doc Google |
| Gemini (application) | Index Google pour le « grounding » ; Google-Extended gouverne grounding et entraînement | Doc Google |
| Microsoft Copilot | Bing (Copilot Search dans Bing) | Doc Microsoft |
| ChatGPT (recherche) | OAI-SearchBot (index propre) plus des fournisseurs tiers de recherche ; Bing largement cité comme fournisseur | OpenAI ne détaille pas ; page d'aide inaccessible sans JavaScript lors de la vérification : non confirmé directement |
| Perplexity | PerplexityBot plus d'autres sources non documentées | Partiel |
| Claude | Claude-SearchBot et Claude-User ; fournisseur de recherche externe non documenté (souvent attribué à Brave Search) | Non vérifié |
| DuckDuckGo (réponses IA) | DuckAssistBot et index propre | Doc DuckDuckGo |
| Siri, Spotlight | Applebot | Doc Apple |
| Mistral | MistralAI-Index et MistralAI-User | Doc Mistral |
| DeepSeek | Inconnu | Non vérifié |

Lecture stratégique : un site bien indexé par Google **et** Bing couvre AI Overviews, Gemini, Copilot et,
très probablement, une bonne part de ChatGPT. C'est pourquoi les leviers 1 à 3 du §3 passent avant tout
le reste, et pourquoi la soumission IndexNow (Bing) et Search Console (Google) fait partie du déploiement.

## 5. Ce qui pèse hors du site

Corrélations publiées (corrélation n'est pas causalité) :

- Ahrefs, 75 000 marques : les mentions web de la marque corrèlent à 0,664 avec la visibilité dans les AI
  Overviews, les liens entrants à 0,218.
- Ahrefs, fin 2025 : les mentions de la marque sur YouTube corrèlent à environ 0,737, le meilleur facteur
  mesuré, devant les mentions web (0,66 à 0,71).
- Semrush, 230 000 requêtes sur 13 semaines : Wikipedia et Reddit dominent les citations de ChatGPT, mais
  les parts bougent fortement d'un mois à l'autre (chute brutale en septembre 2025).

Google, lui, met en garde contre la recherche de mentions « inauthentiques ». Retenir : **être réellement
mentionné** (annuaires, articles de comparaison, vidéos, dépôts publics, avis authentiques) aide ;
fabriquer des mentions nuit (voir mythes). Le détail opérationnel est dans `06-hors-site.md`. Sur
jam-jam.org, l'audit a trouvé trois mentions externes connues et 72 impressions de la marque en 90 jours :
c'est le vrai plafond du site.

## 6. Mythes à écarter

1. « Les balises (JSON-LD, schema) servent un plateau aux IA. » Google : aucun balisage spécial requis ;
   ChatGPT et Perplexity ont lu un JSON-LD invalide comme du texte brut dans un test publié. Utile pour
   Google (entité, résultats enrichis) et Bing, pas un levier IA.
2. « Il faut un llms.txt. » Google l'ignore ; sur 137 000 domaines, 97 % des fichiers n'ont reçu aucune
   requête en mai 2026 (Ahrefs). Gratuit à générer, ne pas y investir.
3. « Le premier sur Google sera cité par ChatGPT. » Faux : ChatGPT a son index et ses sources ; même pour
   les AI Overviews, seulement 38 % des URL citées sont dans le top 10 de la même requête (Ahrefs, mars
   2026, contre 76 % en juillet 2025).
4. « Bloquer Google-Extended retire des AI Overviews. » Faux : il n'a aucun effet sur Search.
5. « Bloquer GPTBot retire de ChatGPT. » Faux : GPTBot est l'entraînement ; la recherche dépend d'OAI-SearchBot.
6. « Les FAQ en JSON-LD donnent des résultats enrichis. » Plus du tout : restreints en août 2023 aux sites
   officiels de santé et d'administration, puis supprimés le 7 mai 2026. Le bloc FAQ **visible** reste utile
   au lecteur.
7. « L'API Indexing accélère l'indexation de toutes les pages. » Réservée aux offres d'emploi et aux
   diffusions en direct ; risque de révocation en cas d'abus.
8. « IndexNow prévient Google. » Non : Bing, Yandex, Naver, Seznam, Yep et Amazon seulement.
9. « Il suffit d'écrire pour les IA (texte caché, consignes aux modèles). » Assimilé à du cloaking ;
   Google précise que ses règles anti-spam s'appliquent aux réponses génératives.
10. « Plus de pages, plus de visibilité. » Les pages produites en masse pour chaque variante de requête
    relèvent du « scaled content abuse » ; Google le répète dans le guide de mai 2026.
11. « Il existe une longueur idéale ou un format magique. » Google : pas de longueur idéale.
12. « Wikipedia, Reddit : y créer une présence rapide. » Comptes jetables et pages autopromotionnelles
    échouent (critères de notoriété) et exposent à des sanctions.

## 7. Honnêteté sur la mesure

- Aucun outil tiers n'a accès aux systèmes internes de Google ; se méfier des « scores GEO ».
- Pew Research (juillet 2025, 900 adultes américains) : avec un résumé IA, 8 % des visites cliquent un
  résultat classique, contre 15 % sans résumé ; 1 % des visites cliquent un lien du résumé. Correction
  d'une version courante de ce chiffre (« 8 % cliquent après une réponse IA ») qui mélange les deux.
- Ahrefs : les assistants citent souvent la marque sans lien ; un lien apparaît dans 10,7 % des mentions des
  AI Overviews et 51,6 % de celles de Perplexity. Compter les citations sans lien.
- Sur jam-jam.org, aucun effet n'est mesuré à la date de rédaction : le déploiement date du 10 octobre
  2026, et les relevés de panel sont prévus à 2 à 4 semaines, les objectifs de CTR à 4 à 8 semaines.

## 8. Plan de lecture et enchaînement

1. `01-verdicts-recherche.md` : pourquoi chaque recommandation tient (ou non).
2. `02-audit-methode.md` : auditer un site inconnu en lecture seule, avec `geo_audit.py`.
3. `03-technique.md` : les onze leviers techniques, avec code et vérification.
4. `04-contenu.md` : patterns de contenu appliqués, avant et après réels.
5. `05-multilingue.md`, `06-hors-site.md`, `07-mesure.md` : langues, mentions externes, suivi.
6. `08-pieges-et-incidents.md`, `09-procedure-autonome.md` : incidents rencontrés et déroulé complet en autonomie.

Exemple chiffré de l'enchaînement sur jam-jam.org : audit du 10 octobre 2026 (972 pages indexables
inventoriées, 44 % des liens internes en redirection 308, aucun `lastmod`), puis lots A (technique) à I
(hors site) les 10 et 11 octobre, premier déploiement `20261010-123714`, 1 090 URL acceptées par IndexNow,
sitemaps resoumis à Search Console. Mesure sur le build en ligne du 13 octobre : 0 lien interne sans
slash sur 102 135 mesurés, `lastmod` sur les 730 URL du sitemap principal, `Organization` avec `sameAs`
sur les 731 pages indexables inventoriées.
