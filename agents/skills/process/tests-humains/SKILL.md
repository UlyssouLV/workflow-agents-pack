---
name: tests-humains
description: >-
  Run the version's human-test plan: the agent plays the scenarios it can
  alone (with screenshots), lists what only the human can do, then records
  the human's results, commits screenshots, updates the issue body, and
  closes the ready-for-human child — « Tests humains » on the version
  branch, or « Essai en staging — VX.Y.Z » on staging, on the pre-release
  vX.Y.Z-rc.<k>, before the final Release. Use when the user types `/th` or `/th #<n>`, says
  « tests humains » / « essai en staging », or reports which scenarios they
  ran after the plan from encadrer-implement. Not `/implement`. Not `/cci`.
---

# Tests humains (`/th`)

Triggered by **`/th`**, **`/th #<n>`**, or when the user reports human-test results for the current version (after `encadrer-implement` wrote the plan). This path **is** permission to edit and close the **human-test child** (or the **staging-trial child**) only, to run the app / browser to play its scenarios, and to commit screenshots via skill **`commit`**.

Paths: **`agents/roles.yml`**. Ticket shapes: **`agents/issue-tracker.md`** (*Human-test child*, *Essai en staging child*).

Two kinds of ticket, same passes:

- **Tests humains — `<nom>`**: the **Branche** scenarios of `## Plan de tests`, played on the version branch, before Finalise. `## À jouer en staging` is **not** played here: Finalise copies it into the staging trial with the first pre-release.
- **Essai en staging — VX.Y.Z**: the **Staging** scenarios, played on the staging environment (role **`staging`** doc) running the pre-release named in `## Pré-release à essayer` (`vX.Y.Z-rc.<k>`). The version branch is still open: the final Release waits for this child to close.

Two passes on the same ticket, possibly in different sessions. The issue body carries the state between them:

- **Pass A — agent:** no human results in the message, and the ticket has no `Joué par l’agent` results yet. Play what you can alone, publish, **stop**.
- **Pass B — human:** the message carries human results (text and/or images), or a plain go (« ok », « valide ») once pass A left nothing for the human. Merge, close.

A message with no results while pass A is already on the ticket: recap what is still waiting for the human and **wait**. Do not replay, do not close.

## 1. Find the ticket

**`/th #<n>`:** `gh issue view <n>`. It must be Open, label **`ready-for-human`**, title **`Tests humains — <nom>`** (old form, before the named-version rule: **`Tests humains — VX.Y.Z`**). Otherwise say why and stop. Take the **version** (`<nom>`, or `X.Y.Z` in the old form) from that title.

**`/th` without a number:** infer the version from the branch — `version/<nom>`, or the old form `vX.Y.Z-<slug>` (missing: ask and **wait**). Find the open child titled **`Tests humains — <nom>`** (or **`Tests humains — VX.Y.Z`**) with label **`ready-for-human`** (parent via `Part of`). None Open: say so and stop. Several: ask which `#n` and wait.

**Staging trial** (`/th #<n>` on a title **`Essai en staging — VX.Y.Z`**, label **`ready-for-human`**, or `/th` on the version branch once the human-test child is Closed: the open child with that title): the pre-release is the tag in `## Pré-release à essayer` (`vX.Y.Z-rc.<k>`). Check the working tree is on the version branch and that staging runs that rc (how to check: role **`staging`** doc; not yet → say staging has not picked the pre-release up, and **stop**). Every scenario runs **there**, never locally. Results go under `## Résultats` in a `### vX.Y.Z-rc.<k>` block (keep the blocks of earlier rcs).

If `## Plan de tests` is still the placeholder: stop and say the plan comes from `encadrer-implement`.

**Tests humains** only: check the working tree is on the version branch (`version/<nom>`, or `vX.Y.Z-…` in the old form). Otherwise stop: the scenarios must run on the code under test.

## 2. Pass A — play what the agent can

### 2a. Sort the scenarios

For each scenario of `## Plan de tests`, decide:

- **Agent:** you can run it and see the outcome yourself: a CLI command, a script, an HTTP call, the app launched locally (skill **`run`** or the project's own launch skill), a page driven in the browser (Claude in Chrome / Playwright).
- **Humain:** it needs something you do not have or must not do: a physical device, a real account or secret not in the environment, a payment or e-mail to a real person, an irreversible action on shared data, or a judgement the plan leaves to the human (look and feel, wording, « est-ce clair »).

Doubt → **Humain**. Never fake a pass: a scenario you started but could not observe to the end is **Humain**, with what blocked you.

### 2b. Play the Agent scenarios

One at a time, in plan order. For each: what you did, what you saw, **OK** / **KO**, and a screenshot whenever there is a screen (UI, terminal output worth showing). Save under **`docs/img/changelog/<version>/`** (`<version>` = `<nom>`, or `vX.Y.Z` in the old form) with short kebab ASCII names (`scenario-1-liste.png`, …).

A **KO** is a result, not a stop: note it and go on. Do not fix code in this skill.

Stop the app / servers you started when done.

### 2c. Publish and stop

1. Screenshots exist → run skill **`commit`** as if the user had typed **`/c -a -p`** (message: preuves des tests humains joués par l’agent, <version>). Note the pushed SHA.
2. `gh issue edit <n> --body` (full body; keep every other section):
   - **`## Plan de tests`**: check the Agent scenarios that passed; annotate each line `(agent : OK)`, `(agent : KO — …)` or `(humain)`.
   - **`## Résultats`**: a `### Joué par l’agent` block, one entry per Agent scenario with outcome and its screenshot (`https://github.com/<owner>/<repo>/raw/<sha>/docs/img/changelog/<version>/<file>.png`); then a `### À jouer par l’humain` block listing the Humain scenarios with why.
3. Tell the user in French, then **stop** (the ticket stays Open):
   - what passed / failed (KO first);
   - the numbered list of scenarios that are theirs, each with what to do and what to look at;
   - next: `/th #<n>` with their results (text, captures optionnelles). If nothing is left for them: `/th #<n> ok` after looking at the captures on the ticket.

## 3. Pass B — read the human report

From the **current user message** (and images attached in this chat):

- Which of the remaining scenarios were **played** (pass / fail / notes); the human may also overturn an agent result
- Which were **not played** (short reason OK)
- Product bullets for **Ce qu’on peut faire maintenant** if the human stated them; otherwise draft them from the played scenarios + parent spec (product language)

Partial plans are OK. Do not invent failures the human did not report. Keep the `### Joué par l’agent` results already on the ticket.

## 4. Screenshots from the human (optional)

If the chat includes images meant as evidence:

1. Save them under **`docs/img/changelog/<version>/`** (create the folder). Filenames: short kebab ASCII (`scenario-3.png`, …), not clashing with the agent's files.
2. Run skill **`commit`** as if the user had typed **`/c -a -p`** (message about preuves / changelog images for this version).

No images → skip this step. Text-only results are enough to close.

## 5. Update the issue body

`gh issue edit <n> --body` with the full *Human-test child* shape:

- Keep `Part of`, What to build, Acceptance criteria (check off what is done), Blocked by
- **`## Plan de tests`**: same scenarios; checkboxes reflect played (agent or human) / left unchecked or annotated as non-joué
- **`## Résultats`**: `### Joué par l’agent` (unchanged unless the human overturned a result), `### Joué par l’humain`, then non-joués
- **`## Ce qu’on peut faire maintenant`**: one product bullet per capability, each **immediately followed by its proof screenshot** (agent's or human's; a blank line, then the image indented under the bullet). One image per sentence; a bullet without a screenshot stays text-only. Never stack the images after the list. Image URL: `https://github.com/<owner>/<repo>/raw/<sha>/docs/img/changelog/vX.Y.Z/<file>.png` (raw at the commit SHA that added that file, so it shows on the ticket):

  ```markdown
  - Voir d’un coup d’œil le statut d’un dossier ouvert.

    ![Liste des dossiers](https://github.com/<owner>/<repo>/raw/<sha>/docs/img/changelog/<version>/scenario-1-liste.png)

  - Relancer une recherche avec les mêmes filtres qu’avant.

    ![Filtres conservés](https://github.com/<owner>/<repo>/raw/<sha>/docs/img/changelog/<version>/scenario-2-filtres.png)
  ```

## 6. Close

1. `gh issue edit <n> --remove-label "ready-for-human"` (absent → continue)
2. `gh issue close <n>` with comment: `Tests humains documentés sur <branch> (<sha>).` — staging trial: `Essai en staging OK sur vX.Y.Z-rc.<k>.` Staging trial with a **KO**: do **not** close; leave it Open with the results.

Staging trial: screenshots go under `docs/img/changelog/<version>/` and are committed on the version branch (`/c -a -p`). That moves `HEAD` past the rc tag: commit them **only on a KO** (a fix and a new rc follow anyway); on an all-OK pass, attach them to the ticket instead, so the final Release lands on the tried SHA. No `## Ce qu’on peut faire maintenant` to fill.

Do **not** use `/cci`. Do not close the parent. Do not `/implement`. Never close in pass A, even when every scenario was Agent and OK: the human looks first.

## 7. Hand off

Tell the user in French: ticket `#n` Closed; next **`/code-review`**, then **Finalise la version** if the review is accepted. Any KO recorded → say so first; fixing it is a new child (`/ct`), not this skill.

Staging trial: all OK → ticket `#n` Closed; next « Finalise la version » publishes the final Release `vX.Y.Z` on the tried SHA. Any KO → ticket stays Open; say which scenarios failed, then: fix on the version branch (`/ct` + `/implement`, or a direct fix), then « Finalise la version » for `vX.Y.Z-rc.<k+1>`. No correctif version: nothing was released.

## Not this skill

- Propose the plan after the last implement → `encadrer-implement`
- Close an implementation child → `fermer-ticket-enfant` (`/cci`)
- Fix a KO scenario → new child via `creer-ticket` (`/ct`), then `/implement`
- Release / squash → `finaliser-la-version`
- Commit only → `commit` (`/c`)
