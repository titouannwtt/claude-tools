# 02. Auditer un site inconnu, en lecture seule

Méthode d'audit GEO + SEO d'un site que l'on ne connaît pas. Tout se fait sans rien modifier : requêtes
HTTP publiques, lecture du dépôt s'il est fourni, lecture de Search Console si l'accès existe. Le livrable
est un `AUDIT.md` chiffré, classé par gravité, qui nourrit le plan (impact/coût) et les lots d'implémentation.

Exemple travaillé : l'audit de jam-jam.org du 10 octobre 2026 (§10), mesuré sur la release en ligne (994
fichiers HTML), Search Console du 10 juillet au 9 octobre 2026 et requêtes réelles avec des user-agents de
robots IA.

## 1. Principes

- **Lecture seule.** Aucune écriture, aucune soumission, aucun contournement de protection. Le script du skill
  `scripts/geo_audit.py` respecte cette règle (bibliothèque standard, JSON sur stdout).
- **Mesurer avant de juger.** Chaque constat porte un chiffre et la commande qui l'a produit.
- **Du moins cher au plus cher.** Les contrôles d'accès et de redirections (minutes) viennent avant la lecture
  du contenu (heures) et avant les actions hors site (jours).
- **Séparer constat et hypothèse.** Dire « mesuré » ou « supposé ». Un journal de serveur illisible est un
  constat ; « les robots IA ne viennent pas » serait une hypothèse.
- **Audit de l'exposition publique d'abord.** On voit le site comme un robot : HTML brut, sans JavaScript, avec
  les user-agents des robots.

## 2. Le script `geo_audit.py`

Appel : `python3 -I <skill>/scripts/geo_audit.py <sous-commande> ...` (le drapeau `-I` évite de charger du
code du dossier courant). Python 3.8 ou plus, aucune dépendance. Codes de sortie : 0 succès, 2 arguments
invalides, 4 réseau inaccessible, 1 erreur inattendue.

| Sous-commande | Ce qu'elle fait | Champs JSON utiles |
|---|---|---|
| `doctor` | Vérifie la version de Python et l'accès réseau | `python_ok`, `network` |
| `robots <url> [--path /x/]` | Lit `/robots.txt`, applique « règle la plus longue, Allow à égalité » pour chaque robot IA sur des chemins testés (par défaut `/`, `/blog/`, `/app/`), liste les sitemaps déclarés | `status`, `sitemaps`, `access` (robot, chemin, autorisé), `notes` (sitemap bloqué par un Disallow, robots IA bloqués, aucun sitemap déclaré) |
| `sitemap <url>` | Charge le sitemap ou l'index (deux niveaux, 60 000 URL maximum), compte les URL | `urls`, `with_lastmod`, `lastmod_distinct`, `with_hreflang`, `hreflang_values`, `duplicates`, `no_trailing_slash`, `errors` (sitemaps illisibles ou XML invalide) |
| `page <url> [--ignore-prefix /app/]` | Analyse une page (suit les redirections et le signale) | `title_len`, `description_len`, `canonical`, `canonical_matches`, `h1`, `visible_words`, `hreflang`, `jsonld` (types, `@id`, `sameAs`, blocs invalides), `internal_links_without_slash`, `has_time_element`, `first_paragraph_words`, `x_robots_tag`, `issues` |
| `bots <url>` | Demande la même page avec le user-agent de chaque robot IA (sans suivre les redirections) | `results` (statut par robot), `refused`, note si la taille de réponse diffère de plus de moitié |
| `crawl <url> --max N` | Échantillonne régulièrement N pages du sitemap et agrège les problèmes | `issues_summary`, `issues_examples`, `duplicate_titles`, `pages` |

Limites à connaître (elles évitent les faux verts) :

- `sitemap` ne vérifie pas le statut de chaque URL listée ; `errors` ne signale que les sitemaps illisibles. Pour
  les statuts, voir §4.
- `crawl` et `page` suivent les redirections : une URL du sitemap qui redirige y reste invisible, sauf via
  `redirected_from` de `page`. Le contrôle de redirection se fait avec `curl` sans `-L` (§4).
