# 04. Patterns de contenu : ce qui a été appliqué, avec avant et après

Ce fichier décrit les gabarits et règles éditoriales de la campagne jam-jam.org (octobre 2026), avec des
extraits avant/après réels pris dans l'historique git du site (lots A à F, demandes de fusion 60 à 74).
Correspondance des lots : A technique (60), B pages existantes (64), C nouvelles pages (63), D articles de
référence (62), E traductions (65 à 73), finitions (74).

Cadre à garder en tête : Google écrit (guide du 15 mai 2026) que le contenu **unique et utile** pèse plus que
toute autre consigne, et que « chunker », réécrire pour les IA ou fabriquer des mentions ne sert à rien chez
lui. Les patterns ci-dessous servent d'abord le lecteur ; leur effet sur les autres assistants est
**probable, pas démontré** (`01` §2). Aucun résultat de la campagne n'est mesuré à ce jour.

## 1. Le bloc « En bref » (réponse en 40 à 60 mots, en tête de page)

**Règle.** Juste après le héros (H1, accroche, capture) et avant le paragraphe d'introduction, un paragraphe de 40 à 60 mots qui répond à la question de la page, avec les chiffres
essentiels, suivi de 3 à 5 faits propres à la page. Le bloc est rendu par le gabarit à partir de clés dédiées
(`tool.<page>.brief`, `tool.<page>.fact1` à `fact5`) et un titre localisé (`toolref.briefHeading` : « En bref »,
« In short », « Kurz gesagt »...). Un bloc générique répété d'une page à l'autre n'est pas publié : chaque bloc
porte des données propres (accordages, fréquences, particularités tirées du code).

