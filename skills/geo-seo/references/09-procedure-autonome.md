# 09. Procédure autonome complète

Procédure qu'un agent suit, de bout en bout, pour refondre le référencement (Google, Bing, assistants IA)
d'un site qu'on lui donne. Elle est tirée de la campagne de jam-jam.org (octobre 2026), dont le plan
v2 prévaut sur le plan v1. Chaque phase donne : entrées, travail, sorties, critères de réussite,
points d'arrêt humain et routage des sous-agents.

Les mécanismes techniques cités (slash final, sitemap, robots.txt, JSON-LD, `llms.txt`, IndexNow) sont
détaillés dans `03-technique.md` ; l'audit dans `02-audit-methode.md`.

Principe d'autonomie : continuer jusqu'aux critères de réussite; ne poser une question que si une
décision est structurellement indécidable sans l'humain. Les points d'arrêt de ce fichier sont de
vraies décisions (légal, compte personnel, publication), pas des confirmations de confort.

## Vue d'ensemble

| Phase | Nom | Livrable principal | Agents |
|---|---|---|---|
| 0 | Cadrage | section « Cadrage » de `ETAT.md` | l'agent principal |
| 1 | Recherche | `RECHERCHE.md` | analyse (jugement), reconnaissance |
| 2 | Audit mesuré | `AUDIT.md`, fiches de requêtes | reconnaissance bon marché, analyse |
| 3 | Plan priorisé, relu, plan v2 | `PLAN.md` (v2) | architecte, deux relecteurs |
| 4 | Lots d'implémentation A à I | PR par lot, code et contenu | implémentation, traduction, relecture |
| 5 | QA visuelle intégrée | captures, mesures, corrections | QA visuelle |
| 6 | Déploiement, vérification, soumission | release en ligne, soumissions | agent principal |
| 7 | Consignation | `ETAT.md`, liste des URL | agent principal |
| 8 | Suivi à 2-4 semaines | rapport de suivi | analyse |

Dossier de travail : `handoff/<CAMPAGNE>/` dans le dépôt du site, avec `RECHERCHE.md`, `AUDIT.md`,
`PLAN.md`, `ETAT.md`, `HORS-SITE.md`, `PANEL.md`, `requetes/<langue>.md`, `captures/`. L'état
d'avancement vit dans `ETAT.md` : c'est la vérité courante, lue en premier à chaque reprise.

---

## Phase 0. Cadrage

**Entrées** : l'adresse du site, le dépôt, le mandat (objectif, langues, contraintes).

**Travail** :

1. **Périmètre.** Familles de pages (accueil, outils, produits, blog, légal, pages générées par une
   application), pages hors périmètre (pages d'un autre chantier : dans la campagne, les pages de
   conversion appartenaient à un autre chantier; la campagne n'en touchait que le sitemap et les
   métadonnées de découverte, en prévenant la session concernée).
2. **Langues.** Liste exacte des langues, langue racine, langues sans texte juridique (voir
   `05-multilingue.md`).
3. **Accès** (liste à constituer et à tester AVANT de planifier) :

| Accès | Utile pour | Si absent |
|---|---|---|
| Dépôt du site en écriture (branches, PR) | tout | arrêt |
| Procédure et script de déploiement officiels | phase 6 | arrêt |
| Search Console (propriété domaine, compte de service) | audit, soumission, suivi | audit sans mesure : demander |
| Bing Webmaster Tools, clé IndexNow | soumission Bing | IndexNow seul |
| Journaux d'accès du serveur | visites des robots IA | le dire dans l'audit |
| Analytique de l'application | canal « ia » | mesure par le panel seul |
| Comptes personnels (annuaires, YouTube, Reddit, Wikidata, stores) | lot I | préparer seulement |

4. **Contraintes légales et de marque** : politique de confidentialité (ce qu'on a le droit de
   collecter), CGU, publicité comparative, droit d'auteur (aucune parole de chanson, aucun contenu
   protégé), mentions obligatoires, chiffres validés (table unique), formules interdites, tutoiement ou
   vouvoiement, usage du mot « IA », règles typographiques (pas de tiret cadratin).
