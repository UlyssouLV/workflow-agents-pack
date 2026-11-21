# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## Bugs (standalone)

Used by `creer-un-bug` (`/cub`). A **bug** is not a version child (`/ct`):

- Title: `Bug — <short description>`.
- Label: **`bug`** only (not `ready-for-agent` until the bug is scheduled into a version and turned into implement work).
- Body: fixed `##` headings — Constat, Reproductibilité, Impact, Cause probable, À corriger, Hors périmètre, Métadonnées — see `docs/dev/feuille-de-route/README.md` (*Bugs*). Same fields go under **Plus tard** on the feuille de route.
- **Captures:** save under `docs/img/bugs/`, then **`gh issue create` / `gh issue edit` with `--attach 'path#alt'`** so GitHub stores real issue attachments (visible on the ticket). Reference `![alt](./file)` in **Constat** so `gh` rewrites to the uploaded asset. Do **not** stop at repo-relative Markdown alone — that is not an attachment and often invisible on the issue. Requires a recent `gh` (see `gh issue create --help` → `--attach`).
- Missing facts: exact token `Informations manquantes` (do not invent). Derived states **complet** / **incomplet** — same README.
- Scheduling into a version: `/afr` removes the `### Bug — … (#n)` block from **Plus tard** (objectif de version). Do not close the issue yet.
- Closing / fixing: version PR includes `Fixes #<n>` ; **`finaliser-la-version`** deletes any leftover Plus tard block and `gh issue close <n>` with `Corrigé en VX.Y.Z.` (the Release number), or `Corrigé dans « <Titre> ».` for a version without Release — not `/cub`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Version parent and children

Used by `ouvrir-la-version` (`/to-tickets`) and by any later child under an open parent (human-test follow-ups). A **single** later child is skill `creer-ticket` (`/ct`): it creates the child, checks the ticket fits the local version spec file, sets the parent GitHub issue body from that file, then syncs the three links below and any open PR’s `Fixes` lines. Three links, each with a job:

1. **`Part of #<parent>`** at the top of the child body — text marker for `fermer-ticket-enfant` / `encadrer-implement`.
2. **GitHub sub-issue** — what the UI uses for the parent progress **Y/Z**. After `gh issue create`, attach the child:
   `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues --input -` with JSON `{"sub_issue_id": <child-db-id>}` (`sub_issue_id` = `gh api repos/<owner>/<repo>/issues/<child> --jq .id`, an **integer**, not the `#number`). Check with `sub_issues_summary` on the parent (`total` / `completed`). A body `Part of` line alone does **not** update that counter.
3. **Native blocked-by** — implementation order and the live gate. Same shape as below: parent blocked by every child; children may block each other. Closing a child updates the gate; it also increments `sub_issues_summary.completed`.

Never `/implement` the parent. Closing children is `encadrer-implement` / `fermer-ticket-enfant`; the parent closes via squash `Fixes #<parent>`.

**Titles** (named versions): a version is identified by its **Nom** (roadmap line **`Nom.`**), never by a number. Parent issue and PR: **`<Titre>`**. At the end of « Finalise la version », the squash commit, the Release and the parent take **`VX.Y.Z — <Titre>`** (the Release number); a version without Release keeps its title. Versions opened before the rule (`vX.Y.Z-…` branches, `VX.Y.Z — …` titles) keep their names.

### Child ticket body (canonical — Matt `/to-tickets`)

**Going forward**, every child issue body uses this exact shape (English headings from Matt Pocock `/to-tickets`). Do **not** invent French equivalents (`Ce qu'il livre`, `Critères d'acceptation`, `Tests attendus`, …). Do **not** rewrite closed historical tickets.

```markdown
Part of #<parent>

## What to build

<What this ticket delivers — one vertical slice, product language where possible.
 Concrete enough to implement without re-reading the whole spec.>

## Acceptance criteria

- [ ] <observable criterion>
- [ ] <…>
- [ ] Suite pytest verte.

## Blocked by

- Aucun
```

When a child **is** blocked by a peer, each line names the kind of edge and what would fail:

```markdown
## Blocked by

- #<n> — vraie dépendance : sans #<n>, <ce qui casse (import, API, test impossible à écrire…)>
```

Or, if the order is only preferred:

```markdown
## Blocked by

- #<n> — ordre de confort : on pourrait inverser parce que <rien de concret ne casse>
```

Do **not** add an edge to justify an order. If nothing would break, write `- Aucun` (or mark an existing edge `ordre de confort` rather than inventing a new `#`).