Avant (premier texte de la page accordeur : un paragraphe d'introduction promotionnel, qui reste, remanié, sous le bloc) :

> The Jam Jam online tuner listens to your instrument through your microphone and tells you, in real time,
> which note you are playing and whether you are sharp or flat. Twenty instruments come with their own
> presets [...] No download, no account, no ads: open the page and tune. The tuner is one screen of Jam Jam,
> the app that finds your songs' chords [...]

Après (bloc ajouté au-dessus, 51 mots) :

> To tune a guitar online, open the Jam Jam tuner, allow the microphone and pluck each open string: E2 (82.41 Hz),
> A2, D3, G3, B3, then E4 (329.63 Hz). The needle turns green within ±5 cents of the target. Eight guitar tunings
> are built in, and 20 more instruments have their own presets.

Autres exemples réels : violon (« To tune a violin online, allow the microphone, pick Violin and start with A4 at
440 Hz. Then tune D4 (293.66 Hz), G3 (196 Hz) and E5 (659.26 Hz)... Jam Jam offers one violin tuning: standard. »),
basse (« E1 (41.20 Hz), A1 (55 Hz), D2 (73.42 Hz) and G2 (98 Hz) ... 5-string bass (low B at 30.87 Hz) ») et
clavier MIDI (« plug it in over USB, open the keyboard in Chrome or Edge and allow MIDI access... the sustain pedal
(CC64) works »).

Modèle de rédaction : une phrase de verbe à l'infinitif répondant à la question, les valeurs numériques avec
leur unité, la limite honnête (« un seul accordage de violon ») et rien de promotionnel. Le nom de la marque
apparaît parce que la réponse décrit l'outil.

Lecture stricte : si une langue n'a pas la clé, le bloc **n'est pas affiché** (pas de repli sur l'anglais) ;
`05-multilingue.md` décrit le contrôle bloquant des clés.

## 2. Faits chiffrés vérifiables

Tout nombre publié répond à trois conditions : il vient du code ou d'une source citée, il est daté ou datable,
il est reproductible par le lecteur. Chiffres de la campagne (recomptés depuis l'application) : 21 instruments et
79 accordages, précision de l'aiguille ±5 cents, 168 accords (14 qualités sur 12 tonalités), 142 sons dont 19
gratuits, 48 kits de batterie, 26 instruments à diagrammes d'accords, 16 gammes, 10 langues.

Mécanisme : un tableau de chiffres autorisés dans un brief de marque, et un contrôle qui **recompte les
catalogues depuis les données de l'application** puis échoue si un chiffre publié diverge, ou si un chiffre
périmé réapparaît (`scripts/check-marketing-numbers.mjs`). Un contrôle qui n'énumère que l'attendu ne voit
jamais une suppression ; d'où la liaison explicite texte ↔ constante pour les lignes sensibles (quotas,
prix).

Limite constatée le 14 octobre 2026 : le `featureList` JSON-LD de l'accueil (`src/layouts/Base.astro`) publie encore
« 9 instruments, 20 tunings » et « 17 sounds free », alors que le brief dit 21 instruments, 79 accordages et
19 sons gratuits. Le script de contrôle ne cite pas ce fichier : **les données structurées sont du contenu
publié et doivent entrer dans le contrôle des chiffres.**

## 3. Tableaux générés à partir du code source

Jamais de tableau de données écrit à la main : il diverge au premier changement du produit.

`scripts/build-tool-reference.mjs` empaquette une petite sonde (esbuild) qui importe les modules de domaine de
l'application (catalogue d'accordages, gammes, voicings de piano, instruments à capodastre, diagrammes d'accords),
l'exécute, et écrit `src/data/tool-reference.json` (79 accordages d'instruments avec fréquences recalculées depuis
le numéro MIDI : `440 × 2^((midi − 69) / 12)`, arrondies à deux décimales).

```bash
node scripts/build-tool-reference.mjs          # écrit le JSON
node scripts/build-tool-reference.mjs --check  # échoue si le fichier n'est plus à jour
```

Les composants `ToolReference.astro` (pages outils et accordeurs) et les blocs de blog (`NoteFrequencyTable`, `CapoChart`,
`CircleOfFifths`...) lisent ce JSON ou calculent à la construction. Exemple : le tableau des fréquences des notes
(108 notes, octaves 0 à 8) est produit par la formule, pas saisi. Le calculateur de fréquence du même article
(référence 440, 432 ou 442 Hz) affiche une valeur initiale **dans le HTML** (lisible sans JavaScript) et se met à
jour par un script externe compatible avec la CSP. Les libellés de colonnes sont dans les 10 langues, avec un
contrôle bloquant.

## 4. Section « Comment faire » en étapes

Pour un besoin de type tâche : 4 à 6 étapes numérotées, chacune avec un intitulé court et une phrase
d'explication, propres à la page. Sur les pages d'accordeurs, une section « Comment accorder un/une <instrument> »
avec ses étapes propres (violon : « Vérifie d'abord le chevalet : il doit être droit, perpendiculaire à la table »),
un tableau des fréquences par accordage (généré, §3), une section « ce qui distingue cet accordeur » (basse :
détection descendue jusqu'à 30 Hz parce que le Mi grave est à 41 Hz). Le JSON-LD `HowTo` correspond aux mêmes clés
que le texte visible, sans divergence possible. Google ne montre plus ce résultat enrichi (2023) : la valeur est
pour le lecteur et l'extraction de passages.

## 5. FAQ

- 3 à 5 vraies questions par page (celles des requêtes réelles : « Does it handle drop D and half-step down? »,
  « Why do other tuners show the wrong octave on my low E? »).
- Chaque réponse commence par la réponse (« Yes. », un chiffre), se comprend seule et tient en une à trois phrases.
- Le texte visible est la source ; le JSON-LD `FAQPage` en dérive (mêmes clés). Sur jam-jam.org : 720 pages et
  2 710 questions avant la campagne, conservées.
- **Pourquoi en mettre malgré Google.** Les résultats enrichis FAQ sont restreints depuis août 2023 et ne
  s'affichent plus du tout depuis le 7 mai 2026. Mais une paire question/réponse autonome est une unité facile à
  extraire pour d'autres moteurs, et répond à une vraie hésitation du lecteur. Ne pas étendre le balisage, ne pas
  gonfler la FAQ : pas de question inventée pour placer un mot-clé.

## 6. Date de mise à jour visible et honnête, auteur réel

- Ligne « Mis à jour le 10 octobre 2026 par <éditeur>, éditeur de <marque> » (clé `toolref.updated`, localisée,
  date formatée selon la langue). Elle lit **le même registre** que `dateModified` et `<lastmod>` (`03` §2) et
  n'apparaît que si la page a une date.
- La date ne change que si le texte visible change (empreintes). Sur la campagne, 44 clés ont été redatées au 10
  octobre parce que leur texte avait vraiment changé ; neuf articles anciens ont gardé leur date d'origine.
- Auteur : l'éditeur légal identifiable, déclaré en un seul endroit (`src/i18n/publisher.ts`, source unique
  aussi des mentions légales). `BlogPosting.author` pointe vers le nœud `Person` du graphe ; jamais un nom
  inventé, jamais « équipe » sans personne derrière.
- Une page À propos (§9) rend cette identité vérifiable.

## 7. Titres et descriptions réécrits sur les vraies requêtes

**Méthode.**

1. Extraire de Search Console, par langue (pas de traduction depuis l'anglais), les requêtes par page sur 90 jours,
   et les pages à 100 impressions ou plus avec un CTR inférieur à 1 % (`02` §4.8). Le fichier de synthèse de la
   campagne liste par exemple `/fr/accordeur-basse/` : 1 180 impressions, 11 clics, position 11,7 (la requête
   « accordeur basse en ligne » pèse 679 impressions) ; `/fr/accordeur-violon/` : 594 impressions, 0 clic,
   position 19,6 ; `/metronome/` : 571 impressions, 1 clic, position 75,7.
2. Placer la requête exacte en tête du titre, dire le bénéfice (« gratuit »), garder l'intention propre à la page.
3. Respecter les seuils : titre au plus 60 caractères latins (30 en japonais et coréen), jamais plus de 70 ;
   description entre 70 et 160 caractères (35 à 80 en CJK) ; titres uniques (`check-seo-meta.mjs --strict`).
4. Mettre le fait précis au début de la description (fréquences, plage, tolérance) plutôt qu'un slogan.
5. Corriger au passage tout chiffre faux.

Avant → après réels (anglais) :

| Page | Titre avant | Titre après | Raison |
|---|---|---|---|
| tuner | Free Online Guitar Tuner: chromatic tuner by mic | Online Tuner: free chromatic tuner by mic | La page sert 21 instruments, « guitar » seul sur-promettait |
| clavier | Free Online MIDI Keyboard | Online Piano Keyboard, free, with MIDI support | L'intention MIDI est portée par la nouvelle page clavier-midi ; la page redevient « piano en ligne » |
| accordeur-basse | Free Online Bass Tuner: 4-string, drop D, by mic | Bass Tuner Online: free 4 and 5-string, by mic | Ordre des mots des requêtes (« bass tuner online ») et 5 cordes ajoutées |
| metronome | Free Online Metronome (description « 40 to 240 BPM ») | Online Metronome: free, 30-300 BPM, tap tempo | Plage corrigée d'après le code |
| accords | AI Chords: find, name and read any chord, free | Chord Finder Online: name any chord, free | Requête réelle « chord finder » plutôt que « AI chords » |
| gammes | Scales on an Online Keyboard: see any scale, free | Piano Scales Online: see 16 scales and modes | Chiffre exact et requête « piano scales » |

Avant → après réels (français) :

| Page | Titre avant | Titre après |
|---|---|---|
| tuner | Accordeur chromatique en ligne, gratuit | Accordeur en ligne gratuit, chromatique, au micro |
| accordeur-violon | Accordeur violon en ligne. Sol Ré La Mi au micro | Accordeur violon en ligne gratuit, au micro |
| accordeur-basse | Accordeur de basse en ligne gratuit, au micro | Accordeur basse en ligne gratuit, au micro |
| transposer | Transposer une chanson + calculateur de capo | Transposer des accords en ligne + calcul du capo |
| accords | Trouve un accord par IA, gratuit | Trouver un accord en ligne, gratuit, par IA |

Description avant → après (violon, fr) : « Accorde ton violon gratuitement en ligne : Mi5 La4 Ré4 Sol3 en quintes
justes, une justesse à ±5 centièmes... » devient « Accordeur de violon en ligne gratuit : Sol3 196 Hz, Ré4, La4 440 Hz
et Mi5 659 Hz, aiguille juste à ±5 centièmes... » : fréquences en tête, ordre des cordes du grave à l'aigu.

Honnêteté sur ces changements : pour le violon français, le titre d'origine commençait déjà par la requête ; le
gain attendu est modeste et **non mesuré**. Le critère de suivi retenu est un CTR des requêtes de niche supérieur
à 3 % à 4 à 8 semaines.

## 8. Pages créées pour les besoins sans page

Principe : une page par **intention** et par besoin réel mesuré, jamais une page par variante de mot-clé (le guide de
Google qualifie cette pratique de « scaled content abuse »). Gabarit commun : H1 = le besoin, bloc En bref, étapes,
différences vérifiées, FAQ, appel à l'action vers l'outil.

| Page | Besoin et requêtes visées | Pourquoi elle n'existait pas |
|---|---|---|
| `/clavier-midi` | « midi keyboard online » (136 impressions), « online midi keyboard » (81), position moyenne 23,8 sur la page du piano ; « clavier midi en ligne » en français | La requête tombait sur une page de piano générique. Contenu propre : navigateurs compatibles (Web MIDI : Chrome et Edge, pas Safari ni Firefox), dépannage, latence, application mobile |
| `/apprendre-piano` | « learn piano online free », « apprendre le piano gratuit » | Fonction réelle d'apprentissage du piano, sans page de présentation ; vérifiée dans le code avant d'être écrite |
| `/karaoke` | création de karaoké, paroles synchronisées | Fonction sans page ; aucune parole de chanson affichée ; suppression de l'audio au plus tard 72 h après traitement, vérifiée |
| `/importer-chanson` | importer des accords depuis un lien, un PDF, une photo | Parcours central sans page ; vie privée décrite exactement (photo : reconnaissance côté serveur sur le web, sur l'appareil sur mobile) ; les sites d'import ne sont jamais nommés |
| `/glossaire` | définitions de théorie musicale | Contenu de référence citable, 21 termes reliés chacun à l'outil qui le montre (réduit de 40 prévus à 20 approfondis) |
| `/a-propos` | qui édite le produit, principes, profils | Page d'entité : l'éditeur n'était public que dans les mentions légales |

Pages écartées ou fusionnées après relecture du plan : `/progressions-accords` (aucun outil web correspondant,
remplacée par un article), `tune-your-bass`, `tune-your-violin`, `tune-your-ukulele` (fusionnés dans les pages
accordeur qui se classaient déjà, §10), `midi-keyboard-browser` (absorbé par `/clavier-midi` : une URL par
intention), `beginner-guitar-chords` (même intention qu'un article d'un autre chantier). Pages « alternatives à X » :
reportées, car la publicité comparative demande un protocole juridique préalable.

## 9. Glossaire, À propos, articles de référence citables

**Glossaire** (`DefinedTermSet`) : chaque terme a une ancre traduite (`#capo`, `#cent`), une définition directe en
une ou deux phrases, une explication, un exemple et un lien vers l'outil. Le JSON-LD porte un `DefinedTerm` par
ancre (un `@id` par ancre), relié à la page par `mainEntity`. Exemple réel : « A capo is a clamp placed on the neck
that shortens every string and raises the instrument by as many semitones as frets. »

**À propos** (`AboutPage` → `Organization`) : qui publie (identité légale, adresse, hébergeur, tirés de la source
unique des mentions légales), ce que fait le produit (une entrée par besoin couvert), principes **vérifiables** (outils
gratuits sans compte, micro analysé sur l'appareil, fichier audio supprimé après traitement, aucune publicité sur le
web, chiffres recomptés depuis le code), plateformes et langues, liens vers contact, mentions légales et
confidentialité. Chaque principe cite un fait contrôlable ; rien de superlatif.

**Articles de référence** (6) : écrits pour être cités, avec réponse dans la première phrase, sections autonomes,
tableau, FAQ, lien vers l'outil.

| Article | Réponse en tête | Bloc généré | Outil lié |
|---|---|---|---|
| `note-frequencies` | « Middle C is 261.63 Hz, A0 27.50 Hz, C8 4,186.01 Hz » avec la formule | Tableau 108 notes, calculateur 440/432/442 Hz, noms de notes (anglais, solfège, allemand) | tuner |
| `capo-chart` | « A G shape played at capo 2 gives an A » | Tableau formes × frettes 1 à 7, capo par tonalité | transposer |
| `circle-of-fifths` | tonalités et armures | Cercle des quintes, ordre des altérations | gammes |
| `read-guitar-tabs` | symboles et rythme | Symboles, accords, rythme | tablature |
| `find-song-bpm` | méthode de tapotement | Calcul du tempo, termes et styles | metronome |
| `common-chord-progressions` | progressions par degrés | Tables de progressions majeur et mineur, accords diatoniques | (application mobile en appel) |

Précautions de fond : sur `note-frequencies`, le mythe du « 432 Hz » est traité par les faits (« aucune étude sérieuse
n'attribue d'effet particulier ») ; la notation H/B allemande est expliquée sans promettre que l'outil l'affiche
(il ne l'affiche pas), et le décalage a été remonté comme ticket produit.

## 10. Fusion et enrichissement des pages minces

- **Fusionner plutôt que créer** : pour tune-your-bass/violin/ukulele, le contenu a été ajouté aux pages accordeur qui
  se classaient déjà (section « Comment accorder », tableau tiré du code, FAQ). Une nouvelle URL aurait mis deux
  pages en concurrence sur la même intention.
- **Enrichir sans délayer** : `piano-chords` (231 mots avant) et `tune-your-harp` (254) ont reçu description
  réécrite (« Piano chords explained: major, minor, seventh, sus and ninth formulas in semitones... »), formules en
  demi-tons, tableau et 3 questions de FAQ. Mesure après (même script d'inventaire, build du 13 octobre) : 453 et 437
  mots. Pas de seuil de mots imposé, car Google ne connaît pas de longueur idéale.
- Reste à faire : 46 pages d'articles restent sous 300 mots toutes langues confondues (dont, en anglais, tune-your-
  charango, find-song-chords, tune-your-guitar, tune-your-oud, play-piano-online, mp3-to-lyrics). Ne les enrichir que
  si la requête réelle le justifie.

## 11. Règles d'exactitude (à appliquer avant d'écrire une ligne)

1. **Tout fait publié correspond au code ou au produit réel.** Vérifier dans le code, jamais dans une spécification,
   un brief ou un autre texte du site : les documents « décrivent parfois comme à faire du travail déjà livré ».
2. **Dire la plateforme** (web, Android, iOS en bêta) et ne jamais promettre une fonction absente (exemple : le site
   explique la notation H allemande sans affirmer que l'outil l'affiche ; un compositeur de progressions n'existe que
   sur mobile).
3. **Corriger les erreurs trouvées** pendant la rédaction. Cas réels de la campagne : « Vingt instruments » devenu 21 ;
   « pentatoniques » au pluriel devenu « pentatonique mineure et blues » (le code n'en connaît qu'une) ; métronome 40-240
   devenu 30-300 BPM ; accordage du cavaquinho D5 A4 B4 E4 harmonisé partout ; basse : 4 cordes (standard, Drop D,
   demi-ton en dessous) et 5 cordes à Si grave, pas de 6 cordes ; ukulélé : standard re-entrant, Low G, baryton ; violon :
   un seul accordage ; import par photo non réservé au mobile ; suppression de l'audio du karaoké au plus tard 72 h.
4. **Chiffres uniquement ceux du brief**, recomptés par script (§2).
5. **Aucun extrait protégé** : progressions génériques ou titres du domaine public.
6. **Pas d'emoji, pas de tiret cadratin** dans le texte publié (contrôle automatique), tutoiement ou vouvoiement fixé
   par le brief de marque.
7. **Vérifier le rendu** : un commentaire HTML coupé par une balise à chevrons s'est affiché en clair sous chaque article
   (toutes langues) avant d'être remplacé. Relire le HTML construit, pas seulement la source.

## 12. Ce qu'il ne faut pas faire

- **Texte caché** pour les IA, consignes adressées aux modèles dans les pages ou le llms.txt : assimilé à du
  cloaking ; Google précise que ses règles anti-spam s'appliquent aux réponses génératives.
- **Contenu produit en masse** sans valeur propre, une page par variante de requête : politique « scaled content abuse ».
- **Notes agrégées inventées** (`aggregateRating` sans avis réels et approuvés), faux avis, faux comptes de forum.
- **Dates trafiquées** : redater sans changement visible, afficher la date du build, mettre une date future.
- **Blocs « En bref » identiques** d'une page à l'autre, FAQ à questions inventées, tableaux écrits à la main.
- **Promesses de plateforme ou de prix** qui ne correspondent pas au comportement réel.
- **Pages « alternatives à X »** sans validation juridique (publicité comparative).
- **Article encyclopédique autopromotionnel** : critère de notoriété non rempli, risque de suppression.

## 13. Ordre de travail recommandé pour un nouveau site

1. Technique et sitemap (`03`), sinon le contenu ne sera ni exploré ni daté.
2. Exactitude : inventaire des chiffres, tableau de référence généré, contrôle de chiffres.
3. Pages existantes qui se classent déjà en positions 5 à 20 : En bref, titres et descriptions, FAQ, date.
4. Pages pour les besoins sans page mesurés, puis articles de référence citables.
5. Traductions localisées par langue (`05-multilingue.md`), seulement les pages complètes.
6. Mentions externes (`06-hors-site.md`), puis mesure (`07-mesure.md`).
