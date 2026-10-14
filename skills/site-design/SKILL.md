---
name: site-design
description: Analyser le design d'un site web existant (palette, typographie, espacements, rayons, ombres, variables CSS, points de rupture, captures aux largeurs mobile, tablette et bureau) pour s'en inspirer, le reproduire ou l'auditer. Utiliser quand l'utilisateur donne l'URL d'un site et demande son style, ses couleurs, ses polices, de le copier dans l'esprit, ou de vérifier son rendu responsive.
---

# site-design

Un script charge la page dans Chromium (Playwright), mesure les styles calculés des éléments visibles, et écrit des
captures et une synthèse. Zéro token de modèle pour la mesure ; tu lis ensuite `summary.md` et regardes les captures.

## Commandes

Script : `~/.claude/skills/site-design/scripts/site_design.py`. Sortie : JSON sur stdout.

- `analyze "<url>" --out <dossier>` : écrit `shot-375.png`, `shot-768.png`, `shot-1280.png`, `design.json`, `summary.md`.
- `--widths 375,1440` : autres largeurs (la plus grande sert aux mesures). `--dark` : capture et mesure la plus grande
  largeur en mode sombre (les mesures décrivent alors le thème sombre ; lancer deux fois pour comparer).
- `doctor` : vérifie Playwright et Chromium.

## Après l'analyse

1. Lire `summary.md` (court). Ouvrir les captures avec Read pour juger l'impression d'ensemble : les mesures disent
   quoi, les captures disent si c'est beau.
2. Restituer en trois blocs : identité (palette, polices, ton), système (échelle de tailles, espacements, rayons,
   ombres), responsive (défilement horizontal, points de rupture). Citer les valeurs mesurées.
3. Pour reproduire un style : s'inspirer du système (échelle, rythme, contrastes), ne pas copier textes, logos, images
   ni polices sous licence.
4. Limites : un fond posé sur `body` ou `html` seul n'apparaît pas dans les fonds ; les feuilles de style tierces
   (autre domaine) ne livrent ni variables ni points de rupture ; un site derrière une connexion n'est pas analysable.

## Codes de sortie

| Code | Sens | Action |
|---|---|---|
| 0 | Succès | Lire `summary.md` et les captures. |
| 4 | Page bloquée (403, 429) | Relancer **une fois** avec `--use-proxy` ; sinon le dire. |
| 5 | Playwright ou Chromium manquant | Voir Installation. |
| 7 | Page injoignable | Vérifier l'URL et la connexion. |
| 2 | URL invalide | Demander une URL http(s). |
| 1 | Erreur inattendue | Réparer le script (voir ci-dessous). |

## Installation

Mac : `python3 -m venv ~/.venvs/site-design && ~/.venvs/site-design/bin/pip install playwright &&
~/.venvs/site-design/bin/playwright install chromium` (si un index pip privé gêne, ajouter
`--isolated --index-url https://pypi.org/simple`). Le script bascule tout seul vers cet environnement.
VPS : `pip install --user playwright && python3 -m playwright install --with-deps chromium`.

## Proxy

`--use-proxy` : proxy résidentiel de `local.env` (clé `IPROYAL_RESIDENTIAL_URL`), seulement après un blocage. Budget
limité : une page charge ses images, donc préférer un seul passage. Ne jamais afficher la valeur du proxy.

## Réparation

Corriger `<claude-tools>/skills/site-design/scripts/site_design.py`, puis `python3 -m unittest discover -s tests`
dans le dossier du skill. Deux tentatives au plus, puis remonter le message exact à l'utilisateur.