5. **Contraintes techniques** : CSP stricte (pas de script ni de style inline), site statique ou non,
   outils de build, procédure de déploiement unique, budgets de performance.
6. **Coordination** : chantiers en cours d'autres personnes ou sessions, fichiers sensibles, verrous,
   déclaration du chantier dans le registre prévu (dans la campagne : un identifiant de chantier
   externe déclaré dans le fichier de coordination).
7. **Worktree dédié** : travailler dans un arbre de travail séparé, pas dans l'arbre partagé; vérifier
   qu'il est à jour de la branche principale.

**Sorties** : section « Cadrage » dans `ETAT.md` (périmètre, langues, accès testés, contraintes,
chantiers voisins).

**Critères de réussite** : chaque accès est testé par une commande réelle (pas supposé); la liste des
langues et le périmètre sont écrits.

**Arrêt humain** : accès indispensable manquant; périmètre légal incertain (que peut-on collecter,
comparer, publier); mandat contradictoire. Ne PAS s'arrêter pour le style, l'ordre des lots ou le choix
des outils.

**Routage** : l'agent principal; une reconnaissance bon marché peut tester les accès.

---

## Phase 1. Recherche

**Entrées** : le mandat, toute source donnée par l'humain (une vidéo, un article), le web.

**Travail** : établir ce qui marche vraiment, en confrontant les affirmations aux sources primaires.
Dans la campagne, la source était une vidéo marketing : ses affirmations ont été confrontées à la
recherche publiée (étude GEO de Princeton, études Ahrefs et Semrush, documentation Google et OpenAI).
Chaque affirmation reçoit un verdict : **prouvé** (documentation officielle ou étude contrôlée),
**probable** (corrélations convergentes), **surestimé** ou **folklore**.

Contenu attendu de `RECHERCHE.md` :

1. Tableau « affirmation / verdict / commentaire ».
2. Les mécanismes en clair : trois voies de recommandation (mémoire du modèle, recherche en direct,
   entité) et la contrainte technique (aucun robot IA n'exécute le JavaScript : seul le HTML statique
   compte).
3. Leviers retenus, classés par impact et coût.
4. « À ne pas faire » (texte caché, pages en masse, dates trafiquées, faux avis, API non officielle).
5. Sources avec adresses.

**Sorties** : `RECHERCHE.md` (une à deux pages). **Critères** : aucune affirmation sans verdict; les
sources sont datées; le folklore est nommé comme tel.

**Arrêt humain** : aucun, sauf si une source payante ou privée est nécessaire.

**Routage** : un agent d'analyse (jugement) pour la synthèse; une reconnaissance bon marché pour
rassembler les sources.

---

## Phase 2. Audit mesuré

**Entrées** : le site en ligne et son build, Search Console, `RECHERCHE.md`.

**Travail** : mesurer, pas supposer. Quatre mesures :

1. **Inventaire du build** : script qui produit une ligne par page HTML (modèle : `geo-inventory.py`,
   lancé avec `python3 -I` sur un dossier de build non fiable) avec titre et longueur, description et
   longueur, h1, canonical, robots, hreflang, types de JSON-LD, présence de `sameAs` et du logo, dates,
   nombre de mots, liens internes, mots étrangers sur les pages non natives, présence d'un tableau et
   d'une date visible.
2. **Liens internes** : taux de redirection (liens sans slash, vers des pages redirigées).
3. **Search Console sur 90 jours** : clics, impressions, CTR, position, par langue et par page, plus
   les requêtes par page (voir `07-mesure.md`).
4. **Requêtes réelles** avec les user-agents des robots IA : robots.txt, sitemap, `llms.txt`, pages
   publiques (200 ou non).