- **`Part of #<parent>`** — first line, always (even if a `## Parent` block also appears from Matt’s quiz).
- **`## What to build`** — required. Not a dump of the parent spec.
- **`## Acceptance criteria`** — required. Checkbox list (`- [ ]`). Include the green-pytest criterion when this repo’s HTTP-boundary tests apply. A child closes only with every box ticked (`encadrer-implement` ticks each proven one): `/cci` runs `node agents/scripts/criteres-non-coches.mjs <n>` and refuses while a `- [ ]` remains, citing the boxes. Only exception: a criterion only a human can check, which `encadrer-implement` leaves unticked and marks at the end of its line `— vérifié par un humain : <scénario du plan de tests>` (the human-test plan takes it over). Old closed tickets are not re-ticked.
- **`## Blocked by`** — required section. `- Aucun` when no peer blockers; otherwise one `- #<n>` per blocking **child**, each with `vraie dépendance : …` or `ordre de confort : …` (see above). Native GitHub `blocked_by` edges are still set by the skills; this section is the human-readable mirror (and fallback). A bare `- #<n>` without that clause is incomplete — `ouvrir-la-version` / `creer-ticket` must not create until it is filled.
- Optional only if Matt’s quiz produced them: `## Implementation decisions` (keep short). No other top-level `##` headings by default.
- Label on create: **`ready-for-agent`**. Not a `bug` issue (bugs → `/cub`).

When `/to-tickets` or the user drafts free-form content: **reshape** into this template before `gh issue create`.

### Human-test child

Created by **`ouvrir-la-version`** after the `/to-tickets` implementation children (not by `/implement`, not by `/ct` for normal work). One per version.

- **Title:** `Tests humains — <nom>` (versions opened before the named-version rule: `Tests humains — VX.Y.Z`)
- **Label on create:** **`ready-for-human`** only (never `ready-for-agent`). Never `/implement` this issue.
- **Links:** same three links as any child (`Part of`, sub-issue, parent blocked by this child). **`## Blocked by`** lists **every** implementation child of the version (native `blocked_by` the same way).
- **Body** — Matt headings plus three required extra sections:

```markdown
Part of #<parent>

## What to build

Plan et trace des tests humains pour <nom> (pas d’implémentation agent).

## Acceptance criteria

- [ ] Plan de tests proposé après le dernier ticket d’implémentation
- [ ] Scénarios joués / non joués documentés
- [ ] Résultats (et images si fournies) publiés sur ce ticket
- [ ] Brouillon « Ce qu’on peut faire maintenant » prêt pour la release

## Blocked by

- #<impl-1> — ordre de process : les tests humains se jouent sur la version complète
- #<impl-2> — ordre de process : les tests humains se jouent sur la version complète

## Plan de tests

_(rempli par `encadrer-implement` après le dernier enfant `ready-for-agent` : scénarios **Branche** seulement)_

## À jouer en staging

_(scénarios **Staging**, rempli par `encadrer-implement` quand le rôle `staging` existe ; joués sur la pré-release dans l’enfant « Essai en staging — VX.Y.Z »)_

## Résultats

_(rempli par `/th`)_

## Ce qu’on peut faire maintenant

_(brouillon produit pour la release ; images sous `docs/img/changelog/<nom>/`)_
```

- At version open: create with empty Plan / Résultats / product draft (placeholders above).
- After the last implementation child closes: `encadrer-implement` writes the concrete plan. Without role **`staging`** (`agents/roles.yml`), every scenario goes in `## Plan de tests` and `## À jouer en staging` reads `Aucun.` With it, each scenario is tagged **Branche** or **Staging**:
  - **Branche** — played locally on the version branch (app or server started locally, a script, a page of the docs site, GitHub). Goes in `## Plan de tests`, as `- [ ] **Branche** — <scénario>`.
  - **Staging** — needs what only the staging environment has (the artifacts built from a Release: images, signed installers, real external services; described by the role **`staging`** doc). Goes in `## À jouer en staging`, as `- [ ] **Staging** — <scénario>`; `/th` does not play them on this child. None → `Aucun.`
- This child keeps only the **Branche** scenarios and **blocks** Finalise until `/th` closes it.
- `/th #<n>` first pass: skill **`tests-humains`** plays the scenarios the agent can run alone, commits their screenshots, writes `### Joué par l’agent` / `### À jouer par l’humain` under `## Résultats`, and leaves the issue Open.
- After the human reports (`/th #<n>` with results): `tests-humains` fills Résultats + product section, commits screenshots if any, removes `ready-for-human`, closes the issue. Partial plans are OK (document non-joués). Closing this child is **`/th`**, not `/cci`.

