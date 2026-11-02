---
name: remonter-au-pack
description: >-
  From a project, list every local change to files that come from
  workflow-agents-pack, sort them (pack bug, generic improvement,
  project-specific, project lagging), wait for oui, then port the chosen ones
  into a local pack checkout and mark them « reporté » in
  agents/docs/ecarts-avec-le-pack.md. Use when the user types `/rap`, says
  « remonte au pack », « reporte dans le pack », or when `/up` is refused
  because a row is « à reporter ». Not `/up`. Does not commit.
---

# Remonter au pack (`/rap`)

Triggered by **`/rap`**, **« remonte au pack »**, or **« reporte dans le pack »**.

Run from the **project** root. The other way round from **`mettre-a-jour-le-pack`** (`/up`): the project changed files that the pack owns; bring the best of it back **before** `/up` overwrites it.

Do **not** run `/up` here. Do **not** commit or push, in the project or in the pack, unless the **current** user message also asks for **`/c`**.

## 0. Guards

1. `agents/skills/` missing → **stop** (not a pack project).
2. Pack checkout: a path in the user message to a **local git checkout** of `workflow-agents-pack` (it contains `agents/scripts/update-from-pack.sh`). Missing → ask for it and **wait**. Never a temporary clone: the changes must survive this skill.
3. Pack checkout has uncommitted changes → say so in one line and ask whether to continue on top of them; wait.

## 1. Base

**`BASE`** = `agents/.pack-sha` of the project (the pack commit of the last `/up`). Missing → ask which pack commit or tag the project was last synced from, and wait. `git -C <pack> cat-file -e <BASE>` fails → `git -C <pack> fetch`, then retry; still missing → **stop**.

## 2. Inventory (read-only)

**Pack-owned files** = what `/up` would overwrite, read at `BASE` with `git -C <pack> show <BASE>:<path>`:

| Project path | Pack path at `BASE` |
| --- | --- |
| `agents/skills/{meta,process}/<name>/**` | same, for each `<name>` present in the pack |
| `agents/hooks/<name>/**`, `.claude/hooks/<name>.py`, `.cursor/hooks/<name>.sh` | same, for each pack hook |
| `agents/scripts/*` | same names |
| `agents/README.md`, `agents/issue-tracker.md`, `agents/triage-labels.md`, `agents/domain.md`, `agents/docs/*.md` (pack names only) | same |
| `docs-site/<p>` for each `<p>` of `agents/templates/docs-site/PACK_OWNED.txt` | `agents/templates/docs-site/<p>` |
| `.github/workflows/deploy-docs.yml`, `build-docs.yml` | `agents/templates/github/workflows/` |
| `docs/dev/feuille-de-route/README.md`, `AGENTS.md`, `.claude/CLAUDE.md`, `agents/roles.yml` | `agents/skills/process/initialise-le-repo/references/…` (project-owned copies: compare, but only conventions are candidates, never project values) |

For each pair, diff project vs pack@`BASE`, and pack@`BASE` vs pack `HEAD`:

- project = pack@`BASE` → no local change. Skip.
- project ≠ pack@`BASE` → **local change**. If pack `HEAD` also changed that file since `BASE` → mark **both changed** (port by hand, never overwrite the pack's newer text).

Also read `agents/docs/ecarts-avec-le-pack.md`: every row « à reporter » must appear in the inventory (its own description explains the why).

Also list, for information, skills and hooks that exist **only** in the project (`/up` keeps them; they are candidates only if the user asks).

## 3. Sort

Put each local change in exactly one class, in French, one line of why:

- **Bug du pack** — the project fixed something broken in the pack (crash, wrong format, portability). Port as is.
- **Amélioration générique** — useful to any project; port after removing project names, owner/repo, project paths (use roles from `agents/roles.yml`) and project vocabulary.
- **Variante optionnelle** — a behaviour some projects need: port behind an **opt-in** (an optional role in `agents/roles.yml`, or an optional file like `agents/integration-channel.yml`) so that its absence keeps the current pack behaviour exactly.
- **Spécifique au projet** — stays in the project. If `/up` would overwrite it, propose where it can live without being a pack file (project skill, `agents/docs/guide-projet.md`, `AGENTS.md`, a role value).
- **Retard du projet** — the project's copy is simply older than the pack (e.g. a section the pack added and the project never got). Not a change to port; `/up` will fix it.

## 4. Propose, then wait

A numbered table: file(s), class, what would change in the pack (one line), and **both changed** when it applies. For each **Variante optionnelle**, name the opt-in switch.

**Wait** for an explicit **oui**, or a subset (« 1, 3, 4 seulement »). Anything else → **stop**. Write nothing.

## 5. Port into the pack

In the pack checkout, on a new branch `remontee-<projet>-<AAAA-MM-JJ>` from its default branch (or the current branch if the user said so in step 0.3):

1. Apply each accepted item to the pack source (`agents/…`, `agents/templates/…`, `references/…`), generalised as in step 3. Keep the pack's style (skills in English with French user-facing lines, scripts commented in French).
2. A change to a pack hook: keep its adapter copies and its entries in `references/settings-hooks.json` and `.cursor/hooks.json` in step (`agents/docs/guide-hooks.md`).
3. A new convention that existing projects must adopt (path, role, section of a project-owned file) → one row in `agents/docs/migrations-pack.md`, so `/up` proposes it.
4. Update `agents/docs/guide-skills.md` / `guide-hooks.md` when a command, option or hook changes.
5. `python3 agents/scripts/dispatch.py` then `--check` in the pack. Fail → **stop** and report.
6. Run the proofs the pack already has for what you touched (e.g. `python3 agents/hooks/<name>/test_hook.py`, `bash -n` on scripts, `node --check` on docs-site scripts).

## 6. Mark the register

In the **project**, `agents/docs/ecarts-avec-le-pack.md` (copy `references/ecarts-avec-le-pack.md` of the pack if missing):

- each ported item → its row with status **reporté** (add the row if the change was not registered);
- each item the user chose to drop → **abandonné**;
- **Spécifique au projet** items that `/up` would overwrite stay **à reporter** until moved out of pack files — say so.

## 7. Reply

French summary: ported items (pack branch name), dropped items, items left « à reporter » and why, **both changed** items to review by hand. Then the next steps, in order: review and commit the pack branch (`/c` in the pack, PR, merge), then **`/up`** in the project with the local pack path.

## Not this skill

- Bring the pack into the project → `mettre-a-jour-le-pack` (`/up`)
- First install → `adopter-le-pack.sh` / `/init`
- Commit / push → `commit` (`/c`)
- New project-only skill or hook → `creer-skill` (`/cs`) / `creer-hook` (`/ch`)