**Sorties** : `AUDIT.md` avec : inventaire des pages par famille; « ce qu'on fait bien »; « ce qu'on
fait mal » classé par gravité (technique, entité, contenu, hors-site); mesures clés de Search Console.
Exemple de mesures de la campagne : 972 pages indexables, 44 % de liens internes en redirection, 0 sitemap
avec `lastmod`, 547 descriptions trop longues, `Organization` sans `sameAs`, 3 mentions externes, marque à
72 impressions sur 90 jours. Fiches `requetes/<langue>.md` (totaux, vue par page, top 40, synthèse par
thème, pages à 100 impressions et CTR sous 1 %).

**Critères** : chaque défaut a un nombre et une manière de le remesurer; les défauts sont classés;
chaque langue a sa fiche de requêtes.

**Arrêt humain** : découverte d'une infraction légale (un texte publié contraire à la loi ou à la
politique) : remonter.

**Routage** : reconnaissance bon marché pour l'inventaire et les requêtes HTTP (tâche mécanique et
entièrement spécifiée); analyse pour classer les défauts et lire Search Console.

---

## Phase 3. Plan priorisé, relu par deux experts, plan v2

**Entrées** : `RECHERCHE.md`, `AUDIT.md`.

**Travail** :

1. **Plan v1** : règles transverses (chiffres validés, vérification dans le code, pas de contenu
   protégé, pas de tiret cadratin, CSP, pipeline de traduction, un seul agent par fichier, déploiement
   par le script officiel, QA avant fusion), puis les lots A à I (phase 4), l'ordre d'exécution, les
   critères de réussite mesurables.
2. **Relecture par deux experts indépendants, en lecture seule** :
   - un expert **marketing IA / GEO** : arbitre le contenu (quelles pages garder, fusionner, retirer; ce
     qui relève du folklore);
   - un expert **métier du site** (dans la campagne : outils musicaux) : vérifie l'exactitude de chaque
     promesse contre le code.
3. **Plan v2** : une section « Révision » qui regroupe les arbitrages et PRIME sur les lots quand elle les
   contredit.

Exemples de ce que les relectures ont changé dans la campagne :

| Relecteur | Décision |
|---|---|
| Métier | « Vingt instruments » est faux, c'est 21; « pentatoniques » est faux, il n'y en a qu'une; la notation H/B ne s'affiche pas dans l'outil; la basse n'a pas de 6 cordes; l'import de photo n'est pas réservé au mobile; les progressions d'accords n'ont aucun outil web |
| Marketing IA | garder `/clavier-midi` (une URL par intention); retirer `/progressions-accords` comme page outil (remplacée par un article); fusionner trois articles d'accordage dans les pages d'accordeur existantes; réduire le glossaire à environ 20 termes approfondis; reporter les pages « alternatives à X » (risque juridique); abandonner l'API Google Indexing; blocs « En bref » avec données propres à chaque page |

**Sorties** : `PLAN.md` v2. **Critères** : chaque lot a un objectif, des fichiers, un contrôle de
sortie; les critères de réussite sont chiffrés (0 lien sans slash, 100 % des URL avec `lastmod`,
`Organization` avec `sameAs` sur 100 % des pages indexables, bloc « En bref » sur 100 % des outils,
descriptions de 160 caractères au plus, 7 pages et 10 articles dans les 10 langues, QA 5 largeurs,
sitemaps soumis); les arbitrages sont lisibles.

**Arrêt humain** : décisions juridiques (comparaison, collecte de données, conservation); arbitrage de
marque contradictoire avec le mandat; tout ce qui engage un budget.

**Routage** : agent d'architecture (jugement élevé) pour le plan; deux agents de relecture (analyse, lecture
seule), lancés EN PARALLÈLE avec le même plan et des consignes distinctes.

---

## Phase 4. Lots d'implémentation

Une branche et une PR par lot; travail délégué toujours par PR dans un worktree dédié; le coordinateur
relit le diff réel et fusionne (un agent ne fusionne jamais sa propre PR). Incrémenter la version du site
à chaque lot. Avant de pousser : `build && push`. Tenir `ETAT.md` à jour à la fin de chaque lot.

### Ordre

