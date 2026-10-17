"""Règles étroites d’enchaînement dans le HOME du runner (#69)."""

import json
import os
from pathlib import Path

import pytest

from wap_runtime.permissions_enchainer import (
    CLAUDE_ALLOW,
    CURSOR_TERMINAL_ALLOWLIST,
    _sous_racine,
    assurer,
    main,
)


def test_assurer_cree_claude_et_cursor(tmp_path: Path):
    assurer(tmp_path)

    claude = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert claude["permissions"]["allow"] == list(CLAUDE_ALLOW)

    cursor = json.loads((tmp_path / ".cursor" / "permissions.json").read_text(encoding="utf-8"))
    assert cursor["terminalAllowlist"] == list(CURSOR_TERMINAL_ALLOWLIST)


def test_assurer_preserve_le_reste_et_est_idempotent(tmp_path: Path):
    claude_path = tmp_path / ".claude" / "settings.json"
    claude_path.parent.mkdir(parents=True)
    claude_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": ["Bash(git status)", CLAUDE_ALLOW[0]],
                    "deny": ["Read(./.env)"],
                },
                "hooks": {"PreToolUse": []},
            }
        ),
        encoding="utf-8",
    )
    cursor_path = tmp_path / ".cursor" / "permissions.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text(
        json.dumps({"terminalAllowlist": ["gh issue view", CURSOR_TERMINAL_ALLOWLIST[0]]}),
        encoding="utf-8",
    )

    assurer(tmp_path)
    assurer(tmp_path)

    claude = json.loads(claude_path.read_text(encoding="utf-8"))
    assert claude["hooks"] == {"PreToolUse": []}
    assert claude["permissions"]["deny"] == ["Read(./.env)"]
    assert claude["permissions"]["allow"] == [
        "Bash(git status)",
        CLAUDE_ALLOW[0],
        CLAUDE_ALLOW[1],
        CLAUDE_ALLOW[2],
    ]

    cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert cursor["terminalAllowlist"] == [
        "gh issue view",
        CURSOR_TERMINAL_ALLOWLIST[0],
        CURSOR_TERMINAL_ALLOWLIST[1],
        CURSOR_TERMINAL_ALLOWLIST[2],
    ]


def test_sous_racine_refuse_la_traversee(tmp_path: Path):
    racine = os.path.realpath(tmp_path)
    with pytest.raises(ValueError, match="refus"):
        _sous_racine(racine, "..", "etc", "passwd")


def test_main_utilise_le_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main() == 0
    assert (tmp_path / ".claude" / "settings.json").is_file()
