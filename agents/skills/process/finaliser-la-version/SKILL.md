---
name: finaliser-la-version
description: >-
  When the user says « Finalise la version », « finalize the version »,
  « clôture la version », or asks to ship/squash-merge the current version
  PR: fix the version's number from its Type (none for a version without
  number), publish a pre-release for the staging trial when the project has
  a staging role, then the final GitHub Release, push a single commit after
  it, tick the PR Test plan, squash and delete the feature branch. Reads the
  Sonar quality gate once on the PR HEAD before the tag. Not for a single
  child ticket or /implement.
---

# Finalise the version

Triggered by **« Finalise la version »** (or equivalent), only after the user accepted a **`/code-review`** of this branch. Do **not** run `/code-review` here. Release and squash go through **`creer-release`** (`/crel`) and **`fusionner-pr`** (`/mpr`), not inline. Docs commit goes through **`commit`** (`/c -a -p`). The quality gate is step 3, after that review and after the docs.

A version = one feature branch + one PR that ships a **set** of child issues (parent spec). Starting a version is skill `ouvrir-la-version`.

Do **not** `/implement` here. Do **not** `gh issue close` children here (they should already be Closed). Do **not** close the parent by hand — squash `Fixes` does that.

Paths: **`agents/roles.yml`**.

## 0. Locate the PR

Resolve **base** / release **tag** prefix per `agents/docs/integration-channel.md`. Current branch must not be **protected** (`main` / `master` / **base**). Resolve the open PR for this branch (`gh pr view`). If none, stop. PR base must be **base**. Releases via `/crel` use **tag(X.Y.Z)** (e.g. `orchestrator-v0.1.0` on this channel).

**Version name `<nom>`**: from the branch `version/<nom>`. Branch opened before the rule (`vX.Y.Z-<slug>`): the roadmap's `**Nom.**` of the version whose title matches the PR title (`docs/dev/feuille-de-route/feuille-de-route-dev.md` names each such branch). Unsure: ask and **wait**. **`<Titre>`** = that version's roadmap title (PR title without any `VX.Y.Z — ` prefix). **`<parent>`** = the spec issue (`Fixes #<parent>` of the PR, `Issue parente` of the spec). The spec is `docs/specs/<nom>.md` (old branch: `docs/specs/vX.Y.Z-….md`).

**Up to date with base.** `git fetch`, then `git rev-list --count HEAD..origin/<base>`. `0` → continue. Otherwise another version shipped on **base** while this one was built in parallel, and the Release must contain it: say in one line how many commits and which versions (`git log --oneline HEAD..origin/<base>`), then merge **base** here, do not hand it back to the user.

1. Working tree not clean → **stop**.
2. `git merge --no-edit origin/<base>`. Conflicts → skill **`resolving-merge-conflicts`**: keep both versions; where both add to the same list (fields, routes, registry entries, sections of a page, docs), keep both in the roadmap order. Roadmap, README banner and its image: the rule of **`debloquer-la-feuille-de-route`** step 2 (step 2 below recomputes them).
3. Look for what git merges silently: migrations that share a number or a parent (renumber this branch's after base's, which already shipped), columns or fields both sides add, symbols base renamed, tests and helpers that assume only one side's entries, e2e scenarios git interleaved (rebuild them as separate tests).
4. Lint and typecheck each brick, then **`/t -a`** (a merge breaks more than its diff shows). Fail → fix it on the branch.
5. Run skill **`commit`** as if **`/c -a -p`** (the merge commit), then continue this step on the new `HEAD`.

**Stop** only when a conflict needs a product decision (both versions changed the same behaviour in incompatible ways): list the files and the choice to make, and tell the user to run « Finalise la version » again once it is made.

A merge after a pre-release changes `HEAD`: the next pass publishes a new `rc.<k+1>` (step 4), never the final Release on an untried SHA.

