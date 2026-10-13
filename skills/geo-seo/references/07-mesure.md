# 07. Mesurer : Search Console, canal « assistants IA », panel de questions

Une refonte GEO/SEO sans mesure est un acte de foi. Ce fichier décrit les trois instruments de la
campagne de jam-jam.org (exemple travaillé) et la cadence pour les faire vivre : Search Console pour
Google, le canal « assistants IA » dans l'attribution pour les visites, le panel de questions pour les
mentions qui ne produisent aucun clic.

## 1. Ce qu'on peut mesurer, et ce qu'on ne peut pas

| Voie de recommandation | Instrument | Limite |
|---|---|---|
| Classement Google (et aperçus IA de Google, qui citent surtout le top 10 organique) | Search Console | requêtes anonymisées absentes, délai de 2 à 3 jours |
| Index Bing (source de ChatGPT et de Copilot en recherche) | Bing Webmaster Tools, IndexNow | mêmes remarques ; IndexNow signale mais ne garantit rien |
| Visite venue d'un assistant (clic sur une source) | canal « ia » dans l'attribution | beaucoup de réponses ne contiennent aucun lien cliquable ; certains clics n'envoient pas de référent |
| Mention dans une réponse (sans clic) | panel de questions | échantillon, réponses variables, relevé manuel |
| Passages des robots IA sur le site | journaux d'accès du serveur | dans la campagne, les journaux n'étaient pas lisibles par la session : impossible de compter les visites des robots IA |

Prérequis de la phase 0 (voir `09-procedure-autonome.md`) : demander l'accès aux journaux du serveur
et à Search Console AVANT la refonte. La campagne a fait l'audit sans pouvoir compter les robots IA.

## 2. Search Console

### 2.1 Mise en place

1. Propriété de type domaine (`sc-domain:exemple.org`) : elle regroupe http, https, www et tous les
   sous-domaines. Vérification par DNS.
