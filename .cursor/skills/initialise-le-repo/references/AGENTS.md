# AGENTS.md

## Cycle

**« Ouvre la version »** → implement each `ready-for-agent` child (close when tests are green) → human tests (`/th` on the `ready-for-human` child) → **`/code-review`** → **« Finalise la version »** (quality gate, then **`/cqg`** if it is not `OK`) — with the optional role **`staging`** and **Staging** scenarios, Finalise runs twice: first a pre-release `vX.Y.Z-rc.<k>` and its **Essai en staging — VX.Y.Z** child (`/th` on staging; a KO is fixed on the branch, then a new rc), then, once that child is Closed, the final Release on the same SHA. The **parent** spec closes via `Fixes` on the squash. Do **not** leave implemented children Open. Do **not** close the parent from `encadrer-implement`.

Versions: one number per version, its Release’s, in strict semver, fixed at Finalise from the version’s **Type** (majeure, mineure, correctif); a documentation, analyse, évaluation or process version has no number and no Release. A version is identified by its **Nom** (roadmap line `**Nom.**`): branch `version/<nom>`, spec `docs/specs/<nom>.md`, issues and PR titled `<Titre>`; the roadmap’s **N° prévu** identifies nothing. Tags `vX.Y.Z`; a pre-release `vX.Y.Z-rc.<k>` (staging trial) reserves its number. Rule: `docs/dev/feuille-de-route/README.md` (*Nom, Type et Numéro prévu*).

- **« Initialise le repo »** (`/init`): skill `initialise-le-repo` (already done in this repo). Optional prompts: Sonar, suivi HTML, Docusaurus + GitHub Pages.
- Upgrade an existing install: `/up` (`mettre-a-jour-le-pack`). Sync-only: `update-from-pack.sh` (`--with-docs` / `--with-suivi`)
- **« Augmente la feuille de route de dev »** (`/afr`): skill `augmenter-la-feuille-de-route-dev`
- **« Ouvre la version »** (optionally with the version’s **Nom**): skill `ouvrir-la-version`
- Child-ticket TDD: `/implement`, then skill `encadrer-implement`
- Human tests: `/th` (`tests-humains`) after the plan on the version’s `ready-for-human` child
- **« Finalise la version »**: skill `finaliser-la-version`

See `agents/README.md`.

## Tracker

Issues live as GitHub issues in this repo, managed via the `gh` CLI. See `agents/issue-tracker.md`. Infer the repo from `git remote`.

Canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `agents/triage-labels.md`. No `awaiting-merge`.

## Domain

See `agents/domain.md`. File roles and path lookup: `agents/roles.yml`. `/code-review` **Standards**: start here (`AGENTS.md`).

## Tests

Tests: `/t`. Quality gate: `/qg` (`-w` waits up to 15 min until the Sonar PR or branch list shows this HEAD; no poll if credentials are missing; never the default `main` gate). Both: `/vf` / « Vérifie la fiabilité du code ». Fix a red gate: `/cqg`. `encadrer-implement` closes the child after the push and does not wait for Sonar. After human tests and an accepted `/code-review`, `finaliser-la-version` runs `/qg -w` once on the PR HEAD before the tag, then `/cqg` if the gate is not `OK`.

## Git

Commit and push only when the **current user message** explicitly asks, **except** skill `encadrer-implement` after green tests, skill `commit` (`/c`; `/c -p` pushes; `/c -p -f` after **oui**), skill `initialise-le-repo` (`/init`: `/c -a -p` on `main` is allowed, once), skill `ouvrir-pr` (`/opr`), skill `creer-release` (`/crel`), and skill `fusionner-pr` (`/mpr`). Never force-push otherwise. Never commit `.env`, `*.db`, `.venv`, or secrets.