1. Lot A seul, en premier (il touche les liens, le sitemap et le gabarit de toutes les pages).
2. En parallèle : rédaction fr/en des lots B, C, D dans des fichiers séparés; lot F (mesure).
3. Lot E (traductions) quand B, C, D sont gelés.
4. Lots G, H, I après le déploiement ou en parallèle selon les dépendances.

### Table des lots

| Lot | Contenu | Exemple de la campagne | Contrôles de sortie |
|---|---|---|---|
| A. Technique | slash final partout (helper unique), sitemap avec `lastmod` réel et tous les sitemaps déclarés, graphe d'entité JSON-LD (`Organization`, `WebSite`, `WebPage`, `Person` fondateur, logiciel), métadonnées (canonical, titres uniques, longueurs), robots.txt (robots IA, `Allow` du sitemap), `llms.txt` généré au build, inventaire versionné | PR #60 | `check-trailing-slash`, `page-dates-check`, `check-seo-meta`, `geo-inventory.py`, build |
| B. Pages existantes | bloc « En bref » de 40 à 60 mots avec faits chiffrés propres à la page, tableaux de référence générés du code, « Comment faire », FAQ, date visible et éditeur, titres et descriptions réécrits sur les requêtes en position 5 à 20, maillage | PR #64 : 31 pages fr/en | `check-marketing-numbers`, `check-seo-meta`, `check-em-dash`, vérification contre le code |
| C. Pages de besoin | une page par besoin non couvert, même gabarit (H1 = besoin, En bref, étapes, différences vérifiées, FAQ, appel vers l'application), plus « À propos » et glossaire | PR #63 : 6 pages | idem + une URL par intention, aucune parole de chanson |
| D. Articles de référence | articles citables : réponse directe en tête, sections autonomes, tableau, FAQ, lien vers l'outil | PR #62 : 6 articles | idem + `check-inline-style` |
| E. Traductions | un agent par langue, une PR par langue, contrôles bloquants (voir `05-multilingue.md`) | PR #65 à #73 | `i18n-assemble`, parité, libellés, `check-seo-meta --strict` |
| F. Mesure | canal « assistants IA » dans l'attribution, panel de questions, relevé Search Console automatisé | PR site #61 et PR application #782 | tests unitaires de l'attribution; relecture de la politique |
| G. Soumission | script d'envoi des sitemaps par l'API Search Console, IndexNow étendu à tous les sitemaps | commit du lot G | exécution en `--dry-run` puis réelle |
| H. Fiches de stores | relire chaque fiche contre le brief (chiffres, besoins manquants), publier le texte seul | PR application #783 : 38 fiches Google Play | pas de binaire; publication en production : arrêt humain |
| I. Hors-site | `HORS-SITE.md` : textes prêts à coller, jamais exécutés par l'agent | voir `06-hors-site.md` | relecture d'exactitude |

### Règles transverses de chaque lot

1. Chaque affirmation de fonction est vérifiée dans le code avant d'être écrite; la plateforme est
   dite (web, Android, iOS bêta, mobile seulement).
2. Chiffres seulement ceux de la table validée; contrôle automatique vert.
3. Aucune parole de chanson ni extrait protégé; exemples génériques ou du domaine public.
4. Pas de texte caché, pas de consignes adressées aux IA dans les pages.
5. Pas de `<style>` ni de script inline (CSP).
6. Les dates visibles et `lastmod` suivent le texte visible (voir `08-pieges-et-incidents.md`, B3).
7. Les pages d'un autre chantier ne sont pas touchées.

### Structure d'une PR de lot

- Titre : `<CAMPAGNE> lot X : <résumé>`.
- Corps : liste des fichiers, ce que le lot change, contrôles lancés avec leur résultat (codes de
  sortie), questions ouvertes.
- Critères d'acceptation vérifiés par le coordinateur, pas par l'auteur.
- Pas de mention d'outil d'IA dans les messages de commit ni les PR publiés.

### Mandat type d'un sous-agent d'implémentation

```
Objectif : <lot X, en une phrase>.
Fichiers à écrire : <liste>. Fichiers interdits : <liste, dont registres partagés>.
Sources : <fichiers de contenu fr/en, AUDIT.md, PLAN.md section lot X>.
Règles : <règles transverses ci-dessus, tutoiement, chiffres validés>.
Contrôles à lancer et à passer : <liste de scripts>; exiger le code de sortie, pas le résumé.
Livrable : branche + PR; rapport court (changements, contrôles, points non résolus).
Interdits : aucune fusion, aucun déploiement, aucune écriture dans la base de production.
```

**Arrêt humain pendant la phase 4** : toute modification d'un texte juridique (protocole juridique du
dépôt avant d'y toucher); toute nouvelle collecte de données; la publication en production d'une
fiche de store; tout compte à créer.

**Routage** : architecte pour le gabarit des nouvelles pages et le schéma des clés; implémentation
(effort moyen) pour A à D et F; traduction (un agent par langue) pour E; relecture indépendante (lecture
seule) sur chaque PR de A, F et H et sur un échantillon de E. Un agent « mécanique » ne reçoit que des
tâches entièrement spécifiées; une tâche de conception échoue chez lui.

---

## Phase 5. QA visuelle intégrée sur le build final

Décision de la campagne : UNE passe intégrée sur le build final avant le déploiement (rien ne part en
production sans le script de déploiement), plutôt qu'une QA par lot; puis une contre-QA ciblée sur les
correctifs.

**Entrées** : le build final (tous les lots fusionnés), la liste des pages (nouvelles, enrichies, un
échantillon par famille et par langue).

**Travail** (Playwright, navigateur sans interface, sous la CSP de production) :

1. **Passe programmatique sur toutes les pages** (campagne : 732 pages à 400 et 1280 px) :
   - débordement horizontal (`scrollWidth` = `clientWidth`);
   - aucune clé de traduction brute affichée;
   - aucune image cassée;
   - erreurs de console et violations de CSP.
2. **Passe visuelle sur un échantillon** : 10 pages représentatives x 5 largeurs (400, 768, 1024, 1280,
   1920 px) x 2 thèmes (clair et sombre), captures plein écran, que l'agent de QA LIT (une capture non lue
   ne prouve rien).