2. Pour l'automatisation : un compte de service Google, ajouté comme utilisateur de la propriété
   (propriétaire si l'on veut aussi soumettre des sitemaps). Le chemin de sa clé JSON vient d'une
   variable d'environnement, jamais du dépôt (exemple : `GSC_SERVICE_ACCOUNT`).
3. Portées OAuth : `https://www.googleapis.com/auth/webmasters.readonly` pour lire ;
   `https://www.googleapis.com/auth/webmasters` pour soumettre un sitemap (celle qu'utilise le script
   `scripts/gsc-submit-sitemaps.py` de la campagne, branché en fin de déploiement).
4. Compléter avec Bing Webmaster Tools (la clé IndexNow y est générée) : c'est l'index que lisent
   ChatGPT en recherche et Copilot.

### 2.2 Les données à tirer (API `searchanalytics.query`)

Requête de base, sur 90 jours, par couple requête et page :

```json
{
  "startDate": "2026-07-10",
  "endDate": "2026-10-09",
  "dimensions": ["query", "page"],
  "rowLimit": 25000,
  "startRow": 0
}
```

Paginer avec `startRow` jusqu'à épuisement. Autres découpages utiles : `["page"]` (vue par page),
`["country"]` (marché réel de chaque langue), `["device"]`, `["date"]` (courbe). Un filtre
`dimensionFilterGroups` sur `page` (« contient /fr/ ») isole une langue. Les requêtes d'analyse
complètes sont dans `templates/gsc-queries.md`.

Un export par langue a servi de fiche de travail dans la campagne
(`handoff/GEO-2026-10/requetes/<langue>.md`), avec trois sections : totaux, vue par page (les 8
meilleures requêtes avec impressions et position), top 40 des requêtes. Plus une synthèse thématique
(requêtes contenant « midi », « accorder une guitare », « basse », « violon », « ukulélé ») et le
tableau « pages avec au moins 100 impressions et CTR sous 1 % ». C'est ce découpage qui a désigné les
pages à réécrire.

### 2.3 Lire les chiffres sans se tromper

1. **Les totaux ne se recoupent pas.** L'audit donne 735 clics et 21 094 impressions sur 90 jours pour
   la propriété ; l'export par requête et page n'en retrouve que 134 clics et 11 457 impressions
   (période identique). Cause connue côté Google : les requêtes anonymisées (trop rares) n'apparaissent
   pas dans les lignes de requête mais comptent dans les totaux de la propriété. Ne comparez que des
   chiffres de même nature.
2. **Comparer sur 90 jours glissants** (ou 28 jours pour réactivité), et sur la même durée, contre la
   mesure de départ. Le mois calendaire déforme (nombre de jours, week-ends, saisonnalité scolaire pour
   un site musical).
3. **Un jeune domaine monte en dents de scie.** Repère de la campagne : impressions moyennes par jour
   de 11 (mi-juillet) à 94 (début août), 211 (fin août), 225 (début septembre) ; position moyenne
   dégradée vers 58 à 66 à la mi-août, remontée vers 30 à 38 début septembre. Une baisse de position
   moyenne est parfois la conséquence de nouvelles impressions sur des requêtes lointaines, pas d'une
   perte.
4. **Séparer la marque et le reste.** La requête « jam jam » (marque) avait 35 impressions en position
   7,7 avec 5 clics (CTR 14,3 %) : elle ne dit rien du référencement des besoins.
5. **Fiches par langue.** Les langues peu concurrencées ont des chiffres faibles en volume ; lisez
   les positions et les clics relatifs (le japonais : 33 clics pour 314 impressions).

### 2.4 CTR par position

Ne vous fiez pas à une courbe de CTR du marché : calculez la vôtre. Regroupez les lignes
requête-page par tranche de position (1-3, 4-7, 8-10, 11-20, 21-50) et calculez clics / impressions
pour chaque tranche. Exemples de la campagne, qui justifient la réécriture de titres :

| Requête / page | Impressions | Position | Clics | CTR |
|---|---|---|---|---|
| accordeur basse en ligne (`/fr/accordeur-basse/`) | 679 | 9,0 | 6 | 0,9 % |
| accordeur violon en ligne (`/fr/accordeur-violon/`) | 290 | 12,2 | 0 | 0,0 % |
| accordeur mandoline en ligne gratuit | 94 | 9,0 | 0 | 0,0 % |
| accordeur basse en ligne gratuit | 66 | 8,8 | 2 | 3,0 % |
| jam jam (marque) | 35 | 7,7 | 5 | 14,3 % |

Lecture : à position 9 le CTR est sous 1 %, alors qu'un titre qui contient « gratuit » et répond à la
requête atteint 3 %. La marge est dans le titre et la description, pas dans la position. Règle : toute
requête en position 5 à 20 avec des impressions et un CTR bas est candidate à une réécriture de titre
(voir `templates/gsc-queries.md`).

### 2.5 Sitemaps et indexation

1. Soumettre `sitemap-index.xml` ET chaque sitemap séparé (dans la campagne : celui des pages de
   conversion, `app/sitemap-convert.xml`) par l'API (`PUT .../sites/{site}/sitemaps/{url}`), puis lire
   l'état (`GET`) : erreurs, avertissements, dernier passage.
2. Contrôler le rapport « Pages » : pages exclues, redirections, « découverte, actuellement non
   indexée ».
3. Vérifier qu'aucun sitemap n'est bloqué par `robots.txt` (incident de la campagne, voir
   `08-pieges-et-incidents.md`).
4. L'API Google Indexing n'est pas la bonne voie (hors usage officiel); le sitemap avec `lastmod` fiable
   est la voie officielle.

## 3. Le canal « assistants IA » dans l'attribution

### 3.1 Le problème

Quand un assistant cite votre page et que le lecteur clique, deux cas : le navigateur envoie un
référent (`chatgpt.com`) ou non (lien ouvert avec `noreferrer`, appli mobile). ChatGPT ajoute en outre
un paramètre `utm_source=chatgpt.com` à certains liens. Autre difficulté : si le conversion se fait
dans une application (ici la web app sous `/app/`), le visiteur arrive de VOTRE site, donc le
référent vu par l'application est le site lui-même et l'origine est perdue.

### 3.2 Architecture retenue dans la campagne

```
assistant IA --clic--> page du site --clic sur un lien /app/--> application web
                       (le site lit le référent               (l'application lit ?ref= et
                        et l'ajoute en ?ref=)                  garde l'hôte, une seule fois)
```

1. **Le site** (script `src/scripts/app-referrer.ts`) lit, sur la page COURANTE seulement, l'hôte nu du
   référent externe (jamais le chemin ni la requête) et un éventuel `utm_source` de l'URL d'arrivée.
   Il les ajoute aux liens `/app/` de cette page sous la forme `?ref=chatgpt.com`. Il n'écrase jamais
   les `utm_*` que le site pose lui-même sur ses boutons (`utm_source=site`).
2. **Aucune écriture sur l'appareil côté site** : ni cookie, ni `sessionStorage`, ni `localStorage`.
   Raison : la politique de confidentialité du site dit « aucune mesure d'audience sur ce site ». Une
   première version stockait l'origine dans `sessionStorage` ; elle a été corrigée avant déploiement
   (voir `08-pieges-et-incidents.md`). Conséquence assumée : si le visiteur parcourt plusieurs pages
   avant de cliquer vers l'application, l'origine est perdue. On accepte ce biais de sous-comptage
   plutôt que d'écrire sur l'appareil d'un visiteur qui n'a pas consenti.
3. **L'application** (`webapp/src/lib/acquisition.ts`) enregistre le « premier contact » une seule
   fois (`localStorage.jamAcq`, immuable) avec : les `utm_*`, l'HÔTE nu du référent (jamais l'URL
   complète), le chemin d'atterrissage sans requête, et une provenance résumée dans une énumération
   fermée (`seo_tool`, `blog`, `landing`, `direct`, `share_link`, `friend_link`, `play_store`).
