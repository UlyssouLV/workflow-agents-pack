# Feuille de route de dev

Runtime self-hosted (monorepo) : pack syncé vers les repos métier ; orchestrateur installé sur la machine de l’utilisateur. Produit public et générique — aucune instance perso dans ce dépôt.

Canal d’intégration : branche `feat/runtime-orchestrator` + `agents/integration-channel.yml` (cycle version et releases `orchestrator-v*` vers cette base, pas `main`). Mis en place **hors semver** (bootstrap), pas une version numérotée.

## Déjà livré

- **0.1.0** — Frontière pack / runtime : sur la branche orchestrateur, le pack de skills est un outil installé depuis `main` (ignoré par git, `update-from-pack.sh`), `orchestrator/` est la seule zone de développement gardée par une suite pytest, et le README présente l’orchestrateur ([#4](https://github.com/UlyssouLV/workflow-agents-pack/issues/4), [spec](../../specs/v0.1.0-frontiere-pack-runtime.md), [ADR 0001](../../adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md)).
- **0.2.0** — Provisionnement self-hosted (Linux + CLIs) : une seule commande `curl … | sudo bash`, sans interaction, prépare un Debian 12+ / Ubuntu 22.04+ — socle manquant (Docker + Compose, `git`, `gh`, `claude`, `agent`, sans authentification), utilisateur d’instance `orchestrator`, instance `~/.wap-runtime/`, service `runtime` sous Compose sur `127.0.0.1` qui repart après reboot ; `wap-runtime health` et `uninstall [--purge]`. Tests humains différés après publication ([#14](https://github.com/UlyssouLV/workflow-agents-pack/issues/14)) ([#9](https://github.com/UlyssouLV/workflow-agents-pack/issues/9), [spec](../../specs/v0.2.0-provisionnement-self-hosted.md), [ADR 0002](../../adr/0002-installation-root-utilisateur-orchestrator-compose.md)).

## Prochaine : 0.3.0 — Registry + cockpit lecture seule

Objectif. L’utilisateur configure des repos liés de façon générique et suit leur état (labels / cycle du pack) depuis un cockpit local en lecture seule.

Hors périmètre : déclencher `/implement` ou toute autre action agent depuis l’UI.

## Ensuite : 0.4.0 — Runner distant borné

Objectif. Depuis le cockpit, lancer une action agent sur un clone local géré par la machine hôte, avec logs visibles.

Hors périmètre : enchaînement autopilot, parallélisme multi-jobs avancé.

## Ensuite : 0.5.0 — FSM et blocages humains

Objectif. Une machine d’états (`running` / `needs-human` / `failed` / `done`) dérivée du tracker rend visibles les blocages (tests humains, erreur, coupure) et le progrès (enfants X/Y, étape).

Hors périmètre : enchaînement automatique des tickets sans validation humaine aux points de blocage.

## Ensuite : 0.6.0 — Autopilot borné

Objectif. Enchaîner les enfants `ready-for-agent` tant que rien ne bloque ; s’arrêter net sur besoin humain ou erreur.

Hors périmètre : SaaS multi-tenant, marketplace, orchestration hors machine utilisateur.

## Plus tard (pas encore numéroté)

### Accès distant optionnel à la machine hôte

Tunnel (Tailscale, Cloudflare Tunnel, etc.) pour joindre le cockpit hors LAN — sans imposer de VPS.

### Workers parallèles multi-repos

Plusieurs jobs agents en parallèle sur la même machine hôte, avec isolation et quotas.
