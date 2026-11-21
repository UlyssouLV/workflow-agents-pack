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
- **X.Y.Z** — <Titre> (`<nom>`, …) : résumé…      ← with a Release
- **<nom>** — <Titre> (…) : résumé… Sans Release.  ← without

## Prochaine : <Titre>
Nom. `<nom>`
Type. majeure | mineure | correctif | documentation | analyse | évaluation | process
N° prévu. (script)
Objectif. …
Hors périmètre …

## Ensuite : <Titre>
…

## Plus tard (pas encore planifié)

### Bug — <titre> (#n)
Constat …
À corriger …
Suivi …
```

Rules when **creating or rewriting a version** (Prochaine / Ensuite):

- Heading: `## Prochaine : <Titre>` or `## Ensuite : <Titre>`, **no number** (README *Nom, Type et Numéro prévu*).
- **`Nom.`** `` `<nom>` `` — kebab-case ASCII, unique in the file (Déjà livré included). Set once when the version enters the file, **never** changed afterwards, even when the title changes. It names the branch `version/<nom>`, the spec `docs/specs/<nom>.md`, the blockers and the Suivi de l’alternance.
- **`Type.`** — `majeure` (everyone must act: reinstall, change address, migrate by hand; decided, never computed), `mineure` (new capability a collaborator or administrator sees), `correctif` (fix or improvement, no new capability), or without number: `documentation`, `analyse`, `évaluation`, `process`. Argue the type with the user when it is not obvious.
- **`N° prévu.`** — never written by hand: the script computes it from the last Release, the file order and the Type. It identifies nothing: cite a version by its **Nom**.
- Exactement **une** **Prochaine**. Other upcoming versions = **Ensuite**, in the order they should ship (the order drives the N° prévu). With blockers (opt-in, below): write every new heading as **`Ensuite`** — the script picks the **Prochaine** (first ouvrable), never choose it by hand.
- Old form `## Ensuite : X.Y.Z — <titre>` (no Nom / Type) is still read; when you rewrite such a version, give it a Nom and a Type and drop the number from the heading.
- **One job** per version (product language).
- Body: **`Objectif.`** (what the collaborator gains) + **`Hors périmètre`** (explicitly deferred). Optional auth / technique / recherche / tests — no spec-level implementation detail.
- Deferred idea not yet planned → under **`## Plus tard (pas encore planifié)`** as `### …`, **not** a version without Nom and **not** `## Plus tard — …`.
- Bugs: prefer **`/cub`** to create (issue + feuille). Format under **Plus tard**: README (*Bugs*). When the user schedules a bug into a version: **delete** the whole `### Bug — … (#n)` block from **Plus tard** and fold the fix into that version’s **Objectif** (Prochaine / Ensuite). Do **not** leave a duplicate under Plus tard. Do **not** `gh issue close` here — closing is **`finaliser-la-version`** after ship (`Fixes #<n>` on the PR).
- **Blockers (opt-in)** — only when `scripts/deblocages-feuille-de-route.mjs` exists (README *Blocages*): **`Bloquée par.`** is **always present**, after **`Objectif.`**: `Aucune.`, or one bullet `- **<nom>** — raison` per version this one **directly** needs (`- **X.Y.Z** — raison` for a version already in Déjà livré under its number), reason in product language. Decide it for every version you write, and re-check the versions whose **Objectif** cites what you add, move or split. No partial blocker: when a blocker only touches part of an objective, propose the split (part → **Hors périmètre** toward the blocker or a new version) and let the user choose. Never write **`État.`** or **`N° prévu.`**: the script does.
- Research notes live in **`docs/dev/recherches/`**, not in the roadmap file.

An intro under the H1 is allowed.

## 1. Read

Read role **`roadmap`**.

List every version (Déjà livré: number or name + title; Prochaine / Ensuite: title, Nom, Type, N° prévu, job), and every **Plus tard** entry (bugs vs idées). Title-only / empty file → say the feuille de route de dev has no versions yet.

Done when that inventory matches the file.

## 2. Argue, then wait

In French: order, jobs that cover more than one job, missing versions, missing or wrong **`Nom.`** / **`Type.`**, missing or wrong **`Bloquée par.`** (opt-in), format drift vs **`docs/dev/feuille-de-route/README.md`**. Propose concrete edits (add / rewrite / reorder). **Wait.**

Write nothing in this step.

## 3. Write what the user asked

When they confirm or name versions to add / change / move:

- Write **only** those edits, in the **Format** above (and the README).
- Keep versions they did not mention.
- Without blockers: preserve exactly one **Prochaine** after the edit (promote / demote **Ensuite** as needed). With blockers: leave the prefixes to the script.
- Then, only when `scripts/avancement-feuille-de-route.mjs` exists (opt-in, project-owned script), run `node scripts/avancement-feuille-de-route.mjs` from the repo root: the README progress banner follows the new total (a project PR check may refuse it stale). The same run recomputes **`N° prévu.`** and, with blockers, **`État.`** and the **Prochaine**; it fails on a missing **`Nom.`** / **`Type.`** / **`Bloquée par.`**, an unknown name or number, or a cycle → fix the file, run again, and report in one line what became ouvrable or blocked and which N° prévu moved.

Done when the file matches what they asked, or when they said to leave it as is.

## Not this skill

- Open a version (branch, spec, tickets, PR) → `ouvrir-la-version`
- Ship a version → `finaliser-la-version`
- Create a bug (issue + Plus tard) → `creer-un-bug` (`/cub`)
- What is ouvrable, in progress or to split (opt-in blockers) → `debloquer-la-feuille-de-route` (`/dfr`)
- Commit / push → `commit` (`/c`)
- Child TDD → `/implement` + `encadrer-implement`
