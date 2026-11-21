---
name: encadrer-implement
description: >-
  Green pytest after a child GitHub ticket, or the implement plugin's closing
  step: `/t`, tick the ticket's acceptance criteria from the tests, `/c`
  (push only when this run does not auto-chain locally), `/cci #<n>`, then
  auto-chain the next unblocked
  ready-for-agent child in a new blank Claude Code conversation (fallback:
  ask the human to open one and `/implement`), or fill the human-test plan
  and point to `/th`, or (all Closed) `/code-review` then Finalise. Do not
  wait for the quality gate. Do not run `/code-review` here. Load this as
  soon as /implement tests pass.
---

# Wrap `/implement`

Use the plugin **`/implement`** for TDD and the ticket body. **This skill owns the end of the run.** The plugin’s last line is a review step; in this repo that last line is **this skill, from Tests onward**.

Git, tests, and closing the child go through the skills below, not inline. The quality gate is not this skill. Do **not** close the **parent** spec (squash `Fixes #<parent>` does that). Do **not** `/implement` the parent.

## 1. Tests

Run skill **`lancer-tests`** as if the user had typed **`/t`**. If it fails: **stop**. No commit, no close.

## 2. Acceptance criteria

Read the child’s `## Acceptance criteria` (`gh issue view <n>`). Every box must be proven before the child closes.

1. For each criterion, name its proof: the test(s) that cover it (`file::test`, `cargo test <name>`, Node test…), green in step 1. A criterion that no test covers is **not** met: write the missing test (red, then green), rerun step 1, then come back here.
2. A criterion no automated test can check (screenshot, doc wording, CI path filter…): prove it with a command or a file you read now (cite it). If only a human can check it, leave it unticked, append `— vérifié par un humain : <scénario>` to its line, and carry that scenario into the human-test plan (step 6). Without that marker, `/cci` refuses the close (`agents/issue-tracker.md`, *Child ticket body*).
3. `gh issue edit <n> --body-file …`: same body, each proven criterion `- [ ]` → `- [x]`, and the human-only marker of step 2. Change nothing else.
4. Any criterion unproven and not human-only → **stop**: no commit, no close. Say which one and why.

## 3. Commit (no push yet)

Stage **only** the ticket files. Never `.env`, `*.db`, `.venv/`, secrets. Do **not** pass `-a`.

Then run skill **`commit`** as if the user had typed **`/c`** (no `-p`). Auto-chained children run in the same clone: pushing after each one only reruns the PR CI for nothing. The push comes in step 5, once.

Do **not** `/qg`, `/qg -w`, or `/cqg`. Do **not** leave the child Open while Sonar runs. Do **not** add a label for that wait. The gate is one read of the PR `HEAD`, in `finaliser-la-version`.

## 4. Close the child

Run skill **`fermer-ticket-enfant`** as if the user had typed **`/cci #<n>`** (`<n>` = the child just implemented). No `-t` (tests already ran). That skill refuses if `<n>` is not a child, or while a box of its `## Acceptance criteria` is empty without the human-only marker: back to step 2.

Then **tick the PR's Test plan line** for this child: `gh pr view --json body` on the version PR; under `## Test plan`, the `- [ ]` line that names `#<n>` (none → one line, continue) becomes `- [x]` via `gh pr edit --body-file`. Change nothing else in the body. No PR yet → skip.

## 5. Push, unless this run auto-chains locally

Push now (`git push`, or `git push -u origin HEAD` without upstream; never force, never to `main` / **base**) in every case **except** one: step 6 will auto-chain the next child with `enchainer-implement.sh` **and** `WAP_ENCHAINER` is unset (the next conversation opens in this same clone and will push later).

So push when: the next step is the human-test plan or Finalise; the auto-chain falls back to asking the human; `WAP_ENCHAINER` is set (the next session may run on another machine); or you stop for any reason. Decide after step 6 has picked its branch, then act. A failed push → **stop**, never auto-chain.

## 6. More child tickets on this PR?

Find the parent (`## Parent` / `Part of #n` on the issue you just finished). List **open** children of that parent.

- **Done:** Closed.
- **Still to build:** Open, `ready-for-agent` (and not `wontfix`).
- **Human tests:** Open, `ready-for-human` (title `Tests humains — <nom>`, or `Tests humains — VX.Y.Z` for a version opened on a `vX.Y.Z-…` branch). Never `/implement`.

A remaining ticket is **unblocked** when GitHub reports no open blockers (`issue_dependencies_summary.blocked_by` is 0), or every issue in a fallback **Blocked by** body line is Closed. See `agents/issue-tracker.md`.

**If at least one unblocked `ready-for-agent` child remains:**

Only reach this block when steps **1–4 succeeded** (tests green, acceptance criteria ticked, commit OK, child closed). Any failure earlier → **stop** here; never auto-chain.