### Pre-release (`vX.Y.Z-rc.<k>`)

Only when role **`staging`** resolves and the Closed human-test child lists at least one **Staging** scenario. `finaliser-la-version` then ships in **two passes**:

1. **Pre-release** — `/crel vX.Y.Z-rc.<k> --prerelease` on the version branch `HEAD` (not squashed). GitHub marks it *Pre-release*; it never becomes *Latest*. Its only job is to make the project's release workflows build the artifacts (images, installers…) and attach them, so staging can run them. `<k>` starts at `1` and goes up by one after each fix.
2. **Final Release** — `vX.Y.Z`, the usual notes, on the **same SHA** as the last green rc, once the staging trial is Closed with every scenario OK. Then the pre-release **Releases** of this version are deleted (`gh release delete <tag>-rc.<k> --yes`, **without** `--cleanup-tag`): the `-rc.<k>` tags stay as the trace of what was tried.

Pre-release notes are minimal — no screenshots, no aperçus, no human-test illustration:

```markdown
Pré-release de VX.Y.Z — <Titre>, pour l’essai en staging. Ne pas déployer en production.

Version : <nom> (#<parent>)

Essai en staging : #<essai>
```

Title: `VX.Y.Z-rc.<k> — <Titre> (pré-release)`.

**Numbering:** a pre-release **reserves** `X.Y.Z`. The next free number of a Type is computed after the highest of the published Releases **and** the rc tags whose final Release does not exist yet; when the version that holds an rc finalises again, it keeps the number of its rc. Pre-releases never count as « the last Release » otherwise (`gh release list --exclude-pre-releases`).

**Project workflows:** a workflow triggered by `release: published` also runs for a pre-release (GitHub fires it for both); that is what builds the rc artifacts. A workflow that must only see final Releases (promotion to production, « latest » channels, public download pages) filters on `github.event.release.prerelease == false` or listens to `release: released`. A tag filter `v*` matches `vX.Y.Z-rc.<k>`: exclude `*-rc.*` where only finals count.

### Essai en staging child

Created by **`finaliser-la-version`** with the first pre-release of a version (see above). One per version, reused by each `rc.<k>`. Never at version open, never by `/implement`.

- **Title:** `Essai en staging — VX.Y.Z` (the reserved number).
- **Label:** **`ready-for-human`**. Sub-issue of the parent (same `POST …/sub_issues` as above), and the parent is blocked by it (the version cannot squash before the trial).
- **Body:**

```markdown
Part of #<parent>

## What to build

Essai en staging de VX.Y.Z (<Titre>) : les scénarios qui demandent l’environnement staging, joués sur la pré-release avant la Release finale.

## Acceptance criteria

- [ ] Chaque scénario Staging joué ou noté non joué, sur la dernière pré-release
- [ ] Résultats publiés sur ce ticket

## Pré-release à essayer

vX.Y.Z-rc.<k>

## Plan de tests

- [ ] **Staging** — <scénario, copié de « À jouer en staging » de Tests humains — <nom>>

## Résultats

_(rempli par `/th`, un bloc `### vX.Y.Z-rc.<k>` par pré-release essayée)_
```

- `/th #<n>` plays it once staging runs the rc named in `## Pré-release à essayer`, and records a `### vX.Y.Z-rc.<k>` block under `## Résultats`.
- **All OK** → `/th` closes it; the next « Finalise la version » publishes the final Release.
- **A KO** → `/th` leaves it Open. Fix on the version branch (`/implement` on a new child, or a direct fix), then « Finalise la version » again: it publishes `rc.<k+1>`, updates `## Pré-release à essayer`, unticks the plan. No correctif version: nothing was released.

### PR `## Test plan`

The version PR body (`ouvrir-la-version`) ends with a `## Test plan` checklist. Every ticked box tells the truth:

- `encadrer-implement`, after closing a child, ticks the Test plan line that names that child (`#<n>`), if one does.
- `finaliser-la-version`, just before the squash, ticks each box it can prove (suites green = required checks of the PR `HEAD`; human tests = the human-test child Closed; staging trial = the Essai en staging child Closed). A box without an object gets `— sans objet : aucun scénario Staging` / `— sans objet : pas de Release`. A box neither proven nor explained stops Finalise, which asks.

## Changes to earlier versions

