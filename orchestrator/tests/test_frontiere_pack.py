"""Frontière pack / runtime : ce que le pack régénère est ignoré, la config du projet reste suivie."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

CHEMINS_REGENERES = [
    "agents/skills/",
    "agents/hooks/",
    "agents/scripts/",
    "agents/templates/",
    ".claude/skills/",
    ".cursor/skills/",
]

CONFIG_PROJET = [
    "agents/roles.yml",
    "agents/integration-channel.yml",
    "agents/issue-tracker.md",
    "agents/domain.md",
    "agents/triage-labels.md",
    "agents/docs/",
    "agents/README.md",
    ".claude/CLAUDE.md",
    ".claude/settings.json",
    ".claude/hooks/",
    ".cursor/hooks.json",
    ".cursor/hooks/",
    "orchestrator/",
]


def est_ignore(chemin: str) -> bool:
    resultat = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", chemin],
        cwd=REPO_ROOT,
    )
    if resultat.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore a échoué sur {chemin}")
    return resultat.returncode == 0


def avec_fichiers_suivis(chemin: str) -> list[str]:
    """Un dossier non ignoré peut contenir des fichiers ignorés : on les vérifie aussi."""
    if not chemin.endswith("/"):
        return [chemin]
    fichiers = subprocess.run(
        ["git", "ls-files", "--", chemin],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [chemin, *fichiers]


@pytest.mark.parametrize("chemin", CHEMINS_REGENERES)
def test_chemin_regenere_par_le_pack_est_ignore(chemin):
    assert est_ignore(chemin)


@pytest.mark.parametrize(
    "chemin", [f for c in CONFIG_PROJET for f in avec_fichiers_suivis(c)]
)
def test_config_du_projet_reste_suivie(chemin):
    assert not est_ignore(chemin)