3. **Mesures** : CLS (seuil 0,1), poids transféré, bouton d'arrêt des animations, décor masqué aux
   lecteurs d'écran (voir `check-vitrine-qa.mjs`).
4. **Points de regard** : tableaux défilants (indice de défilement), cartes alignées, libellés qui ne
   tombent pas en bout de ligne, polices CJK, captures d'interface dans la bonne langue, dièse et bémol,
   flèches de bouton.
5. **Correctifs** par un agent d'implémentation, nouvelle version; **contre-QA ciblée** des seules pages
   corrigées.

**Sorties** : dossiers `captures/qa-finale/` et `captures/qa-correctifs/`; liste des défauts et de leur
état dans `ETAT.md` (corrigés, restes connus non bloquants).

**Critères** : 0 débordement, 0 clé brute, 0 image cassée sur la passe programmatique; chaque défaut
visuel majeur corrigé ou consigné avec une raison.

**Arrêt humain** : aucun, sauf un défaut qui exige une décision de marque (nom de compte visible sur une
capture, par exemple).

**Routage** : agent de QA visuelle à effort moyen au minimum (la lecture visuelle ne se délègue pas à un
agent bon marché); rapport seulement (pas de correctif par le même agent).

---

## Phase 6. Déploiement, vérification en ligne, soumission

**Entrées** : branche principale à jour et verte, build local qui passe.

**Travail** :

1. **Déployer par le script officiel seulement** (construit dans une release horodatée, lance les
   contrôles, bascule atomiquement). Jamais de build ou copie manuelle vers la production.
2. **Contrôles bloquants du script** (campagne) : tiret cadratin, endpoints de la page développeurs,
   styles en ligne, slash final, dates des pages, métadonnées SEO en `--strict`, qualité mesurée au
   navigateur (console, débordement, poids, CLS).
3. **Vérification EN LIGNE avec des user-agents de robots IA** (et pas seulement un navigateur) :