4. **Règles de confiance de `ref=`** : l'hôte relayé n'est cru que si le vrai référent est vide ou est le
   site lui-même (un référent externe réel prime toujours) et seulement s'il est un nom d'hôte valide
   (expression régulière stricte, 120 caractères au plus).
5. **Détection de l'assistant** : une liste d'hôtes et une fonction pure.

```ts
export const AI_ASSISTANT_HOSTS = [
  'chatgpt.com', 'chat.openai.com', 'perplexity.ai', 'gemini.google.com',
  'copilot.microsoft.com', 'claude.ai',
] as const;

/** Vrai si `host` est un assistant IA de la liste, ou l'un de ses sous-domaines. */
export function isAiAssistantHost(host) {
  if (!host) return false;
  const h = host.trim().toLowerCase().replace(/\.$/, '');
  return AI_ASSISTANT_HOSTS.some((d) => h === d || h.endsWith(`.${d}`));
}

// `utm_source` nus parfois posés à la place de l'hôte (utm_source=perplexity)
const AI_UTM_NAMES = ['chatgpt', 'openai', 'perplexity', 'gemini', 'copilot', 'claude'];
```

   `isAiAcquisition(a)` est vrai si l'hôte du référent est un assistant, ou si `utm_source` est un
   assistant (hôte ou nom nu). Le test vérifie « pas de faux suffixe » (un hôte qui se termine par
   `chatgpt.com.evil.example` ne passe pas).
6. **Pas de nouvelle valeur dans l'énumération** : le canal IA n'ajoute pas de valeur à `entry`, donc pas
   de migration de base de données. On l'analyse par `referrer_host` dans les évènements d'acquisition
   (le visiteur reste classé `landing`). C'est une décision de la campagne.

Hôtes à envisager en plus si vous voulez les mesurer (absents de la liste de la campagne, à vérifier
avant ajout) : `chat.deepseek.com`, `chat.mistral.ai`. Revoir la liste chaque trimestre : les assistants
changent de domaine.

### 3.3 Pourquoi le RGPD a dicté cette forme

