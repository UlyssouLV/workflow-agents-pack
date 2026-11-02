---
name: creer-hook
description: >-
  Author a project hook under agents/hooks/<name>/ then wire it for Claude
  Code and Cursor. Use when the user types `/ch` or says « crée un hook ».
  Grill then confirm before writing. Not `/cs`. Not user-level ~/.hooks.
---

# Create a project hook

`/ch` is the same trigger as « crée un hook ».

Write **one** hook under `agents/hooks/<name>/`. Then wire **both** adapters. Do **not** write only `.claude/hooks/` or only `.cursor/hooks/`. Never `~/.claude/` or `~/.cursor/`.

`dispatch.py` copies **skills only**. This skill owns hook files and settings.

## 1. Gather

Use the current conversation if it already has: when it fires, what it does (block / allow / audit), which tools.

If any of that is missing: invoke **grill-with-docs**. Wait until that interview is finished. Do not invent the gaps.

Always **project** hooks.

## 2. Propose, then wait

**Even if there was no grill**, describe in French **before any write**:

- folder name `agents/hooks/<name>/`
- Claude event (e.g. `PreToolUse`) and Cursor event (e.g. `preToolUse`)
- matcher
- block vs pass-through vs audit
- what the user will see when it fires

**Wait** for an explicit **oui**. Anything else → do not write.

## 3. Write `agents/hooks/<name>/`

One script, `agents/hooks/<name>/hook.py`. Both adapters run it from the **repo root**, choosing the interpreter **once** (`python3`, else `py -3`), like the peers:

- Claude: `cd "$CLAUDE_PROJECT_DIR" && { python3 -c "" </dev/null >/dev/null 2>&1 && exec python3 .claude/hooks/<name>.py; exec py -3 .claude/hooks/<name>.py; }` (`.claude/hooks/<name>.py` = `runpy` wrapper of the canonical script).
- Cursor: `sh .cursor/hooks/<name>.sh` (`git rev-parse --show-toplevel`, then the same choice).

Never `python3 … || py -3 …`: after a deny (exit 2) the `||` runs the hook again and the deny is lost. Tell Cursor from Claude by `cursor_version` or the camelCase event name (`preToolUse`); never `lower()` the event name (Claude sends `PreToolUse`).

Claude Code (`PreToolUse`, matcher `Skill|Agent|Task`, …): JSON on stdin; **deny** = exit **2** + `decision: block` / `permissionDecision: deny` (see `agents/hooks/gate-code-review/hook.py`).

Cursor (`.cursor/hooks.json` `version: 1`): JSON on stdin; **deny** = `"permission": "deny"` or exit **2**. Matcher = JavaScript regex on the tool name. `failClosed` only if a crash must block. Make a wrapper executable if Cursor needs a shebang file under `.cursor/hooks/` that execs the same Python.

Preserve unrelated hooks. Merge into `.claude/settings.json` **hooks** only (do not add plugins). Merge into `.cursor/hooks.json` without dropping other events.

Do not echo secrets.

## 4. Guide

Which guide:

- **In a project** (`agents/docs/ecarts-avec-le-pack.md` exists): `agents/docs/guide-projet.md`, section `## Hooks` (create the file with `# Guide du projet` and that heading if missing). `guide-hooks.md` belongs to the pack and is overwritten by `/up`.
- **In `workflow-agents-pack` itself**: **`agents/docs/guide-hooks.md`**. A pack hook also ships its adapter copies (`.claude/hooks/<name>.py`, `.cursor/hooks/<name>.sh`) and its entries in `references/settings-hooks.json` and `.cursor/hooks.json`, so that `cabler-hooks.py` wires it in every project.

Add (or replace if that heading already exists) one section there. Same shape as the peers already in `guide-hooks.md`:

- French title (`### <nom>`)
- **Source :** `agents/hooks/<nom>/…`
- **Claude :** event + matcher
- **Cursor :** event + matcher
- **Fait :** one line of what it blocks or allows

Do not put the hook inventory in `guide-skills.md` (`/ch` stays there as the command). Do not rewrite the rest of the hooks guide.

Done when `agents/hooks/<name>/` exists, **both** adapters are wired, **and** the right guide has that section.

## Not this skill

- Project skills → `creer-skill` (`/cs`)
- MCP configs
- Moving `gate-code-review.py` without `/ch` (inventory: `agents/docs/guide-hooks.md`)
