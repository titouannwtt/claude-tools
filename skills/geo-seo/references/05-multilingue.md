# 05. Refonte multilingue (10 langues)

Ce fichier explique comment refondre un site pour qu'il soit recommandé dans plusieurs langues sans
jamais publier une page à moitié traduite. Il s'appuie sur la campagne menée sur jam-jam.org (exemple
travaillé) : anglais à la racine, puis fr, es, de, it, pt, nl, pl, ja, ko, avec 560 URL datées du même
jour, toutes présentes dans les 10 langues.

Les chemins cités sont ceux du dépôt du site (Astro, rendu statique). Sur un autre site, gardez le
principe et adaptez les noms. Pour la mécanique de `hreflang` en elle-même (balises, sitemap,
réciprocité), voir aussi `03-technique.md`, §5.

## 1. Pourquoi faire les langues, et dans quel ordre de priorité

Les langues ne pèsent pas le même poids. Mesure Search Console sur 90 jours (audit de la campagne,
10 juillet au 9 octobre 2026), clics et impressions par langue :

| Langue | Clics | Impressions | Lecture |
|---|---|---|---|
| en (racine) | 311 | 8 725 | volume, mais requêtes génériques très concurrencées |
| fr | 171 | 5 397 | marché d'origine |
| es | 118 | 4 002 | forte demande sur les accordeurs |
| de | 43 | 1 369 | requêtes très précises (« guitalele stimmen online ») |
| ja | 33 | 314 | peu d'impressions, mais clics proportionnellement élevés |
| it | 14 | 695 | |
| pl | 14 | 194 | |
| pt | 12 | 222 | |
| ko | 6 | 188 | |
| nl | 3 | 206 | |

Les langues peu concurrencées (ja, pl, nl, ko) se classent vite si la page est bonne, et chaque langue a
son propre vocabulaire de requêtes : on ne traduit pas un titre, on le reconstruit (voir §5).

Règle de cadrage : si le mandat dit « toutes les langues du site », la liste des langues est un
livrable de la phase 0 (voir `09-procedure-autonome.md`), pas une décision prise en cours de route.

## 2. Architecture des catalogues : un fichier par langue

### Ce que la campagne a trouvé

Le site avait deux gros dictionnaires `Record<Locale, Dict>` : `src/i18n/ui.ts` (interface) et
`src/i18n/seo.ts` (contenu SEO). Quatre langues (fr, en, es, de) vivaient dans `seo.ts` (965 Ko), les
six autres avaient chacune leur fichier (`seo.it.ts`, `seo.pt.ts`, `seo.nl.ts`, `seo.pl.ts`,
`seo.ja.ts`, `seo.ko.ts`, et les `ui.<langue>.ts` correspondants). C'est un défaut de conception :
deux agents qui traduisent es et de écrivent dans le même fichier.

### Ce que la campagne a ajouté

Pour les nouvelles pages et articles, un dossier `src/i18n/geo/` avec deux fichiers par langue :

```
src/i18n/geo/
  index.ts          assemble { ...pages.<langue>, ...blog.<langue> } par langue
  pages.en.ts  pages.fr.ts  pages.es.ts  ...  pages.ko.ts   (pages outils, glossaire, à propos)
  blog.en.ts   blog.fr.ts   blog.es.ts   ...  blog.ko.ts    (articles de référence)
```

Le lecteur de textes (`useSeoT`) consulte ces catalogues APRÈS `seo*.ts` : une clé qui existe déjà
dans l'ancien catalogue y reste prioritaire. Avantages : les 10 agents de traduction écrivent chacun
dans leurs fichiers, jamais dans le même ; l'ajout d'une langue n'oblige pas à ouvrir un fichier de
900 Ko.

### Convention de nommage des clés

Une clé = `<famille>.<identifiant>.<champ>`. Exemples réels :

| Clé | Contenu |
|---|---|
| `tool.clavier-midi.brief` | bloc « En bref » de la page |
| `post.note-frequencies.s1h` | titre de la section 1 d'un article |
| `glossary.a440.def` / `.more` / `.example` | définition, développement, exemple d'un terme |
| `about.publisherForm` | forme juridique de l'éditeur (à traduire, ja/ko l'avaient oubliée) |
| `install.tool.<slug>.*` | encart d'installation propre à la page |

