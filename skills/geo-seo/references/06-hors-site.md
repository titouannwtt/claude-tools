# 06. Le hors-site : le vrai plafond du GEO

Un site parfaitement refondu reste invisible des assistants IA si personne d'autre ne parle de lui.
Ce fichier donne la méthode générale, puis l'applique point par point avec l'exemple complet de
Jam Jam (jam-jam.org). Les textes modèles sont paramétrés : `[NOM]` pour le produit, `[FONCTION]` pour
ce qu'il fait, `[CHIFFRE]` pour un chiffre vérifié, `[URL]` pour une adresse. Les versions prêtes à
copier sont dans `templates/` (e-mails, README d'exemples d'API, JSON-LD).

## 1. Pourquoi c'est le plafond

Constats de la recherche et de l'audit de la campagne :

| Constat | Source |
|---|---|
| Les modèles de langage fonctionnent à la mention de marque plus qu'au lien : corrélation d'environ 0,66 entre mentions de marque et visibilité dans les aperçus IA, contre environ 0,22 pour les backlinks (étude Ahrefs sur 75 000 marques). Corrélation, pas causalité. | `RECHERCHE.md`, Ahrefs |
| Wikipedia et Reddit sont les domaines les plus cités par ChatGPT (étude Semrush, 230 000 requêtes), mais la part varie fortement d'un mois à l'autre. | `RECHERCHE.md`, Semrush |
| YouTube est la mention la plus corrélée à la visibilité IA (Ahrefs, décembre 2025). | `RECHERCHE.md` |
| Être premier sur Google ne garantit pas d'être cité par ChatGPT, qui s'appuie sur sa mémoire d'entraînement et sur un index propre adossé en partie à Bing. | `RECHERCHE.md` |
| Au départ de la campagne : trois mentions externes connues (AlternativeTo, SaaSHub, Trustpilot avec 1 avis), rien sur Wikidata, YouTube, Reddit, GitHub public, presse. La marque faisait 72 impressions en 90 jours. Homonymes gênants (Jamn, jam.dev, Cookie Jam, jamm). | `AUDIT.md` §3, point 14 |

Conséquence : le travail sur le site (voir `09-procedure-autonome.md`) rend le site CITABLE ; le
hors-site le rend CITÉ. Les deux sont nécessaires, mais seul le second est lent (des mois) et
dépend de personnes extérieures.

## 2. Méthode générale

### 2.1 Les sept règles

1. **Cohérence d'entité.** Une seule description de référence (nom exact, fonction, plateformes, prix,
   chiffres) copiée à l'identique dans chaque fiche : les assistants recoupent. Dans la campagne, la
   description AlternativeTo sert de référence (SaaSHub la reprend).
2. **Exactitude.** Chaque chiffre vient de la table de chiffres validés (`BRIEF-MARKETING.md` §3.2,
   contrôlé par `scripts/check-marketing-numbers.mjs`) ; chaque plateforme est dite telle qu'elle est (iOS
   en bêta publique, pas « sur l'App Store »). Un texte hors-site faux est plus dur à corriger qu'un texte
   du site.
3. **Un humain détient les comptes.** L'agent prépare des textes à coller ; il ne crée pas de compte, ne
   publie rien au nom du propriétaire, ne répond pas sur un forum (point d'arrêt de
   `09-procedure-autonome.md`).
4. **Divulguer** : toute mention faite par le créateur le dit (« Disclosure: I make [NOM] »).
5. **Pas de faux** : ni faux compte, ni faux avis, ni vote concerté, ni lien payant.
6. **Mesurer avant d'insister** : le panel (`07-mesure.md`) dit quelles sources les assistants citent ; c'est
   la liste de prospection.
7. **Espacer** : un pic de mentions identiques le même jour ressemble à du spam.

### 2.2 Classement impact / effort (campagne)

