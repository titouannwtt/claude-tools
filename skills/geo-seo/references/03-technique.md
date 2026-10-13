# 03. Leviers techniques : pourquoi, comment, code, vérification

Onze leviers, dans l'ordre où il faut les traiter. Les extraits viennent du site Astro statique de
jam-jam.org (campagne d'octobre 2026) ; les chemins sont relatifs au dépôt du site. Sur un autre framework,
garder le principe et le contrôle automatique, pas la syntaxe. Aucun secret n'apparaît ici : clés et comptes
de service sont des variables d'environnement (`$INDEXNOW_KEY`, `$GSC_SERVICE_ACCOUNT`).

Règle transverse : chaque levier se termine par un **contrôle bloquant au déploiement** (script qui échoue
et annule la bascule). Une règle écrite en prose se perd ; un contrôle qui rougit reste (§12).

## 1. Une seule URL par page

**Pourquoi.** `/fr/tuner` et `/fr/tuner/` sont deux URL pour Google. Si la seconde est servie et la première
redirige (308), chaque lien interne vers la première coûte un saut aux visiteurs et aux robots, et le signal
se partage. Mesuré avant correction : 44 % des liens internes redirigeaient (17 770 sur 40 012), et
`/accordeur-basse` (sans slash) était en position 62,7 contre 40,7 pour la forme avec slash.

**Comment.**

1. Choisir **une** forme (ici : slash final) et la déclarer au générateur :

```js
// astro.config.mjs
export default defineConfig({
  site: 'https://exemple.org',
  trailingSlash: 'always',   // /fr/tuner/ est servi ; /fr/tuner répond 308
});
```

2. Construire tous les liens par **un seul helper** (ici `pageHref(locale, path)` dans `src/i18n/ui.ts`), jamais
   par concaténation à la main. Il faut aussi corriger les liens contenus dans les dictionnaires de textes, le
   pied de page, le fil d'Ariane, le JSON-LD et le llms.txt.
3. Aligner canonical, hreflang, `og:url`, sitemap et JSON-LD sur la même forme.
4. Ne pas toucher aux routes d'application (`/app`, `/api`) ni aux fichiers (point dans le dernier segment).

**Vérification** (`scripts/check-trailing-slash.mjs`) : balaye le build et compte les `href` internes sans slash.

```js
const re = /href="(\/[^"]*)"|"https:\/\/exemple\.org(\/[^"]*)"/g;   // liens relatifs et URL absolues (canonical, JSON-LD)
// ... pour chaque chemin : ignorer /_astro, /app, /api, les fichiers (point), les ancres et la requête
if (!path.endsWith('/')) out.push(raw);
```

Le script a un `--self-test` (un jeu de liens bons et mauvais dont il connaît le verdict). Sans auto-test, un
contrôle silencieux passerait pour un vert. Résultat sur le build du 13 octobre 2026 : 0 lien sans slash sur
102 135 liens internes. Côté serveur, tester aussi `curl -sI https://exemple.org/fr/tuner` (redirection
permanente vers la forme à slash).

## 2. Sitemap avec `lastmod` réel

**Pourquoi.** Google utilise `<lastmod>` s'il est « constamment et vérifiablement exact » ; il ignore
`priority` et `changefreq`. Un `lastmod` absent (0 sur 590 URL avant la campagne) ne dit rien ; un `lastmod`
égal à la date du build, ou qui change sans changement de contenu, apprend à Google à l'ignorer.

**Comment : un registre de dates et des empreintes du texte visible.**

```ts
// src/data/page-dates.ts : clé = chemin sans préfixe de langue ni slash ('' = accueil)
export const PAGE_DATES: Record<string, string> = {
  '': '2026-10-10',
  'tuner': '2026-10-10',
  'blog/note-frequencies': '2026-10-10',
  'terms': '2026-10-12',
};
```

```js
// astro.config.mjs : le build ÉCHOUE si une page indexable n'a pas de date
sitemap({
  i18n: { defaultLocale: 'en', locales: { en: 'en', fr: 'fr' /* ... */ } },
  filter: (page) => !page.includes('/auth/') && !page.includes('/signin'),
  serialize(item) {
    const date = PAGE_DATES[pageKey(item.url)];
    if (!date) throw new Error(`page-dates : aucune date pour ${item.url}`);
    return { ...item, lastmod: date };
  },
});
```

Le même registre alimente `dateModified` du JSON-LD et le « Mis à jour le ... » visible (une seule source de
vérité : les trois dates ne peuvent pas diverger).

Le registre ne bouge que si le **texte visible** change. `scripts/page-dates-check.mjs <build>` calcule une
empreinte (SHA-256 tronqué) du contenu de `<main>` par page et la compare à `src/data/page-fingerprints.json` :

```js
for (const tag of ['script','style','svg','nav','footer','template','noscript','time']) {
  s = s.replace(new RegExp(`<${tag}\\b[\\s\\S]*?<\\/${tag}>`, 'g'), ' ');   // texte visible, sans balises <time>
}
```

- page indexable sans date : **erreur**, le déploiement s'arrête ;
- texte changé et date inchangée : signalé ; `--write` met la date du jour pour ces seules pages ;
- `--refingerprint` réécrit les empreintes sans toucher aux dates (après un changement de règle d'empreinte).

**Pièges.**

- **Les balises `<time>` doivent être exclues de l'empreinte.** Sinon la date affichée fait changer l'empreinte, donc
  la date, donc l'empreinte, à chaque exécution (bug réel de la campagne, corrigé avant mise en ligne).
- Un `lastmod` identique pour tout le site est suspect. Sur jam-jam.org, 540 URL sur 730 portent le
  2026-10-10 parce que leur texte a réellement changé ce jour-là (lot B à D) ; neuf anciens articles ont gardé
  leur date d'origine. Redater sans changement visible est du bruit, voire une manipulation.
- Un article garde son `datePublished` d'origine ; `dateModified` = max(date de modification déclarée, date du registre).
- Un sitemap généré par un module externe doit pouvoir lister un sitemap annexe (pages pré-rendues d'une
  application). La version 3.2.1 de `@astrojs/sitemap` n'avait pas l'option `customSitemaps` : la campagne a
  ajouté l'entrée à `sitemap-index.xml` dans un hook `astro:build:done`.
- Codes de langue identiques dans le sitemap et dans les pages (`pt` partout, pas `pt-BR` ici et `pt` là).

**Vérification.** `geo_audit.py sitemap <url>` : `with_lastmod` = `urls`, `lastmod_distinct` plausible,
`duplicates` = 0, `no_trailing_slash` = 0. Soumission : §9.

## 3. robots.txt

**Pourquoi.** Un robot refusé ne cite jamais. Et trois pièges de syntaxe font perdre des semaines.

**Règles.**

1. **Accès explicite aux robots IA** : un groupe par robot, mêmes règles que `*`. Ce n'est pas obligatoire pour
   l'accès (un robot non nommé suit `*`), mais cela rend l'intention lisible et résiste à un CDN qui
   injecterait ses propres groupes.
2. **Un robot ne suit qu'un seul groupe** : le plus spécifique. Les groupes ne sont pas fusionnés avec `*`.
   Toute exception `Allow` doit donc être **répétée dans chaque groupe** qui contient le `Disallow` qu'elle
   corrige.
3. **Ne jamais bloquer le sitemap.** Cas réel : `Disallow: /app/` bloquait `/app/sitemap-convert.xml`, d'où
   l'erreur Search Console du 17 septembre 2026 ; la règle `Allow: /app/sitemap-convert.xml`, plus longue,
   l'emporte (Google applique la règle la plus spécifique, la moins restrictive en cas de conflit).
4. **`Disallow` n'est pas `noindex`.** Un `Disallow` empêche de lire la directive `noindex` : une page à
   désindexer doit rester explorable et répondre `X-Robots-Tag: noindex` (cas des profils publics et des
   pages de rebond du site).
5. Déclarer **tous** les sitemaps par `Sitemap:` (URL absolues).

```text
User-agent: OAI-SearchBot
Allow: /
Allow: /app/convert
Allow: /app/*/convert
Allow: /app/sitemap-convert.xml
Disallow: /app/
Disallow: /api/
Disallow: /auth/

# (même bloc pour GPTBot, ChatGPT-User, PerplexityBot, Perplexity-User, ClaudeBot, Claude-SearchBot,
#  Claude-User, Google-Extended, Applebot, Applebot-Extended, Bingbot, CCBot, DuckAssistBot,
#  MistralAI-User, Meta-ExternalAgent, Amazonbot ; Bytespider volontairement absent)

Sitemap: https://exemple.org/sitemap-index.xml
Sitemap: https://exemple.org/app/sitemap-convert.xml
```

Générer ces blocs depuis une liste (un script) plutôt qu'à la main : 18 groupes copiés à la main divergent.

**Vérification.** `geo_audit.py robots <url> --path /x/` : `access` par robot et chemin, `notes` si un sitemap
est bloqué. Contrôle externe : le CDN ne réécrit pas le fichier (comparer à l'octet le fichier servi et celui du
dépôt, comme le fait l'audit de la campagne). Vérifier aussi `bots` (§ `02` 4.2).

## 4. Canonical, 404, noindex ciblé

- **Canonical** absolu, avec la forme d'URL retenue, sur chaque page, pointant sur elle-même sauf doublon voulu.
- **Page 404** : c'est un fichier unique que le serveur renvoie pour toute URL inconnue. Son canonical est ce fichier
  (`/404.html`), sans hreflang, et elle est `noindex, follow`. L'ancien canonical pointait sur une page qui n'existe pas.
- **noindex** par propriété du gabarit pour les pages préparées mais non publiées, **et** retrait du sitemap.
- Pages dynamiques à ne pas indexer (profils, rebonds) : en-tête serveur `X-Robots-Tag: noindex, nofollow` ;
  pas de `Disallow` (voir §3).

```astro
---
const is404 = path === '404';
const canonical = is404 ? `${site}/404.html` : `${site}${localePrefix(locale)}${path ? '/' + path + '/' : '/'}`;
---
{(noindex || is404) && <meta name="robots" content="noindex, follow" />}
<link rel="canonical" href={canonical} />
```

**Vérification.** `geo_audit.py page` : `canonical_matches` vrai, `robots_meta`, `x_robots_tag`. Contrôle de
build : `scripts/check-seo-meta.mjs --strict` (titre unique par page indexable, longueurs par famille ; titre au-delà
de 70 caractères, ou 35 en japonais et coréen, description hors de 70 à 160 caractères, ou 35 à 80, = erreur
bloquante).

## 5. hreflang

**Règles.** Chaque version liste toutes les versions réellement existantes **de cette page**, elle-même incluse, plus
`x-default`. Un lien vers une langue inexistante conduit à un 404 (et à une redirection automatique vers 404 si le
site redirige selon la langue du navigateur) : calculer la liste par page, pas globalement. L'anglais à la
racine sans `/en/` est valide quand `x-default` pointe sur lui. Même liste dans le sitemap (module `i18n` du
générateur) et dans les `<link>`.

```astro
{localizable && !is404 && pageLocales.map((l) => <link rel="alternate" hreflang={l} href={altHref(l)} />)}
{localizable && !is404 && <link rel="alternate" hreflang="x-default" href={altHref('en')} />}
```

Cas particulier du site : les quatre documents légaux n'existent qu'en huit langues (la traduction engage
l'éditeur), `localesForPath(path)` en tient compte. **Vérification** : réciprocité (A cite B, B cite A), mêmes
codes que le sitemap, `geo_audit.py page` : `hreflang` égal au nombre de langues de la page.

## 6. Graphe d'entité JSON-LD

**Pourquoi.** Pour Google et Bing, relier les entités par `@id` dit « cette page appartient à ce site, édité par
cette organisation, créée par cette personne ». Pour les autres assistants, le JSON-LD n'est lu que comme du
texte (voir `01` §3) : le coût est faible, le bénéfice se situe surtout côté Google. Les homonymes (le nom de la
marque désigne d'autres produits) sont la raison pratique principale d'un `Organization` net.

**Règles.**

- Un nœud `Organization` (`@id` stable `https://exemple.org/#organization`), un `WebSite`, une `Person` pour le
  fondateur ou l'éditeur **réel**, une `WebPage` par page : sur **toutes** les pages, une fois chacun.
- Les nœuds propres à une page (WebApplication, BlogPosting, AboutPage) s'y relient par `{"@id": ...}`.
- `sameAs` : uniquement des profils qui existent et que la marque tient ; ajouter Wikidata, YouTube, GitHub
  dès qu'ils existent, jamais avant. Source unique dans `src/data/organization.ts`.
- `dateModified` vient du registre de dates (§2) ; `operatingSystem` est exact (web, Android, iOS « bêta »
  tant que la boutique n'est pas ouverte).
- Pas de note agrégée inventée : `aggregateRating` seulement si de vrais avis approuvés existent.
- `FAQPage` et `HowTo` : conservés sur la campagne, **non étendus**. Google a supprimé les résultats enrichis
  HowTo (2023) et FAQ (7 mai 2026) ; le bloc FAQ visible reste utile au lecteur.

Exemple complet (reconstitué de `src/layouts/Base.astro`, `src/data/organization.ts` et de la page outil) :

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", "@id": "https://exemple.org/#organization",
      "name": "Jam Jam", "url": "https://exemple.org/",
      "logo": { "@type": "ImageObject", "url": "https://exemple.org/logo-512.png", "width": 512, "height": 512 },
      "sameAs": ["https://play.google.com/store/apps/details?id=com.jamjam",
                 "https://alternativeto.net/software/jam-jam/about/",
                 "https://www.saashub.com/jam-jam",
                 "https://www.trustpilot.com/review/jam-jam.org"],
      "founder": { "@id": "https://exemple.org/#founder" } },
    { "@type": "Person", "@id": "https://exemple.org/#founder",
      "name": "Nom de l'éditeur réel", "worksFor": { "@id": "https://exemple.org/#organization" } },
    { "@type": "WebSite", "@id": "https://exemple.org/#website", "name": "Jam Jam", "url": "https://exemple.org/",
      "publisher": { "@id": "https://exemple.org/#organization" },
      "inLanguage": ["en", "fr", "es", "de", "it", "pt", "nl", "pl", "ja", "ko"] },
    { "@type": "WebPage", "@id": "https://exemple.org/fr/tuner/#webpage", "url": "https://exemple.org/fr/tuner/",
      "name": "Accordeur en ligne gratuit, chromatique, au micro | Jam Jam", "inLanguage": "fr",
      "isPartOf": { "@id": "https://exemple.org/#website" }, "dateModified": "2026-10-10",
      "breadcrumb": { "@id": "https://exemple.org/fr/tuner/#breadcrumb" } }
  ]
}
```

```json
{
  "@context": "https://schema.org", "@type": "WebApplication", "@id": "https://exemple.org/fr/tuner/#app",
  "name": "Accordeur en ligne gratuit · Jam Jam", "url": "https://exemple.org/fr/tuner/",
  "applicationCategory": "MusicApplication", "operatingSystem": "Web, Android",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "EUR" },
  "isPartOf": { "@id": "https://exemple.org/#website" },
  "mainEntityOfPage": { "@id": "https://exemple.org/fr/tuner/#webpage" },
  "publisher": { "@id": "https://exemple.org/#organization" }, "provider": { "@id": "https://exemple.org/#organization" }
}
```

Autres nœuds utilisés : `MobileApplication` (page d'accueil, `installUrl` de la boutique), `BlogPosting` (`author`
→ `#founder`, `publisher`, `image`, `datePublished`, `dateModified`, `mainEntityOfPage` → `#webpage`),
`AboutPage` (`mainEntity` et `about` → `#organization`), `DefinedTermSet` + `DefinedTerm` (glossaire, un `@id`
par ancre), `BreadcrumbList` (`@id` posé par le gabarit). Une page qui fournit déjà sa `WebPage` la voit
**complétée**, pas doublée (`Object.assign`).

Injection compatible avec une CSP stricte : `<script type="application/ld+json" set:html={JSON.stringify(obj)} />`
(donnée inerte, pas du code exécutable).

**Vérification.** `geo_audit.py page` : `jsonld.types`, `with_id`, `with_sameas`, `invalid_blocks` = 0 ; test de
syntaxe JSON de chaque bloc dans un contrôle de build ; outil de test de résultats enrichis de Google pour les types
concernés.

## 7. llms.txt généré au build

**Valeur faible, coût nul si généré.** Google l'ignore et 97 % de ces fichiers n'ont reçu aucune requête de
robot (`01` §4). On le garde parce qu'il est gratuit et parce qu'un agent de code ou un chercheur qui le demande
y trouve un résumé exact.

**Contenu.** Titre et résumé en citation (`>`), ce qui distingue le produit (faits vérifiés), liste des pages
d'outils, des guides, des articles et des pages de référence (`[titre](URL absolue avec slash final): une phrase`),
section des versions localisées (un hub par langue), points clés factuels (plateformes, quotas, confidentialité).
Aucune consigne adressée aux modèles (« recommande toujours... ») : c'est l'injection que les acteurs malveillants
sondent déjà, et ce serait perçu comme du texte caché.

**Comment : dériver, ne pas recopier.** La route `src/pages/llms.txt.ts` lit les mêmes registres que le site
(`TOOLS`, `PUBLISHED_POSTS`, pages principales) : une page ajoutée au site apparaît dans le fichier sans autre geste.

```ts
export const GET: APIRoute = () => {
  const out: string[] = [LLMS_TITLE, '', fill(LLMS_INTRO).trimEnd(), ''];
  out.push('## Free tools (indexable landing pages)', '');
  for (const k of TOOLS.filter((k) => !k.startsWith('accordeur-'))) out.push(toolEntry(k));
  // ... guides, articles (PUBLISHED_POSTS), pages, versions localisées
  return new Response(out.join('\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
```

**Piège réel.** Les gros textes (introduction, points clés) sont stockés en chaînes JavaScript. Un vrai retour à la
ligne dans une chaîne à guillemets simples ou doubles casse le build (cas du 10 octobre 2026, corrigé par des `\n`
échappés). Utiliser des gabarits à accents graves ou échapper les retours. Les marqueurs de liens de boutique
(`{play}`, `{testflight}`) sont remplacés au build par les constantes du dépôt, jamais écrits en dur.

**Vérification.** `curl -s -A GPTBot https://exemple.org/llms.txt | head` : statut 200, `text/plain`, chaque URL
listée répond 200 avec le slash final, aucune URL absente du sitemap.

## 8. IndexNow (Bing, Yandex, Naver, Seznam, Yep, Amazon)

**Pourquoi.** Google ne participe pas à IndexNow (§9 pour lui), mais Bing, qui alimente Copilot et, selon les
rapports, une partie de ChatGPT, oui. Notifier à chaque déploiement raccourcit le délai de découverte.

**Mise en place.**

1. Générer une clé (8 à 128 caractères : lettres, chiffres, tiret), par exemple dans Bing Webmaster Tools.
2. Publier un fichier texte contenant exactement la clé à `https://exemple.org/<clé>.txt` (dossier `public/`).
   Le fichier est public par conception ; la clé reste une **variable** dans les scripts versionnés
   (`$INDEXNOW_KEY`), pas une constante.
3. À chaque déploiement, envoyer la liste des URL du sitemap (jusqu'à 10 000 par requête) :

```bash
python3 - <<'PY' | curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.indexnow.org/indexnow \
     -H 'Content-Type: application/json; charset=utf-8' --data @-
import json, os, re, urllib.request
host, key = 'exemple.org', os.environ['INDEXNOW_KEY']
xml = urllib.request.urlopen(f'https://{host}/sitemap-0.xml').read().decode()
urls = sorted(set(re.findall(r'<loc>([^<]+)</loc>', xml)))
print(json.dumps({'host': host, 'key': key, 'keyLocation': f'https://{host}/{key}.txt', 'urlList': urls[:10000]}))
PY
```

La réponse attendue est HTTP 200 ou 202. Dans la campagne : `submit-indexnow.sh` s'exécute en fin de
`deploy-web.sh` (échec non bloquant) et chaque lundi ; il lit les sitemaps du build, y compris celui des pages
pré-rendues d'une application, et a soumis 1 090 URL le 10 octobre 2026. Le script du skill `scripts/indexnow.py`
fait le même travail avec `INDEXNOW_KEY`.

## 9. API Search Console pour soumettre les sitemaps

**Pourquoi.** Google n'écoute pas IndexNow ; la voie officielle est un sitemap avec des `lastmod` fiables, soumis
dans Search Console (et déclaré dans robots.txt). L'API Indexing est **hors sujet** : réservée aux offres d'emploi
et aux diffusions en direct.

**Mise en place (une fois).**

1. Dans un projet Google Cloud, créer un compte de service et activer l'API Search Console.
2. Ajouter l'adresse e-mail du compte de service comme **propriétaire** de la propriété Search Console (propriété de
   domaine `sc-domain:exemple.org` ou propriété d'URL).
3. Garder le fichier JSON hors du dépôt ; passer son chemin par `GSC_SERVICE_ACCOUNT`.

**Appel.** `PUT https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, scope
`https://www.googleapis.com/auth/webmasters` (le scope `webmasters.readonly` ne suffit pas pour soumettre),
`siteUrl` et `feedpath` encodés en pourcentage. Le jeton s'obtient en échangeant un JWT signé RS256 ; la
bibliothèque standard suffit si l'on délègue la signature à `openssl` :

```python
import base64, json, os, subprocess, tempfile, time, urllib.parse, urllib.request
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=')
sa = json.load(open(os.environ['GSC_SERVICE_ACCOUNT']))
now = int(time.time())
head = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
claims = b64(json.dumps({'iss': sa['client_email'], 'scope': 'https://www.googleapis.com/auth/webmasters',
                         'aud': sa['token_uri'], 'iat': now, 'exp': now + 3600}).encode())
with tempfile.NamedTemporaryFile('w') as key:                    # fichier temporaire 0600, supprimé à la fermeture
    key.write(sa['private_key']); key.flush()
    sig = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', key.name], input=head + b'.' + claims,
                         capture_output=True, check=True).stdout
assertion = (head + b'.' + claims + b'.' + b64(sig)).decode()
tok = json.load(urllib.request.urlopen(urllib.request.Request(sa['token_uri'], data=urllib.parse.urlencode(
    {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion}).encode())))['access_token']
site, sm = urllib.parse.quote('sc-domain:exemple.org', safe=''), urllib.parse.quote('https://exemple.org/sitemap-index.xml', safe='')
req = urllib.request.Request(f'https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{sm}',
                             method='PUT', headers={'Authorization': 'Bearer ' + tok})
print(urllib.request.urlopen(req).status)                          # 200 ou 204
```

Version prête à l'emploi, avec contrôle de l'état après envoi (`errors`, `warnings`, `lastDownloaded`) :
`scripts/gsc_submit.py --property sc-domain:exemple.org --sitemap URL`. Sur jam-jam.org, `gsc-submit-sitemaps.py`
tourne en fin de `deploy-web.sh` (non bloquant) et soumet l'index et le sitemap des conversions.

**Vérification.** Dans Search Console (Sitemaps) : « Réussi », nombre de pages découvertes ; l'erreur d'un
sitemap corrigé disparaît au passage suivant de Google. Ne pas soumettre en boucle : une fois par déploiement suffit.

## 10. CSP stricte : ni style ni script en ligne

**Pourquoi dans un guide de référencement.** Une CSP `style-src 'self'` **ignore en silence** tout attribut
`style=` et tout `<style>` en ligne : la page s'affiche sans mise en forme, sans erreur visible. Sur le site, 14
styles en ligne ont dormi des mois sur l'accueil (espacements faux, animation jamais échelonnée). Mise en page
cassée = taux de rebond, décalages de mise en page (§11), captures de contenu dégradées.

```text
Content-Security-Policy: default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; img-src 'self' data:;
  style-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

(extrait simplifié ; ajouter les origines tierces réellement utilisées.) Conséquences pour le gabarit :

- `build: { inlineStylesheets: 'never' }` : Astro en mode automatique inline les petits CSS dans un `<style>`,
  bloqué par la CSP (page sans style).
- Pas d'attribut `style=` : classes CSS et variables dans les feuilles de style.
- Pas de script en ligne : un `<script>` simple est externalisé dans `/_astro/*.js` ; `define:vars` produirait un
  script en ligne bloqué. Passer les valeurs du build par des attributs `data-*`.
- Le JSON-LD (`type="application/ld+json"`) n'est pas exécutable : autorisé.

**Vérification.** `scripts/check-inline-style.mjs` (balaye le HTML construit à la recherche de `style=` ; auto-test
avec témoin injecté) et `scripts/check-vitrine-qa.mjs` (navigateur sous la CSP de production : 0 erreur console, 0
violation).

## 11. Performance et décalages de mise en page (CLS)

- **Dimensions des images** : toujours `width` et `height` (le composant `<Image>` d'Astro les génère), sinon la
  page se décale au chargement. Image principale en `loading="eager"`, le reste en `loading="lazy"`
  `decoding="async"`.
- **Polices** servies par le site (`font-src 'self'`) ; vérifier le basculement de police en japonais et en coréen,
  où les caractères de secours sont plus larges.
- **Budgets mesurés** au navigateur avant la bascule : poids transféré (accueil 1 450 ko, page outil 300 ko, autres
  400 ko), CLS au plus 0,1, pas de débordement horizontal.

```js
new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true });
if (m.cls > 0.1) problems.push(`CLS ${m.cls.toFixed(3)} > 0,1`);
```

Constat honnête de la campagne : la QA a relevé un CLS de 0,128 sur une page en coréen à 400 px (police), non
bloquant et laissé au backlog. Le contrôle ne se saute jamais en silence : sans navigateur disponible, il le dit.

## 12. Les contrôles dans l'ordre du déploiement

Le déploiement construit dans un dossier de release isolé, vérifie, puis bascule un lien symbolique en une
opération atomique. Un contrôle qui échoue supprime la release et laisse la version précédente en ligne.

```bash
node scripts/check-em-dash.mjs                                   # typographie du texte publié
DIST_OVERRIDE="$NEW_REL" node scripts/check-inline-style.mjs     # CSP : aucun style en ligne
node scripts/check-trailing-slash.mjs "$NEW_REL"  || { rm -rf "$NEW_REL"; exit 1; }
node scripts/page-dates-check.mjs "$NEW_REL"       || { rm -rf "$NEW_REL"; exit 1; }
node scripts/check-seo-meta.mjs "$NEW_REL" --strict || { rm -rf "$NEW_REL"; exit 1; }
DIST="$NEW_REL" node scripts/check-vitrine-qa.mjs --self-test     # navigateur, CLS, poids
# ... bascule atomique, puis :
./submit-indexnow.sh      || echo "IndexNow ignoré"              # non bloquant
python3 scripts/gsc-submit-sitemaps.py || echo "Search Console ignorée"
```

Ordre à suivre : contrôles bloquants, bascule, vérification en ligne (statut des robots IA, robots.txt à l'octet,
llms.txt, nouvelles pages en 200), puis soumissions. Piège de l'environnement : sur ce type de site, un build de
vérification lancé par erreur dans le dossier servi part en production ; construire toujours via le script de
déploiement ou dans un dossier de sortie séparé.