```sh
for UA in "Googlebot" "Bingbot" "GPTBot" "OAI-SearchBot" "ChatGPT-User" "ClaudeBot" "PerplexityBot"; do
  for URL in "https://[DOMAINE]/robots.txt" "https://[DOMAINE]/sitemap-index.xml" \
             "https://[DOMAINE]/llms.txt" "https://[DOMAINE]/[NOUVELLE-PAGE]/"; do
    printf '%s %s ' "$UA" "$URL"
    curl -s -o /dev/null -w '%{http_code} %{content_type}\n' -A "$UA" "$URL"
  done
done
```

   Attendus : 200 partout, `llms.txt` en `text/plain`, `robots.txt` identique à celui du dépôt (si un CDN
   est devant le site, vérifier qu'il ne le réécrit pas), nouvelles pages en 200, `sameAs` présent dans le
   JSON-LD, les sitemaps déclarés répondent 200 aux robots. Dans la campagne cette vérification a trouvé le
   403 du sitemap des conversions (`08`, B6).
4. **Soumission** pour TOUTES les langues :
   - sitemaps vers Search Console par l'API (`sitemap-index.xml` et chaque sitemap séparé), puis lire
     l'état : 0 erreur, dernier passage;
   - IndexNow pour toutes les URL des sitemaps (campagne : 1 090 URL acceptées, code 200) : Bing, Yandex,
     Naver, Seznam;
   - Bing Webmaster Tools : vérifier la propriété et l'index;
   - PAS l'API Google Indexing.
5. **Compter par langue** que les URL soumises couvrent toutes les langues (campagne : 560 URL datées du
   jour, présentes dans les 10 langues); un décompte par langue dans `ETAT.md`.

**Sorties** : release en ligne, journal de déploiement (identifiant de release, nombre d'URL), état des
soumissions.

**Critères** : tous les contrôles verts; vérification robots sans 403 ni 5xx; soumissions acceptées.

**Arrêt humain** : une publication sur un store en production; une modification de la configuration
du serveur ou du CDN qui dépasse le dépôt (la campagne a ouvert un ticket pour l'exception du serveur
et l'a fait avec le chantier voisin).

**Routage** : agent principal; reconnaissance bon marché pour la boucle de vérification HTTP.

---

## Phase 7. Consignation

**Travail** : tenir `ETAT.md` comme une vérité courante, pas un journal. Sections de la campagne :

1. **Fait** : lot par lot, avec PR, chiffres et décisions.
2. **Restes connus** (mineurs, non bloquants).
3. **Décisions** (API Indexing abandonnée, canal IA sans nouvelle valeur d'énuméré, QA intégrée).
4. **Questions ouvertes pour l'humain** (dossier juridique, pages comparatives).
5. **Déploiement** : identifiant de release, résultat des contrôles, soumissions, vérification en ligne.
6. **URL créées ou modifiées** : liste par page, avec « NOUVELLE » ou « modifiée », le nombre de langues
   (« 10 langues »), la date de `lastmod`.
7. **Suite** : événements postérieurs datés (corrections du serveur, textes juridiques, captures).

Autres sorties durables : note de mémoire du projet (mécanismes ajoutés qu'il faut respecter dans tout
futur lot, restes pour l'humain); ligne dans la file d'attente de l'humain pour les actions du lot I;
tâches du suivi planifiées dans l'outil de pilotage du projet (pas de planification dans un dossier
temporaire de session : elle disparaît).

**Critères** : un agent qui reprend le travail comprend l'état en lisant `ETAT.md` seul.

---

## Phase 8. Suivi à 2-4 semaines

**Entrées** : le déploiement du jour J, les soumissions, la ligne de base.

**Travail** : voir `07-mesure.md` (cadence, panel, indicateurs).

1. **Semaine 2 à 4** : premier relevé du panel (ligne de base), comparaison Search Console contre le
   départ sur 28 puis 90 jours, état des sitemaps, pages indexées.
2. **Rapport d'une page** : résumé, GSC par langue, pages gagnantes et perdantes, réécritures de titres
   proposées pour les requêtes en position 5 à 20 à CTR bas, panel, canal « ia », hors-site, questions
   pour l'humain.
3. **Corrections** : titres et descriptions des pages à CTR bas (nouveau lot court, mêmes contrôles),
   corrections d'exactitude signalées par le panel.
4. **Objectif du plan** : à 4-8 semaines, CTR des requêtes de niche supérieur à 3 % et positions moyennes en
   hausse; mentions des assistants en mois.

**Arrêt humain** : mentions inexactes persistantes dans un assistant (correction à la source = souvent
une fiche externe tenue par un compte personnel); décision d'étendre le hors-site.

**Routage** : analyse (effort moyen) pour le rapport; reconnaissance bon marché pour l'export des
données; le panel lui-même est fait par un humain avec ses comptes.

---

## Récapitulatif : quand s'arrêter pour demander à l'humain

| Situation | Pourquoi | Ce que l'agent prépare |
|---|---|---|
| Décision juridique (texte légal, collecte de données, conservation, publicité comparative, droit d'auteur) | engage l'éditeur; un défaut est une infraction, pas une coquille | question précise, options, texte proposé, traduction à parité |
| Création ou usage d'un compte personnel (annuaires, YouTube, Reddit, Wikidata, Product Hunt) | seul l'humain peut agir sous son nom; faux comptes interdits | textes prêts à coller, ordre d'exécution, ligne dans sa file d'attente |
| Publication en production sur un store (Google Play, App Store) | irréversible, validation écrite exigée | fiches rédigées, vérifiées, déposées en brouillon ou en test interne |
| Accès manquant (Search Console, déploiement, journaux) | impossible de mesurer ou de publier | liste des accès avec la commande de test |
| Modification de l'infrastructure hors dépôt (serveur, CDN, pare-feu) | hors du périmètre du dépôt, risque d'incident | bloc de configuration prêt et testé en local |
| Arbitrage produit (fonction promise mais absente, ex. notation H/B) | décision de produit | ticket produit, contenu qui ne promet pas la fonction |
| Contradiction entre le mandat et l'état réel du produit | risque de contenu faux | liste des écarts avec preuve dans le code |

## Récapitulatif : routage des sous-agents

| Besoin | Classe d'agent | Effort | Remarque |
|---|---|---|---|
| Inventaires, requêtes HTTP, comptages, tests d'accès | reconnaissance / exécution mécanique | bas | tâches entièrement spécifiées seulement |
| Synthèse de recherche, diagnostic de Search Console, rapport de suivi | analyse | moyen | lecture seule |
| Plan, schéma des clés, arbitrages inter-systèmes, problème qui a résisté | architecte | élevé | lecture seule; jamais le niveau maximal |
| Implémentation des lots, traduction (un agent par langue), correctifs | implémentation | moyen | un agent par fichier, une PR par lot |
| Relecture indépendante (exactitude, vie privée, diff réel) | relecture | moyen | lecture seule, deux relecteurs de profils différents pour le plan |
| QA visuelle (captures lues, mesures) | QA visuelle | moyen au minimum | rapport seulement |

Règles de délégation : l'objectif précis, le périmètre limité, un livrable court; ne pas créer d'agent
quand une tâche simple se fait directement; lancer des agents en parallèle seulement pour des travaux
indépendants (fichiers distincts); ne monter d'un cran d'effort qu'après un échec constaté, pas par
précaution.

## Erreurs de procédure à éviter

1. Planifier avant d'avoir mesuré (la moitié des défauts de la campagne n'étaient visibles qu'à la mesure).
2. Écrire un contenu sans le vérifier dans le code.
3. Traduire avant de geler la source.
4. Faire la QA lot par lot au lieu d'une passe finale intégrée, puis oublier la contre-QA.
5. Déployer sans vérifier avec les user-agents des robots IA.
6. Soumettre seulement l'anglais.
7. Oublier de consigner : la reprise après interruption dépend d'`ETAT.md`.
8. Promettre une mesure en jours : l'indexation prend des jours à des semaines, les mentions des
   assistants des mois.
