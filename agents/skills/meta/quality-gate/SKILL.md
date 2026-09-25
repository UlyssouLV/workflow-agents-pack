---
name: quality-gate
description: >-
  Read the SonarQube / SonarCloud quality gate for the current git branch
  and HEAD SHA. Use when the user types `/qg` or `/qg -w`, says
  « quality gate » / « vérifie le quality gate », or when another skill
  tells you to run quality-gate. `-w` polls until an analysis exists for
  that branch+SHA. Do not fix code. Do not commit. Do not run pytest.
---

# Read the quality gate

`/` = this skill’s trigger. `-` = options. Treat `/qg` and `-w` as whole tokens.

This path **is** permission to call the Sonar API **read-only**. Do not change code. Do not `git commit`. Never print `SONAR_TOKEN` or dump `.env`.

## 1. Credentials

From the repo root, load `.env` if it exists (`set -a; . ./.env; set +a`). Need:

- `SONAR_HOST_URL` (no trailing slash)
- `SONAR_TOKEN`
- `SONAR_PROJECT_KEY`

If any is missing or empty: **stop now**. Say to put those three in `.env` (gitignored). Do not invent a host or key. Do not commit `.env`. **`-w` does not poll** when this step stops.

## 2. Current ref

```bash
BRANCH=$(git branch --show-current)
HEAD=$(git rev-parse HEAD)
```

Empty `BRANCH` (detached HEAD) → **stop**. The gate is keyed by branch (or PR), not by `main` by default.

## 3. HEAD vs last analysis **on this ref**

Search the current branch (URL-encode `BRANCH`; slashes are legal):

```bash
curl -sS -u "$SONAR_TOKEN:" -G \
  "$SONAR_HOST_URL/api/project_analyses/search" \
  --data-urlencode "project=$SONAR_PROJECT_KEY" \
  --data-urlencode "branch=$BRANCH" \
  --data-urlencode "ps=20"
```

If that list is empty, and `gh pr view --json number -q .number` returns a number for this branch, search again with `--data-urlencode "pullRequest=<n>"` instead of `branch`. Keep that ref (`branch=…` or `pullRequest=…`) for the rest of the run.

A call **without** `branch` / `pullRequest` is the default branch (`main`). Do not make that call.

Find the analysis whose `revision` is `HEAD`. Its `key` is the `analysisId`.

- **Without `-w`:** no match → **stop**. The gate is not for this commit on this branch.
- **With `-w`:** repeat **that same scoped search** every **15 s**, up to **12** times (3 min). Stop the poll as soon as `revision` matches `HEAD`. Still no match after 12 tries → **stop**.

Do not use an older analysis, and do not use an analysis from another branch.

## 4. Gate status

```bash
curl -sS -u "$SONAR_TOKEN:" -G \
  "$SONAR_HOST_URL/api/qualitygates/project_status" \
  --data-urlencode "analysisId=$ANALYSIS_ID"
```

`$ANALYSIS_ID` is the `key` from step 3. **Always** pass `analysisId`. A `projectKey`-only call is `main` — do not use it.

`projectStatus.status` must be **`OK`**. Report the **branch** (or PR), SHA, and status.

- **`OK`** → green. Done.
- Anything else (`ERROR`, `WARN`, `NONE`, …) → **fail**. List failed conditions. Do not continue a caller’s later steps.

Done when the gate for **this branch + this SHA** is `OK`, or as soon as it is not (or there is no analysis for that ref).

## Not this skill

- Fix the gate: `corriger-quality-gate` (`/cqg`)
- Tests: `lancer-tests` (`/t`)
- Both: `verifier-la-fiabilite` (`/vf`)
