# Questions types du panel IA (à adapter)

Ce fichier donne le gabarit des questions à poser chaque mois aux assistants (voir
`../07-mesure.md`, §4). Remplacez les crochets par les termes de votre site. Principe : les questions
sont formulées comme le ferait un utilisateur, jamais comme une liste de mots-clés, et ne nomment jamais
votre marque (sauf la question de marque `BRD`).

## 1. Comment construire votre panel

1. Listez 6 à 12 **besoins** auxquels votre site répond (un besoin = une intention de recherche =
   idéalement une page). Donnez un identifiant de 3 lettres à chacun (`TUN`, `PNO`...).
2. Pour chaque besoin, rédigez 3 questions (une version courte, une version "contrainte", une version
   "comment faire") dans les langues mensuelles (par exemple en, fr, es, de), et 1 question dans chacune
   des autres langues (relevé trimestriel).
3. Identifiant d'une question : `<BESOIN>-<langue>-<n>` (ex. `TUN-fr-2`).
4. Ne traduisez pas mot à mot : partez des requêtes réelles de la langue dans Search Console (voir
   `gsc-queries.md`) et demandez à un locuteur natif, ou à un agent de traduction avec cette consigne, de
   formuler la question comme on la poserait à un assistant.
5. Gardez le texte des questions IDENTIQUE d'un mois à l'autre : changer une question casse la
   comparaison. Si une question doit changer, créez un nouvel identifiant.
6. Ajoutez la question de marque (voir §4).

## 2. Les trois formes de question par besoin

| Forme | Rôle | Gabarit (en) | Gabarit (fr) |
|---|---|---|---|
| 1. Recommandation | "quel est le bon outil" | What's a good free online [OUTIL] that [CONTRAINTE] ? | Quel [OUTIL] en ligne gratuit [CONTRAINTE] me conseilles-tu ? |
| 2. Contrainte précise | une condition qui départage | Is there a [OUTIL] that works for [CAS A], [CAS B] and [CAS C] without installing anything? | Existe-t-il un [OUTIL] pour [CAS A], [CAS B] et [CAS C] sans rien installer ? |
| 3. Comment faire | la question d'apprentissage | How can I [TÂCHE] online for free? | Comment [TÂCHE] en ligne gratuitement ? |

## 3. Banque de questions par type de besoin

Remplacez les exemples ; la colonne "Type" aide à choisir.

| Type de besoin | Question en | Question fr |
|---|---|---|
| Outil gratuit en ligne | What's a good free online [OUTIL]? | Quel [OUTIL] en ligne gratuit me conseilles-tu ? |
| Sans installation | Is there a [OUTIL] website that works without installing an app? | Existe-t-il un site de [OUTIL] sans installer d'appli ? |
| Avec un matériel ou un format précis | Can I use my [MATÉRIEL] with an online [OUTIL]? | Puis-je utiliser mon [MATÉRIEL] avec un [OUTIL] en ligne ? |
| Cas de niche | Is there a free online [OUTIL] for [CAS RARE]? | Existe-t-il un [OUTIL] en ligne gratuit pour [CAS RARE] ? |
| Comment faire | How do I [TÂCHE] with [CONTRAINTE]? | Comment [TÂCHE] avec [CONTRAINTE] ? |
| Comparaison implicite | What's the best app to [TÂCHE], free or cheap? | Quelle est la meilleure appli pour [TÂCHE], gratuite ou pas chère ? |
| Développeur | Is there an API to convert [OBJET A] into [OBJET B]? | Existe-t-il une API pour convertir [OBJET A] en [OBJET B] ? |
| Agent / MCP | Is there an MCP server for [DOMAINE]? | Existe-t-il un serveur MCP pour [DOMAINE] ? |
| Vie privée | Is there a [OUTIL] that works offline or does not upload my files? | Existe-t-il un [OUTIL] hors ligne ou qui n'envoie pas mes fichiers ? |
| Marque | What is [NOM] ([DOMAINE]) ? | Qu'est-ce que [NOM] ([DOMAINE]) ? |