1. Le site promet : aucun traceur tiers, aucun cookie publicitaire ou d'analyse, valeurs stockées
   strictement nécessaires seulement. Écrire une provenance sur l'appareil à l'arrivée sur le site
   contredirait cette promesse (la campagne a corrigé ce défaut avant déploiement : voir `08`).
2. On ne garde que l'hôte (jamais l'URL complète, qui porte chemins, termes de recherche et parfois
   des jetons) et le chemin d'atterrissage sans requête.
3. La mesure ne bloque jamais le démarrage de l'application : navigation privée, quota plein,
   stockage refusé, tout est avalé.
4. Toute évolution (nouvelle donnée collectée, nouveau flux) passe par la politique de confidentialité
   (la campagne a reformulé la mention « provenance de l'installation » dans la politique en 8
   langues).

### 3.4 Pour un autre site

1. Décidez ce que votre politique autorise AVANT de coder (cookie, stockage, rien).
2. Si vous avez un site vitrine et une application sur le même domaine : relayez l'hôte du référent en
   paramètre d'URL, sans stockage.
3. Si vous n'avez qu'un site : lisez `document.referrer` et `utm_source` à l'arrivée dans votre outil
   de mesure respectueux (ou dans les journaux serveur) et classez avec la liste d'hôtes.
4. Testez : référent vide, référent externe réel prioritaire, hôte invalide, faux suffixe,
   sous-domaine.
5. Documentez qu'une partie des visites venues des assistants est invisible : le panel (§4) comble ce
   manque.

## 4. Le panel mensuel de questions

### 4.1 Objectif

Savoir, besoin par besoin et langue par langue, si les assistants citent le produit, à quel rang, avec
quelle URL, avec quelle exactitude, et qui ils citent à la place. Le panel est l'unique instrument qui
voit les mentions sans clic.

### 4.2 Protocole

- **Assistants** : ChatGPT (recherche activée), Gemini, Perplexity (mode par défaut), Microsoft
  Copilot, Claude (recherche web activée), plus Google AI Overviews (recherche Google ordinaire,
  navigation privée, région de la langue : google.fr, google.es, google.de...). Ajouter DeepSeek si
  votre public l'utilise.
- **Conditions** : navigation privée ou compte sans historique, mémoire et personnalisation
  désactivées, une conversation neuve par question. Région ou VPN alignés sur la langue quand c'est
  possible.
- **Répétitions** : poser **chaque question 5 fois**, dans 5 conversations distinctes. Les réponses
  varient d'un tirage à l'autre; une seule passe ne dit rien. (La campagne avait fixé 3 répétitions
  comme minimum; 5 donne une fréquence plus stable.) Noter « cité » si le produit apparaît au moins 1
  fois sur 5 et consigner le nombre (0/5 à 5/5).
- **Ne jamais** nommer le produit dans la question, ni orienter l'assistant, ni lui demander de retenir
  quoi que ce soit : cela fausse la mesure et n'a aucun effet sur les autres utilisateurs.
- **Qui** : un humain avec les comptes. Un agent peut préparer les grilles, consolider les relevés et
  rédiger l'analyse, mais les assistants demandent souvent une connexion.

### 4.3 Grille de relevé

Une ligne par (date, assistant, langue, question). Fichier mensuel CSV à séparateur `;`
(`panel/AAAA-MM.csv` dans la campagne).

| Colonne | Contenu |
|---|---|
| date | AAAA-MM-JJ |
| assistant | ChatGPT / Gemini / Perplexity / Copilot / Claude / AIO |
| langue | en, fr, es... |
| id | identifiant de la question (ex. `TUN-fr-2`) |
| cite | oui / non |
| nb_sur_5 | 0 à 5 |
| rang | position dans la liste de recommandations (1 = premier cité), vide si absent |
| url_citee | URL du produit citée ou liée (vide si nom sans lien) |
| exact | oui / non : ce que l'assistant dit du produit est-il juste ? (noter l'erreur sinon) |
| concurrents | outils cités, dans l'ordre |
| sources | domaines et URL sources affichés par l'assistant |
| note | remarque libre |

