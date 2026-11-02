# Guide des hooks

Hooks **projet** seulement (`agents/hooks/`, jamais `~/.claude` / `~/.cursor`).

Un hook = un dossier `agents/hooks/<nom>/` (script canonique `hook.py`). `/ch` le câble vers Claude Code **et** Cursor. `dispatch.py` ne copie **pas** les hooks.

| Adapter | Câblage |
|---|---|
| Claude Code | `.claude/settings.json` (`PreToolUse`, …) → souvent un wrapper `.claude/hooks/` |
| Cursor | `.cursor/hooks.json` (`version: 1`, `preToolUse` / `subagentStart`, …) |

Commandes portables : ancrées à la racine (`$CLAUDE_PROJECT_DIR`, `git rev-parse --show-toplevel`), elles testent `python3 -c ""` puis lancent le hook **une seule fois** (`python3`, sinon `py -3`). Jamais `python3 … || py -3 …` : après un refus (exit 2) le `||` relance le hook et le refus est perdu. Les hooks distinguent Cursor (`preToolUse` camelCase / `cursor_version`) et Claude Code (`PreToolUse`) sans `lower()`.

Les hooks **du pack** sont câblés par `agents/scripts/cabler-hooks.py` (appelé par `/init`, `adopter-le-pack.sh`, `update-from-pack.sh`) : copies adapter + entrées de réglages ; une entrée qui lance le même hook est remplacée, jamais doublée. Les hooks **du projet** ne sont pas touchés et se documentent dans `agents/docs/guide-projet.md` (ce guide-ci appartient au pack, `/up` l’écrase).

Nouveau hook : skill **`creer-hook`** (`/ch`).

---

### gate-code-review

**Source :** `agents/hooks/gate-code-review/hook.py`

**Claude :** `PreToolUse`, matcher `Skill\|Agent\|Task` (`.claude/settings.json` → `.claude/hooks/gate-code-review.py`)

**Cursor :** `preToolUse` matcher `Task\|Skill\|Agent` ; `subagentStart` (`.cursor/hooks.json`)

**Fait :** refuse `/code-review` tant que le message utilisateur du tour ne le demande pas, **sauf** « Finalise la version ». Message : enchaîner sur `encadrer-implement`.

### bloque-up-ecarts-pack

**Source :** `agents/hooks/bloque-up-ecarts-pack/hook.py`

**Claude :** `PreToolUse`, matcher `Skill\|Bash\|PowerShell` (`.claude/settings.json` → `.claude/hooks/bloque-up-ecarts-pack.py`)

**Cursor :** `preToolUse` matcher `Skill` ; `beforeShellExecution` (`.cursor/hooks.json`)

**Fait :** refuse `/up` (skill `mettre-a-jour-le-pack`, ou `update-from-pack.sh` / `adopter-le-pack.sh` lancés en commande, chemin entre guillemets compris) tant que `agents/docs/ecarts-avec-le-pack.md` a une ligne au statut « à reporter » : le pack écraserait ces modifications locales. Une simple mention du script (grep, heredoc, argument entre guillemets) passe ; fichier absent ou aucune ligne « à reporter » → tout passe. Reporter : skill `remonter-au-pack` (`/rap`).

**Preuve :** `python3 agents/hooks/bloque-up-ecarts-pack/test_hook.py`
