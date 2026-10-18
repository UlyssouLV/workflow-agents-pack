# 0010 — Identifiants cockpit et authentification obligatoire

- Statut : accepté
- Date : 2026-10-18
- Version : 0.6.0 (#89)

## Contexte

Jusqu’à la 0.5.x, quiconque atteint le port du service `runtime` a le cockpit (HTTP clair sur `127.0.0.1`, sans login). `wap-runtime auth` connecte GitHub et les agents, pas l’accès web. Si l’on « fait confiance » à localhost sans login, un reverse proxy (ou un mauvais bind) qui relaie vers ce port ouvre le cockpit sans porte.

## Décision

1. **Identifiants cockpit** : un seul jeu login + mot de passe par instance, stocké (hash) dans l’instance, distinct des tokens GitHub / agents ; CLI pour créer et pour changer après déploiement.
2. **Auth partout** : toute surface cockpit/API exige une session valide (sauf page de login + assets nécessaires, et `GET /health` sans secrets), y compris sur loopback.
3. **Sessions serveur** : cookie httpOnly + registre de sessions dans l’instance (fichier / SQLite) ; déconnexion et changement de mot de passe invalident ; durée ~7 jours ; limitation des tentatives de login.

## Conséquences

- Pas d’exception « confiance localhost » qui redeviendrait une faille derrière un proxy.
- Rotation du mot de passe coupe les sessions ouvertes.
- Le vocabulaire ops sépare clairement auth outillage (`wap-runtime auth*`) et porte d’entrée web.