- `first_paragraph_words` mesure le premier paragraphe d'au moins douze mots. Ce n'est pas un détecteur de
  « bloc de réponse » : le bloc se juge à la lecture (40 à 60 mots répondant à la question de la page, §8).
- `bots` envoie des user-agents de robots depuis l'adresse IP de l'auditeur. Un pare-feu qui vérifie aussi
  l'adresse IP d'origine (plages publiées par les éditeurs) peut répondre autrement aux vrais robots :
  un résultat 200 est encourageant, pas définitif ; un 403 est déjà un défaut à corriger.
- `crawl` lit `/sitemap-index.xml` puis `/sitemap.xml` à la racine ; pour un autre emplacement, passer par
  `sitemap <url>` puis `page` sur un échantillon.

## 3. Ordre de l'audit

| Étape | Question | Outil |
|---|---|---|
| 1 | Quelles pages indexables, par famille et par langue ? | Sitemap, dépôt, `geo-inventory.py` (§4.1) |
| 2 | Les robots (humains, Google, Bing, IA) reçoivent-ils les pages ? | `bots`, `robots`, curl |
| 3 | Une seule URL par page ? | curl sans suivi, `page` |
| 4 | Le sitemap est-il fiable et déclaré ? | `sitemap`, `robots` |
| 5 | Titres, descriptions, canonical, hreflang | `crawl`, `page` |
| 6 | Données structurées, entité | `page` (`jsonld`), lecture du JSON-LD |
| 7 | Le texte est-il dans le HTML brut ? | curl, `page` (`visible_words`) |
| 8 | Contenu : minceur, réponse en tête, faits, dates, auteur | `crawl`, lecture |
| 9 | Search Console : requêtes, positions 5 à 20, CTR | API ou interface |
| 10 | Besoins sans page | Search Console + inventaire |
| 11 | Présence hors site, homonymes | Recherches manuelles |
| 12 | Rapport par gravité | `AUDIT.md` |

## 4. Les contrôles, avec les commandes

### 4.1 Inventaire des pages indexables

Si le dépôt est disponible, l'inventaire se fait sur le **build**, pas sur les sources (ce que le robot reçoit
compte). Un script d'inventaire produit une ligne CSV par page : famille, langue, titre et description (et
leurs longueurs), H1, canonical, robots, hreflang, types JSON-LD, dates, nombre de mots, liens internes. Dans
la campagne, c'est `scripts/geo-inventory.py` du dépôt du site (modèle à reprendre).

Sans dépôt, depuis le sitemap :

```bash
curl -s https://exemple.org/sitemap-index.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//'     # sitemaps
curl -s https://exemple.org/sitemap-0.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//' > urls.txt
wc -l urls.txt
awk -F/ '{l=$4; if (l ~ /^(fr|es|de|it|pt|nl|pl|ja|ko)$/) c[l]++; else c["en"]++} END{for(k in c) print c[k], k}' urls.txt   # par langue
```

Classer ensuite par famille (accueil, outils, produits, blog, légal, divers) et noter les pages `noindex`
(méta `robots` ou en-tête `X-Robots-Tag`). Un site avec langues préfixées (`/fr/`) et langue par défaut à la
racine est valide.

### 4.2 Accès et rendu sans JavaScript

```bash
UA_BASE='Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; %s/1.0)'
for bot in GPTBot OAI-SearchBot ChatGPT-User ClaudeBot Claude-SearchBot Claude-User PerplexityBot \
           Perplexity-User Googlebot bingbot Applebot Amazonbot meta-externalagent MistralAI-User DuckAssistBot CCBot; do
  printf '%-18s ' "$bot"
  curl -s -o /dev/null -w '%{http_code} %{size_download}\n' -A "$(printf "$UA_BASE" "$bot")" https://exemple.org/page/
done
```

