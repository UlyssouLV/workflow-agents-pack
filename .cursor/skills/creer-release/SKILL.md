---
name: creer-release
description: >-
  Create a GitHub Release on the current feature-branch SHA (not the
  integration base). Tag is vX.Y.Z by default, or
  {release_tag_prefix}X.Y.Z when agents/integration-channel.yml exists.
  `--prerelease` with a tag vX.Y.Z-rc.<k> publishes a pre-release with
  minimal notes. Use when the user types `/crel` or says « crée une
  release », or when another skill tells you to run creer-release with
  vX.Y.Z. Do not squash or merge. Not « Finalise la version ».
---

# Create a GitHub Release

`/` = this skill’s trigger. One option: **`--prerelease`**. Treat `/crel` as a whole token. The rest of the message is the tag (`vX.Y.Z`, `orchestrator-vX.Y.Z`, or bare `X.Y.Z`; with `--prerelease`, `vX.Y.Z-rc.<k>`) plus optional purpose / notes.

**Base / tag:** resolve per `agents/docs/integration-channel.md` (*Résolution*). Default **base** = `main`, **tag(X.Y.Z)** = `vX.Y.Z`.

`/crel` **is** permission to `gh release create` **targeting the current branch SHA**. Do not merge. Do not delete the branch. Do not `git commit`. Do not force-push. Do not retag an existing tag.

Paths: **`agents/roles.yml`**.

## 1. Guards

