---
name: web-fetch
description: Récupérer le contenu d'une URL (page HTML, texte, JSON) quand l'accès direct est bloqué ou instable, avec repli automatique sur un proxy résidentiel. Utiliser quand WebFetch échoue (403, 429, 503, expiration), ou pour enregistrer le texte d'une page dans un fichier sans passer par le modèle.
---

# web-fetch

Un script récupère la page : essai direct, puis proxy résidentiel seulement si l'accès direct est bloqué.
Ton rôle : lancer, lire le JSON, décider de la suite. Le script ne contourne ni connexion ni abonnement.

## Commande

`python3 ~/.claude/skills/web-fetch/scripts/fetch_url.py "<url>" [--text] [--out fichier]`

- `--text` : texte lisible de la page (sans script ni style) ; sans lui, HTML brut.
- `--out` : écrit le corps dans un fichier ; le JSON ne contient alors que le chemin (utile pour une grande page).
- `--no-proxy` : jamais de proxy. `--force-proxy` : directement par le proxy (rare, voir budget).
- Sortie JSON : `url`, `status`, `via` (`direct` ou `proxy`), `content_type`, `bytes`, `text` ou `file`.

## Codes de sortie

| Code | Sens | Action |
|---|---|---|
| 0 | Succès | Lire `text` ou `file`. Si `via` vaut `proxy`, le dire à l'utilisateur. |
| 4 | Bloqué, même avec le proxy ou proxy absent | Dire que le site refuse l'accès. Ne pas insister ; proposer le navigateur piloté (skill `mac-control`) si l'utilisateur est d'accord. |
| 6 | Erreur HTTP hors blocage (404, 500...) | Vérifier l'URL ; le proxy n'y changerait rien. |
| 7 | Réseau injoignable | Vérifier la connexion ou le nom de domaine. |
| 2 | URL invalide | Demander une URL http(s). |
| 1 | Erreur inattendue | Réparer le script (voir ci-dessous). |

## Proxy

Adresse dans `local.env` à la racine de `claude-tools` (clé `IPROYAL_RESIDENTIAL_URL`, ignoré par git). Budget limité
(2 Go) : ne pas télécharger de gros fichiers par ce canal. Ne jamais afficher la valeur du proxy.

## Réparation

Corriger `~/dev/claude-tools/skills/web-fetch/scripts/fetch_url.py`, puis lancer `python3 -m unittest discover -s tests`
dans le dossier du skill. Deux tentatives au plus, puis remonter le message exact à l'utilisateur.
