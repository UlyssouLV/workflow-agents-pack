# Feuille de route de dev

Runtime self-hosted (monorepo) : pack syncé vers les repos métier ; orchestrateur installé sur la machine de l’utilisateur. Produit public et générique — aucune instance perso dans ce dépôt.

Canal d’intégration : branche `feat/runtime-orchestrator` + `agents/integration-channel.yml` (cycle version et releases `orchestrator-v*` vers cette base, pas `main`). Mis en place **hors semver** (bootstrap), pas une version numérotée.

Contrainte transverse : rien n’est global à la machine hôte. Registry, token, cache, clones et jobs sont propres à l’instance (`~/.wap-runtime/` de l’utilisateur d’instance) ; aucun chemin système ni port codé en dur — pour que les instances multiples restent une affaire de provisionnement quand elles arriveront.

## Déjà livré

- **0.1.0** — Frontière pack / runtime : sur la branche orchestrateur, le pack de skills est un outil installé depuis `main` (ignoré par git, `update-from-pack.sh`), `orchestrator/` est la seule zone de développement gardée par une suite pytest, et le README présente l’orchestrateur ([#4](https://github.com/UlyssouLV/workflow-agents-pack/issues/4), [spec](../../specs/v0.1.0-frontiere-pack-runtime.md), [ADR 0001](../../adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md)).
- **0.2.0** — Provisionnement self-hosted (Linux + CLIs) : une seule commande `curl … | sudo bash`, sans interaction, prépare un Debian 12+ / Ubuntu 22.04+ — socle manquant (Docker + Compose, `git`, `gh`, `claude`, `agent`, sans authentification), utilisateur d’instance `orchestrator`, instance `~/.wap-runtime/`, service `runtime` sous Compose sur `127.0.0.1` qui repart après reboot ; `wap-runtime health` et `uninstall [--purge]`. Tests humains différés après publication ([#14](https://github.com/UlyssouLV/workflow-agents-pack/issues/14)) ([#9](https://github.com/UlyssouLV/workflow-agents-pack/issues/9), [spec](../../specs/v0.2.0-provisionnement-self-hosted.md), [ADR 0002](../../adr/0002-installation-root-utilisateur-orchestrator-compose.md)).
- **0.3.0** — Registry + cockpit lecture seule : `sudo wap-runtime auth` connecte l’instance à GitHub (device flow quand un terminal existe, `GH_TOKEN` ou `--with-token` sinon ; à relancer après une déconnexion), `wap-runtime repo add|remove|list` gère le registry `repos.toml` des repos liés, et le service `runtime` (FastAPI + front React) sert sur `127.0.0.1` un cockpit en lecture seule : liste (version ouverte, progression X/Y, étape déduite du tracker, badge « Intervention humaine requise », repos qui attendent quelqu’un en tête) et détail par repo relu en direct ; tunnel SSH documenté. Les labels d’état `in-agent-test` / `in-human-test` sont lus, pas encore posés par les skills du pack ([#24](https://github.com/UlyssouLV/workflow-agents-pack/issues/24)) ([#17](https://github.com/UlyssouLV/workflow-agents-pack/issues/17), [spec](../../specs/v0.3.0-registry-cockpit-lecture-seule.md), [ADR 0003](../../adr/0003-authentification-github-de-l-instance.md)).
- **0.4.0** — Runner distant borné : depuis la vue détail du cockpit, lancer `/implement #n` sur un enfant éligible avec Claude Code ou Cursor (connectés par `sudo wap-runtime auth claude` / `auth agent --with-token`, état dans `auth status` et l’encart **Agents**), sur un clone géré par le nouveau service `runner` (conteneur sans socket Docker ni port publié), dans un vrai terminal tmux affiché par xterm.js ; un onglet écrit, les autres lisent, **Terminer** arrête l’agent ; clone sale → **Reprendre** ou **Jeter** ; une seule session ouverte à la fois (badge **Session en cours**) ; chaque session est enregistrée sous `jobs/<id>/` (`session.json`, `terminal.cast`, transcription) et se rejoue depuis le cockpit. Bugs relevés aux tests humains ([#34](https://github.com/UlyssouLV/workflow-agents-pack/issues/34)), corrigés en 0.4.1 : [#40](https://github.com/UlyssouLV/workflow-agents-pack/issues/40) à [#44](https://github.com/UlyssouLV/workflow-agents-pack/issues/44) ([#27](https://github.com/UlyssouLV/workflow-agents-pack/issues/27), [spec](../../specs/v0.4.0-runner-distant-borne.md), [ADR 0004](../../adr/0004-runner-en-conteneur-agents-interactifs.md)).
- **0.4.1** — Correctifs du runner distant (tests humains 0.4.0) : le runner lance le `dispatch.py` du clone géré avant l’agent, qui dispose des skills du pack à la version de la branche ; `sudo wap-runtime …` se lance tel quel (lien `/usr/local/bin/wap-runtime` créé par `setup`) et `auth claude` trouve la CLI quel que soit le PATH ; `WAP_REF` installe le paquet depuis un ref choisi et `setup` construit les images au commit du paquet installé ; quitter la page de session libère la main, **Prendre la main** la donne à un onglet en lecture seule ; une session peut ouvrir la suivante (`wap-runtime enchainer`, état `enchaînée`, chaîne `precedente` / `suivante` suivie par le cockpit), la partie pack restant un bug sur `main` ([#54](https://github.com/UlyssouLV/workflow-agents-pack/issues/54)). Bugs corrigés : [#40](https://github.com/UlyssouLV/workflow-agents-pack/issues/40) à [#44](https://github.com/UlyssouLV/workflow-agents-pack/issues/44) ([#45](https://github.com/UlyssouLV/workflow-agents-pack/issues/45), [spec](../../specs/v0.4.1-correctifs-runner-distant.md), [ADR 0005](../../adr/0005-ref-d-installation-images-au-commit-du-paquet.md), [ADR 0006](../../adr/0006-une-session-peut-ouvrir-la-suivante.md)).
- **0.4.2** — Session libre et réponse attendue : depuis le détail d’un repo, **Nouvelle session** (agent + branche) lance l’agent vide dans le clone géré ; une session ouverte par repo, activité *travaille* / *réponse attendue* / *inconnue* par les hooks, page **Sessions** et compteur de réponses attendues ([#62](https://github.com/UlyssouLV/workflow-agents-pack/issues/62), [spec](../../specs/v0.4.2-session-libre-et-reponse-attendue.md), [ADR 0007](../../adr/0007-sessions-par-repo-activite-par-hooks.md)).
- **0.5.0** — Pilote (autopilot borné) : toggle opt-in par repo, boucle dans `runtime` qui lance le premier `/implement #n` éligible, notifie aux stops et reprend ; l’enchaînement reste le pack ([#73](https://github.com/UlyssouLV/workflow-agents-pack/issues/73), [spec](../../specs/v0.5.0-pilote.md), [ADR 0008](../../adr/0008-boucle-pilote-dans-le-runtime.md)).
- **0.5.1** — Modèle Cursor par session : préférence repo, override à Nouvelle session, `--model` (sauf Auto), héritage via `precedente`, affichage cockpit ([#82](https://github.com/UlyssouLV/workflow-agents-pack/issues/82), [spec](../../specs/v0.5.1-modele-cursor-par-session.md), [ADR 0009](../../adr/0009-modele-cursor-preference-et-heritage.md)).
- **0.6.0** — Accès web authentifié : identifiants cockpit + sessions serveur, auth obligatoire (y compris local), reverse proxy Caddy opt-in (80/443), TLS Let’s Encrypt dès qu’un domaine pointe, pas de HTTP public ; diagnostic CLI ; README refondu ([#89](https://github.com/UlyssouLV/workflow-agents-pack/issues/89), [spec](../../specs/v0.6.0-acces-web-authentifie.md), [ADR 0010](../../adr/0010-identifiants-cockpit-auth-obligatoire.md), [ADR 0011](../../adr/0011-caddy-exposition-web-opt-in.md)).

## Prochaine : 0.7.0 — CI

Objectif. Chaque changement proposé sur l’orchestrateur est vérifié automatiquement (tests, contrôles de qualité) avant d’être accepté : on sait vite si la branche est saine, sans relancer à la main toute la suite.

Hors périmètre : publication ou déploiement automatiques (0.7.1).

## Ensuite : 0.7.1 — CD

Objectif. Une version validée se publie et se déploie sans enchaînement manuel : artefacts et mise à disposition suivent la validation CI, sur le modèle du repo ArgOS.

Hors périmètre : parcours d’enregistrement self-service (0.8.0).

## Ensuite : 0.8.0 — Enregistrement d’orchestrateur par compte GitHub

Objectif. Une personne crée son orchestrateur sur le serveur depuis le web avec son compte GitHub : elle s’enregistre, obtient une instance isolée, et peut y démarrer / lier un workflow — sans que l’admin provisionne à la main.

Hors périmètre : refonte graphique du cockpit (0.8.1) ; SaaS multi-tenant hors de ce serveur ; facturation.

## Ensuite : 0.8.1 — Refonte graphique du cockpit

Objectif. Un vrai design du cockpit à la place du style minimal de la 0.3.0 : hiérarchie visuelle claire, pages liste / détail / sessions / terminal / enregistrement cohérentes, sans changer les capacités déjà livrées.

Hors périmètre : nouvelles fonctionnalités métier ; redesign de la doc ou du README.

## Ensuite : 0.9.0 — Main d’aiguillage et feuilles de route multi-branches

Objectif. Ce dépôt a plusieurs chantiers (pack, orchestrateur, …) mais une seule branche porte aujourd’hui la feuille de route : on obtient une feuille de route par branche, lisible depuis le dépôt. La branche pack quitte le nom `main` pour un nom dédié au pack ; une nouvelle `main` par défaut devient la porte d’entrée du repo (README global d’explication des branches et du produit). Corrige [#81](https://github.com/UlyssouLV/workflow-agents-pack/issues/81).

Hors périmètre : nouvelles capacités du cockpit ou du runtime ; chantier labels d’état du pack (#24) ; correctif du skill `/afr` (#80).

## Plus tard (pas encore numéroté)

### Labels déclencheurs configurables

Chaque instance choisit quels labels déclenchent quelle étape (ex. un autre label que `needs-info` pour « Question en attente »).

### Workers parallèles multi-repos

Plusieurs jobs agents en parallèle sur la même machine hôte, avec isolation et quotas.

### Plusieurs sessions sur le même repo

Plusieurs sessions du runner sur le même clone (worktrees) : la 0.4.2 en autorise une par repo.

### Labels d’état posés par le pack (#24)

Un hook du pack, versionné dans les repos métier et compatible macOS / Windows / Linux, pose et retire `in-agent-test` / `in-human-test` (Claude Code et Cursor, sur les postes comme dans le runner). Chantier du pack sur `main` ([#24](https://github.com/UlyssouLV/workflow-agents-pack/issues/24)).

### Bug — skill afr ajoute des notions techniques dans la feuille de route (#80)

**Constat :** Le skill `/afr` a enrichi l’Objectif d’une version (accès web, aujourd’hui 0.6.0) avec des notions techniques alors que la demande ne portait que sur un objectif produit (accès via reverse proxy sans exposer le réseau privé). La feuille sert à l’aiguillage (objectifs, attendus, hors scopes) ; les choix techniques se décident à l’ouverture de version via grill.

**Reproductibilité :** Demander à `/afr` de détailler un Objectif qui touche à l’infra ou à la sécurité → le texte écrit contient des méthodes / mécanismes techniques.

**Impact :** Feuille qui parle comme une mini-spec ; mauvais aiguillage avant « Ouvre la version » ; confusion avec les décisions réservées au grilling.

**Cause probable :** `/afr` (ou son application) n’interdit pas assez fermement le détail d’implémentation dans un Objectif.

**À corriger :** `/afr` n’écrit que des objectifs, attendus et hors scopes en langage produit ; aucune notion technique dans la feuille.

**Hors périmètre :** Aucun.

**Suivi :** [#80](https://github.com/UlyssouLV/workflow-agents-pack/issues/80) (`bug`). Trouvé dans : inconnu · Contexte : usage · Date : 2026-10-18 · Priorité : Informations manquantes.

### Bug — Le cockpit affiche « ok » pour un check CI ignoré (#105)

**Constat :** Dans la vue détail d’un repo, un check de la PR de version **ignoré** (conclusion `skipped`) s’affiche « ok ». Aux tests humains V0.7.0, `sonar` n’a pas tourné parce que `pytest` échouait, mais le cockpit affichait `sonar : ok` (le badge « CI en échec » restait juste). Capture en pièce jointe sur #105.

**Reproductibilité :** PR de version avec un job qui échoue et un job qui en dépend (`needs:`), marqué `skipped` par GitHub ; ouvrir la vue détail du repo → le check ignoré apparaît « ok ».

**Impact :** L’opérateur peut croire qu’un check (ici le quality gate Sonar) est passé alors qu’il n’a jamais tourné.

**Cause probable :** `etat_check` range toute conclusion hors de l’ensemble d’échec en `ok`, donc `skipped` et `neutral` aussi.

**À corriger :** Un check qui n’a pas tourné ne s’affiche pas comme réussi : il a un état visible distinct (ex. « ignoré »).

**Hors périmètre :** Aucun.

**Suivi :** [#105](https://github.com/UlyssouLV/workflow-agents-pack/issues/105) (`bug`). Trouvé dans : 0.7.0 · Contexte : test humain · Date : 2026-10-21 · Priorité : Informations manquantes.
