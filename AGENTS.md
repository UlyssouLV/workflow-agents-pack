# AGENTS.md — branche orchestrateur

Cette branche (`feat/runtime-orchestrator`) développe l’**orchestrateur** self-hosted. Le pack de skills se maintient sur `main`.

## Règles

- **Ne pas modifier le pack ici.** `agents/skills/`, `agents/hooks/`, `agents/scripts/`, `agents/templates/`, `.claude/skills/` et `.cursor/skills/` sont installés depuis `main` (ou supprimés par la mise à jour) et ignorés par git. Un skill à corriger se corrige sur `main`, puis se réinstalle ici (voir README).
- **Jamais de merge dans `main`.** Les versions de cette branche partent de `feat/runtime-orchestrator` et y reviennent (`agents/integration-channel.yml`, tags `orchestrator-v*`).
- **Le code vit sous `orchestrator/`.** Tests : `orchestrator/tests/` (rôle `test-roots`), pytest dans `orchestrator/.venv`.

## Repères

- Chemins par rôle : `agents/roles.yml`.
- Cycle Ouvre / Implement / Finalise, tracker, labels : `agents/issue-tracker.md`, `agents/triage-labels.md`, `agents/docs/integration-channel.md`.
- Vocabulaire : `docs/glossaire.md`. Décisions : `docs/adr/`. Specs de version : `docs/specs/`.
- Feuille de route : `docs/dev/feuille-de-route/feuille-de-route-dev.md`.