A version may change behaviour that an earlier version shipped (a renamed tool, a raised limit, a replaced mechanism). The record is one section of the version spec (role `spec`), written by `ouvrir-la-version` and read by `finaliser-la-version`:

```markdown
## Changements apportés aux versions antérieures

| Version | Élément | Avant | Après | À annoter |
| --- | --- | --- | --- | --- |
| 1.4.0 | Boucle d'outils | 3 appels principaux par message | 5 | `v1.4.0`, #117, #119 |
```

- One row per changed behaviour. **À annoter**: the earlier release tag and the earlier issues (spec, child) that describe the old behaviour.
- Nothing changed → the section holds the single line `Aucun.` Missing section = `Aucun.`

After the squash-merge, each row becomes one block, prepended to the earlier release notes (`gh release edit <tag> --notes-file`) and posted as a comment on each listed issue (`gh issue comment`):

```markdown
> **Modifié en VX.Y.Z** ([#<parent>](<parent url>)) — <Élément>
> Avant : <Avant>
> Après : <Après>
```

**Critical (docs site):** when prepending to release notes, keep **Markdown structure intact**:

1. Each annotation is its own blockquote paragraph (three `>` lines), blocks separated by a blank line.
2. After the **last** annotation block, always insert a **blank line**, then the existing notes starting at `## Pourquoi` (never glue `Après : … ## Pourquoi` on one line).
3. Read the current notes first (`gh release view <tag> --json body`). Write back via `--notes-file` (full body), never a one-line paste that collapses newlines.
4. Downstream docs that extract `## Pourquoi` and `## Ce qu'on peut faire maintenant` from release notes will empty those sections if newlines are collapsed — keep Markdown structure intact.

Skip a target that already holds the block for `VX.Y.Z` and that element. `Aucun.`, a missing section, or a failed annotation never blocks a release: report it in one line and continue.

## Release notes (canonical — `/crel`)

**Going forward**, every GitHub Release body uses this layout (skill `creer-release`). French. Do not invent alternate top-level headings.

```markdown
## Pourquoi

<problem / parent spec, one short paragraph>

## Ce qu'on peut faire maintenant

<features in product language — prefer the Closed human-test child’s section (text + images under `docs/img/changelog/<nom>/`) when present>

## Pour l’administrateur

<only when this version asks the administrator for a gesture after updating the server: one bullet per gesture, in order — otherwise omit the whole section>

## Historique des tickets

- PR : https://github.com/<owner>/<repo>/pull/<n>
- Commits : https://github.com/<owner>/<repo>/pull/<n>/commits

Version : <nom> (#<parent>)

Tickets (`Fixes`) : #<parent> #<enfant> …

## Hors périmètre

<what is not in this version>

Spec : https://github.com/<owner>/<repo>/blob/vX.Y.Z/<spec-path>

ADRs de cette version (liens **sur ce tag**, pas `main`) :

- https://github.com/<owner>/<repo>/blob/vX.Y.Z/<adr-path>

Issues laissées de côté (PR / spec hors périmètre) : #…
```

**`## Pour l’administrateur`** (optional): the gestures the administrator makes once the server runs this version (a new secret to set, a command to run, a setting to check), one bullet each, imperative, product language, no `#n`. Write it only when the version asks for one; never `Aucun.` Recurring tasks do not belong here.

Title: `VX.Y.Z — <Titre>`, where `X.Y.Z` is the version’s only number, fixed at « Finalise la version » (next free number of its **Type** after the last Release, `node scripts/numero-definitif.mjs <nom>`, `docs/dev/feuille-de-route/README.md`). The `Version : <nom> (#<parent>)` line of the notes names the version; the docs changelog reads it to find the spec (`docs/specs/<nom>.md`). Releases made before the named-version rule carry `Développement : D (#<parent>)` instead, still read. No Release for a version whose Type has no number (documentation, analyse, évaluation, process). Tag on the **feature SHA**, not `main`. Optional leading `> **Modifié en …**` annotation blocks (from a later version) may sit **above** `## Pourquoi`, each separated by blank lines as above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (same `POST …/sub_issues` as version children above). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<blocked>/dependencies/blocked_by --input -` and JSON `{"issue_id": <blocker-db-id>}` (`issue_id` must be an **integer**, not a string). `<blocker-db-id>` is `gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`. GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). After `/to-tickets`, the **parent spec** is blocked by **every child**; each child may also be blocked by other children. Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is **Closed**. After a green `/implement`, close the child (`encadrer-implement`) without waiting for the quality gate, so this graph updates. Never `/implement` the parent.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
