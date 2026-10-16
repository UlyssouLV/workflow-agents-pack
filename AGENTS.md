# AGENTS.md — branche orchestrateur

Cette branche (`feat/runtime-orchestrator`) développe l’**orchestrateur** self-hosted. Le pack de skills se maintient sur `main`.

## Règles

- **Ne pas modifier le pack ici.** `agents/skills/`, `agents/hooks/`, `agents/scripts/`, `agents/templates/`, `.claude/skills/` et `.cursor/skills/` sont installés depuis `main` (ou supprimés par la mise à jour) et ignorés par git. Un skill à corriger se corrige sur `main`, puis se réinstalle ici (voir README).
- **Jamais de merge dans `main`.** Les versions de cette branche partent de `feat/runtime-orchestrator` et y reviennent (`agents/integration-channel.yml`, tags `orchestrator-v*`).
- **Le code vit sous `orchestrator/`.** Tests : `orchestrator/tests/` (rôle `test-roots`), pytest dans `orchestrator/.venv`.

## Cycle

**« Ouvre la version »** → implement each `ready-for-agent` child (close when tests are green) → human tests (`/th` on the `ready-for-human` child) → **`/code-review`** → **« Finalise la version »** (quality gate, then **`/cqg`** if it is not `OK`). The **parent** spec closes via `Fixes` on the squash. Do **not** leave implemented children Open. Do **not** close the parent from `encadrer-implement`.

- **« Initialise le repo »** (`/init`): skill `initialise-le-repo` (already done in this repo). Optional prompts: Sonar, suivi HTML, Docusaurus + GitHub Pages.
- Upgrade an existing install: `/up` (`mettre-a-jour-le-pack`). Sync-only: `update-from-pack.sh` (`--with-docs` / `--with-suivi`)
- **« Augmente la feuille de route de dev »** (`/afr`): skill `augmenter-la-feuille-de-route-dev`
- **« Ouvre la version »** (must include **`X.Y.Z`**): skill `ouvrir-la-version`
- Child-ticket TDD: `/implement`, then skill `encadrer-implement`
- Human tests: `/th` (`tests-humains`) after the plan on the version’s `ready-for-human` child
- **« Finalise la version »**: skill `finaliser-la-version`

See `agents/README.md`.

## Tests

Tests: `/t`. Quality gate: `/qg` (`-w` waits up to 15 min until the Sonar PR or branch list shows this HEAD; no poll if credentials are missing; never the default `main` gate). Both: `/vf` / « Vérifie la fiabilité du code ». Fix a red gate: `/cqg`. `encadrer-implement` closes the child after the push and does not wait for Sonar. After human tests and an accepted `/code-review`, `finaliser-la-version` runs `/qg -w` once on the PR HEAD before the tag, then `/cqg` if the gate is not `OK`.

## Repères

- Chemins par rôle : `agents/roles.yml`.
- Cycle Ouvre / Implement / Finalise, tracker, labels : `agents/issue-tracker.md`, `agents/triage-labels.md`, `agents/docs/integration-channel.md`.
- Vocabulaire : `docs/glossaire.md`. Décisions : `docs/adr/`. Specs de version : `docs/specs/`.
- Feuille de route : `docs/dev/feuille-de-route/feuille-de-route-dev.md`.