Lecture : tout doit répondre 200 (ou une redirection propre vers l'URL canonique) avec une taille voisine de celle
d'un navigateur. Un 403 ou un 429 pour un robot seul, un contenu très différent ou une page de contrôle
(« Verify you are human ») indiquent un pare-feu ou un CDN à régler. `geo_audit.py bots <url>` fait la même
chose en JSON.

Rendu sans JavaScript :

```bash
curl -s https://exemple.org/page/ -o page.html
grep -c '<h1' page.html                                    # un seul H1 dans le HTML brut
python3 -I -c "import re,sys;h=open('page.html').read();h=re.sub(r'<(script|style|svg|nav|footer)\b.*?</\1>','',h,flags=re.S);print(len(re.findall(r'\w+',re.sub(r'<[^>]+>',' ',h))))"
```

Un nombre de mots proche de zéro, ou un `<div id="root"></div>` seul, signifie que le contenu est construit côté
client : invisible pour OpenAI, Anthropic, Perplexity (voir `00` §2). Les routes d'une application (SPA)
peuvent rester hors référencement si chaque besoin a un équivalent statique ; le dire dans le rapport.

### 4.3 Une URL par page (slash final, redirections)

C'est le contrôle le plus rentable de l'audit de la campagne. Deux gestes.

1. **Statut des URL du sitemap sans suivre les redirections** (échantillon ou liste entière) :

```bash
while read -r u; do
  printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$u")" "$u"
done < <(shuf -n 300 urls.txt) | awk '{c[$1]++} END{for(k in c) print c[k], k}' | sort -rn
```

Toute URL du sitemap qui répond autre chose que 200 est un défaut (le sitemap ne doit lister que des URL
canoniques, indexables, répondant 200).

2. **Part des liens internes qui redirigent.** Extraire les `href` internes de quelques dizaines de pages,
dédupliquer, tester sans suivre :

```bash
curl -s https://exemple.org/page/ | grep -o 'href="/[^"#?]*"' | sed 's/href="//;s/"$//' | sort -u |
while read -r p; do printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "https://exemple.org$p")" "$p"; done |
awk '{c[$1]++} END{for(k in c) print c[k], k}'
```

`geo_audit.py page` donne `internal_links_without_slash` par page. Sur un site dont les pages vivent en
`/x/`, un lien `/x` coûte une redirection (308 ou 301) à chaque visiteur et brouille le signal canonique.

### 4.4 robots.txt

```bash
curl -s https://exemple.org/robots.txt
python3 -I <skill>/scripts/geo_audit.py robots https://exemple.org --path / --path /blog/ --path /app/
```

À vérifier :

- aucun `Disallow` sur les pages à référencer ; un `Disallow` ne retire pas une page d'un index et empêche
  de lire un `noindex` (voir `03` §3-4) ;
- les sitemaps sont déclarés par `Sitemap:` en URL absolue ;
- un sitemap ne se trouve pas dans un dossier interdit (cas jam-jam.org : `/app/sitemap-convert.xml` sous
  `Disallow: /app/`) ;
- un groupe nommé (`User-agent: GPTBot`) ne reprend pas les règles du groupe `*` : s'il existe, il doit les
  répéter, y compris les `Allow` d'exception ;
- les robots IA ne sont pas bloqués par inadvertance (`notes` de la commande) ;
- ne pas auditer avec `urllib.robotparser` : il applique la première règle dans l'ordre du fichier et ignore
  les jokers (voir `01` §5).

### 4.5 Sitemap

```bash
python3 -I <skill>/scripts/geo_audit.py sitemap https://exemple.org/sitemap-index.xml
```

Indicateurs : nombre d'URL, `with_lastmod` (cible : toutes), `lastmod_distinct` (une seule date partout est
suspecte, sauf si tout a vraiment changé le même jour), `with_hreflang`, `hreflang_values` (mêmes codes que
dans les pages : `pt` contre `pt-BR` est une divergence réelle), `duplicates`, `no_trailing_slash`. Vérifier
aussi que chaque sitemap annexe (pages pré-rendues d'une application, par exemple) est déclaré dans l'index
**et** dans robots.txt, et répond 200 aux robots.

### 4.6 Canonical, titres, descriptions, doublons

```bash
python3 -I <skill>/scripts/geo_audit.py crawl https://exemple.org --max 60
```

`issues_summary` agrège : titre long (au-delà de 65 caractères), description longue (au-delà de 160),
canonical absent, nombre de H1 différent de un, contenu mince (moins de 300 mots visibles), liens sans slash,
absence de données structurées, `noindex`. `duplicate_titles` liste les titres identiques. Pour un contrôle
exhaustif sur le build, utiliser un script dédié (modèle : `check-seo-meta.mjs`, `03` §4) : seuils par famille,
longueurs en caractères latins et plus courtes en japonais et coréen (pixel et largeur des caractères).
Vérifier à part le canonical de la page 404 (doit être le fichier 404 lui-même) et l'absence de canonical
pointant vers une URL qui redirige.

### 4.7 Données structurées

`geo_audit.py page` renvoie `jsonld.types`, le nombre de nœuds avec `@id` et avec `sameAs`, et les blocs
invalides. À lire en plus à la main sur trois pages (accueil, un outil, un article) :

- `Organization` : `sameAs` vers des profils **réels**, `logo` en 512 px, `@id` stable ;
- `WebSite` et `WebPage` reliés par `@id`, `dateModified` honnête ;
- `BlogPosting` : `author` réel, `datePublished` et `dateModified` ;
- types adaptés (`WebApplication`, `MobileApplication`, `SoftwareApplication`) avec `operatingSystem` exact ;
- cohérence entre le balisage et le texte visible (prix, plateformes).

### 4.8 Search Console

Voir `07-mesure.md` pour la mise en place et l'API. Pour l'audit, trois extractions sur 90 jours :

1. **Requêtes en positions 5 à 20** avec au moins quelques dizaines d'impressions : ce sont les gains rapides.
2. **Pages à CTR quasi nul** : au moins 100 impressions et moins de 1 % de clics, à comparer au CTR moyen du
   site (3,48 % sur jam-jam.org).
3. **Requêtes sans page dédiée** : regrouper par thème, repérer celles dont la page affichée est une page
   générique (cas « midi keyboard online » affiché sur la page du piano).

Corps de requête type (API `searchanalytics.query`, scope lecture seule) :

```json
{"startDate": "2026-07-10", "endDate": "2026-10-09", "dimensions": ["page", "query"], "rowLimit": 25000}
```

Mise en garde : l'export par requête omet les requêtes anonymisées. Sur jam-jam.org, le fichier de requêtes
totalise 134 clics et 11 457 impressions alors que la propriété affiche 735 clics et 21 094 impressions ;
l'écart tient probablement à cette anonymisation (hypothèse non vérifiée). Utiliser les totaux de la
propriété pour les ordres de grandeur, l'export par requête pour décider des titres.

### 4.9 Contenu mince, réponse en tête, auteur, dates

- Mots visibles par page (`visible_words`), distribution par famille ; marquer les pages sous 300 mots, mais
  juger sur la valeur : une page courte et complète vaut mieux qu'une page délayée (Google : pas de longueur
  idéale).
