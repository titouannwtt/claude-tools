# Instructions globales (tous les projets)

## Modèles autorisés

Uniquement **Haiku 5.5**, **Sonnet 5.5** et **Opus 5.5** (alias `haiku`, `sonnet`, `opus`, épinglés
sur `claude-*-5-5` dans settings.json). Jamais Fable ni un autre modèle, ni en session ni en sous-agent.

## Matrice modèle × effort (validée)

| Modèle | Efforts autorisés | Remarque |
|---|---|---|
| Haiku 5.5 | low, medium, high, xhigh, max | max autorisé pour les tâches difficiles |
| Sonnet 5.5 | medium, high | low interdit : plus cher en tokens que Haiku max, et moins bon |
| Opus 5.5 | low, medium, high ; xhigh sur confirmation | max interdit (moins bon que xhigh, bien plus cher) |

`xhigh` est exceptionnel : justifie-le en une phrase dans le chat avant de le lancer.

## Choisir modèle et effort d'un sous-agent

Règle : le contexte du brief compte plus que le modèle ou l'effort. En cas d'échec, d'abord enrichir
le brief, puis monter l'effort d'un cran, puis seulement le modèle.

| Tâche | Agent | Modèle · effort |
|---|---|---|
| Inventaire, grep, état d'un système, extraction, résumé | `scout` | Haiku · low |
| Recherche web ou GitHub, relevés sourcés, synthèse par lot | `researcher` | Haiku · medium (high si beaucoup de sources) |
| Exécution entièrement spécifiée, petit bugfix localisé, scripts simples | `worker` | Haiku · high (max si difficile, medium si mécanique) |
| Exécution complexe à dépendances non triviales, spécification complète | `fixer` | Opus · low (Sonnet medium/high si l'exécution est plus simple) |
| Implémentation de features, refactors multi-fichiers, tests | `implementer` | Sonnet · high (medium pour un correctif local) |
| Analyse, débogage, arbitrage entre approches | `analyst` | Opus · medium (high pour les cas limites) |
| QA visuelle (captures, rendu, mobile, web) | `visual-qa` | Opus · medium |
| Revue indépendante, sécurité, régression transversale | `reviewer` | Opus · high |
| Architecture, arbitrage inter-systèmes, bug qui a résisté | `architect` | Opus · high (xhigh exceptionnel) |
| Design, créativité, interface, montage, objet 3D, idées | `designer` | Opus · high (xhigh sur confirmation) |

- Un agent de projet (`.claude/agents/` du dépôt) prime sur l'agent global du même rôle.
- `general-purpose`, `claude` et `Plan` : toujours passer `model` ET `effort` explicitement (le hook
  `~/.claude/hooks/subagent-gate.py` refuse sinon). Pour ajuster un agent nommé, passer `effort`.
- Ne pas déléguer ce qui se fait en 1 ou 2 appels d'outil : le faire soi-même.

## Brief obligatoire à chaque lancement d'agent

Un sous-agent ne voit pas la conversation (sauf `fork`) : le prompt doit se suffire à lui-même.
Le hook refuse un brief de moins de 400 caractères. Rubriques, en texte court :
1. **Objectif** : le livrable attendu, en une phrase.
2. **Contexte** : pourquoi, décisions déjà prises, pistes déjà écartées, ce que l'on sait déjà.
3. **Entrées** : chemins exacts (lignes si utiles), commandes, numéros d'issue/PR, URLs.
4. **Périmètre et interdits** : ce qu'il ne faut pas toucher ni relire.
5. **Critères d'acceptation** : vérifiables (test, commande, sortie attendue).
6. **Format du rapport** : conclusions et `fichier:ligne`, jamais de dump de fichiers ; schéma si possible.
7. **Arrêt** : quand s'arrêter et remonter au lieu de deviner.
Ne pas recopier CLAUDE.md (déjà injecté aux sous-agents) : nommer seulement la règle utile.
Paralléliser uniquement des sous-tâches indépendantes, dans un seul message.

## Ultracode et Workflow : validation obligatoire

- Ultracode est désactivé par défaut (`"ultracode": false`). Ne jamais lancer `Workflow` sans accord
  explicite de l'utilisateur dans la conversation ; le hook demande en plus une confirmation à chaque run.
- Le mot-clé `ultracode` tapé par l'utilisateur vaut accord pour cette demande seulement.
- Bons candidats : audit transversal, migration large, nombreuses sous-tâches indépendantes et
  vérifiables, revue adversariale. Mauvais : modification locale, demande encore vague (cadrer d'abord).
- Pour proposer, écrire dans le chat puis attendre la réponse : pourquoi, phases, nombre d'agents
  (10 au plus sauf accord), modèle et effort par phase, ordre de grandeur des tokens.
- Dans un script, chaque `agent()` porte `model` et `effort` selon la matrice ci-dessus.

## Tâche vague ou précise

Avant d'agir, juger la demande :
- **Précise** : étapes ou livrable explicites (« fais X, puis Y, quand c'est fini fais Z »). Traiter directement.
- **Vague** : périmètre ouvert (« audite tout mon code »). Demander AVANT d'agir :
  « Veux-tu une recherche légère par sous-agents Haiku pour réduire les tokens ? »
  - Non : traiter au mieux avec la meilleure approche.
  - Oui : lister le périmètre (scout Haiku), puis traiter par lots dimensionnés (environ 15 à 30 k tokens
    de contenu par agent, pas un fichier par agent), avec effort adapté (max autorisé pour Haiku).
- Seuil : si le périmètre estimé dépasse environ 30 fichiers ou 50 k tokens, poser la question ;
  en dessous, le faire soi-même.

## Création de skills

Quand une demande est conséquente et réutilisable entre projets (par exemple obtenir la transcription
d'une vidéo YouTube), le dire explicitement : « Nous n'avons pas de skill pour cela, ça pourra servir
plus tard. Veux-tu que je crée un skill ? ». Ne le créer qu'après accord. Si accord : planifier via un
sous-agent (modèle et effort adaptés), chercher d'abord l'existant (bibliothèques, crates Rust, dépôts GitHub),
puis proposer le plan. Un skill appelle un script qui fait le travail ; l'agent n'intervient qu'en cas
d'échec, pour corriger le script. Le skill est créé dans le dépôt `claude-tools` et publié avec
`tools/publish_skill.sh <nom>` (contrôle des secrets et des noms personnels, commit, push, synchronisation
de l'autre machine) : voir `skill-forge`, section Publier.

## Rust ou Python

Pour tout outil ou script : Rust seulement si le gain de performance est mesuré (calcul intensif, binaire unique
à distribuer, appels très fréquents). Sinon, Python (bibliothèque standard de préférence). Le travail lié au réseau
et aux sous-processus (yt-dlp, ffmpeg, API) reste en Python. Vérifier d'abord par un audit léger, possiblement par
un Haiku, et dire dans le plan pourquoi Rust n'est pas retenu.

## Compaction

Si la conversation devient volumineuse et que la compaction est critique, le signaler en tête de réponse.
Sinon, dès que cela devient intéressant, écrire : « Ça peut être intéressant d'utiliser /compact pour
réduire le coût en tokens. »

## Si tu es un sous-agent

Fais le mandat, rien de plus. Rapport court et factuel : résultat, preuves (`fichier:ligne`,
commandes et sorties), points non traités. Si le mandat dépasse ton rôle, dis-le au lieu d'improviser.

## Style

Ne jamais utiliser le tiret cadratin (U+2014) dans ce qui est écrit.