**Definitive number `N`** (rule: `docs/dev/feuille-de-route/README.md`, *Nom, Type et Numéro prévu*). After `git fetch --tags`, from the repo root: `node scripts/numero-definitif.mjs <nom>` (opt-in, project-owned script; when it is missing: apply the rule below by hand from the version's **`Type.`** and `gh release list --exclude-pre-releases`). It reads the version's **`Type.`** in the roadmap, the last published Release and the role **`livrables`** diff (`git diff --name-only origin/<base>...HEAD`, ignoring `tests/` and `*.md`), and prints one JSON line:

- **`majeure`** → `X+1.0.0`, **`mineure`** → `X.Y+1.0`, **`correctif`** → `X.Y.Z+1`, after the last Release `X.Y.Z`. That is **`N`**.
- **`documentation`**, **`analyse`**, **`évaluation`**, **`process`** → **`N` = none**: no Release, no tag (step 4 skips `/crel`).
- Exit `1` = **incoherence**: a version without number that touches `livrables`, or a numbered one that touches none. **Stop**. Quote its message and the `livrables` files of the diff, and ask: change the version's **`Type.`** (`/afr`, then Finalise again), or move those files out of this version. Never pick a number by hand to get past it.
- Exit `2` → **stop**, quote the error.

**Reserved numbers** (`agents/issue-tracker.md`, *Pre-release*): this version already has a pre-release (a Release marked *Pre-release* whose notes carry `Version : <nom> (#<parent>)`) → **`N`** = its number, whatever the script says. Otherwise, an rc tag `vA.B.C-rc.<k>` of **another** version whose final `vA.B.C` does not exist reserves `A.B.C`: take the next free number of the Type after it.

Say in one line the type, the last Release and **`N`** (e.g. « mineure après v1.15.0 → **1.16.0** », or « process : sans Release »). The roadmap's **N° prévu** is a forecast: **`N`** may differ when another version shipped first; say so if it does.

Below, **`V<N>`** = `VN` when **`N`** exists, else `« <Titre> » (sans Release)`.

## 1. Every related issue is published

Related = listed in the PR body (`Fixes` / `Part of`) **and** children of the parent spec that are in scope for this PR. Ignore `wontfix` and issues the PR or parent spec mark as out of this version. See `agents/issue-tracker.md`.

**Published** = each in-scope **child** is **Closed** — including the **human-test** child (`ready-for-human` / title `Tests humains — <nom>`, old form `Tests humains — VX.Y.Z`). An Open human-test ticket **blocks** Finalise; tell the user to finish with **`/th`** first. Its **Branche** scenarios are the ones that block here; its `## À jouer en staging` scenarios are played on the pre-release (step 4) and block the final Release, not this step. The **Essai en staging — VN** child is not checked here either: step 4 reads it.

If any in-scope child is still **Open**: **stop**. List what’s missing. Do not tag, merge, or delete.

The **parent** spec may still be Open until squash. Leave it Open here.

If the PR body’s `Fixes` line would not close the **parent** on squash, **edit the PR body first** (`Fixes #n` once per issue; include `Fixes #<parent>`). Children already Closed are fine to leave in `Fixes` (no-op).

## 1 bis. No open Dependabot PR

Only when `.github/dependabot.yml` exists (missing → one line, continue). Run `gh pr list --state open --author app/dependabot --base <base> --json number,title,url,headRefName`.

- Empty → continue.
- Otherwise **stop**. Do not tag, merge, or delete. List each PR: number, title, link, kind (**groupée** = minor/patch group, title mentions « group »; else **majeure**), and its CI in one word from `gh pr checks <n>` (verte / rouge / en cours). Tell the user each one must be **resolved** first: **merged**, or **closed** (closing = skipping that version; Dependabot will not propose it again). Do not merge or close them yourself unless the user asks.

Once they are resolved, a merged one moved **base**: on the next « Finalise la version », step 0’s « up to date with base » rule merges **base** into the version branch first.

Same rule outside the agent, when the project uses it: check `Dépendances à jour` (template `agents/templates/github/workflows/dependances-a-jour.yml`). Listed in `agents/checks-requis.yml` (or the ruleset), step 4 and `/mpr` refuse too.

## 2. Docs must match this version (before tag and squash)

Read each role below (paths from `agents/roles.yml`), against the parent spec / ADRs / code that this PR actually ships:

- **`readme`** — matches what this version shipped. Extra README checks live in role **`agent-adapter`**; do not invent a layout.
- **`glossary`** — glossary and ADR links match the model (new terms, reversed decisions).
- **`agent-adapter`** — adapter still valid (hook, `/implement` close, Standards pointer); skills named there exist under `agents/skills/` (synced to the IDE adapters); implement / finalise cycle matches those skills; process docs still match (tracker, labels, domain).
- **`spec`** — spec for this version exists there.
- **`adr`** — new ADRs if decisions changed.
- **`roadmap`** — follow **`docs/dev/feuille-de-route/README.md`** (*Déjà livré*): move the version into **Déjà livré**, one bullet — with **`N`**: ``- **N** — <Titre> (`<nom>`, [#<parent>](…), [spec](…)) : résumé…``; without: `- **<nom>** — <Titre> ([#<parent>](…), [spec](…)) : résumé… Sans Release.` (the script reads both as shipped and lifts the blockers that cite `<nom>`); drop it from **Prochaine** / **Ensuite**; the first remaining **Ensuite** becomes the sole **Prochaine** (keep its Objectif / Hors périmètre) — with blockers (`scripts/deblocages-feuille-de-route.mjs` exists), do not pick it by hand: the next bullet recomputes it. Drop claims this version has **not** delivered. Do not invent new versions; only reshuffle what is already listed. New version ideas → leave for **`/afr`**.
- **Roadmap progress** — only when `scripts/avancement-feuille-de-route.mjs` exists (opt-in, project-owned script): after the **`roadmap`** edit, run `node scripts/avancement-feuille-de-route.mjs` from the repo root (local, no token). It counts **Déjà livré** over **Déjà livré** + **Prochaine** + **Ensuite**, recomputes the **`N° prévu.`** of every remaining version from the new last Release (**`N`**), and rewrites the README progress banner and its image. They enter the same docs commit as the roadmap, hence the squash: no bot commit on **base**. Fails → **stop**. **With blockers** (`scripts/deblocages-feuille-de-route.mjs` exists, README *Blocages*): run skill **`debloquer-la-feuille-de-route`** as if the user had typed **`/dfr`** instead of the script alone — it merges **base** into the branch when the roadmap changed there since the branch was cut, runs the script (which also recomputes **`État.`** and **Prochaine**), and reports what this version unblocked; show that report in the final summary.
- **Bugs fixed by this version** (same docs commit as roadmap):
  1. From the open PR body, collect every `Fixes #<n>` / `Fix #<n>` / `Closes #<n>`.
  2. Keep only issues that still have label **`bug`** (`gh issue view <n> --json labels`). Also include any `#n` the parent **spec** / version narrative explicitly says this version closes, if it has label `bug` and is missing from the PR — then **edit the PR body** to add `Fixes #<n>` (same rule as step 1 for the parent).
  3. On role **`roadmap`**: delete each matching `### Bug — … (#n)` block under **Plus tard** (from that heading through the line before the next `###` / `##`). Already absent → OK.
  4. For each such `#n` still **Open**: `gh issue close <n> --comment "Corrigé en VN."` (**`N`**, step 0), or `Corrigé dans « <Titre> ».` for a version without number. Already Closed → one line, continue.
- **`suivi-avancement`** (opt-in) — if that role is **missing or unresolved** in `agents/roles.yml` → one line soft-skip (suivi not enabled for this repo). Do **not** stop the release. If the role **is** resolved: run skill **`mettre-a-jour-suivi-avancement`** as if the user had typed **`/msa`** for this version (`<nom>`, and **`N`** when it exists) (convention: **`docs/suivi-avancement/README.md`**). That skill soft-skips with a **`/os`** reminder when there is no current-week folder (do **not** stop the release). PDF failure after an HTML edit (when `generer-pdf.mjs` exists) → **stop** the release until fixed. Do not create a week folder here. Do not edit other weeks.
- **`docs-site`** (opt-in) — if that role is missing → soft-skip (no site). If it is resolved: the Docusaurus site refreshes via GitHub Pages on the squash-merge push (workflow `deploy-docs.yml` — build + Pages only, no bot push on **base**). Do **not** run `npm run build` here. README aperçus are **not** regenerated here: « Dernières versions » is built from the GitHub Releases, so a capture before `/crel` still shows the previous version. They come in step 4, after the final release.

If anything is stale (except soft-skip on missing suivi / docs-site role / missing week HTML / missing PDF script): **stop the release**. Update those files on the **feature branch**, then run skill **`commit`** as if the user had typed **`/c -a -p`**. Then re-read this section. Do **not** `/crel` or `/mpr` until this gate is green — the tag must include the docs (HTML + PDF when updated); only the README aperçus come after it (step 4). Bug issue closes (step above) may run in that same docs turn; they do not require a second commit.

## 3. Quality gate

One read, on the PR `HEAD` after the docs commit. This analysis covers the branch, not one child. Do not reopen children. Do not add a label.

Load `.env` the same way **`quality-gate`** does. If any of that skill’s three `SONAR_*` keys is missing or empty → continue. One line that Sonar is skipped. Do not `/qg`. Do not `/cqg`.

Otherwise run **`quality-gate`** as if **`/qg -w`**.

- No analysis for `HEAD` after the wait → **stop**. Do not `/crel` or `/mpr`.
- **`OK`** → continue.
- Not **`OK`** (`ERROR`, `WARN`, …) → run skill **`corriger-quality-gate`** as if **`/cqg`**.
  - That skill stopped without a code change (policy / user needed) → **stop**. Do not `/crel` or `/mpr`.
  - Working tree dirty after the fix → run **`/t`** (fail → **stop**). Stage the files that fix touched and run skill **`commit`** as if **`/c -p`**. Then **`/qg -w`** once. Not **`OK`**, or no analysis this time → **stop**. Do not `/crel` or `/mpr`.

## 4. Pre-release, Release, then squash

**Required checks first** — only when `agents/checks-requis.yml` exists. Same rule as step 1.4 of **`fusionner-pr`**: run `python3 agents/scripts/checks-requis.py <PR number>` on the PR `HEAD`; only `en attente` → `gh pr checks <PR number> --watch`, then once more. Any check still `rouge`, `en attente` or `absent` (or exit `2`) → **stop**: name each faulty check. Do not `/crel` or `/mpr`. A red PR gets no tag. (`/mpr` checks again after the aperçus commit below.)

**Which pass.** Two passes only when role **`staging`** resolves in `agents/roles.yml` **and** **`N`** exists **and** the Closed human-test child lists at least one **Staging** scenario under `## À jouer en staging` (`agents/issue-tracker.md`, *Pre-release*). Otherwise one pass: go to **4b**.

- No pre-release of this version yet → **4a** (`rc.1`).
- A pre-release exists and its **Essai en staging — VN** child is Open:
  - `HEAD` = the SHA of the last `vN-rc.<k>` tag → **stop**: the trial is still running. Tell the user to play it with **`/th #<essai>`** once staging runs `vN-rc.<k>`.
  - `HEAD` moved since that tag (a fix after a KO, a merge of **base**) → **4a** (`rc.<k+1>`).
- The Essai child is **Closed** with every scenario OK on the last rc:
  - `HEAD` = the SHA of that rc tag → **4b**, on that SHA.
  - `HEAD` moved since → **stop**: that SHA was never tried in staging. Say what changed (`git log --oneline <rc-tag>..HEAD`) and that the next « Finalise la version » will publish `rc.<k+1>` once the Essai child is reopened (`gh issue reopen`); do it only if the user says so.

### 4a. Pre-release for the staging trial

1. Run skill **`creer-release`** as if the user had typed **`/crel vN-rc.<k> --prerelease`**, with purpose `<Titre>`, version name `<nom>` and parent `#<parent>`. That skill writes the **minimal** pre-release notes (`agents/issue-tracker.md`, *Pre-release*): no screenshots, no human-test illustration, no aperçus, no counters. Wait until it is visible: the project's `release: published` workflows build and attach the artifacts.
2. **`rc.1`** → create the child **`Essai en staging — VN`** in the shape of `agents/issue-tracker.md` (*Essai en staging child*): label **`ready-for-human`**, `Part of #<parent>`, sub-issue of the parent, parent blocked by it, `## Pré-release à essayer` = `vN-rc.1`, `## Plan de tests` = the Staging scenarios of the human-test child, unticked. **`rc.<k>`, `k` > 1** → on the same child, `gh issue reopen` if needed, set `## Pré-release à essayer` to `vN-rc.<k>` and untick `## Plan de tests` (keep `## Résultats`: the previous rc's block stays).
3. **Stop** here: no README commit, no Test plan, no squash. Tell the user, in French: the pre-release URL, that staging must run `vN-rc.<k>` (role **`staging`** doc says how), then **`/th #<essai>`**; all OK → « Finalise la version » again for the final Release; a KO → fix on this branch, then « Finalise la version » again for `rc.<k+1>`.

### 4b. Final Release

**`N`** = none → no `/crel`: one line « Pas de Release (type <Type>) », then the single commit below, the Test plan, then `/mpr`.

Otherwise run skill **`creer-release`** as if the user had typed **`/crel vN`**, with purpose `<Titre>`, version name `<nom>` and parent `#<parent>` for the notes (`Version : <nom> (#<parent>)`). That skill owns title (`VN — <Titre>`) and notes layout (the full one, with the human-test illustration). After a pre-release, the target is the SHA of the last rc tag, which is `HEAD`. **Gestures for the administrator:** list what the administrator must do once the server runs this version (new secret to set, command to run, setting to check), from the spec, the child tickets and `git diff --name-only origin/<base>...HEAD`; pass them so the notes get a `## Pour l’administrateur` section (`agents/issue-tracker.md`, *Release notes*). None → no section. Wait until the release is visible.

After a pre-release: delete the pre-release **Releases** of this version (`gh release delete vN-rc.<k> --yes` for each `k`, **without** `--cleanup-tag`): the tags stay. One line listing them.

**Two CI cycles, the second one tiny.** A version runs the PR CI twice at this stage:

1. **The Release CI** — the full suite on the SHA that gets the tag. The required checks above are green on it: that is what was released.
2. **The counters CI** — on the single commit below, after the Release. That commit only touches `README.md` and `docs/img/`: its CI must be **tiny** — the required checks answer in seconds without rerunning builds, tests or e2e (model: `scripts/ci-eclair.mjs`, from `initialise-le-repo/references/scripts/`, called by a `changes` job of the PR workflow; or a paths filter). Nothing it could break was not already tested.

If the project's CI reruns everything on that commit, say so in one line of the final summary (« la CI du compteur rejoue toute la suite : à alléger ») and continue; never `[skip ci]` (the required checks must answer on the new `HEAD`).

**One commit after the Release.** The README aperçus and the commit counters below go in **one** commit: compute both, then commit once.

**README aperçus** (opt-in) — only when role **`docs-site`** resolves and `docs-site/scripts/capturer-apercus-readme.mjs` exists: run `node docs-site/scripts/capturer-apercus-readme.mjs` from the repo root. It soft-skips (exit 0, `[apercus-readme] soft-skip : …`) when the README shows no aperçu or Playwright is missing: one line, continue. Otherwise, when the README shows `docs/img/apercu-docs-accueil.png` and **`N`** exists, open that image and check **`vN`** heads « Dernières versions »; if not, the build did not see the release → **stop**. A `README.md` diff made only of line endings → `git checkout -- README.md`. Leave the changed files (`docs/img/apercu-*.png`, `README.md`) **uncommitted**: they go with the counters. Never rely on a bot commit on **base** after Finalise.

**README commit counters** — only when `scripts/stats-commits-readme.mjs` exists. One commit per version on **base**: the counters enter the squash, no bot commits after it. From the repo root, on the version branch with its PR open, aperçus still uncommitted: `GH_TOKEN="$(gh auth token)" node scripts/stats-commits-readme.mjs --avant-squash`. It anticipates the squash with **one** commit after the Release (commits on **base** + 1; commits of merged PRs + those of this PR + that single commit, aperçus and counters together) and prints `déjà à jour` when that commit is already in the PR. Fails → **stop**. Do not `/mpr`.

Then the single commit: nothing changed (aperçus and counters) → one line, continue. Otherwise stage only `README.md` and the changed `docs/img/apercu-*.png` and run skill **`commit`** as if **`/c -p`**. The tag stays on the pre-commit SHA: do **not** move it. A second commit after the Release is a mistake: never commit the aperçus and the counters apart.

**PR Test plan** — just before the squash, once the required checks of the final `HEAD` (after the single commit) have answered (`gh pr checks <PR number> --watch`), `gh pr view --json body`. Under `## Test plan`, tick (`- [ ]` → `- [x]`) each box proven now (`agents/issue-tracker.md`, *PR `## Test plan`*):

- a test suite / CI line → proven when the required checks of the PR `HEAD` are green (`agents/scripts/checks-requis.py`, or `gh pr checks`);
- a child line (`#<n>`) → proven when that child is Closed;
- the human tests → proven when the human-test child is Closed;
- the staging trial → proven when the Essai en staging child is Closed; none → append `— sans objet : aucun scénario Staging` / `— sans objet : pas de Release`.

A box neither proven nor explained → **stop**, quote it and ask (prove it, reword it, or drop it). Write back with `gh pr edit --body-file` (full body; change nothing else).

**Titles** — **`N`** exists: `gh pr edit --title "VN — <Titre>"` (the squash subject) and `gh issue edit <parent> --title "VN — <Titre>"`. **`N`** = none: both keep `<Titre>`.

Then run skill **`fusionner-pr`** as if the user had typed **`/mpr`**.

## 5. Annotate earlier versions

Read the spec section **Changements apportés aux versions antérieures** (format and blocks: `agents/issue-tracker.md`, *Changes to earlier versions* **and** the Critical newline rules there). `Aucun.` or no section → one line, go to step 6. Otherwise annotate each row's targets:

1. `gh release view <tag> --json body` — keep the existing notes.
2. Prepend each new `> **Modifié en VN** …` blockquote (version without number: `> **Modifié dans « <Titre> »** …`) **with blank lines between blocks**, then a blank line, then the previous body starting at `## Pourquoi` (or whatever already headed the notes).
3. Write with `gh release edit <tag> --notes-file` (UTF-8 file). Never collapse the body to a single line.
4. Same block as a comment on each listed issue.

Never stop the version on this step: a target that fails is listed in the final reply.

## 6. Stop

Final summary: **`N`** (or « sans Release ») and the Release URL, the pre-releases deleted (tags kept) or why there was none, the squash SHA, whether the counters CI stayed tiny, and the `/dfr` report. After **4a**, the summary is the pre-release URL and the Essai child instead (no squash yet).

Do not start the next version’s branch unless the user asks.

## Not this skill

- Release only → `creer-release` (`/crel`)
- Squash-merge only → `fusionner-pr` (`/mpr`)
- Commit / push → `commit` (`/c`)
- Child wrap → `encadrer-implement`
- Open a version → `ouvrir-la-version`
- Human-test results / close → `tests-humains` (`/th`)
- Feuille de route de dev only → `augmenter-la-feuille-de-route-dev` (`/afr`)