- Premier paragraphe : promotionnel ou réponse ? La page répond-elle à la question de son H1 dans les
  premières lignes ?
- Faits chiffrés : y en a-t-il, sont-ils vérifiables et datés ?
- Auteur : un nom réel (personne ou éditeur identifiable) ou un nom de marque générique sur chaque page ?
- Date de mise à jour visible et dans le JSON-LD ; ne pas confondre `datePublished` et `dateModified`.
- Langues : texte étranger résiduel sur une page traduite (compter les mots d'une autre langue).

### 4.10 Présence hors site

Recherches manuelles, sans compte : nom de la marque sur Google et Bing, résultats de la requête « marque +
catégorie », présence d'un panneau de connaissances, mentions sur annuaires, vidéos, dépôts publics, forums,
presse, avis. Noter les **homonymes** (le nom désigne-t-il d'autres produits ?) et le volume de recherche de
la marque dans Search Console. Les mentions sont le plafond du site seul (`06-hors-site.md`).

### 4.11 Journaux d'accès

Si le serveur est lisible, c'est la seule mesure directe des visites de robots :

```bash
grep -E 'GPTBot|OAI-SearchBot|ChatGPT-User|ClaudeBot|Claude-User|Claude-SearchBot|PerplexityBot|Perplexity-User|bingbot|Googlebot' access.log |
  awk '{print $NF}' | sort | uniq -c | sort -rn | head
```

Si les journaux ne sont pas accessibles (cas de la campagne), l'écrire comme limite de l'audit et proposer
d'ouvrir cet accès ou d'utiliser l'analyse de robots du CDN.

## 5. Grille de gravité

| Gravité | Définition | Exemples de l'audit |
|---|---|---|
| Critique | Empêche l'indexation, divise les signaux ou casse un sitemap | Liens internes en redirection, sitemap bloqué par robots.txt, robots IA refusés |
| Haute | Prive Google d'informations ou brouille l'entité | Aucun `lastmod`, `Organization` sans `sameAs`, aucun auteur réel |
| Moyenne | Perte de clics ou de citabilité | Descriptions trop longues, CTR nul sur les positions 8 à 13, pas de réponse en tête, pages minces |
| Basse | Hygiène | Titres dupliqués isolés, canonical de la 404, texte obsolète sur les plateformes |
| Plafond | Limite hors du site | Peu de mentions externes, marque peu recherchée |

Pour chaque constat : gravité, mesure, cause probable, correction proposée, effort (faible, moyen, élevé).

## 6. Restitution : le format de `AUDIT.md`

1. Périmètre et méthode (date, build ou environnement mesuré, outils, limites d'accès).
2. Inventaire des pages indexables : tableau par famille avec nombre de pages, puis par langue.
3. Ce qui est bien fait (utile : on ne le « corrige » pas).
4. Ce qui est mal fait, par gravité, avec les chiffres.
5. Mesures Search Console clés.
6. Recommandations classées impact/coût, qui alimentent le plan.

Après relecture par deux regards extérieurs (marketing IA, métier du site), produire un plan v2 : les arbitrages
(pages à créer, fusionner, retirer, reporter) priment sur la version initiale.

## 7. Exemple travaillé : jam-jam.org, 10 octobre 2026

### 7.1 Inventaire (972 pages indexables)

| Famille | Pages | Détail |
|---|---|---|
| Accueil | 10 | une par langue |
| Outils | 130 | 13 outils × 10 langues |
| Accordeurs par instrument | 180 | 18 instruments × 10 langues |
| Blog | 160 | index + 15 articles × 10 langues |
| Conversion (`/app/convert`, pré-rendu) | 380 | environ 37 conversions × 10 langues |
| Divers | 70 | premium, développeurs, journal des versions, contact, retours... |
| Légal | 42 | 8 langues (choix juridique : pas de japonais ni de coréen) |

Anglais à la racine, neuf autres langues préfixées. `noindex` : connexion, page de rebond, SPA `/app/*`,
profils `/u/*` (en-tête serveur).

### 7.2 Ce qui était bien

- Site statique : tout le texte est dans le HTML.
- 10 langues complètes avec hreflang et `x-default` (932 pages à 11 alternatives), `html lang` juste partout.
- robots.txt ouvert à 13 robots IA, non réécrit par le CDN (identique à l'octet), tous reçoivent 200 sur les
  pages publiques ; la SPA reste protégée à dessein.
- JSON-LD riche : FAQPage (720 pages, 2 710 questions), WebApplication, HowTo, BreadcrumbList, BlogPosting.
- IndexNow à chaque déploiement et chaque lundi (591 URL acceptées) ; llms.txt riche.
- Pages d'instruments rares qui se classent (accordeur de basse en français position 9, guitalélé 8, mandoline,
  violon, violoncelle 9 à 13).
- Discipline des chiffres publiés (brief marketing et contrôle automatique).

### 7.3 Ce qui était mal, par gravité

| # | Gravité | Constat | Mesure |
|---|---|---|---|
| 1 | Critique | Liens internes en redirection 308 | 17 770 liens sur 40 012 (44 %) vers `/fr/tuner` au lieu de `/fr/tuner/` ; `/accordeur-basse` position 62,7 contre `/accordeur-basse/` position 40,7 ; `/fr/clavier` en « Redirect error » depuis juillet |
| 2 | Critique | Aucun `lastmod` | 0 sur 590 URL du sitemap |
| 3 | Critique | Sitemap des conversions non déclaré, bloqué par robots.txt, en erreur dans Search Console depuis le 17/09 | `Disallow: /app/` couvrait le fichier ; hreflang `pt-BR` contre `pt` ailleurs |
| 4 | Haute | `Organization` sans `sameAs`, logo sur 10 pages seulement, aucun `@id` | 490 pages concernées |
| 5 | Haute | Aucun auteur réel (marque sur 150 pages), pas de page À propos, pas de date de mise à jour hors blog | Éditeur public seulement dans les mentions légales |
| 6 | Haute | Besoins sans page | « midi keyboard online » en position 13 sans page dédiée ; apprendre le piano, karaoké, import de chansons, progressions d'accords, glossaire ; aucun contenu de référence citable |
| 7 | Moyenne | Descriptions trop longues, titres dupliqués, canonical de la 404 faux | 547 pages au-delà de 160 caractères ; 12 titres dupliqués |
| 8 | Moyenne | Journaux d'accès illisibles pour la session | Impossible de compter les visites de robots IA |
| 9 | Moyenne | Pas de réponse en tête des pages outils, peu de faits chiffrés | Premier paragraphe promotionnel |
| 10 | Moyenne | CTR quasi nul sur positions 8 à 13 | Accordeur de violon en ligne : 297 impressions, 0 clic ; online mandolin tuner : 176, 0 ; afinador cromático : 181, 0 ; `/transposer` : 448 impressions, 1 clic ; `/accords` : 851, CTR 0,7 % |
| 11 | Moyenne | Blog mince | 61 pages d'articles sous 300 mots (piano-chords 231, tune-your-harp 254) |
| 12 | Moyenne | Usage hors périmètre officiel de l'API Indexing | 412 URL d'outils soumises |
| 13 | Basse | Plateformes obsolètes dans les données et le llms.txt | « Android, Web » alors que la bêta iOS existe |
| 14 | Plafond | Requêtes génériques hors d'atteinte | Métronome en position 70 à 82 |
| 15 | Plafond | Hors site | Trois mentions externes connues ; rien sur Wikidata, YouTube, Reddit, GitHub public, presse ; la marque fait 72 impressions en 90 jours ; homonymes |

Mesures clés de Search Console sur 90 jours : 735 clics, 21 094 impressions, CTR 3,48 %, position moyenne
26,6. Clics et impressions par langue : racine anglaise 311 et 8 725, français 171 et 5 397, espagnol 118 et
4 002, allemand 43 et 1 369, japonais 33 et 314, italien 14 et 695, polonais 14 et 194, portugais 12 et 222,
coréen 6 et 188, néerlandais 3 et 206.

### 7.4 Ce qu'il faut retenir de l'exemple

- Les trois premiers défauts (redirections, `lastmod`, sitemap bloqué) sont purement techniques, coûtent peu à
  corriger, et passaient avant toute écriture de contenu.
- Les requêtes en position moyenne (5 à 20) avec zéro clic ont été traitées en premier : un titre et une
  description réécrits sur la requête exacte (voir `04`).
- Les besoins sans page ont été mesurés sur les requêtes réelles, pas imaginés (voir `04`).
- Le plafond hors site a été documenté et préparé (`06-hors-site.md`), pas exécuté par l'auditeur.
- Après correction (build en ligne du 13 octobre) : 0 lien interne sans slash sur 102 135 liens mesurés, `lastmod`
  sur 730 URL du sitemap principal, mais 46 pages d'articles encore sous 300 mots (même script) : seuls les
  deux articles les plus minces avaient été enrichis, par choix du plan (« enrichir sans délayer »).
