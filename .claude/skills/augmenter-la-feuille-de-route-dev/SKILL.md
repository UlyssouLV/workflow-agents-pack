---
name: augmenter-la-feuille-de-route-dev
description: >-
  Read the dev roadmap, list planned versions, argue changes, and write
  versions the user asked for in that file’s format. Use when the user
  types `/afr` or says « Augmente la feuille de route de dev » /
  « Améliore la feuille de route de dev ». Not « Ouvre la version ».
  Do not implement. Do not merge.
---

# Augment the dev roadmap

Triggered by **`/afr`**, **« Augmente la feuille de route de dev »**, or **« Améliore la feuille de route de dev »**. `/` = this skill’s trigger. No hyphen options.

Git commit goes through **`commit`** (`/c`) only if the user asked to commit this turn. This skill does **not** `/c` on its own.

Paths: **`agents/roles.yml`**. Role **`roadmap`** is the **feuille de route de dev** (not a product marketing plan).

**Writing standards (source of truth)** — read and follow **`docs/dev/feuille-de-route/README.md`** before arguing or writing: sections, version body, bugs, recherches. Do not invent a parallel format.

## Format (summary — details in the README)

```markdown
# Feuille de route de dev

## Déjà livré
- **X.Y.Z** — titre : résumé…

## Prochaine : X.Y.Z — <titre>
Objectif. …
Hors périmètre …

## Ensuite : X.Y.Z — <titre>
Objectif. …
Hors périmètre …

## Plus tard (pas encore numéroté)

### Bug — <titre> (#n)
Constat …
À corriger …
Suivi …
```

Rules when **creating or rewriting a version** (Prochaine / Ensuite):

- Semver produit `X.Y.Z`. Heading: `## Prochaine : X.Y.Z — <titre>` or `## Ensuite : X.Y.Z — <titre>`.
- Exactement **une** **Prochaine**. Other numbered upcoming versions = **Ensuite** (ordered). With blockers (opt-in, below): order by number, write every new heading as **`Ensuite`** — the script picks the **Prochaine** (first ouvrable), never choose it by hand.
- **One job** per version (product language).
- Body: **`Objectif.`** (what the collaborator gains) + **`Hors périmètre`** (explicitly deferred). Optional auth / technique / recherche / tests — no spec-level implementation detail.
- Deferred idea **without** a number → under **`## Plus tard (pas encore numéroté)`** as `### …`, **not** a fake semver and **not** `## Plus tard — …`.
- Bugs: prefer **`/cub`** to create (issue + feuille). Format under **Plus tard**: README (*Bugs*). When the user schedules a bug into a version: **delete** the whole `### Bug — … (#n)` block from **Plus tard** and fold the fix into that version’s **Objectif** (Prochaine / Ensuite). Do **not** leave a duplicate under Plus tard. Do **not** `gh issue close` here — closing is **`finaliser-la-version`** after ship (`Fixes #<n>` on the PR).
- **Blockers (opt-in)** — only when `scripts/deblocages-feuille-de-route.mjs` exists (README *Blocages*): **`Bloquée par.`** is **always present**, after **`Objectif.`**: `Aucune.`, or one bullet `- **X.Y.Z** — raison` per version this one **directly** needs, reason in product language. Decide it for every version you write, and re-check the versions whose **Objectif** cites what you add, move or split. No partial blocker: when a blocker only touches part of an objective, propose the split (part → **Hors périmètre** toward the blocker or a new version) and let the user choose. Never write **`État.`**: the script does.
- Research notes live in **`docs/dev/recherches/`**, not in the roadmap file.

An intro under the H1 is allowed.

## 1. Read

Read role **`roadmap`**.

List every **`X.Y.Z`** (title + job) under Déjà livré / Prochaine / Ensuite, and every **Plus tard** entry (bugs vs idées). Title-only / empty file → say the feuille de route de dev has no versions yet.

Done when that inventory matches the file.

## 2. Argue, then wait

In French: order, jobs that cover more than one job, missing versions, missing or wrong **`Bloquée par.`** (opt-in), format drift vs **`docs/dev/feuille-de-route/README.md`**. Propose concrete edits (add / rewrite / reorder). **Wait.**

Write nothing in this step.

## 3. Write what the user asked

When they confirm or name versions to add / change / move:

- Write **only** those edits, in the **Format** above (and the README).
- Keep versions they did not mention.
- Without blockers: preserve exactly one **Prochaine** after the edit (promote / demote **Ensuite** as needed). With blockers: leave the prefixes to the script.
- Then, only when `scripts/avancement-feuille-de-route.mjs` exists (opt-in, project-owned script), run `node scripts/avancement-feuille-de-route.mjs` from the repo root: the README progress banner follows the new total (a project PR check may refuse it stale). With blockers, the same run recomputes **`État.`** and the **Prochaine**; it fails on a missing **`Bloquée par.`**, an unknown number or a cycle → fix the file, run again, and report in one line what became ouvrable or blocked.

Done when the file matches what they asked, or when they said to leave it as is.

## Not this skill

- Open a version (branch, spec, tickets, PR) → `ouvrir-la-version`
- Ship a version → `finaliser-la-version`
- Create a bug (issue + Plus tard) → `creer-un-bug` (`/cub`)
- What is ouvrable, in progress or to split (opt-in blockers) → `debloquer-la-feuille-de-route` (`/dfr`)
- Commit / push → `commit` (`/c`)
- Child TDD → `/implement` + `encadrer-implement`