## 4. La question de marque

Une question par mois, au minimum en deux langues. But : vérifier l'**exactitude** et la confusion avec
des homonymes. Liste des homonymes à surveiller : à établir en phase 2 (Jam Jam : Jamn, jam.dev, Cookie
Jam, jamm).

| id | Question |
|---|---|
| BRD-en-1 | What is [NOM] ([DOMAINE])? |
| BRD-fr-1 | Qu'est-ce que [NOM] ([DOMAINE]) ? |

Relevé spécifique : plateformes citées (web, Android, iOS), chiffres, prix, fonctions inventées ou
manquantes.

## 5. Exemple complet (jam-jam.org, quatre besoins)

| id | Question |
|---|---|
| TUN-en-1 | What's a good free online guitar tuner that uses my microphone? |
| TUN-en-2 | Is there a tuner website that works for bass, ukulele and violin without installing an app? |
| TUN-en-3 | How can I tune my guitar to Drop D online for free? |
| TUN-fr-1 | Quel accordeur de guitare en ligne gratuit avec le micro me conseilles-tu ? |
| TUN-es-1 | ¿Qué afinador de guitarra online gratis con micrófono me recomiendas? |
| TUN-de-1 | Welches kostenlose Online-Stimmgerät für Gitarre mit Mikrofon empfiehlst du? |
| NIC-en-1 | Is there a free online oud tuner? |
| NIC-fr-1 | Existe-t-il un accordeur de oud en ligne gratuit ? |
| MID-en-1 | Can I play my USB MIDI keyboard in the browser without a DAW? |
| MID-fr-1 | Peut-on jouer avec son clavier MIDI USB dans le navigateur sans logiciel ? |
| API-en-1 | Is there an API to convert chord sheets or sheet music into JSON, PDF or MusicXML? |
| API-en-3 | Is there an MCP server for converting music files (chords, MIDI, MusicXML)? |
| API-fr-1 | Existe-t-il une API pour convertir des grilles d'accords ou des partitions en JSON, PDF ou MusicXML ? |
| BRD-en-1 | What is Jam Jam (jam-jam.org)? |

Dans la campagne : 10 besoins (`TUN`, `NIC`, `PNO`, `MID`, `DET`, `SBK`, `CNV`, `API`, `MET`, `SCL`),
3 questions par besoin en en/fr/es/de et 1 dans les six autres langues (it, pt, nl, pl, ja, ko).

## 6. Fiche de relevé (copier)

Fichier mensuel `panel/AAAA-MM.csv`, séparateur `;`, une ligne par (date, assistant, langue, question) :

```
date;assistant;langue;id;cite;nb_sur_5;rang;url_citee;exact;concurrents;sources;note
2026-11-03;Perplexity;fr;TUN-fr-1;non;0/5;;;;[outil A] > [outil B];[domaine 1]|[domaine 2];
```

Colonnes :

- `cite` : oui si le produit apparaît au moins 1 fois sur 5 ;
- `nb_sur_5` : nombre de conversations (sur 5) où il apparaît ;
- `rang` : 1 = premier cité (meilleur rang observé) ;
- `url_citee` : l'URL de votre site citée ou liée ;
- `exact` : oui/non (noter l'erreur dans `note`) ;
- `concurrents` : outils cités dans l'ordre ; `sources` : domaines et URL affichés comme sources.

## 7. Protocole en cinq lignes

1. Assistants : ChatGPT (recherche activée), Gemini, Perplexity, Copilot, Claude (recherche web), Google
   AI Overviews (navigation privée, région de la langue).
2. Compte sans historique, mémoire désactivée, une conversation neuve par question.
3. Chaque question 5 fois, dans 5 conversations.
4. Ne jamais nommer la marque (hors `BRD`), ne jamais demander à l'assistant de retenir quoi que ce soit.
5. Mensuel pour les langues principales, trimestriel pour les autres ; version courte (première question de
   chaque besoin) deux mois sur trois.