| # | Action | Impact | Effort | Quand |
|---|---|---|---|---|
| 1 | Mettre à jour la fiche AlternativeTo et ajouter des « alternative à » croisées | Fort | 1 h | Tout de suite |
| 2 | Mettre à jour la fiche SaaSHub | Moyen | 30 min | Tout de suite |
| 3 | Dépôt GitHub public d'exemples de l'API | Moyen à fort (cité par les IA de code, `sameAs`) | 2 h | Après relecture du README |
| 4 | Trois vidéos YouTube courtes | Fort à terme (mention la plus corrélée) | 1 à 2 jours | Après le lot site |
| 5 | Réponses utiles sur Reddit | Moyen, lent | 30 min par réponse | En continu, compte rodé |
| 6 | Contact des auteurs de listes « meilleurs outils » | Fort si la liste est citée par les IA | 15 min par e-mail | Après le premier relevé du panel |
| 7 | Wikidata | Moyen | 1 h | SEULEMENT après une source indépendante |
| 8 | Product Hunt | Moyen | 1 jour | Reporté (voir §9) |
| 9 | Pages « alternatives à X » | Fort | 2 jours par page | Reportées (voir §12) |

### 2.3 Tenir le registre

Un tableau (date, plateforme, URL de la mention, texte publié, statut, assistants qui la citent au panel
suivant). L'URL de chaque profil créé s'ajoute au `sameAs` du JSON-LD (voir `templates/json-ld-graph.json`),
seulement quand le profil existe et est tenu par le projet. À éviter : texte caché, pages en masse, faux avis
ou comptes, article Wikipedia autopromotionnel, API Google Indexing hors usage officiel (voir
`01-verdicts-recherche.md`).

## 3. AlternativeTo (fiche existante)

Pourquoi : site d'alternatives très cité par les assistants pour les questions « quelle appli pour
X ». La fiche existait déjà dans la campagne ; le travail est de la rendre exacte et de la relier à
d'autres fiches.

### Champs et texte modèle

- **Name** : `[NOM]`
- **Tagline** (100 caractères maximum) : exemple réel :
  `Free chord songbook, AI chord detection, tuner and MIDI-ready online piano. Web and Android.`
  Modèle : `[FONCTION 1], [FONCTION 2] and [FONCTION 3]. [PLATEFORMES].`
- **Description** (texte de référence, en anglais) :

```
[NOM] is [CATÉGORIE EN UNE PHRASE]: [BÉNÉFICE PRINCIPAL].

What you can do for free:
- [FONCTION 1]: [détail vérifié avec [CHIFFRE]].
- [FONCTION 2]: [détail vérifié].
- [FONCTION 3]: [détail vérifié].

Platforms: [web / Android / iOS bêta...]. Available in [N] languages.

Free to use. [Offre payante en une phrase : ce qu'elle débloque, ce qu'elle ne change pas.]
Made by [ÉDITEUR, pays].
```

Exemple réel : « Jam Jam is a songbook for musicians: find the chords of a song, adapt it to your
instrument and keep it ready to play [...] Free to use. An optional Premium subscription raises the weekly
limits and removes ads on mobile. There are no ads on the website. »

- **Platforms** : cocher seulement ce qui est publié. Pour Jam Jam : Online, Android. iPhone
  seulement à la sortie sur l'App Store (une bêta TestFlight n'est pas une plateforme « disponible »).
- **License** : Freemium. **Category** : Audio & Music.
- **Tags** : ceux qui existent déjà sur le site (chord-detection, guitar-tuner, virtual-piano,
  midi-keyboard, songbook, metronome, offline, no-registration-required, web-based, api...).
