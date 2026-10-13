---
name: light-research
description: Recherche légère sur un grand périmètre (audit de tout un dépôt, relecture de nombreux documents) à coût de tokens réduit, en découpant le travail en lots lus par des sous-agents Haiku. À utiliser quand une demande est vague (« audite tout le code », « lis tous les documents ») et que le périmètre dépasse environ 30 fichiers ou 50 000 tokens estimés.
---

# light-research

Objectif : réduire le coût en tokens d'une tâche vague sur un grand périmètre. Le découpage est fait
par un script déterministe (zéro token de modèle). Les sous-agents Haiku lisent les lots. Opus fait la synthèse,
sur les constats seulement, jamais sur les sources.

## Procédure

1. **Juger le prompt.** Précis (étapes et livrable explicites) : ne pas utiliser cette skill. Vague (périmètre ouvert) :
   continuer.
2. **Demander avant d'agir.** Écrire : « Veux-tu une recherche légère par sous-agents Haiku pour réduire les tokens ? »
   - Non : traiter la demande au mieux, sans lots.
   - Oui : continuer.
3. **Mesurer le périmètre.** Lancer
   `python3 ~/.claude/skills/light-research/scripts/plan_batches.py <dossier> --budget 25000`.
   Le JSON donne le nombre de fichiers, les tokens estimés et les lots. Si le périmètre est sous 30 fichiers et 50 000 tokens,
   le faire soi-même : ne pas lancer de sous-agents.
4. **Préciser la question.** Une phrase : ce que l'on cherche dans chaque lot (bugs, dette, incohérences, sécurité…).
   Sans question précise, les constats seront flous.
5. **Lancer les lots.** Un sous-agent `researcher` (Haiku 5.5, medium) par lot, tous dans **un seul message**
   (au plus 10 à la fois). Chaque brief contient : objectif, liste exacte des fichiers du lot, question, fichier de sortie
   (`<scratchpad>/lot-<id>.json`), schéma de sortie, condition d'arrêt. Voir le gabarit ci-dessous.
6. **Synthétiser.** Un sous-agent `analyst` (Opus 5.5, medium) lit les seuls fichiers de constats, les dédoublonne,
   les classe par gravité et renvoie le rapport. Il ne relit les sources que pour confirmer un constat douteux, `fichier:ligne` à l'appui.
7. **Rendre le résultat** : rapport, nombre de lots, tokens estimés, lots en échec.

## Gabarit de brief par lot

```
Objectif : lire les fichiers du lot <id> et répondre à : <question>.
Contexte : <une phrase sur le projet et ce qui est déjà connu>.
Entrées : fichiers (chemins exacts) : <liste>. Ne lis rien d'autre.
Périmètre et interdits : aucune modification ; ne relis pas les fichiers hors du lot.
Critères d'acceptation : chaque constat cite fichier:ligne et une preuve (extrait de 1 à 3 lignes).
Format : écris un JSON dans <chemin de sortie> : [{"fichier": "...", "ligne": n, "gravite": "bloquant|majeur|mineur", "constat": "...", "preuve": "..."}] ; liste vide si rien.
Arrêt : si un fichier est illisible ou binaire, note-le dans le JSON et passe au suivant.
```

## Garde-fous

- Ne jamais lancer les lots en série : c'est le parallélisme (un message, plusieurs appels) qui fait gagner du temps.
- Un lot en échec n'arrête pas les autres : le signaler dans le rapport final.
- Le script ignore les dossiers de dépendances et les binaires, mais pas les secrets : ne jamais inclure `.env`
  ni `*credentials*` dans un périmètre, vérifier la liste avant de lancer.
