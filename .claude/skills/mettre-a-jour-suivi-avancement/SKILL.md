---
name: mettre-a-jour-suivi-avancement
description: >-
  Update the current calendar week’s suivi HTML for a shipped version
  and regenerate the sibling PDF when a script exists. Use when the user
  types `/msa`, says « mets à jour le suivi d’avancement », or when
  finaliser-la-version runs this step. Does not create the week folder
  (that is `/os`).
---

# Mets à jour le suivi d’avancement

Triggered by **`/msa`**, **« mets à jour le suivi d’avancement »**, or by **`finaliser-la-version`**. Records the shipped version in the current week HTML (functional product language) and regenerates the PDF when possible. Does **not** commit. Does **not** create a week folder.

If role **`suivi-avancement`** is missing or unresolved → one line **soft-skip** (do **not** stop a parent finaliser release). Remind that suivi is opt-in at `/init`.

Paths: **`agents/roles.yml`**. Convention: **`docs/suivi-avancement/README.md`**.

## 0. Version

Infer the version from the user message, or from the open version branch / PR when called from finaliser: **`<nom>`** from `version/<nom>` (old form `vX.Y.Z-…`: that number), its **`<Titre>`** from the roadmap, and its **Release number** `X.Y.Z` when it has one (finaliser passes it; none for a version without Release). If missing: ask and **wait**.

Below, **`<id>`** = `<nom>` (old form: `X-Y-Z`), and the version is **cited by its title**: `VX.Y.Z — <Titre>` once released, `<Titre>` otherwise.

## 1. Locate the week HTML

Under role **`suivi-avancement`**, find folder `semaine-…` whose lun–ven range (Europe/Paris) **contains today**. Parse folder names as in the README (*Noms*): `semaine-<lun>-<ven>-<mois>-<année>`.

Inside that folder: first `suivi-semaine-*.html` (flexible name — README).

**None** → one line soft-skip: no week file; remind **`/os`** / « ouvre la semaine de travail ». Do **not** stop a parent finaliser release. Do not invent a folder.

Done when: HTML path known, or soft-skip done.

## 2. Update the HTML for the version

Follow **`docs/suivi-avancement/README.md`** (*Structure HTML*, *Langage*):

1. TOC: ensure an entry `#version-<id>` under Descriptif des versions, labelled as above.
2. Bloc `.version#version-<id>`: create if missing; heading `VX.Y.Z — <Titre>` (no Release: `<Titre>`, and say « Sans Release » in the body); set badge to  
   `Déployé le JJ/MM/AAAA à HH:MM` (`.deploye`, drop `.prevu`); body = what shipped in **functional product** language (no stack, no tool package names, no `#ticket` in day bullets / version body).
3. **Travail réalisé**: add a bullet on **today’s** `.jour` (or the ship day if the user gives it).
4. **Livré pour** / recap: fold the version into the “livré” side.
5. **Reste à implémenter**: remove the version if listed as still todo (by title).
6. **Order**: keep `.version` blocks and their TOC entries chronological — shipped versions by `Déployé le` date and time, not by version number, then planned versions. Move the block and its TOC entry when the version ships out of order.

Do **not** edit other weeks. Do **not** rewrite the whole HTML without need.

## 3. PDF

If **`docs/suivi-avancement/generer-pdf.mjs`** is **absent** → one line soft-skip: HTML updated, PDF skipped (no script in this repo). Continue.

If present, from repo root:

```bash
node docs/suivi-avancement/generer-pdf.mjs <chemin-du-html-ou-dossier-semaine>
```

If the script fails (PDF locked, no Chrome/Edge, …): **stop**. HTML may already be updated — say so in one line and tell the user how to fix (close the PDF, install Chrome/Edge, rerun the command). Do not invent another print method.

## 4. README aperçus (typed `/msa` only)

Called by **`finaliser-la-version`** → skip: it regenerates the aperçus after the Release (step 4), so « Dernières versions » shows the new version.

Typed **`/msa`** (opt-in) — only when role **`docs-site`** resolves and `docs-site/scripts/capturer-apercus-readme.mjs` exists: from the repo root, run `node docs-site/scripts/capturer-apercus-readme.mjs`, so the README capture of the suivi matches the HTML. It soft-skips (exit 0, `[apercus-readme] soft-skip : …`) when the README shows no aperçu or Playwright is missing: one line, continue. Never leave this to a bot commit on **base**. Changed `docs/img/apercu-*.png` / `README.md` go in the same later `/c` as the suivi HTML; a `README.md` diff made only of line endings → `git checkout -- README.md`.

Done when: HTML updated and PDF regenerated (or soft-skip: no week / no script / parent finaliser), and, for a typed `/msa`, aperçus attempted (or soft-skip).

## Not this skill

- Create the week → `ouvrir-semaine-de-travail` (`/os`)
- Commit / push → `commit` (`/c`)
- Finalise / tag / merge → `finaliser-la-version`