- **Features** : ne cocher que ce qui est vrai sur la plateforme visée (« sans publicité » vaut pour le site,
  pas pour l'app mobile).

### « Alternative à » : par fonction réelle

Sur la fiche de chaque logiciel comparable, utiliser « Suggest an alternative » vers `[NOM]`, avec une
phrase factuelle, sans dénigrement. Principe : une ligne par logiciel dont la fonction recouvre
réellement une fonction du produit.

| Logiciel | Fonction commune | Justification à coller |
|---|---|---|
| Chordify | détection d'accords depuis l'audio | `Detects chords from the mic, a browser tab or an audio file, then saves them to an editable songbook.` |
| Chord ai | détection d'accords en direct | `Real-time chord detection (168 chords) that runs on the phone, offline.` |
| GuitarTuna | accordeur | `Free chromatic tuner, 21 instruments and 79 tunings, in the browser or on Android.` |
| Ultimate Guitar | carnet d'accords, transposition | `Personal chord and lyrics songbook with transpose, capo and PDF export.` |
| Virtual Piano | piano en ligne | `Online piano with 142 sounds that accepts a real USB MIDI keyboard in Chrome or Edge.` |

La liste complète de la campagne comptait 11 logiciels. Modèle de phrase :
`[FONCTION précise] with [CHIFFRE vérifié], [plateforme].`

À NE PAS lister : un logiciel dont le recouvrement est trop faible, ou dont la fonction n'est pas
promise par le produit (la campagne a écarté un outil de séparation de pistes alors que la fonction
n'était pas encore publiée, un lecteur de tablatures au recouvrement trop faible, un accompagnateur de
grilles dont la parité web et mobile n'était pas vérifiée).

## 4. SaaSHub

Même logique que AlternativeTo : fiche déjà soumise (le 3 août dans la campagne), à compléter.

- **Tagline** : version courte du texte de référence (`Chord songbook, AI chord detection,
  21-instrument tuner and MIDI online piano`).
- **Description** : identique à celle d'AlternativeTo (cohérence d'entité).
- **Categories** : Music, Music Education, Audio Tools, Developer Tools (pour l'API).
- **Pricing** : Freemium. **Platforms** : Web, Android.
- **Alternatives** : valider la proposition de SaaSHub par catégorie et ajouter les logiciels de la
  liste AlternativeTo.
- **Questions du formulaire** (réponses types) :
  - Qu'est-ce qui rend [NOM] différent ? Exemple : `The songbook, the chord detection and the practice tools share the same data: a detected song lands in your songbook, and the keyboard can follow its key.`
  - Y a-t-il une offre gratuite ? Exemple : `Yes. The web tools need no account. A free account has weekly limits (for example 10 imports per week); Premium raises them.`

## 5. Dépôt GitHub public d'exemples de l'API

### Pourquoi

Les assistants de code (ChatGPT, Claude Code, Cursor, Copilot) lisent GitHub. Un dépôt public d'exemples
exécutables répond aux questions « existe-t-il une API pour [FONCTION] » (le panel en posait trois par
langue), fournit une page de haute autorité qui cite le produit, donne un profil de plus au `sameAs`
(Wikidata P1324 plus tard) et coûte peu : deux heures, les exemples existant déjà dans la documentation.

### Licence : MIT

MIT pour les exemples (copiables dans du code propriétaire). Apache-2.0 si l'éditeur veut une clause de
brevets. La licence couvre les exemples, PAS l'API ni le service, ce que le README dit en dernière
section et renvoie vers les conditions d'utilisation.

### Structure recommandée

```
[nom]-api-examples/
  README.md
  LICENSE
  .env.example              # [NOM]_API_KEY=cle_exemple_xxxxxxxx  (JAMAIS une vraie clé)
  samples/
    public-domain-song.pdf  # contenu du domaine public, créé pour le dépôt
  curl/       01-list-formats.sh ... 06-usage.sh
  javascript/ package.json, list-formats.mjs, convert-file.mjs, convert-url.mjs, follow-events.mjs
  python/     requirements.txt, list_formats.py, convert_file.py, convert_url.py, usage.py
  mcp/        claude_desktop_config.json
```

Nom réel de la campagne : `jam-jam-api-examples`. Description GitHub :
`Examples for the [NOM] REST API: [FONCTION] ...`. Topics : `music`, `chords`, `chordpro`, `musicxml`,
`midi`, `pdf`, `rest-api`, `openapi`, `songbook`. Champ site : la page développeurs du site.

### Règles du dépôt

1. Aucune vraie clé, aucune parole ni titre protégé dans les exemples : remplacer toute URL de chanson
   connue de la page développeurs par une URL neutre.
2. Identifiants de format pris dans `GET /formats` et vérifiés contre le contrat OpenAPI avant
   publication (un identifiant périmé fait échouer l'exemple du premier lecteur).
3. Zéro dépendance quand c'est possible (Node 20 avec `fetch` natif ; Python avec `requests`).
4. Chaque exemple s'exécute tel quel après copie de `.env.example` en `.env`.
5. Une section sur les erreurs (`application/problem+json`, RFC 9457), la rétention des fichiers, les
   quotas et les droits (« ne convertissez que ce que vous avez le droit d'utiliser »).
6. Une section MCP si le produit en expose un : configuration d'un client, liste des outils.

Squelette complet du README : `templates/readme-api-examples.md`.

### À vérifier avant publication

Que le paquet MCP cité est réellement publié sur le registre de paquets, que les adresses des pages
légales sont exactes, et qu'un identifiant de format donné en exemple est encore valide. Une fois le
dépôt en ligne : l'ajouter au `sameAs`, à la page développeurs et à Wikidata (P1324, qualifié
« exemples de l'API »).

## 6. Vidéos YouTube courtes

### Pourquoi et comment

YouTube est la mention la plus corrélée à la visibilité IA. Trois vidéos de 45 à 75 secondes, une par
grand besoin, valent mieux qu'une chaîne ambitieuse jamais alimentée.

Format : 16:9 avec une version 9:16 pour Shorts à partir du même enregistrement, capture d'écran
RÉELLE du site, voix ou sous-titres incrustés, aucune musique protégée (jouer soi-même ou utiliser
les sons du produit). La chaîne est créée par le propriétaire, nommée comme la marque, avec un lien
vers le site dans l'en-tête, puis ajoutée au `sameAs`.

### Intégration sur le site

Vidéo en façade cliquable : vignette statique et lien `youtube-nocookie.com` chargé au clic, pour
respecter une CSP stricte et le RGPD (rien n'est demandé à YouTube avant le clic). Placement sous le
bloc « En bref » de la page concernée, avec un JSON-LD `VideoObject` (`name`, `description`,
`thumbnailUrl`, `uploadDate`, `duration`, `embedUrl`). Une vidéo par langue de page : fr sur les
pages fr, en sur la racine et les autres langues (sous-titres traduits ensuite). La campagne a livré
ensuite un lot « YouTube officiel : consentement, confidentialité et CSP » (PR #75), signe que
l'intégration touche la politique de confidentialité et l'en-tête de sécurité : à traiter comme un lot
à part.

### Exemple complet : vidéo 1, accordeur

Page cible : `/tuner/` et sa version localisée. Titre fr : « Accordeur guitare en ligne gratuit (micro,
Drop D, basse, ukulélé) ». Titre en : « Free online guitar tuner with your mic (Drop D, bass,
ukulele) ».

| Plan | Durée | Image | Voix (fr) | Voice (en) |
|---|---|---|---|---|
| 1 | 0 à 4 s | gros plan d'une guitare désaccordée, puis l'écran | « Accorder ta guitare sans installer d'appli. » | "Tune your guitar without installing an app." |
| 2 | 4 à 12 s | ouverture du site, autorisation du micro | « Ouvre l'accordeur dans ton navigateur et autorise le micro. Le son reste sur ton appareil. » | "Open the tuner in your browser and allow the mic. The sound stays on your device." |
| 3 | 12 à 30 s | corde de mi grave jouée, aiguille qui se centre | « Joue une corde : l'aiguille te dit si c'est trop haut ou trop bas, à plus ou moins 5 cents. » | "Play a string: the needle shows if it is sharp or flat, within plus or minus 5 cents." |
| 4 | 30 à 42 s | menu des accordages : Drop D, DADGAD | « Change d'accordage en un geste. » | "Switch tunings in one tap." |
| 5 | 42 à 55 s | menu des instruments | « 21 instruments et 79 accordages : basse, ukulélé, violon, oud, sitar... » | "21 instruments and 79 tunings." |
| 6 | 55 à 62 s | logo et adresse | « Gratuit, sans compte : jam-jam.org/tuner » | "Free, no account: jam-jam.org/tuner" |

Description YouTube : une phrase de promesse avec les chiffres, les liens (page de l'outil, page de
l'instrument phare, application), puis les chapitres horodatés (`00:00 Accorder sans appli`, `00:04 Ouvrir
l'accordeur et autoriser le micro`, `00:12 Lire l'aiguille (±5 cents)`...).

### Les deux autres vidéos de la campagne

| Vidéo | Page cible | Axe | Précaution |
|---|---|---|---|
| 2. Clavier MIDI | `/clavier-midi/` | clavier USB branché dans Chrome ou Edge, branchement à chaud, vélocité, sustain | vérifier dans le code, avant de tourner, chaque phrase (nom d'accord affiché sur le web ?) |
| 3. Détection d'accords | `/detection/` | micro, son d'un onglet, fichier audio, tonalité et tempo, envoi au carnet | aucune chanson protégée à l'image |

## 7. Reddit

Reddit fait partie des deux domaines les plus cités par ChatGPT dans l'étude Semrush (avec Wikipedia),
donc une réponse utile et durable y compte. C'est aussi l'endroit où l'autopromotion est la plus sanctionnée. Règles non
négociables :

1. **Divulguer, à chaque fois** : « Disclosure: I make [NOM] ».
2. **Répondre d'abord à la question, complètement.** Le lien n'est qu'un appui facultatif ; la réponse
   doit se suffire sans lui.
3. **Aucun faux compte, aucun vote concerté, jamais le même lien collé en série.**
4. **Respecter les règles du sous-forum**; dans le doute, ne pas mettre de lien.
5. **Compte rodé** : ancienneté, contributions utiles, ratio d'environ 9 contributions non
   promotionnelles pour 1 mention du produit (stratégie historique du projet).
6. Ne jamais lier une chanson protégée ni un site qu'on ne nomme pas publiquement.
7. Un modèle de réponse est une trame, jamais un texte collé. Les anciens modèles du projet laissaient
   croire à un utilisateur tiers (« I use [NOM] ») : bannir cette formulation.

### Cinq situations où répondre est utile (trame)

Adaptez la liste à votre domaine : une situation = une question récurrente + une réponse complète +
un appui par le produit.

| # | Question type | Sous-forums | Réponse utile |
|---|---|---|---|
| 1 | Accordeur gratuit pour un instrument rare | r/oud, r/mandolin, r/banjo, r/bouzouki, r/Cello | donner l'accordage standard et les fréquences des cordes, puis le lien de l'outil avec l'instrument précis ; divulguer |
| 2 | Utiliser son clavier MIDI sans logiciel de musique | r/piano, r/midi, r/synthesizers | expliquer Web MIDI (Chrome et Edge, pas Safari ni Firefox), puis l'outil comme exemple |
| 3 | Trouver les accords d'une chanson à l'oreille | r/guitar, r/musictheory | méthode (la basse d'abord, degrés I-IV-V-vi), puis la détection pour vérifier ; divulguer |
| 4 | Appli pour ranger ses grilles d'accords et sa setlist | r/guitar, r/ukulele, r/WorshipLeaders | critères (transposition, capo, export PDF, hors ligne), le produit parmi d'autres options citées honnêtement |
| 5 | Transposer une grille pour un capodastre ou une autre tonalité | r/guitar, r/singing | expliquer le calcul en demi-tons, un exemple générique, puis l'outil |

Gabarit d'une réponse : (1) la réponse en 3 à 6 lignes, (2) le pas à pas ou le tableau utile, (3) une
phrase « Disclosure: I make [NOM], it has a free [FONCTION] if you want to check it: [URL] », (4) une
invitation aux retours critiques.

## 8. Listes « meilleurs outils » citées par les IA

### Pourquoi

Quand un assistant répond « les meilleurs accordeurs en ligne gratuits », il s'appuie sur quelques
articles de liste. Y figurer vaut plus que dix annuaires. La méthode commence par savoir QUELS
articles sont cités.

### Méthode

1. Poser les questions du panel (voir `07-mesure.md`, `templates/panel-questions.md`) à Perplexity,
   ChatGPT (recherche activée), Copilot et Google AI Overviews. Relever **les URL sources citées**, pas
   seulement les outils nommés.
2. Garder les pages éditoriales (blogs, médias, sites d'enseignants) ; écarter les pages de
   concurrents et les forums.
3. Compléter par des requêtes Google dans chaque langue cible : `"best free online [OUTIL]"`,
   `"meilleur [OUTIL] en ligne gratuit"`, `intitle:"best" "[OUTIL]" 2026`, puis Bing (source de ChatGPT
   et de Copilot).
4. Noter dans un tableau : URL, date de mise à jour, auteur, contact (page contact ou e-mail public),
   outils cités, assistants qui la citent.
5. Prioriser : citée par plusieurs assistants, puis mise à jour depuis moins d'un an, puis langue où le
   produit est fort (pour Jam Jam : fr, es, de, pl, ja).
6. **Un seul e-mail par article, une relance au plus, pas avant 3 semaines.** Ne rien offrir en
   échange d'un lien (pas de lien payant, pas de contrepartie).

### E-mail type

Texte complet en fr et en, avec relance et liste de contrôle : `templates/email-outreach.md`. Structure : un
objet qui nomme l'article ; une phrase précise sur ce que l'article apporte (jamais un compliment générique) ;
une phrase sur la fonction qui correspond à SA section, avec un chiffre vérifié ; un lien direct vers la page de
l'outil (jamais l'accueil) ; une sortie polie (« je comprends si ça ne correspond pas à votre ligne ») ; une
invitation aux retours critiques. Personnaliser la première phrase de chaque message.

## 9. Product Hunt (reporté)

Décision du propriétaire (15 juillet 2026) : reporter à la sortie iOS sur l'App Store. Justification
générale, que la campagne n'a pas documentée : un lancement ne se rejoue pas, donc on le fait quand
toutes les plateformes visées sont disponibles et que le texte est à jour. La copie historique du projet était périmée (formules interdites par le brief marketing,
emoji, prix non à jour) : à réécrire avant le lancement à partir de la description de référence (§3).
Règle générale : ne pas lancer sur Product Hunt tant que le produit n'est pas disponible là où les
visiteurs iront l'installer.

## 10. Wikidata

**Mise en garde** : ne créer l'élément qu'APRÈS au moins une source indépendante publiée (article de
presse, blog spécialisé, liste éditoriale qui cite le produit). Les fiches AlternativeTo, SaaSHub et le
site officiel ne suffisent pas : un élément sans source tierce risque la suppression pour notoriété
insuffisante, ce qui laisse une trace négative. Création par le compte personnel du propriétaire, avec
déclaration du conflit d'intérêts sur sa page utilisateur.

Libellé : le nom du produit, dans chaque langue. Description courte par langue
(« music app with chord songbook, chord detection and tuner » en anglais).

| Propriété | Valeur (exemple) | Remarque |
|---|---|---|
| P31 nature de l'élément | application mobile ; application web | identifiants d'éléments à vérifier à la saisie |
| P178 développeur | nom de l'éditeur | pas d'élément personne sans notoriété propre : omettre plutôt que créer |
| P856 site officiel | `https://[domaine]/` | |
| P400 plateforme | Android ; navigateur web | iOS seulement à la sortie sur l'App Store |
| P136 genre | logiciel de musique | identifiant à rechercher |
| P407 langue de l'oeuvre | les langues publiées | |
| P275 licence | logiciel propriétaire | |
| P3418 identifiant Google Play | `[ID DU PAQUET]` | |
| P1324 dépôt de code | dépôt d'exemples | seulement s'il existe |
| P2397 chaîne YouTube | identifiant de chaîne | quand elle existe |
| Référence (P854) | URL de la source indépendante | sur P31 et P856 au minimum |

Ensuite : ajouter l'URL Wikidata au `sameAs` de l'`Organization`.

## 11. Badges d'annuaires

Beaucoup d'annuaires proposent un badge (« Featured on... », « Verified on... ») à placer sur le site
en échange d'une fiche. La campagne n'en a posé aucun ; les règles ci-dessous découlent des contraintes
du site (CSP stricte, politique « aucun script tiers par défaut », budgets de performance mesurés au
déploiement).

### Avantages possibles

Une fiche et un lien entrant (de valeur très variable), une preuve sociale légère si l'annuaire est connu de
votre public, parfois une fiche conditionnée à la pose du badge.

### Risques

Chaque badge est un lien sortant (l'échange de liens massif est visé par les règles anti-spam des moteurs) ;
beaucoup se posent avec un `<script>` externe, interdit par une CSP stricte et par une politique qui promet
l'absence de tiers ; une image ou un script tiers ajoute une requête externe et un risque de CLS (le
déploiement de la campagne contrôle le CLS et le poids) ; un badge chargé depuis l'annuaire lui révèle l'IP
et la page du visiteur ; un annuaire de faible qualité ou payant pour les liens affaiblit la marque.

### Règles si vous en posez un

1. **Image locale** : copier le badge dans les assets du site, jamais de chargement depuis l'annuaire.
2. **Aucun script**, jamais de `<iframe>` d'un tiers.
3. Dimensions `width` et `height` explicites (pas de CLS), `loading="lazy"`.
4. Lien sortant avec `rel="noopener"`, et `nofollow`/`sponsored` si l'annuaire est payant ou s'il
   l'exige pour rester conforme.
5. Un seul endroit (pied de la page « À propos » ou d'une page « Ils parlent de nous »), pas dans le
   gabarit de toutes les pages.
6. Texte alternatif localisé, et ajout du profil de l'annuaire au `sameAs` seulement s'il est tenu par le
   projet.

### Quand ne pas le faire

Si le badge exige du JavaScript tiers ; si l'annuaire fait payer le lien ou n'est pas lu par votre public ; si
la performance du site est en cours de correction ; si la fiche n'existe pas encore ou est inexacte (corriger
la fiche d'abord).

## 12. Pages « alternatives à X »

### Pourquoi les faire

Les requêtes « alternative to [CONCURRENT] », « [CONCURRENT] alternative », « free [CONCURRENT]
alternative » sont des intentions de comparaison que les assistants servent avec des pages de ce type.
Le site de la campagne n'en avait aucune alors que le besoin existe (potentiel jugé fort).

### Pourquoi attendre : le risque de publicité comparative

La campagne a reporté ces pages : la **publicité comparative** est encadrée par les articles L122-1 et
suivants du code de la consommation et la directive 2006/114/CE (art. 4). Elle est licite si elle porte sur
des biens répondant aux mêmes besoins, compare objectivement des caractéristiques essentielles, pertinentes,
vérifiables et représentatives (dont le prix), n'est pas trompeuse, ne dénigre pas, ne crée pas de confusion
et ne tire pas indûment profit de la notoriété d'une marque. Conséquences retenues :

- chaque ligne du tableau est **vérifiable** : source publique avec lien et **date de relevé** visible ;
- marque citée en texte seul, jamais de logo ni de charte graphique d'un tiers ;
- pas d'adjectif dévalorisant ni de « meilleur que » : des faits, y compris ce que le concurrent fait et que le
  produit ne fait pas (sinon la comparaison n'est pas représentative) ;
- revue trimestrielle, ligne retirée si elle n'est plus vérifiable ; l'article L122-5 impose de prouver
  l'exactitude des allégations à bref délai, donc archiver chaque source (capture datée) ;
- validation par le protocole juridique du dépôt AVANT toute rédaction.

C'est un point d'arrêt humain : lancer ou non, et dans quelles langues (suggestion : fr et en d'abord).

### Trois cibles suggérées dans la campagne (recouvrement fonctionnel réel et volume de recherche)

| Cible | Fonction comparable | Ce que la page doit dire honnêtement |
|---|---|---|
| Chordify | détection d'accords depuis l'audio | le produit détecte depuis le micro, un onglet (web) ou un fichier, avec résultat dans un carnet éditable ; l'autre part de bibliothèques de morceaux en ligne, pas le produit |
| GuitarTuna | accordeur | le produit fonctionne dans le navigateur sans installation, 21 instruments, 79 accordages ; l'autre propose des jeux et des leçons, et une app iOS publiée |
| Ultimate Guitar (carnet personnel) | carnet d'accords, transposition, capo, export PDF | l'autre a un catalogue de partitions ; le produit est un carnet personnel |

Plan de page (quand elle sera autorisée) : réponse directe en tête, tableau de fonctions avec sources
et date de relevé, ce que chacun fait mieux, pour qui, lien vers l'outil, FAQ, JSON-LD `WebPage`
simple (pas de `Review` ni de note agrégée inventée).

## 13. Suivi

Après chaque action, noter la date. Au relevé suivant du panel (voir `07-mesure.md`), vérifier trois
choses : le produit est-il cité plus souvent, avec quelle URL, et les sources citées par les assistants
incluent-elles maintenant vos fiches ? Les délais sont en mois (voir `07-mesure.md`, §7). Le suivi des
mentions est la boucle qui alimente la liste de prospection du §8.
