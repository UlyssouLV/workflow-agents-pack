# 0002 — Installation en une commande root, utilisateur `orchestrator`, Compose

- Statut : accepté
- Date : 2026-10-15
- Version : 0.2.0 (#9)

## Contexte

L’orchestrateur s’installe sur la machine hôte de l’utilisateur : un serveur Linux à lui, souvent partagé avec d’autres services. L’installation doit tenir en une commande sans interaction, installer elle-même le socle (Docker, `git`, `gh`, CLIs agents) et survivre aux redémarrages.

## Décision

1. **Une commande** `curl -fsSL …/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash`. L’URL pointe sur la **branche de base** du canal d’intégration, qui ne bouge qu’au « Finalise » : elle sert toujours la dernière version livrée, jamais une branche de version en cours.
2. L’installation **s’exécute en root et n’interagit pas** (`DEBIAN_FRONTEND=noninteractive`, options par variables d’environnement). Elle installe le socle manquant par les méthodes officielles et ne réinstalle pas ce qui est présent.
3. Un **utilisateur système dédié `orchestrator`** (groupe `docker`) possède l’instance (`/home/orchestrator/.wap-runtime/`) et les CLIs agents. Rien ne tourne en root à l’exécution.
4. Les services runtime tournent sous **Docker Compose** avec `restart: unless-stopped` et le service `docker` activé ; pas d’unité systemd propre à l’orchestrateur. Les ports sont publiés sur `127.0.0.1` uniquement.
5. L’image runtime est **construite localement** sur l’hôte ; pas de registry.
6. Plateformes : Debian 12+ / Ubuntu 22.04+ (apt).

## Conséquences

- Renommer la branche de base change l’URL d’installation.
- Le paquet installé par pipx et l’image construite par Compose viennent tous deux de la tête de la branche de base, lue à des moments différents : un `setup` lancé pendant un Finalise peut les désaligner ; relancer la commande les réaligne.
- Le serveur reçoit les dépôts apt Docker et GitHub CLI ; les autres services du serveur ne sont pas touchés.
- L’utilisateur `orchestrator` devient naturellement l’identité des runners (0.4.0).
- La mise à jour des serveurs déjà installés se fait en relançant la commande (`setup` idempotent) ; une mise à jour CI/CD et une image publiée sont à venir.
- Les autres distributions demandent un autre gestionnaire de paquets : hors 0.2.0.
