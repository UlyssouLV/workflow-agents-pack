# Feuille de route de dev

Runtime self-hosted (monorepo) : pack syncé vers les repos métier ; orchestrateur installé sur la machine de l’utilisateur. Produit public et générique — aucune instance perso dans ce dépôt.

Canal d’intégration : branche `feat/runtime-orchestrator` + `agents/integration-channel.yml` (cycle version et releases `orchestrator-v*` vers cette base, pas `main`). Mis en place **hors semver** (bootstrap), pas une version numérotée.

Contrainte transverse : rien n’est global à la machine hôte. Registry, token, cache, clones et jobs sont propres à l’instance (`~/.wap-runtime/` de l’utilisateur d’instance) ; aucun chemin système ni port codé en dur — pour que les instances multiples (0.7.0) restent une affaire de provisionnement.

## Déjà livré

- **0.1.0** — Frontière pack / runtime : sur la branche orchestrateur, le pack de skills est un outil installé depuis `main` (ignoré par git, `update-from-pack.sh`), `orchestrator/` est la seule zone de développement gardée par une suite pytest, et le README présente l’orchestrateur ([#4](https://github.com/UlyssouLV/workflow-agents-pack/issues/4), [spec](../../specs/v0.1.0-frontiere-pack-runtime.md), [ADR 0001](../../adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md)).
- **0.2.0** — Provisionnement self-hosted (Linux + CLIs) : une seule commande `curl … | sudo bash`, sans interaction, prépare un Debian 12+ / Ubuntu 22.04+ — socle manquant (Docker + Compose, `git`, `gh`, `claude`, `agent`, sans authentification), utilisateur d’instance `orchestrator`, instance `~/.wap-runtime/`, service `runtime` sous Compose sur `127.0.0.1` qui repart après reboot ; `wap-runtime health` et `uninstall [--purge]`. Tests humains différés après publication ([#14](https://github.com/UlyssouLV/workflow-agents-pack/issues/14)) ([#9](https://github.com/UlyssouLV/workflow-agents-pack/issues/9), [spec](../../specs/v0.2.0-provisionnement-self-hosted.md), [ADR 0002](../../adr/0002-installation-root-utilisateur-orchestrator-compose.md)).

## Prochaine : 0.3.0 — Registry + cockpit lecture seule

Objectif. L’utilisateur connecte son instance à GitHub, déclare ses repos liés de façon générique et suit leur état (étape du cycle du pack, intervention humaine requise) depuis un cockpit local en lecture seule.

Hors périmètre : déclencher `/implement` ou toute autre action agent depuis l’UI ; le vrai design du cockpit ; faire poser les labels d’état par les skills du pack.

## Ensuite : 0.4.0 — Runner distant borné

Objectif. Depuis le cockpit, lancer une action agent sur un clone local géré par la machine hôte, avec logs visibles.

Hors périmètre : enchaînement autopilot, parallélisme multi-jobs avancé.

## Ensuite : 0.5.0 — FSM et blocages humains

Objectif. Une machine d’états (`running` / `needs-human` / `failed` / `done`) dérivée du tracker rend visibles les blocages (tests humains, erreur, coupure) et le progrès (enfants X/Y, étape).

Hors périmètre : enchaînement automatique des tickets sans validation humaine aux points de blocage.

## Ensuite : 0.6.0 — Autopilot borné

Objectif. Enchaîner les enfants `ready-for-agent` tant que rien ne bloque ; s’arrêter net sur besoin humain ou erreur.

Hors périmètre : SaaS multi-tenant, marketplace, orchestration hors machine utilisateur.

## Ensuite : 0.7.0 — Instances multiples isolées

Objectif. Plusieurs personnes ont chacune leur orchestrateur sur un même serveur : un utilisateur système, un port, une identité GitHub, un registry et un cockpit par instance, sans rien de partagé entre instances.

Hors périmètre : accès au cockpit depuis Internet.

## Ensuite : 0.8.0 — Accès web authentifié

Objectif. Chaque personne joint son cockpit depuis Internet de façon sûre : TLS, identifiants propres à l’instance, aucune instance accessible par une autre, aucun port runtime exposé en clair sur le réseau du serveur.

Hors périmètre : SaaS multi-tenant, comptes partagés entre instances.

## Plus tard (pas encore numéroté)

### Style du cockpit

Un vrai design du cockpit (la 0.3.0 livre un style minimal).

### Labels déclencheurs configurables

Chaque instance choisit quels labels déclenchent quelle étape (ex. un autre label que `needs-info` pour « Question en attente »).

### Workers parallèles multi-repos

Plusieurs jobs agents en parallèle sur la même machine hôte, avec isolation et quotas.