La colonne **sources** nourrit la liste de prospection des articles « meilleurs outils » (voir
`06-hors-site.md`, §8) : c'est la valeur secondaire la plus importante du panel.

### 4.4 Les questions

Identifiants par besoin (campagne) : `TUN` accordeur, `NIC` accordeur d'instrument de niche, `PNO`
piano en ligne, `MID` clavier MIDI, `DET` détection d'accords, `SBK` carnet de chansons, `CNV`
conversion de fichiers, `API` API, `MET` métronome, `SCL` gammes, `BRD` marque. Trois questions par
besoin en en/fr/es/de, une dans les six autres langues. Les questions sont formulées comme un
utilisateur (« Quel accordeur de guitare en ligne gratuit avec le micro me conseilles-tu ? »), jamais
comme une requête de mots-clés. Modèle adaptable : `templates/panel-questions.md`.

Question de marque, chaque mois, en deux langues : « Qu'est-ce que [NOM] ([domaine]) ? ». On y relève
surtout l'**exactitude** (plateformes, bêta, chiffres) et la confusion avec les homonymes. Pour Jam
Jam : Jamn, jam.dev, Cookie Jam, jamm.

### 4.5 Volume et cadence

- Mensuel : 10 besoins x 3 questions x 4 langues (en, fr, es, de) x 6 assistants = 720 relevés, chacun
  répété. C'est lourd : prévoir une **version courte**, la PREMIÈRE question de chaque besoin
  (240 relevés), et la version complète un mois sur trois.
- Trimestriel (janvier, avril, juillet, octobre) pour les langues restantes (it, pt, nl, pl, ja, ko).
- Première semaine du mois, pour comparer des mois comparables.

### 4.6 Tableaux de synthèse à tenir

**Ligne de base** (à remplir au premier relevé) : nombre d'assistants sur 6 qui citent le produit au
moins une fois sur les questions du besoin.

| Besoin | en | fr | es | de | it | pt | nl | pl | ja | ko |
|---|---|---|---|---|---|---|---|---|---|---|
| TUN accordeur | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 |
| NIC niche | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 | /6 |
| (un besoin par ligne) | | | | | | | | | | |
| BRD marque | /6 | /6 | | | | | | | | |

**Concurrents les plus cités** (top 5 par besoin, toutes langues) et **sources les plus citées**
(domaines, toutes questions). Un relevé antérieur sur un protocole différent (ici 5 requêtes en août :
absent partout, marque comprise) n'est pas comparable : le dire dans le tableau.

### 4.7 Lire le panel

1. Une mention sans lien vaut déjà quelque chose (mention de marque), mais l'URL citée dit quelle page
   fait le travail : si c'est la page d'accueil et pas la page du besoin, la page du besoin est mal
   positionnée ou illisible.
2. Une mention inexacte est une priorité : corriger la source (fiche d'annuaire, `llms.txt`, page du
   site) plutôt que « se plaindre » à l'assistant.
3. Les concurrents cités et leurs sources disent où être présent (voir `06-hors-site.md`).
4. Ne concluez rien d'un seul mois : les réponses bougent, et la part des sources varie fortement d'un
   mois à l'autre selon les études citées dans `RECHERCHE.md`.

## 5. Indicateurs et objectifs

| Indicateur | Source | Cadence | Objectif de la campagne |
|---|---|---|---|
| Liens internes sans slash final | `check-trailing-slash` | à chaque déploiement | 0 |
| URL du sitemap avec `lastmod` | `page-dates-check` | à chaque déploiement | 100 % |
| Pages avec `Organization` + `sameAs` + `@id` | `geo-inventory.py` | à chaque déploiement | 100 % des pages indexables |
| Bloc « En bref » sur outils et accordeurs | inventaire | à chaque déploiement | 100 %, 10 langues |
| Descriptions <= 160 caractères | `check-seo-meta --strict` | à chaque déploiement | 100 % des familles mesurées |
| Erreurs de sitemap dans GSC | API sitemaps | après déploiement | 0 |
| Clics, impressions, CTR, position | GSC | hebdomadaire | tendance à la hausse |
| CTR des requêtes de niche | GSC | mensuelle | plus de 3 % à 4-8 semaines |
| Visites `ref` assistants IA | analytique de l'application | mensuelle | non nul, croissant |
| Taux de citation du panel (besoin x langue) | panel | mensuelle / trimestrielle | croissant |
| Exactitude des mentions | panel, colonne `exact` | mensuelle | 100 % |
| Core Web Vitals par famille de pages | PageSpeed / CrUX | mensuelle | pas de dégradation |

