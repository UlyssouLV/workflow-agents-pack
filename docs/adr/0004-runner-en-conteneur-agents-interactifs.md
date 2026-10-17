# 0004 — Runner en conteneur, agents en mode interactif dans un terminal

- Statut : accepté
- Date : 2026-10-17
- Version : 0.4.0 (#27)

## Contexte

La 0.4.0 lance depuis le cockpit `/implement #n` avec Claude Code ou Cursor, sur un clone géré par la machine hôte. L’agent exécute du code du repo métier (tests, scripts) et doit pouvoir commiter et pousser sans demander de permission à chaque outil. Sur l’hôte, l’utilisateur d’instance `orchestrator` est dans le groupe `docker` (ADR 0002) : un agent lancé sans permissions sous cet utilisateur aurait de fait les droits root. L’ADR 0003 prévoyait un runner qui appelle `gh` sur l’hôte. L’utilisateur veut retrouver dans le cockpit exactement son terminal local, pas une interface différente.

## Décision

1. **Les sessions tournent dans un service Compose `runner`** dédié, image construite localement : `git`, `gh`, `claude` (version épinglée), `agent` (dernière version au build), Python + venv, Node, `tmux`, skills de Matt Pocock installés par `npx skills` à un commit épinglé. UID d’`orchestrator`, **pas de socket Docker**, montages en écriture limités à `clones/`, `jobs/` et `runner-home/` de l’instance, aucun port publié : le `runtime` lui parle sur le réseau Compose.
2. **Identités** : `GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` et `CURSOR_API_KEY` dans `secrets.env`, lus par `env_file`. Les CLIs de l’hôte (0.2.0) ne servent qu’à obtenir les tokens (`wap-runtime auth claude`). Le point 1 de l’ADR 0003 (« le runner appellera `gh` sur l’hôte ») est remplacé : le runner utilise le `gh` de son image avec `GH_TOKEN`.
3. **L’agent tourne en mode interactif** dans une session `tmux`, affichée dans le cockpit par xterm.js et websocket. Pas de mode `-p` ni de chat : le cockpit reproduit le terminal local et le workflow des skills s’y tape tel quel.
4. **Une seule session ouverte par instance** en 0.4.0. Sans hooks des agents, le runner ne sait que si la session est ouverte ou fermée.

## Conséquences

- Un agent sans permissions ne peut toucher que le clone, les sessions et le `HOME` du runner, pas l’hôte ni Docker.
- Un repo métier qui exige d’autres outils que Python ou Node échoue dans le runner ; il faut enrichir l’image.
- Mettre à jour Cursor = relancer `setup` (reconstruction de l’image) ; sa version n’est pas reproductible d’un build à l’autre.
- L’orchestrateur ne lit pas la conversation de façon structurée : l’enregistrement est le flux du terminal (`.cast`) plus la transcription native de l’agent. Les états « en train de travailler » / « réponse attendue » viendront des hooks des agents (0.4.2).
- Avec plusieurs instances (0.6.0), chacune aura son `runner`, ses clones et son `HOME`.
