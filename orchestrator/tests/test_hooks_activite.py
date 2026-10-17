"""Hooks d’activité en portée utilisateur (`runner-home/`), fusionnés sans écraser."""

import json
from pathlib import Path

from wap_runtime.hooks_activite import (
    CLAUDE_HOOKS,
    CURSOR_HOOKS,
    assurer,
)


def test_assurer_ecrit_les_hooks_claude_et_cursor(tmp_path: Path):
    assurer(tmp_path)

    claude = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for event, commande, matcher in CLAUDE_HOOKS:
        blocs = claude["hooks"][event]
        assert any(
            (matcher is None or b.get("matcher") == matcher)
            and any(h.get("command") == commande for h in b.get("hooks", []))
            for b in blocs
        )

    cursor = json.loads((tmp_path / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor["version"] == 1
    for event, commande, matcher in CURSOR_HOOKS:
        assert any(
            h.get("command") == commande and (matcher is None or h.get("matcher") == matcher)
            for h in cursor["hooks"][event]
        )


def test_assurer_preserve_les_reglages_existants_et_est_idempotent(tmp_path: Path):
    claude_path = tmp_path / ".claude" / "settings.json"
    claude_path.parent.mkdir(parents=True)
    claude_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(git status)"]},
                "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo ok"}]}]},
            }
        ),
        encoding="utf-8",
    )
    cursor_path = tmp_path / ".cursor" / "hooks.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {"preToolUse": [{"command": "echo ok", "matcher": "Shell"}]},
            }
        ),
        encoding="utf-8",
    )

    assurer(tmp_path)
    assurer(tmp_path)

    claude = json.loads(claude_path.read_text(encoding="utf-8"))
    assert claude["permissions"]["allow"] == ["Bash(git status)"]
    assert claude["hooks"]["PreToolUse"] == [{"hooks": [{"type": "command", "command": "echo ok"}]}]
    assert len(claude["hooks"]["UserPromptSubmit"]) == 1

    cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert cursor["hooks"]["preToolUse"] == [{"command": "echo ok", "matcher": "Shell"}]
    assert len(cursor["hooks"]["beforeSubmitPrompt"]) == 1


def test_assurer_n_ecrit_pas_hors_du_home(tmp_path: Path):
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "README.md").write_text("suivi\n")
    home = tmp_path / "runner-home"
    home.mkdir()

    assurer(home)

    assert list(clone.iterdir()) == [clone / "README.md"]
    assert (home / ".claude" / "settings.json").is_file()
