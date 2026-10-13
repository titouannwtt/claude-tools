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
- Règle en attente de validation par l'utilisateur : « Rust si le gain est mesuré, Python sinon ».

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

## 7. Installer

- Ranger dans `skills/<nom>/` du dépôt `claude-tools`.
- Mac : lien symbolique `~/.claude/skills/<nom>` vers ce dossier.
- VPS : même lien, une fois le script d'installation en place.
- Commit par skill, message `feat(skill): <nom>`.

## Garde-fous

- Aucun nom personnel, pseudo ou chemin personnel dans un fichier versionné. Les valeurs locales vont dans `local.env`.
- Aucun secret commité. Les identifiants proxy ou API restent dans `local.env`.