Le préfixe sert à la disponibilité calculée (§3) : il doit regrouper TOUTES les clés d'une page.

### Règle d'or

Un seul agent par fichier de catalogue, à tout moment. Si deux langues partagent un fichier, soit on
sépare le fichier avant de lancer les agents, soit on sérialise leurs PR (voir §4, piège de
`seo.ts`).

## 3. La disponibilité calculée : jamais d'anglais dans une page traduite

### Le défaut à éviter

Une clé de traduction manquante est servie en repli, donc en anglais, au milieu d'une page allemande.
Pour Google, c'est une page « de » dont le contenu est anglais : qualité faible, risque de page
considérée comme doublon de la version anglaise. Pour un assistant IA, c'est un passage qui ne
correspond pas à la langue de la question, donc non cité. Pour le visiteur, c'est une impression de
site bâclé.

### Le principe

Une page n'est PUBLIÉE dans une langue que si TOUTES ses clés existent dans le catalogue de cette
langue. L'anglais est la référence : les clés requises d'une page sont toutes les clés anglaises qui
commencent par son préfixe. La disponibilité n'est pas tenue à la main dans un registre (la campagne
l'avait fait d'abord, puis a supprimé le registre) : elle est calculée à chaque build.

Code de la campagne (`src/data/geo-locales.ts`, abrégé) :

```ts
const PAGE_PREFIXES: Record<string, string> = {
  'clavier-midi': 'tool.clavier-midi.',
  'glossaire': 'glossary.',
  'a-propos': 'about.',
  'blog/note-frequencies': 'post.note-frequencies.',
  // ...
};

function requiredKeys(prefix: string): string[] {
  // Les clés `install.<préfixe>…` (encart d'installation propre à la page) comptent aussi.
  return Object.keys(geo.en).filter((k) => k.startsWith(prefix) || k.startsWith(`install.${prefix}`));
}

/** Clés manquantes d'une page dans une langue (vide = page complète). */
export function geoMissingKeys(path: string, locale: Locale): string[] {
  const prefix = PAGE_PREFIXES[path];
  if (!prefix) return [];
  return requiredKeys(prefix).filter((k) => !(k in geo[locale]));
}

export const GEO_PAGE_LOCALES: Record<string, readonly Locale[]> = Object.fromEntries(
  Object.keys(PAGE_PREFIXES).map((path) => [path, LOCALES.filter((l) => geoMissingKeys(path, l).length === 0)]),
);
```

### Qui consomme cette liste

Tout ce qui propose ou génère une autre langue passe par une seule fonction (`localesForPath`) :

1. les `getStaticPaths` des routes : une langue absente n'est pas construite, donc il n'y a pas de
   page, pas d'URL, pas de 404 annoncé ;
2. les balises `hreflang` (jamais d'alternate vers une page qui n'existe pas) ;
3. le sélecteur de langue du pied de page ;
4. la redirection automatique de la page racine vers la langue du navigateur ;
5. le sitemap, le `llms.txt` généré (bloc « versions localisées ») et le maillage interne (pied de
   page, index du blog filtré par langue disponible).

Le commentaire du code de la campagne explique pourquoi une seule fonction : une page légale annonçait
neuf traductions dont six n'avaient jamais été générées, le sélecteur menait à un 404 et la
redirection automatique y envoyait le visiteur sans qu'il clique, y compris sur la politique de
confidentialité. Règle générale : jamais deux listes de langues pour la même page.

### Effets à connaître

Une traduction complète fait apparaître la page au prochain build, sans toucher à aucune liste. Trois clés
oubliées sur 361 la retirent de cette langue, silencieusement. Une clé anglaise ajoutée après coup fait
perdre la page à toutes les autres langues tant qu'elles n'ont pas la clé.

