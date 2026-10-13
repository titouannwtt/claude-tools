# 08. Pièges et incidents de la campagne

Chaque entrée suit le même plan : **Symptôme**, **Cause**, **Correctif**, **Garde-fou** (ce qui empêche
le retour). Les entrées viennent de l'audit, du plan, de `ETAT.md` et de l'historique Git de la
campagne de jam-jam.org (octobre 2026). Quand le détail exact n'a pas pu être relu dans les documents,
l'entrée le dit.

## Les garde-fous mécaniques créés ou utilisés

Une règle qui n'est pas vérifiée par une machine finit oubliée. Tableau des contrôles, avec la date de
création (la campagne a créé ceux du 2026-10-10 ; les autres existaient et ont servi) :

| Script | Rôle | Créé | Bloquant au déploiement |
|---|---|---|---|
| `scripts/check-trailing-slash.mjs` | 0 lien interne sans slash final vers une page HTML (exclut `/app`, `/api`, `/_astro`, fichiers) | campagne, lot A | oui |
| `scripts/check-seo-meta.mjs` | titres et descriptions : longueurs selon l'écriture, titres uniques ; `--strict` échoue à la moindre erreur | campagne, lot A | oui (`--strict`, depuis #74) |
| `scripts/page-dates-check.mjs` (+ `page-dates-init.mjs`) | `lastmod` du sitemap et `dateModified` ne changent que si le texte visible change (empreinte du `<main>`) ; une page sans date fait échouer le build | campagne, lot A | oui |
| `scripts/geo-inventory.py` | inventaire CSV de chaque page : titre, description, h1, canonical, hreflang, types JSON-LD, mots français sur pages non françaises, dates, liens | campagne, lot A | non (mesure avant déploiement) |
| `scripts/gsc-submit-sitemaps.py` | soumet les sitemaps à Search Console par l'API et affiche erreurs et avertissements | campagne, lot G | non (échec toléré) |
| `src/data/geo-locales.ts` | disponibilité calculée des pages par langue | campagne | par construction |
| garde à l'import de `src/data/tool-reference-labels.ts` | une langue manquante dans un libellé de tableau casse `astro build` | campagne, #73 | oui (le build échoue) |
| `scripts/build-tool-reference.mjs` | génère `tool-reference.json` depuis le code de l'application (accordages, gammes, accords) | campagne, lot B | non (génération) |
| `scripts/check-em-dash.mjs` | aucun tiret cadratin dans les textes publiés (dictionnaires, pages, `llms.ts`) ; `--self-test` | existant | oui |
| `scripts/check-inline-style.mjs` | CSP stricte (`style-src 'self'`) : aucun attribut `style=` dans le site publié (le navigateur l'ignorerait sans rien dire) | existant | oui |
| `scripts/check-marketing-numbers.mjs` | recompte les catalogues depuis les données de l'application et compare aux chiffres publiés ; échoue aussi sur les chiffres périmés connus | existant | oui |
| `scripts/check-legal-parity.mjs` | parité de structure, liens, marqueur de politique et chiffres entre langues juridiques | existant | oui |
| `scripts/i18n-assemble.mjs` | valide un lot traduit (clés, marqueurs, double accolade, tiret) avant d'en faire un module | existant | oui |
| `scripts/check-vitrine-qa.mjs` | pages témoins en 390 et 1440 px sous la CSP de production : console, débordement horizontal, poids, CLS, animations | existant | oui |
| `scripts/check-developers-endpoints.mjs` | la page développeurs liste tous les chemins du contrat OpenAPI (tolérant à l'absence du dépôt voisin) | existant | oui |

Tous les contrôles ont un mode `--self-test` qui injecte un témoin et prouve que le contrôle rougit
(un contrôle qui ne sait pas échouer ne protège de rien). Le script de déploiement `deploy-web.sh`
construit dans un dossier de release horodaté, lance ces contrôles sur le build, et ne bascule le site
que s'ils passent (un build raté laisse la version précédente en ligne).

---

## A. Build, déploiement, Git

### A1. Commit poussé sur `main` avec un build cassé

- **Symptôme** : une minute après un commit de lot (`d950961`, nouvelles pages dans le pied de page
  et `llms.txt`), un second commit (`62374d0`) corrige « build cassé par d950961 ».
- **Cause** : dans `src/i18n/llms.ts`, deux chaînes JavaScript entre guillemets contenaient un vrai
  retour à la ligne (une phrase coupée « at the latest 72 hours after upload / if it was never
  processed ») au lieu de `\n`. Le fichier ne se compile plus. Le commit a été poussé sans avoir
  construit le site.
- **Correctif** : retours à la ligne échappés dans les chaînes (`62374d0`).
- **Garde-fou** : enchaîner TOUJOURS `npm run build && git push` (le `&&` interdit le push si le build
  échoue). Production non touchée parce que le déploiement passe par `deploy-web.sh` qui construit
  d'abord dans une release à part : `main` cassé ≠ site cassé, mais le coordinateur suivant hérite
  d'une branche rouge. Ajouter au mandat de chaque agent : « construire avant de pousser, exiger code
  de sortie 0 ».

### A2. Build nu qui part en production

- **Symptôme** (historique du projet, ayant motivé le script) : un `npm run build` isolé redéployait
  la vitrine en détruisant l'application embarquée sous `/app/` (bug du 12 juillet 2026).
- **Cause** : l'application (SPA) est copiée dans `public/app/` AVANT le build de la vitrine ; un
  build seul réutilise le dernier état présent.
- **Correctif et garde-fou** : un seul chemin de publication, `deploy-web.sh`, qui construit
  l'application, copie, construit la vitrine dans `releases/<horodatage>/`, lance les contrôles, puis
  bascule atomiquement. Règle écrite dans la documentation du projet : jamais de build ou de copie
  manuels vers la production.

### A3. Hook qui interdit `git stash`

- **Symptôme** : un agent veut mettre ses changements de côté pour reconstruire l'état propre et se
  voit refuser `git stash` (ou `git checkout`/`git restore` sur un répertoire) par un hook du projet.
- **Cause** : l'arbre de travail est partagé avec d'autres sessions (agents, humain). Un `stash` ou un
  `checkout` de répertoire emporterait aussi le travail non commité des autres, parfois irrécupérable.
- **Correctif** : travailler dans un worktree dédié, ne committer que ses propres fichiers, annuler
  des fichiers nommés explicitement, vérifier `git status` avant tout commit.
- **Garde-fou** : le hook `block-dir-revert.py` (refus des opérations de répertoire) plus la règle
  écrite dans les consignes agents du dépôt. Au mandat : « ne jamais stasher ». Le détail de l'incident
  précis de la campagne n'a pas été relu ici; la règle et le hook sont, eux, vérifiés.

### A4. `python -I` qui masque les modules

- **Symptôme** : un script Python lancé avec `-I` échoue avec `ModuleNotFoundError` pour un module
  pourtant installé (ou, inversement, fonctionne chez l'un et pas chez l'autre).
- **Cause** : `-I` (mode isolé) ignore les variables d'environnement `PYTHON*` et le répertoire de
  paquets de l'utilisateur, donc les paquets installés avec `pip --user` disparaissent. Le mode est
  voulu pour lire un dossier non fiable (`geo-inventory.py` demande `python3 -I`, car le dossier de
  build n'est pas du code de confiance), mais il casse un script qui a besoin de `requests` ou de
  `cryptography` installés hors du système.
- **Correctif** : réserver `-I` aux scripts qui lisent des données non fiables et n'ont que la
  bibliothèque standard ; pour les autres (soumission de sitemaps), utiliser un environnement virtuel
  dont on appelle l'interpréteur explicitement. Ne jamais lancer un interpréteur dans le dossier de
  données.
- **Garde-fou** : mettre la commande exacte (avec ou sans `-I`) dans l'en-tête du script, comme le fait
  `geo-inventory.py`. L'enchaînement exact de l'incident n'a pas pu être relu dans les documents.

### A5. Règle WAF réécrite en perdant ses champs

- **Symptôme** : après la mise à jour d'une règle de pare-feu par script, la règle perd des champs
  (commit `0eeee3d`, « Conserver les champs de la règle WAF lors de sa mise à jour »).
- **Cause** : l'API de mise à jour (PATCH) exige la définition complète de la règle, y compris les
  champs inchangés.
- **Correctif** : reconstruire le corps depuis la règle lue (sans `id`, `version`, `last_updated`),
  changer seulement l'expression, relire et comparer tous les champs après écriture.
- **Garde-fou** : mode `--dry-run`, relecture et assertion après écriture.

---

## B. Technique : indexation, sitemap, robots

### B1. Moitié des liens internes via une redirection 308

- **Symptôme** : 44 % des liens internes (17 770 sur 40 012) pointaient vers `/fr/tuner` au lieu de
  `/fr/tuner/` ; Google indexait les deux formes et partageait le signal (`/accordeur-basse` position
  62,7 contre `/accordeur-basse/` position 40,7) ; `/fr/clavier` en « Redirect error » dans GSC.
- **Cause** : le serveur redirige les adresses sans slash vers les adresses avec slash, mais les
  composants, dictionnaires, pied de page, fil d'Ariane et JSON-LD liaient la forme sans slash.
- **Correctif** : `trailingSlash: 'always'`, helper unique de construction d'URL localisée
  (`pageHref`), correction de tous les composants et dictionnaires : 0 lien sans slash sur 308 pages.
- **Garde-fou** : `check-trailing-slash.mjs` bloquant au déploiement, avec ses exclusions justifiées.

### B2. Sitemap sans `lastmod`

- **Symptôme** : aucune des 590 URL du sitemap n'avait de `lastmod`.
- **Cause** : le générateur ne savait pas quelle page avait changé.
- **Correctif** : registre `src/data/page-dates.ts` (une date par clé de page) ; `lastmod` et
  `dateModified` en sont tirés, jamais de la date du build.
- **Garde-fou** : `page-dates-check.mjs` (voir B3) ; ne jamais mettre la date du build en `lastmod` :
  Google cesse de faire confiance à un champ qui change partout à chaque déploiement.

### B3. Empreinte de date instable à cause des balises `<time>`

- **Symptôme** : à chaque redatation d'une page, l'empreinte du texte changeait, donc la page
  paraissait « modifiée » de nouveau au contrôle suivant, sans fin (commit `f5efe83`).
- **Cause** : l'empreinte hachait le texte visible de `<main>`, qui incluait la balise `<time>` portant
  la date « Mis à jour le... ». Écrire la nouvelle date changeait l'empreinte.
- **Correctif** : exclure `<time>` de l'empreinte (avec `script`, `style`, `svg`, `nav`, `footer`,
  `template`, `noscript`) ; option `--refingerprint` qui réécrit les empreintes sans toucher aux dates
  après un changement de la règle d'empreinte ; 44 clés redatées au 2026-10-10 parce que leur texte avait
  vraiment changé, 9 anciens articles gardant leur date d'origine.
- **Garde-fou** : `page-dates-check.mjs` en `--strict` signale un texte changé sans date changée ;
  `--write` ne redate que les clés dont le texte a changé. Règle : jamais de date changée sans texte
  changé (signal de fraude pour les moteurs).

### B4. `robots.txt` qui bloque le sitemap des conversions

- **Symptôme** : erreur Search Console sur `app/sitemap-convert.xml` depuis le 17 septembre.
- **Cause** : le fichier vit sous `/app/`, que `Disallow: /app/` interdit ; Google ne pouvait pas le lire.
  Le sitemap utilisait de plus `pt-BR` quand le reste du site utilise `pt`.
- **Correctif** : `Allow: /app/sitemap-convert.xml` dans CHAQUE bloc `User-agent` (la règle la plus
  longue l'emporte), plus les `Allow` des pages de conversion avant le `Disallow` général.
- **Garde-fou** : après chaque changement de `robots.txt`, relire l'état du sitemap par l'API et tester
  l'URL du sitemap avec le user-agent de Googlebot. Un `Disallow` sur un chemin qui contient un sitemap ou
  une page à indexer est un classique ; lister dans `robots.txt`, en commentaire daté, POURQUOI chaque
  règle existe (le fichier de la campagne le fait).
- **Piège voisin** : ne pas mettre `Disallow` sur une URL qu'on veut désindexer; un `Disallow` empêche le
  robot de lire l'en-tête `noindex`. C'est l'en-tête `X-Robots-Tag: noindex` qui désindexe, à condition de
  laisser le robot récupérer la page.

### B5. Sitemap non déclaré

- **Symptôme** : le sitemap des 380 pages de conversion n'apparaissait ni dans `sitemap-index.xml` ni
  dans `robots.txt`.
- **Cause** : généré par un autre module (la SPA, pré-rendu), oublié par le générateur du site.
- **Correctif** : déclaré dans l'index et par une ligne `Sitemap:` de `robots.txt` ; soumis par l'API.
- **Garde-fou** : `gsc-submit-sitemaps.py` liste les sitemaps à soumettre ; `submit-indexnow.sh` lit aussi
  le sitemap des conversions ; ajouter tout nouveau sitemap aux deux.

### B6. Filtre anti-bots du serveur : 403 sur le sitemap

- **Symptôme** : `/app/sitemap-convert.xml` répondait 403 aux robots IA, alors que les pages de conversion
  leur répondaient 200 (constaté après le déploiement avec des user-agents de robots IA).
- **Cause** : une règle anti-clonage du serveur (Caddy) sur `/app/*` refuse les robots, et le sitemap
  tombait dans le périmètre.
- **Correctif** : exception dans la configuration de sécurité (`deploy/security.caddy`), placée AVANT le
  filtre anti-clonage de `/app/*`, qui reste actif ailleurs ; le sitemap répond 200 à tous les robots.
- **Garde-fou** : vérification en ligne avec les user-agents des robots IA après CHAQUE déploiement
  (voir `09-procedure-autonome.md`, phase 6), pas seulement avec un navigateur ; une règle de sécurité
  doit lister ses exceptions pour les ressources d'indexation.

### B7. Autres défauts techniques de l'audit initial

| Défaut | Correctif |
|---|---|
| 547 descriptions au-delà de 160 caractères, 12 titres dupliqués (Feedback x6, Contact, Kontakt, Aviso legal), canonical de `/404.html` faux | réécriture + `check-seo-meta.mjs` ; seuils par écriture (latin, ja/ko) |
| `Organization` sans `sameAs` (490 pages), logo sur 10 seulement, aucun `@id`, aucun auteur réel | graphe d'entité relié par `@id` sur toutes les pages (`src/data/organization.ts`) |
| `llms.txt` écrit à la main, dérive (disait « Android, Web », ignorait la bêta iOS et la conversion) | généré au build depuis les registres de pages ; la prose seule reste dans `src/i18n/llms.ts` |
| API Google Indexing utilisée pour 412 URL | abandonnée : réservée aux offres d'emploi et aux diffusions en direct |
| Journaux d'accès illisibles pour la session | demander l'accès en phase 0 |

---

## C. Exactitude et juridique

### C1. Le texte du site contredit le code

- **Symptôme** : l'audit par un expert métier et la relecture contre le code ont trouvé des
  affirmations fausses : « Vingt instruments » alors que le catalogue en compte 21 ; « pentatoniques »
  au pluriel alors que le code n'a que la pentatonique mineure et le blues ; la notation H/B promise
  alors que l'outil ne l'affiche pas ; une basse à 6 cordes alors que seuls 4 et 5 cordes existent ;
  ukulélé en ré inexistant ; import de photo décrit comme « mobile seulement » alors que le web le fait
  côté serveur; progressions d'accords décrites comme outil web alors que le générateur est mobile
  seulement ; métronome 30 à 300 BPM ; capodastre pour 9 instruments ; durée de conservation des
  fichiers audio (suppression « au plus tard 72 h » ; calage du karaoké fait sur le serveur et non sur
  l'appareil).
- **Cause** : textes écrits d'après des documents (brief, anciennes pages) qui avaient dérivé du code.
  Chaque vérification doit se faire dans le code, pas dans la spécification.
- **Correctif** : lot B (corrections d'exactitude) et corrections de `llms.txt` et de l'article karaoké ;
  tableaux d'accordages, de gammes et d'accords GÉNÉRÉS depuis le code de l'application
  (`build-tool-reference.mjs`).
- **Garde-fou** : `check-marketing-numbers.mjs` recompte les catalogues depuis les données et rougit si un
  chiffre publié diverge, si un chiffre périmé réapparaît, ou si une constante a disparu du code. Règle de
  méthode : « chaque affirmation de fonction est vérifiée dans le code avant d'être écrite, et la
  plateforme est dite ». Limite : le contrôle n'énumère que ce qu'on lui déclare et ne voit pas une
  suppression non déclarée.
- **Écart constaté à l'écriture de ce fichier** : la prose de `llms.ts` annonce encore un métronome de
  40 à 240 BPM, alors que les pages disent 30 à 300 (à vérifier contre le code de l'application). Les
  textes qui dupliquent un fait (ici `llms.txt`) sont les plus exposés; les placer sous le même contrôle.

### C2. Politique de confidentialité non alignée sur le comportement réel

- **Symptôme** : la campagne a révélé que le serveur séparait automatiquement la voix de
  l'instrumental (question juridique Q72), sans que la politique de confidentialité le décrive ; et la
  provenance de l'installation (nom du site d'origine) n'était pas précisée (Q71). Une phrase
  « seul cas où un audio est conservé » devenait fausse.
- **Cause** : un service serveur ajouté sans mise à jour du texte juridique.
- **Correctif** : politique mise à jour dans les 8 langues juridiques en un seul lot, datée du
  11 octobre 2026 (site 2.34.3) ; rétention des pistes séparées précisée ensuite (#84) ; brief marketing à
  mettre à jour (reste ouvert côté base légale et droit d'auteur des copies dérivées).
- **Garde-fou** : `check-legal-parity.mjs` (même structure, mêmes chiffres dans les 8 langues) ; décision
  juridique remontée au propriétaire, pas tranchée par l'agent ; règle : tout nouveau flux de données ou
  service doit mettre à jour la politique AVANT sa mise en ligne.

### C3. Script de mesure qui écrivait dans `sessionStorage`

- **Symptôme** : la première version du relais de provenance (lot F1) gardait l'hôte du référent dans
  `sessionStorage` côté site, alors que la politique du site promet « aucune mesure d'audience sur ce
  site ».
- **Cause** : implémentation pragmatique sans relecture de la promesse faite au visiteur.
- **Correctif** : le commit suivant retire toute écriture (« aucune écriture sur l'appareil côté site,
  relais du référent limité à la page courante »). Le site relaie `ref=` dans les liens de la page
  courante, et l'application enregistre la provenance par son mécanisme existant.
- **Garde-fou** : relire la politique de confidentialité avant tout code qui lit ou écrit un identifiant,
  un stockage ou un référent; revue par un second agent avec la politique en entrée. Voir
  `07-mesure.md`, §3.

### C4. Chiffres publiés qui dérivent en dehors du site

- **Symptôme** : textes hors-site historiques périmés (« all-in-one », « compagnon », « composer »,
  emoji, prix à jour) ; la fiche Google Play et les fiches d'annuaires disaient autre chose que le site.
- **Correctif** : dossier hors-site réécrit avec les chiffres du brief ; 38 fiches Google Play mises à
  jour avec les chiffres exacts.
- **Garde-fou** : une seule table de chiffres validés ; toute valeur qui change est modifiée partout
  (comportement et chaque occurrence publiée) puis on vérifie que l'ancienne a disparu.

---

## D. Interface et QA visuelle

### D1. Captures d'interface périmées et en français

- **Symptôme** : pages traduites montrant des captures de l'application dans une ancienne interface et en
  français ; image de la page métronome qui montrait l'écran Clavier ; nom d'un compte de revue visible ;
  section d'une page d'accueil restée en anglais.
- **Cause** : captures prises une fois en français ; aucune variante par langue ; aucun contrôle sur
  l'image servie.
- **Correctif** : 6 écrans recapturés en 10 langues dans l'interface actuelle (2.34.4), fonction
  `webShot(name, locale)` avec repli anglais, scripts versionnés dans `scripts/captures-web/`; trois
  captures restent en français (elles montrent le compte personnel du propriétaire).
- **Garde-fou** : passe visuelle sur le build final par langue ; recommandation non réalisée par la
  campagne : faire échouer l'inventaire quand une page non anglaise sert une capture de repli. Voir
  `05-multilingue.md`, §7.

### D2. Cartes étirées, tableaux sans indice de défilement

- **Symptôme** : à la QA visuelle intégrée, des tableaux de référence plus larges que l'écran défilaient
  horizontalement sans que rien ne l'indique ; et des cartes de grille d'une même rangée paraissaient
  étirées à la hauteur de la plus haute.
- **Cause** : conteneurs en `overflow-x: auto` sans repère visuel ; cartes de grille laissées à
  l'alignement par défaut. Le détail du correctif des cartes n'a pas pu être relu dans les documents.
- **Correctif** (version 2.34.2) : ombre de défilement qui apparaît au bord cachant des colonnes et
  disparaît au bout (fonds `local` et `scroll` superposés) sur les trois familles de tableaux défilants ;
  coins arrondis sur le conteneur et non sur la table.
- **Garde-fou** : QA à 400 px au moins (le défaut apparaît en étroit) ; tout tableau large est dans un
  conteneur défilant AVEC indice.

### D3. Défauts de mise en page vus par la QA finale

| Défaut | Cause | Correctif |
|---|---|---|
| En-têtes « Corde 1 » des tableaux d'accordages à corriger | libellé composé de deux expressions de gabarit dans la cellule (cause exacte du défaut non relue) | construit en une seule chaîne `${T.string} ${i + 1}` |
| Libellés doubles du cercle des quintes (« C♯/D♭ ») trop larges sur une ligne dans le SVG | deux noms dans un seul `<text>` | un `<tspan>` par nom, décalé de plus ou moins 0,55 em |
| Flèche de bouton qui tombe seule sur une ligne | espace ordinaire avant `→` | `&nbsp;→` |
| « Développeurs » resté en anglais en 6 langues | clé non traduite | traduit en it, pt, nl, pl, ja, ko |
| CLS de 0,128 à 400 px sur `/ko/accords-mp3/` | police coréenne | noté, non bloquant (seuil de contrôle : 0,1) |
| Espaces visuels autour de ♯ et ♭ | police de secours | texte propre, résidu connu |

Mesures du build final : 732 pages à 400 et 1280 px, 0 débordement, 0 clé brute, 0 image cassée ; 10
pages x 5 largeurs x 2 thèmes passées en revue.

### D4. Commentaire HTML qui s'affiche sous chaque article

- **Symptôme** : sous chaque article de blog, dans les 10 langues, un fragment de texte apparaissait en
  clair (commit `02d2193`).
- **Cause** : un commentaire HTML du gabarit contenait une balise entre chevrons (`<slug>` dans
  `install.post.<slug>.body`). Le gabarit l'a lue comme une balise, ce qui a coupé le commentaire et rendu
  sa fin visible.
- **Correctif** : commentaire Astro `{/* ... */}` (jamais envoyé au navigateur), avec le nom
  `install.post.SLUG.body` sans chevrons.
- **Garde-fou** : dans un gabarit, ne jamais écrire de chevrons dans un commentaire HTML; préférer le
  commentaire du moteur de gabarit. Détectable par un contrôle sur le build qui cherche des fragments
  du type « .body --> » dans le texte visible, ou à la passe visuelle.

---

## E. Orchestration d'agents

### E1. Un agent trop limité pour un mandat de conception

- **Symptôme** : un agent de classe « exécution mécanique » (effort faible) refuse ou échoue un mandat
  qui demande un jugement de conception (rédiger un plan de contenu, trancher des arbitrages).
- **Cause probable** : le routage de modèles réserve l'effort bas aux tâches entièrement spécifiées. Le
  détail de l'incident n'a pas pu être relu ici.
- **Correctif** : relancer sur un agent d'implémentation (effort moyen) ; l'architecture et les
  arbitrages inter-systèmes à effort élevé.
- **Garde-fou** : choisir l'agent selon la nature du mandat (voir `09-procedure-autonome.md`, routage) ;
  si un agent rapporte qu'il « ne peut pas », ne pas insister avec le même agent, changer de classe.

### E2. Limites d'usage atteintes en pleine campagne

- **Symptôme** : le travail s'est interrompu avant la fin à cause de limites d'usage.
- **Cause probable** : beaucoup d'agents lancés en parallèle (8 agents de traduction, relecteurs, QA) et
  des lectures de gros fichiers. Le détail exact n'a pas été relu dans les documents.
- **Correctif** : reprise depuis `ETAT.md` (la vérité courante de l'avancement) et depuis l'historique
  des branches; relance par lots.
- **Garde-fou** : tenir `ETAT.md` à jour à CHAQUE lot terminé (fait, restes, décisions, questions ouvertes,
  déploiement, URL), une branche et une PR par lot, des mandats courts avec un livrable court; étaler les
  agents lourds; ne pas relancer une phase déjà consignée.

### E3. Ajouts en cours de route perdus ou ignorés

- **Symptôme** : une consigne ajoutée au milieu d'un mandat n'est pas prise en compte par l'agent.
- **Garde-fou** : consigner chaque ajout dans `ETAT.md` et le citer dans le mandat suivant; relancer un lot
  neuf au-delà de 2 à 3 ajouts.

### E4. Deux agents sur le même fichier

- **Symptôme** : catalogues écrasés ou conflits de fusion (es et de partagent `seo.ts`).
- **Garde-fou** : un seul agent par fichier de catalogue; registres partagés (`page-dates.ts`,
  `page-fingerprints.json`) régénérés par le coordinateur seulement; jamais deux agents sur les fichiers de
  traduction du même dossier.

---

## F. Contenu et SEO

### F1. Bloc « En bref » générique répété

- **Symptôme (évité)** : un bloc de réponse identique sur 130 pages.
- **Décision (plan v2)** : chaque bloc porte des données PROPRES à la page (accordages, fréquences,
  particularités tirées du code) ; un bloc générique répété n'est pas publié (risque de contenu en masse
  sans valeur propre).

### F2. Pages pour des besoins sans fonction web

- **Symptôme (évité)** : page « progressions d'accords » promettant un outil qui n'existe que sur mobile.
- **Décision** : retirée comme page outil, remplacée par un article générique par degrés avec appel à
  l'application mobile. Règle : une page par intention, pas deux pages pour la même requête
  (`midi-keyboard-browser` absorbé dans `/clavier-midi`, `beginner-guitar-chords` retiré).

### F3. Données structurées surestimées

- **Constat** : ChatGPT et Perplexity lisent le JSON-LD comme du texte brut; les résultats enrichis FAQ
  sont réservés à des sites officiels et de santé. Décision : FAQPage et HowTo conservés mais non étendus.
  Le graphe d'entité (Organization + WebSite + WebPage, `sameAs`) sert surtout Google et Bing.

### F4. Dates et auteur

- **Défaut** : aucune date de mise à jour hors blog, auteur « Jam Jam » sur 150 pages, éditeur uniquement dans
  les mentions légales.
- **Correctif** : « Mis à jour le » visible, éditeur et fondateur nommés (`Person`), page « À propos »,
  `dateModified` aligné. Règle : date visible = date du sitemap = date du JSON-LD, et elle ne bouge que
  si le texte visible change.

---

## G. Les dix règles à retenir

1. Construire avant de pousser : `build && push`.
2. Un seul chemin de production, des contrôles qui bloquent la bascule.
3. Chaque contrôle a un `--self-test`.
4. Vérifier chaque affirmation dans le code, pas dans une spécification; générer les tableaux depuis le code.
5. Une seule fonction décide des langues d'une page.
6. `robots.txt`, sitemap, filtre anti-bots du serveur : se testent ensemble, avec des user-agents de
   robots.
7. Jamais de date qui bouge sans texte qui bouge.
8. La mesure obéit à la politique de confidentialité, pas l'inverse.
9. Une QA visuelle sur le build final, à 400 px au moins, dans chaque langue.
10. `ETAT.md` à jour à chaque lot, un fichier par agent, une PR par lot.
