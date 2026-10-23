# 0013 — Images publiées sur ghcr, promotion du digest à la Release, mise à jour de l’instance au démarrage et par commande

- Statut : accepté
- Date : 2026-10-21
- Version : 0.7.1 (#106)

## Contexte

Depuis l’ADR 0005, chaque hôte construit les images `runtime` et `runner` au commit du paquet installé : le digest qui tourne n’est pas celui que la CI (ADR 0012) a vérifié, et un build cassé sur l’hôte bloque l’installation. Sans `WAP_REF`, `install.sh` prend la tête de la base, pas une version livrée. Une instance ne se met jamais à jour seule ; après un reboot, `restart: unless-stopped` relance les anciennes images. Le dépôt ArgOS (ADR 0010 d’ArgOS) a déjà résolu ce problème : images sur ghcr, canal staging, promotion par retag, mise à jour du Site au démarrage de l’unité systemd et par une commande unique. Alternatives : garder le build sur l’hôte et publier seulement la Release ; reconstruire les images à la Release ; pousser depuis la CI vers un serveur précis (contraire à « aucune instance perso dans ce dépôt ») ; un timer de mise à jour périodique.

## Décision

1. **Images publiées** : `ghcr.io/ulyssoulv/wap-runtime` et `wap-runner`, multi-arch `amd64` + `arm64`, paquets publics. Les instances n’ont pas de jeton ghcr.
2. **Staging automatique** : sur chaque PR du dépôt vers la base dont la CI est verte, le job `images` construit au **SHA de tête de la PR** et pousse `:sha-<sha>`, puis déplace `:staging`. Ce job est un check requis.
3. **Promotion à la Release** : la publication de `orchestrator-vX.Y.Z` (tag posé par Finalise sur ce même SHA) retaggue `:sha-<sha>` vers `X.Y.Z` et `latest`, sans rebuild. Contrairement à ArgOS, staging et promotion n’ont pas de geste manuel : `:sha-<sha>` est publié avant les tests humains et ne peut pas être écrasé.
4. **Installation** : sans `WAP_REF`, la dernière Release (paquet au tag, images `X.Y.Z`). Avec un ref, les images `:sha-<commit>` si elles existent, sinon le build sur l’hôte de l’ADR 0005, gardé en secours.
5. **Mise à jour de l’instance** : `sudo wap-runtime update` applique la Release la plus haute si la version locale est un semver plus bas et que ses images existent (paquet, compose, pull, recreate) ; codes 0 / 2 / 1, pas de rollback, refus si une session est ouverte sauf `--force`. L’unité systemd `wap-runtime.service` la lance avant `docker compose up` à chaque démarrage ; un échec n’empêche pas le démarrage.

## Conséquences

- Le digest en production est celui testé sur la PR, et un serveur redémarré se met à jour seul.
- Affine l’ADR 0002 (installation par défaut = dernière Release ; démarrage par une unité systemd) et l’ADR 0005 (build sur l’hôte en secours seulement ; paquet et images restent au même commit).
- Une instance installée depuis un ref non semver ne se met pas à jour seule : on la réinstalle avec `WAP_REF`.
- Une instance 0.7.0 passe à la CD en relançant `install.sh` une fois.
- La visibilité publique des paquets est un geste manuel unique (l’API GitHub ne le permet pas).
- Sur un hôte partagé (ArgOS), rien n’est commun sauf le démon Docker ; le conflit 80/443 de l’exposition web n’est pas résolu ici, `diagnostic` le signale.