Garde-fou nécessaire, car l'oubli est silencieux : un compte-rendu de build qui affiche, par page, le
nombre de langues publiées et les clés manquantes, et un contrôle de déploiement qui échoue si ce nombre
baisse ou si la cible (10 langues) n'est pas atteinte. Dans la campagne, la liste des 560 URL de `ETAT.md`
(« toutes présentes dans les 10 langues ») a servi de vérification finale.

## 4. Workflow de traduction par sous-agents

```
1. Contenu source fr + en écrit et relu (lots B, C, D de 09-procedure-autonome.md), puis GELÉ
2. Liste exacte des clés à traduire (fichier de clés)
3. Un agent par langue, une branche et une PR par langue, un fichier de catalogue par agent
4. Contrôles bloquants dans chaque PR
5. Relecture par un second agent sur échantillon (es, de, ja dans la campagne)
6. Fusion une langue après l'autre, puis build, QA visuelle, déploiement
```

Neuf PR séparées dans la campagne : #65 japonais, #66 polonais, #67 espagnol, #68 portugais (pt-BR), #69
allemand, #70 néerlandais, #71 italien, #72 coréen, #73 libellés des tableaux de référence dans les 10
langues. Volume par langue : 408 clés SEO (81 remplacées, 327 ajoutées, issues d'une liste établie avant le
lancement), les méta de l'accueil, 361 clés de `pages.<langue>.ts` et 263 clés de `blog.<langue>.ts`, soit
environ 1 000 clés.

### Le mandat d'un agent de traduction

Court, identique pour chaque langue : (1) le fichier à écrire et l'interdiction d'en toucher un autre ;
(2) les clés et la source anglaise (la source française aide pour le solfège) ; (3) les règles de
localisation de la langue (§5) ; (4) les requêtes réelles de la langue relevées dans Search Console (voir
`07-mesure.md`) pour construire titres et descriptions : « accordatore online, accordatore violoncello,
metronomo online » en it, « stemapparaat online, viool stemmen online » en nl, « afinador online, cifra » en
pt ; (5) les seuils de longueur ; (6) les contrôles à lancer, avec exigence du code de sortie 0 ;
(7) l'interdiction de modifier les registres partagés (`geo-locales.ts`, `page-dates.ts`).

### Contrôles bloquants

