---
name: skill-forge
description: Décider s'il faut créer un skill pour une demande réutilisable (outil, script, téléchargement, transcription, analyse), puis le concevoir, le rechercher et le construire après accord. À utiliser quand une demande est conséquente et réutilisable entre projets, ou quand l'utilisateur demande de créer ou d'améliorer un skill.
---

# skill-forge

Objectif : accumuler des skills réutilisables, un à un, sans en créer à tort. Un skill n'est pas justifié pour une tâche
ponctuelle ; il l'est pour une capacité qui servira dans d'autres projets.

## 1. Vérifier l'existant

Lister `~/.claude/skills/` et `skills/` du dépôt `claude-tools`. Si un skill couvre la demande, l'utiliser et s'arrêter là.

## 2. Proposer, ne pas créer

Si rien ne couvre la demande, écrire :
« Nous n'avons pas de skill pour cela. Ça semble utile pour plus tard. Veux-tu que je le crée ? »
Attendre la réponse. Sans accord, ne rien créer.

## 3. Planifier (après accord)

Présenter un plan court, à valider avant toute implémentation :
- **Nom** (kebab-case, générique, sans nom personnel ni chemin en dur).
- **Périmètre** : ce que fait le skill, et ce qu'il ne fait pas.
- **Entrées et sorties** : arguments, format de sortie (texte, JSON).
- **Script** : langage, justification (voir section 4), tests prévus.
- **Recherche** : sources à explorer (dépôts GitHub, crates.io, PyPI, documentation officielle).
- **Configuration** : valeurs locales (chemins, identifiants) dans `local.env`, ignoré par git.

## 4. Choisir le langage

Checklist de faisabilité Rust, à remplir avant d'écrire le script :
1. Le travail est-il limité par le calcul (boucles lourdes, parsing de gros volumes) ? Oui/non.
2. Faut-il distribuer un binaire unique sans dépendances ? Oui/non.
3. Le script sera-t-il appelé très souvent (dizaines de fois par jour) ? Oui/non.

- Au moins un « oui » et un gain mesuré ou estimé : Rust.
- Sinon, ou si le travail est lié au réseau et aux sous-processus (yt-dlp, ffmpeg, API) : Python (bibliothèque standard
  de préférence). Dire dans le plan pourquoi Rust n'est pas retenu.
- Règle validée par l'utilisateur : Rust seulement si le gain est mesuré, Python sinon.

## 5. Rechercher (sous-agent)

Lancer un `researcher` (Haiku 5.5, medium ; high si beaucoup de sources) avec un brief complet : question, sources,
critères (licence, maintenance, installation, limites), format de rapport en tableau avec URL et date de consultation.
Ne rien recommander sans ce tableau.

## 6. Construire

- `SKILL.md` court : quand l'utiliser, quelle commande lancer, quoi faire en cas d'erreur.
- Le script fait le travail (déterministe, JSON en sortie, codes de sortie, sous-commande `doctor` qui vérifie les dépendances).
- Tests unitaires dans `tests/` (lancés avec `python3 -m unittest`).
- Réparation : si le script échoue, l'agent lit l'erreur, corrige le script, relance. Deux tentatives au plus,
  puis il remonte à l'utilisateur. Le script ne doit jamais demander à un modèle de faire le travail à sa place.

## 7. Publier

Le skill est créé dans `skills/<nom>/` du dépôt `claude-tools` (Mac : `~/dev/claude-tools`, VPS : `~/claude-tools`).
Une fois les tests verts, lancer depuis la racine du dépôt :

`tools/publish_skill.sh <nom> ["message de commit"]`

Le script enchaîne, sans autre intervention :
1. contrôle des secrets, des e-mails, des IP, des chemins personnels et des termes interdits de `local.env`
   (`tools/check_repo.py --staged`) ; en cas de constat, rien n'est commité, corriger puis relancer ;
2. commit et push sur `main` ;
3. `git pull` et `./install.sh` sur l'autre machine (réglage `PEER_SSH` de `local.env`), qui crée le lien dans
   `~/.claude/skills/`. Sans `PEER_SSH`, il affiche la commande à lancer à la main.

Ne jamais contourner le contrôle (`--no-verify`) ni commiter un fichier de `local.env`.

## Garde-fous

- Aucun nom personnel, pseudo ou chemin personnel dans un fichier versionné. Les valeurs locales vont dans `local.env`.
- Aucun secret commité. Les identifiants proxy ou API restent dans `local.env`.