1. `git branch --show-current` is **protected** (base, `main`, `master`) → stop.
2. Tag: from the message (`finaliser-la-version` passes the version's definitive number, step 0 there). Extract semver `X.Y.Z`, then set the Git tag to **tag(X.Y.Z)** (channel prefix or `v`). If the message already has the full prefixed tag, use it as-is when it matches **tag(X.Y.Z)**. If missing: ask and **wait**. Do not invent a bump, and never read it from a branch name: a version branch is `version/<nom>` (an old `vX.Y.Z-…` branch carries no Release number; the named-version rule).
   **Version name `<nom>`**: from the caller, else the branch `version/<nom>`, else the roadmap's `**Nom.**` of this version (old branch `vX.Y.Z-…`: `docs/dev/feuille-de-route/feuille-de-route-dev.md` gives each such branch a Nom). Missing: ask and **wait**. **Parent** `#<parent>`: from the PR body (`Fixes #<parent>` of the spec) or the spec's `Issue parente`.
3. `git fetch`. `git tag -l '<full-tag>'` or `gh release view <full-tag>` already exists → stop. Never retag.
4. **`--prerelease`**: the tag must end in `-rc.<k>` (`k` ≥ 1), and `vX.Y.Z` itself must not exist yet. A tag ending in `-rc.<k>` without `--prerelease`, or the reverse → stop. **Final tag `vX.Y.Z`** after pre-releases: target the SHA of the last `vX.Y.Z-rc.<k>` tag; `HEAD` must be that SHA, else stop (an untried SHA never gets the final Release).

## 2. Target

Tip of the **current** branch = `HEAD`. If an open PR exists for this branch, `HEAD` must match the PR head. If it does not: stop.

Target = that SHA (or the branch name while it still exists), **not** **base**. Squash would drop this history.

## 3. Title

`--title` is **one line**, same shape as the version PR:

`VX.Y.Z — <purpose>` (pre-release: `VX.Y.Z-rc.<k> — <purpose> (pré-release)`)

Purpose = the rest of the user / caller message after the tag, else the PR title (`<Titre>`), else the parent spec’s one-job sentence. The title carries the Release number; the version's name goes in the notes (`Version : <nom>`). Do not use a commit-subject dump as the title. (Title keeps `VX.Y.Z` for humans; the Git tag may be `orchestrator-vX.Y.Z`.)

## 4. Notes (body)

**`--prerelease`**: only the minimal notes of `agents/issue-tracker.md` (*Pre-release*): one sentence, `Version : <nom> (#<parent>)`, `Essai en staging : #<essai>` (from the caller; unknown yet → omit that line). No screenshots, no human-test illustration, no gap pass: skip the rest of this section.

`--notes` are for a human who did **not** watch the PR. **French** (unless this repo’s user-facing docs are English). Not a dump of `git log` subjects. **Keep this layout** — never invent new top-level headings for a commit sweep. Canonical copy also in `agents/issue-tracker.md` (*Release notes*). Later annotations (`finaliser-la-version`) must keep blank lines before `## Pourquoi` (Critical rules in that file) or the docs changelog empties.

Always this layout (omit a section only if it would be empty **and** you said so in **Hors périmètre**):

```markdown
## Pourquoi

<problem / parent spec, one short paragraph>

## Ce qu’on peut faire maintenant

<features in product language, what a user can do>

## Pour l’administrateur

<only when this version asks the administrator for a gesture after updating the server: one bullet per gesture, in order — otherwise omit the whole section>

## Historique des tickets

- PR : https://github.com/<owner>/<repo>/pull/<n>
- Commits : https://github.com/<owner>/<repo>/pull/<n>/commits

Version : <nom> (#<parent>)

Tickets (`Fixes`) : #<parent> #<enfant> …

## Hors périmètre

<what is not in this version if it could be confused>

Spec : https://github.com/<owner>/<repo>/blob/<full-tag>/<spec-path>

ADRs de cette version (liens **sur ce tag**, pas la base) :

- https://github.com/<owner>/<repo>/blob/<full-tag>/<adr-path>

Issues laissées de côté (PR / spec hors périmètre) : #…
```

`<full-tag>` = **tag(X.Y.Z)**. `<spec-path>` = parent spec under role **`spec`**. Always this one-line shape: `Spec : <url>`.

`<adr-path>` = files under role **`adr`**.

`## Pour l’administrateur` = gestures the administrator makes after updating the server to this version (new secret, command, setting to check), one imperative bullet each. Only when the version asks for one: otherwise omit the section (never `Aucun.`, and do not mention it in **Hors périmètre**). Recurring tasks do not belong here. Sources: the caller’s gestures (`finaliser-la-version`), else the spec / PR / child tickets.

`Version : <nom> (#<parent>)` is always written: the docs changelog finds the version's spec (`docs/specs/<nom>.md`) through this line. Releases made before the named-version rule carry `Développement : D (#<parent>)` instead; never rewrite them, the site still reads them.

### Fill order

1. Draft from the PR body (`Fixes`, summary), parent spec, and role **`adr`** files added on this branch. If the caller already passed notes, **fit them into these headings** — do not replace the layout with a free-form blob.
2. **Human-test child (product illustration).** If a Closed child titled **`Tests humains — <nom>`** exists (old version: `Tests humains — VX.Y.Z` with its development number) (see `agents/issue-tracker.md`, *Human-test child*), read its `## Ce qu’on peut faire maintenant` and **merge it into** the release section of the same name (text + Markdown images). Prefer that ticket’s product bullets and screenshots as the primary illustration; keep or add short gaps from the spec/PR only when they are still missing. Keep the pairing: each bullet **immediately followed by its proof screenshot** (blank line, image indented under the bullet), one image per sentence; never a block of images after the list. A gap without a screenshot is folded into the closest bullet's sentence or stays text-only. Do not invent a new top-level heading for preuves.
3. **Gap pass (commits only to complete, not to rewrite).** Read `git log origin/<base>..HEAD --oneline` (or the PR commits). Compare to the draft. Add only what is **missing** from the notes and useful to a human: a real capability the spec/PR omitted, or a bugfix beyond the parent `Fixes`. Fold each gap into the existing headings — usually **Ce qu’on peut faire maintenant** (product wording) or **Historique des tickets** (extra `#n` if a ticket exists). Do **not** paste commit subjects, hashes, or a « changelog commits » section. Do **not** duplicate points already covered by the spec/PR or the human-test section. Skip chore / noise (typos, lockfile-only, WIP) unless they change what a user can do.

Owner/repo from `git remote`. PR number from `gh pr view` for this branch.

## 5. Create

```bash
gh release create <full-tag> --target <sha-or-branch> --title "VX.Y.Z — <purpose>" --notes "$(cat <<'EOF'
<notes markdown>
EOF
)"
```

The tag must be **pushed** and the release **visible** before any squash. After the branch is deleted, `git log <full-tag>` still shows the development commits.

With **`--prerelease`**, add `--prerelease` to that command: GitHub marks it *Pre-release* and never *Latest*.

Done when GitHub shows the release with that title, that body, and the tag on the feature SHA. Reply with the full tag and URL.

## Not this skill

- Squash-merge / delete branch: `fusionner-pr` (`/mpr`).
- Whole version ship: `finaliser-la-version`.