1. Pick the **next** unblocked child (lowest issue number among unblocked `ready-for-agent`). Never the parent. Never a `ready-for-human` child.
2. In one French sentence, name `#<next>` and quote its `## Blocked by` clause (`vraie dépendance` / `ordre de confort`), so the human sees what would have broken.
3. **Do not** start `/implement #<next>` inside **this** conversation (keep this session as the finished ticket’s log).
4. **Auto-chain** (preferred when possible):
   - From the **repo root**, run **exactly** (do not expand env vars yourself):
     `bash agents/scripts/enchainer-implement.sh <next>`
   - That script either (a) runs `$WAP_ENCHAINER <next>` when set — macOS **or** session de l’orchestrateur — or (b) opens a **new** terminal window and a **blank** Claude Code conversation on `/implement #<next>` (macOS Terminal.app, Linux graphical terminal, or Windows `wt`/`cmd`; fresh context, no `/clear` of this chat).
   - If the script exits 0: tell the human in French that `#<next>` démarre dans une **nouvelle** conversation (Claude locale ou session suivante du runner). **Leave this conversation open** — do not kill this terminal, do not `/clear`, do not wait on the next implement here.
   - If the script fails (no `claude`, no terminal, `WAP_ENCHAINER` error, etc.): **fallback** — ask the user to open a new Claude session (or cockpit session) and run `/implement #<next>`, and **wait**. Do not pretend the next ticket started.
5. Never auto-chain on red tests, unproven acceptance criteria, failed commit or push, refused `/cci`, ambiguous parent/next, or when more than one “next” is unclear — push (step 5), then ask and wait instead.

**Else if an open `ready-for-human` human-test child remains** (format: `agents/issue-tracker.md`, *Human-test child*):

1. Build a **concrete** numbered test plan in product language from the parent spec and the Closed implementation children (what a human can click / verify). Include every acceptance criterion left unticked as human-only in step 2. Partial runs are allowed later.
2. Only when role **`staging`** resolves in `agents/roles.yml` (otherwise every scenario is **Branche**): tag each scenario **Branche** or **Staging** (`agents/issue-tracker.md`, *Human-test child*):
   - **Branche** — playable locally on this branch (app or server started locally, scripts, docs site, GitHub).
   - **Staging** — needs what only the staging environment has (artifacts built from a Release, real external services; role **`staging`** doc). Staging gets the version through its **pre-release**, published by Finalise before the final Release. A version without Release (Type documentation / analyse / évaluation / process) has no Staging scenario: write it as Branche or leave it out and say why.
3. `gh issue edit` that issue: replace `## Plan de tests` with one checkbox per **Branche** scenario (`- [ ] **Branche** — …`) and `## À jouer en staging` with one per **Staging** scenario (`- [ ] **Staging** — …`, or `Aucun.`). Missing `## À jouer en staging` heading (older child) → add it after `## Plan de tests`. Leave `## Résultats` and `## Ce qu’on peut faire maintenant` for `/th`.
4. Stop after telling the user, in French (adapt `#n` / PR):

   Tous les tickets d’implémentation sont Closed. Plan de tests humains proposé sur #<n> (scénarios Branche ; les scénarios Staging éventuels seront joués sur la pré-release, dans l’enfant « Essai en staging » que crée Finalise, avant la Release finale). Jouez ce que vous voulez (plan partiel OK). Lancez **`/th #<n>`** : l’agent joue d’abord les scénarios qu’il peut faire seul (avec captures) et vous liste ceux qui restent pour vous ; relancez ensuite **`/th #<n>`** avec vos résultats. Ne lancez pas `/code-review` tant que #<n> est Open.

5. Do **not** propose `/code-review` or Finalise here. Do not merge, tag, or start the next version.

**Else if all in-scope children are Closed** (including the human-test child):

- Stop after telling the user, in French, exactly this handoff (adapt only the parent/PR numbers if useful):

  Tous les tickets sont Closed (implémentation et tests humains). Lancez `/code-review`. Si la revue est bonne, lancez le skill **Finalise la version** (`finaliser-la-version`) : le quality gate est lu à ce moment-là, et s’il n’est pas OK c’est `/cqg`, pas la release.

- Do not merge, tag, or start the next version.

## Not this skill

- Tests only → `lancer-tests` (`/t`)
- Commit → `commit` (`/c`); push only in step 5
- Read-only gate → `quality-gate` (`/qg`)
- Fix the gate only → `corriger-quality-gate` (`/cqg`)
- Close a child only → `fermer-ticket-enfant` (`/cci`)
- Human-test results / close → `tests-humains` (`/th`)
- Opening or merging the PR, GitHub Release, deleting the branch → `finaliser-la-version`
- Re-implementing Closed children
- `needs-triage` work that is not a child of this PR
- A two-axis review vs `main`: only if the human typed `/code-review` this turn
- Starting the next `/implement` **inside** this same conversation (use `enchainer-implement.sh` or ask for a new Claude session)
- Killing / `/clear` of the finished conversation (keep it; only open a new one)
- Auto-chain after any failure in steps 1–5
