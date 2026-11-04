---
name: debloquer-la-feuille-de-route
description: >-
  Recompute the dev roadmap’s État lines and Prochaine from its « Bloquée
  par. » rubriques and Déjà livré, then report in French what is ouvrable,
  in progress (open branches / PRs on GitHub), newly unblocked, still
  blocked and worth splitting. Use when the user types `/dfr`, says
  « débloque la feuille de route », « analyse les blocages », « quelles
  versions sont ouvrables », or when finaliser-la-version runs it. Does not
  edit objectives or blockers (that is `/afr`). Does not commit.
---

# Unblock the dev roadmap

`/` = this skill’s trigger. No options.

Paths: **`agents/roles.yml`** (role **`roadmap`**). Rules: **`docs/dev/feuille-de-route/README.md`**, section *Blocages*. Opt-in: `scripts/deblocages-feuille-de-route.mjs` (project script) missing → say the repo does not use blockers, **stop**.

**Script** = `node scripts/avancement-feuille-de-route.mjs` when that file exists (it also rewrites the README banner), else `node scripts/deblocages-feuille-de-route.mjs`. Both take `--verifier`.

Never write **`État.`** or the **Prochaine** by hand, never edit **`Objectif.`** / **`Bloquée par.`**, never write « en cours » in the file. Do not `git commit` or push.

## 1. Which roadmap

Resolve **base** per `agents/docs/integration-channel.md` (`main` by default). `git fetch origin`.

- **Called by `finaliser-la-version`** (on the version branch, after it moved **`X.Y.Z`** into **Déjà livré**) → **finalise mode**: work on the branch’s file. Keep a copy of every `**État.**` line and the **Prochaine** heading as they stand now (the « before »).
- **Otherwise** (typed `/dfr`, on any branch) → **read mode**: the truth is base’s file, `git show origin/<base>:<roadmap path>`. The current branch’s copy may be stale (another version shipped since it was cut): do not touch it. Go to step 4 with base’s file.

Done when the mode and the file to read are fixed.

## 2. Base merged (finalise mode)

If the roadmap changed on `origin/<base>` since the merge-base (`git diff --quiet $(git merge-base HEAD origin/<base>) origin/<base> -- <roadmap path>` fails), merge `origin/<base>` into the branch (`git merge --no-edit origin/<base>`), so versions shipped meanwhile count.

Conflict on the roadmap, `README.md` or the banner image only: in the roadmap keep **both** sides’ **Déjà livré** bullets and each version’s **`Bloquée par.`** from base unless this branch changed it; take either side for **`État.`**, **Prochaine** and the README / image (step 3 rewrites them). Any other conflict → **stop**, list the files.

Done when the branch contains base’s roadmap changes.

## 3. Recompute (finalise mode)

From the repo root, run the **Script**. It rewrites **`État.`** and the **Prochaine** (and, with the avancement script, the README banner and its image).

Fails (missing **`Bloquée par.`**, unknown number, cycle) → **stop**: quote the message and the version, say to fix it with **`/afr`**.

Done when the **Script** with `--verifier` is green.

## 4. In progress

Versions in progress = remote branches `v<X.Y.Z>-…` (`git ls-remote --heads origin 'v*'`) plus open PRs whose head starts with `v<X.Y.Z>-` (`gh pr list --state open --json number,headRefName`). `gh` unavailable → say so in one line, continue without.

Done when each upcoming version is marked in progress or not.

## 5. Report (French)

From the file of step 1 (after step 3 in finalise mode):

1. **Débloquées** (finalise mode) — versions Bloquée before, Ouvrable now, and by which version.
2. **Blocages réduits** (finalise mode) — still Bloquée, fewer left: `1.9.1 : il reste 5 sur 6`.
3. **Ouvrables** — number — title, `(Prochaine)` on the Prochaine, `(en cours, #PR)` when step 4 says so. Then the first ouvrable not in progress: what « Ouvre la version » without a number would open.
4. **Bloquées** — number — title : what each still waits for.
5. **Découpages à envisager** — a version whose blocker, by its reason, touches only part of its **Objectif** (the rest could ship now). One line each: the part, and where it could go (**Hors périmètre** → the blocker, or a new version). Proposals only: the user decides, **`/afr`** writes.

Read mode adds one line when the current branch’s copy differs from base’s (« la copie de cette branche date d’avant la livraison de … ; elle sera recalculée au Finalise »).

Done when the report is shown. In finalise mode, the roadmap (and README / image) are left modified for `finaliser-la-version`’s docs commit.

## Not this skill

- Add, rewrite, split versions or their blockers → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Open a version → `ouvrir-la-version`
- Ship a version → `finaliser-la-version`
- Commit → `commit` (`/c`)