| Contrôle | Ce qu'il attrape | Où |
|---|---|---|
| Parité des clés | clé manquante ou inconnue, valeur vide ou non textuelle | `scripts/i18n-assemble.mjs --verifier`, `geoMissingKeys` |
| Marqueurs | `{n}` renommé ou perdu (afficherait « {nombre} »), double accolade `{{…}}` | `i18n-assemble.mjs` |
| Doublons de lots | même clé, deux textes différents | `i18n-assemble.mjs` |
| Non traduit | chaîne identique à l'anglais : signalée, pas refusée (nom propre, symbole d'accord) | `nonTraduites()` |
| Libellés de tableaux | une langue manquante fait échouer `astro build` (boucle de contrôle à l'import du module) | `src/data/tool-reference-labels.ts` |
| Tiret cadratin | le caractère U+2014, toutes langues | `scripts/check-em-dash.mjs` |
| Titres et descriptions | longueur selon l'écriture, titres uniques | `scripts/check-seo-meta.mjs --strict` |
| Chiffres | un chiffre produit qui diverge du code | `scripts/check-marketing-numbers.mjs` |
| Slash final | lien interne sans `/` dans un texte traduit | `scripts/check-trailing-slash.mjs` |
| Textes juridiques | parité de structure (§9) | `scripts/check-legal-parity.mjs` |

Le contrôle des libellés mérite d'être copié : le site n'a pas de vérification de types au build, donc le
module vérifie lui-même, à l'import, que chaque ligne a toutes les langues.

Seuils de `check-seo-meta` : titre en avertissement au-delà de 60 caractères latins (30 en ja/ko), en erreur
au-delà de 70 (35) ; description de 70 à 160 caractères latins (35 à 80 en ja/ko). Le français et l'allemand
dépassent facilement 160 : à écrire dans le mandat.

### Relecture sur échantillon

Un second agent, en lecture seule, reçoit 30 à 50 clés tirées au hasard et vérifie sens, terminologie de
l'app, notation, chiffres et ton, puis rend une liste de corrections. Un contrôle automatique ne lit pas le
polonais : la qualité du sens reste une relecture humaine ou un second agent.

### Pièges d'orchestration

1. **Deux langues dans un même fichier.** Les PR es (#67) et de (#69) modifient toutes deux `seo.ts` : les
   fusionner l'une après l'autre, en rebasant.
2. **Registres partagés.** `page-dates.ts` et `page-fingerprints.json` sont régénérés par
   `page-dates-check.mjs --write` : seul le coordinateur les régénère, sur le build final.
3. **Source modifiée pendant la traduction.** Une clé anglaise changée après le lancement rend les 8 PR
   incomplètes d'un coup (la disponibilité calculée retire la page). Geler la source avant le lot E.
4. **Descriptions préexistantes hors plage.** Plusieurs PR ont dû raccourcir des descriptions existantes que
   `check-seo-meta --strict` voyait : à prévoir dans le mandat.

## 5. Pièges de terminologie et de notation

### Règle générale

La terminologie vient de l'interface du produit, pas du traducteur. La campagne a dû aligner : « de :
Liederbuch partout (terme de l'app) », « pl : AI (terme de l'app) », « ja/ko : Premium comme nom de
l'offre ». Un site qui dit « carnet de chansons » dans l'app et « recueil » dans les pages SEO
désoriente l'utilisateur qui clique. Livrable utile : un glossaire par langue extrait du catalogue de
l'app, fourni à l'agent.

### Notation des notes

| Langue | Notation dans les textes | Remarque |
|---|---|---|
| fr | solfège : Do, Ré, Mi, Fa, Sol, La, Si | le tableau affiche aussi la lettre entre parenthèses |
| es | solfège : Do, Re, Mi, Fa, Sol, La, Si | pas d'accent sur Re |
| it | solfège : Do, Re, Mi, Fa, Sol, La, Si | |
| pt | solfège : Dó, Ré, Mi, Fá, Sol, Lá, Si | accents propres au portugais |
| en, nl, ja, ko | lettres C D E F G A B | ja et ko : lettres pour les accordeurs (choix de la campagne) |
| de, pl | lettres, avec le piège H/B ci-dessous | |

Le code de la campagne gère le solfège par une table `SOLFEGE` (fr, es, it, pt) et une fonction qui
remplace chaque lettre d'un gabarit (`E A D G` devient `Mi La Ré Sol` en français) : le gabarit
reste unique, la notation est appliquée à la sortie. Ne jamais faire retaper les notes à un
traducteur : les accordages viennent de données générées depuis le code du produit
(`src/data/tool-reference.json`, produit par `scripts/build-tool-reference.mjs`), et le fichier de
libellés ne porte que des noms.

Piège constaté : le cavaquinho portugais était écrit avec un accordage différent de celui du produit.
Correction de la campagne : « cavaquinho D5 A4 B4 E4 partout » (aligné sur le fichier d'accordages de
l'app, dans les 10 langues et dans `llms.txt`). Leçon : une valeur chiffrée d'une page traduite doit
sortir d'une source unique, jamais d'une saisie manuelle par langue.

### Le piège H/B en allemand et en polonais

En allemand et en polonais, B désigne le si bémol et H le si naturel. Un texte qui écrit « B » pour le
si naturel (usage anglais) est faux pour un lecteur allemand ou polonais. La campagne a constaté que
le produit ne sait pas afficher cette notation (lettres anglaises ou solfège seulement). Règles
retenues :

1. un contenu peut EXPLIQUER la différence, il ne doit jamais promettre que l'outil l'affiche ;
2. ouvrir un ticket produit ;
3. quand le produit l'implémente, recapturer les images de et pl (elles montraient B3 et B5) ;
4. en attendant, la branche `geo/notation-hb` (H = si, B = si bémol dans les accordages, gammes,
   capo, blocs d'articles, textes de et pl) est prête mais NON déployée à la date de la campagne,
   en attente de décision produit.

### Nombres, symboles, ponctuation

| Sujet | Règle |
|---|---|
| Virgule décimale | de, fr, es, it, pt, nl, pl écrivent « 82,41 Hz » ; en, ja, ko écrivent « 82.41 Hz ». Les tableaux générés doivent suivre la langue (la campagne a laissé « virgule décimale en nl » à arbitrer côté produit) |
| Séparateur de milliers | varie (espace insécable, point, virgule) : fixer une règle par langue et la tester dans les tableaux |
| Marque et offre | « Premium », « Jam Jam » ne se traduisent pas ; vérifier en ja/ko (corrigé en finitions) |
| Flèche et bouton | `&nbsp;→` après le libellé : sans espace insécable, la flèche tombe seule sur une ligne en allemand ou en néerlandais (corrigé en 2.34.2) |
| Dièse, bémol | ♯ et ♭ : les espaces visuels autour viennent de la police de secours, le texte est propre (reste connu) |
| Tiret cadratin | interdit dans toutes les langues (contrôle automatique) ; le demi-cadratin « – » reste valide pour les plages |
| Guillemets | propres à chaque langue (« » en fr, "" en en, 「」 en ja) ; ne pas laisser ceux de la source |

### Vocabulaire de requêtes par langue

Ne traduisez pas « tuner » mot à mot. Les mots que les utilisateurs tapent (relevés dans les
questions du panel et les requêtes Search Console de la campagne) :

| Langue | Accordeur | Exemple réel |
|---|---|---|
| fr | accordeur | accordeur basse en ligne |
| es | afinador | afinador de bajo online |
| de | Stimmgerät, stimmen | guitalele stimmen online |
| it | accordatore | accordatore violoncello online |
| pt | afinador | afinador de violão online |
| nl | stemapparaat, stemmen | viool stemmen online |
| pl | tuner | tuner gitarowy online |
| ja | チューナー, チューニング | バイオリン チューニング サイト |
| ko | 튜너, 조율 | 온라인 기타 튜너 |

Procédure : pour chaque langue, extraire de Search Console les 8 meilleures requêtes par page
(`handoff/GEO-2026-10/requetes/<langue>.md` dans la campagne), puis écrire le titre autour de la
requête dominante. Exemple de page : `/fr/accordeur-basse/` avait 679 impressions sur « accordeur
basse en ligne » en position 9,0 pour 6 clics ; le titre a été réécrit pour cette requête.

## 6. hreflang et x-default

### Règles appliquées sur le site

1. Toute page déclinée par langue porte un `<link rel="alternate" hreflang="xx">` pour chaque langue
   RÉELLEMENT publiée de cette page (donc issue de `localesForPath`), plus un `hreflang="x-default"`.
2. `x-default` pointe vers l'anglais (racine du site). Pas de `/en/` : l'anglais à la racine avec
   x-default est valide, il faut seulement vérifier la réciprocité (chaque page cite toutes les autres
   et elle-même).
3. Les codes sont ceux de la langue seule (`pt`, pas `pt-BR`), cohérents partout. L'audit a trouvé
   que le sitemap des pages de conversion utilisait `pt-BR` quand le reste du site utilisait `pt` :
   incohérence listée parmi les causes possibles de l'erreur Search Console de ce sitemap.
4. Une page qui n'existe qu'en anglais (page de retour d'authentification, 404) n'a aucun alternate.
5. L'attribut `html lang` est exact sur chaque page (vérifié par l'inventaire de la campagne).
6. Chaque URL canonique a un slash final et est la seule forme liée (voir `08-pieges-et-incidents.md`).

Mesure de la campagne (audit) : 932 pages à 11 alternates (10 langues et x-default).

### La redirection automatique vers la langue du visiteur

Le site redirige la page racine anglaise vers la langue du navigateur, une fois par session (drapeau
dans `sessionStorage`), en préférant d'abord le choix explicite enregistré par l'application, puis
`navigator.language`, puis une géolocalisation de l'IP par un service du site lui-même (aucun tiers).
Trois précautions :

1. le script est un `<script>` simple, externalisé par le build, pour passer une CSP stricte (les
   valeurs de build passent par des attributs `data-*` sur `<html>`) ;
2. la redirection ne vise QUE les langues disponibles pour cette page (sinon elle envoie le visiteur
   vers un 404) ;
3. les robots n'exécutent pas ce JavaScript : ils voient toujours l'anglais à la racine et découvrent
   les autres langues par hreflang et sitemap. Ne pas rediriger les robots côté serveur selon la
   langue : Google recommande d'éviter toute redirection automatique fondée sur la langue perçue.

## 7. Captures d'interface par langue

### La leçon de la QA

La QA visuelle finale a trouvé des pages traduites qui montraient des captures de l'interface en
français : une page espagnole avec un écran français est une incohérence que le visiteur et un
assistant qui lit les images relèvent. Règle : **jamais une capture française sur une page espagnole**.
Une capture appartient à une langue ; si la langue n'a pas la sienne, le repli est l'anglais, jamais
le français, sauf exception documentée.

### Mécanisme du site

Les captures sont des fichiers `src/assets/screenshots/web/<langue>/<nom>.webp`. Une fonction unique
les choisit :

```ts
// src/lib/web-shots.ts (abrégé)
const variants = import.meta.glob<ImageMetadata>('../assets/screenshots/web/*/*.webp', { eager: true, import: 'default' });

export function webShot(name: string, locale: string): ImageMetadata {
  const img = variants[`../assets/screenshots/web/${locale}/${name}.webp`]
    ?? variants[`../assets/screenshots/web/en/${name}.webp`]
    ?? legacy[name];            // ancienne capture française, seulement 3 noms
  if (!img) throw new Error(`web-shots : capture inconnue « ${name} »`);
  return img;
}
```

Ordre de repli : langue de la page, puis anglais, puis ancienne capture. Trois captures restent en
français et périmées (`melodie-tablature`, `diagrammes-piano`, `carnet-voix`) parce qu'elles montrent
des chansons du compte personnel du propriétaire : elles n'ont pas été refaites (confidentialité), ce
qui est une exception assumée et notée dans `ETAT.md`.

### Produire les captures

Scripts versionnés dans `scripts/captures-web/` (`capture.mjs`, `lib.mjs`, `compare-layout.mjs`).
Principes à reprendre :

1. **Même viewport pour toutes les langues** (1280 x 1100, facteur d'échelle 2, soit 2560 x 2200),
   thème clair, sortie WebP qualité 88 ; sinon les mises en page ne se comparent pas.
2. **Langue forcée** par le stockage local de l'application avant le chargement (`jamLang`), avec
   `locale` du contexte navigateur alignée.
3. **Couper la synchronisation des réglages** (requêtes de lecture et d'écriture du profil) pour que
   la langue du compte serveur n'écrase pas la langue forcée et qu'aucune écriture n'atteigne le
   compte de démonstration.
4. **Trouver les boutons par leur libellé traduit**, construit depuis les catalogues de l'application
   (le script cherche toutes les traductions dans la langue des clés dont le texte français est
   donné), pas depuis des sélecteurs de position.
5. **Entrée audio factice** pour l'accordeur et la détection (fichier WAV bouclé par le navigateur).
6. **Compte de démonstration** d'un store, jamais un compte personnel; identifiants en variables
   d'environnement, jamais dans le code.

Résultat de la campagne : les 6 écrans (tuner, clavier, détection, métronome, verrouillage de gamme,
détection d'accord) recapturés dans l'interface actuelle, en 10 langues (version 2.34.4).

### Défauts trouvés par la QA des captures traduites

| Défaut | Cause | Statut |
|---|---|---|
| Image `diagrammes-piano` de l'accueil ja en français | capture ancienne sans variante | à refaire |
| Section « Social » de l'accueil ja en anglais | clés manquantes dans le catalogue de l'accueil | à traduire |
| Image de la page métronome = écran Clavier | mauvais nom d'image associé | à corriger |
| Nom « AppleReviewer » visible sur les nouvelles captures | compte de revue utilisé pour les captures | à renommer ou masquer |
| Images de et pl avec B3 et B5 | notation H/B non affichable (§5) | après décision produit |

Recommandation (non faite par la campagne) : faire échouer l'inventaire quand une page non anglaise résout
une capture par repli, et localiser les `alt` des images (prévu au plan v2).

## 8. Contrôle de fuite de langue

Il y a deux fuites : du français dans une page traduite (le contenu source) et de l'anglais dans une
page traduite (la clé manquante). La disponibilité calculée (§3) supprime la seconde pour les pages
de la campagne ; les autres couches :

| Couche | Outil | Ce qu'il voit |
|---|---|---|
| 1. Parité du catalogue | `geoMissingKeys`, `i18n-assemble.mjs` | clé manquante |
| 2. Inventaire de build | `scripts/geo-inventory.py` | colonne `fr_words_on_non_fr` : compte de mots-outils français sur les pages non françaises ; `html_lang` ; hreflang ; `has_table` |
| 3. Parcours du build | QA intégrée sur le build final | 732 pages à 400 et 1280 px : 0 débordement, 0 clé brute affichée (une clé du type `tool.x.y` visible), 0 image cassée |
| 4. Revue visuelle | captures 5 largeurs, clair et sombre, sur un échantillon par langue | texte étranger, image étrangère, coupures de mots |

L'inventaire de la campagne mesurait les mots français sur les pages non françaises (« aucune fuite de
français mesurée ») mais pas l'anglais sur les pages non anglaises, la fuite la plus probable : étendre
la méthode avec des mots-outils anglais (the, and, with, your, for) sur le texte de `<main>`. Lancer
l'inventaire avec `python3 -I` (dossier de build non fiable), voir `08-pieges-et-incidents.md`, A4.

Résidus réels de la campagne (`ETAT.md`) : section « Social » de l'accueil ja en anglais, quelques
captures en français. Trouvés par la QA visuelle, non par un contrôle automatique : garder la passe
visuelle même avec tous les contrôles verts.

## 9. Textes juridiques par langue : la parité

### Principe

Les documents juridiques n'obéissent pas à la liste des langues du site. Sur jam-jam.org ils existent en 8
langues (en, fr, es, de, it, pt, nl, pl), pas en ja ni ko : traduire un document juridique est un acte
juridique, pas une adaptation rédactionnelle, et le dépôt impose un protocole juridique avant d'y toucher.
Pour ja et ko, le pied de page renvoie vers la version anglaise (`legalHref`) et aucune page légale n'est
générée sous leur préfixe : une traduction non validée, ou une page anglaise sous une URL japonaise, serait
pire que le renvoi explicite. Le français fait foi ; les autres versions sont des traductions et le disent.

### Le contrôle `scripts/check-legal-parity.mjs`

Le risque est la clause qui manque dans une langue (paragraphe sauté, puce de moins dans la liste des droits
RGPD, lien de contact perdu). Le script compare chaque langue au français :

1. **Structure** : même nombre de blocs, même suite de types (titre, paragraphe, liste), mêmes tailles de
   listes ;
2. **Liens** : même suite de `href` ;
3. **Marqueur de politique** : `<!-- policy-version: … -->` exactement une fois par langue ;
4. **Chiffres** : mêmes nombres au même endroit (durées, plafonds) ; dates de mise à jour hors champ.

Il a un `--self-test` qui injecte un défaut et prouve qu'il rougit. Limite assumée : il compte des blocs, il
ne lit pas le polonais ; une clause édulcorée reste invisible, cette moitié est une relecture humaine.

### Règles de travail

1. Un changement juridique est un seul lot qui touche TOUTES les langues juridiques et passe la parité
   (campagne : politique de confidentialité mise à jour en 8 langues dans une seule PR, version 2.34.3,
   datée du 11 octobre 2026).
2. Lire le protocole juridique du dépôt avant de modifier ; les questions de fond (provenance du site
   d'origine, séparation automatique des pistes) vont au propriétaire.
3. La forme juridique de l'éditeur sur la page « À propos » (`about.publisherForm`) est une clé de contenu :
   ja et ko l'avaient oubliée.
4. Si le périmètre légal est plus petit que celui des langues du site, l'écrire en phase 0 : « ja et ko hors
   périmètre légal, repli vers l'anglais ».