## 6. Cadence

**Chaque semaine (30 minutes)** : GSC clics, impressions, position moyenne sur 28 jours ; pages
nouvelles indexées ; erreurs de sitemap ; erreurs d'indexation. Rien d'autre : une lecture trop
fréquente pousse à retoucher des pages pour du bruit.

**Chaque mois (une demi-journée)** : relevé du panel (version courte ou complète), export GSC par
langue, comparaison avec la ligne de base sur 90 jours, liste des requêtes en position 5 à 20 à CTR
bas (réécritures de titres), tableau de prospection mis à jour avec les sources, rapport d'une page.

**Chaque trimestre** : panel des langues restantes, revue des hôtes d'assistants du canal « ia »,
revue de la liste des comparaisons si des pages « alternatives » existent, relecture des faits publiés
(chiffres, plateformes, prix) contre le produit.

## 7. Attentes réalistes de délai

Ces ordres de grandeur viennent des documents de la campagne et des repères publics; aucun n'est une
promesse.

| Événement | Délai | Appui |
|---|---|---|
| Notification IndexNow acceptée par Bing, Yandex, Naver, Seznam | immédiate (code HTTP 200), la prise en compte par le moteur se compte en jours | `ETAT.md` : 1 090 URL acceptées au déploiement |
| Google relit un sitemap soumis | au prochain passage de Google (délai non mesuré par la campagne) | `ETAT.md` : l'erreur historique du sitemap de conversions « disparaîtra au prochain passage de Google » |
| Indexation des nouvelles pages | de l'ordre de quelques jours à quelques semaines (estimation, non mesurée par la campagne) | le relevé de base du panel a été planifié 2 à 4 semaines après le déploiement, le temps de l'indexation |
| Effet sur CTR et positions des titres réécrits | 4 à 8 semaines | objectif du plan : CTR niche supérieur à 3 % à 4-8 semaines |
| Effet d'un domaine neuf | trois mois pour passer de 11 à environ 225 impressions par jour | repère GSC de septembre 2026 |
| Mentions dans les assistants (mémoire des modèles) | mois | `RECHERCHE.md` : voie « mémoire du modèle », lente (mois) mais durable |
| Mentions via la recherche en direct des assistants | semaines, dès que la page est indexée et bien classée | `RECHERCHE.md` : les moteurs récupèrent des passages |
| Effet d'une mention hors-site (fiche, vidéo, liste) sur le panel | plusieurs relevés mensuels | cadence du panel |

Erreurs à éviter : conclure à l'échec au bout d'une semaine ; changer la date d'une page sans
changement de contenu pour « forcer » la relecture (voir `08-pieges-et-incidents.md`) ; relancer des
soumissions d'URL à répétition.

## 8. Format du rapport de suivi (phase 8)

Une page, toujours le même plan :

1. **Résumé** : trois phrases (ce qui a bougé, ce qui n'a pas bougé, la décision proposée).
2. **GSC** : clics, impressions, CTR, position sur 90 jours contre la base ; par langue.
3. **Pages gagnantes et perdantes** : cinq de chaque, avec la requête dominante.
4. **Réécritures proposées** : requêtes en position 5 à 20 à CTR bas, titre actuel et titre proposé.
5. **Panel** : tableau besoin x langue, citations nouvelles ou perdues, mentions inexactes.
6. **Canal « ia »** : visites par hôte d'assistant, avec l'avertissement de sous-comptage.
7. **Hors-site** : actions faites, mentions obtenues, prochaines actions.
8. **Questions pour l'humain** : décisions en attente (comptes personnels, juridique, publication).
