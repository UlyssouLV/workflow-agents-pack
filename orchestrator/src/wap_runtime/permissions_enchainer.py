"""Règles de permission étroites pour l’enchaînement dans le runner (bug #69).

Le `HOME` du runner (`runner-home/`) est persistant : on fusionne ces règles à
chaque démarrage du conteneur, sans écraser le reste des settings agent.
"""

from __future__ import annotations

import os
from pathlib import Path

from wap_runtime.home_json import ecrire_json, lire_json, sous_racine

# Préfixes / motifs étroits — jamais Bash(*) ni allow-all.
CLAUDE_ALLOW = (
    "Bash(bash agents/scripts/enchainer-implement.sh *)",
    "Bash(wap-runtime enchainer *)",
    "Bash(wap-runtime etat *)",
)
CURSOR_TERMINAL_ALLOWLIST = (
    "bash agents/scripts/enchainer-implement.sh",
    "wap-runtime enchainer",
    "wap-runtime etat",
)

_CLAUDE_RELATIF = (".claude", "settings.json")
_CURSOR_RELATIF = (".cursor", "permissions.json")


def assurer(home: Path) -> None:
    """Ajoute les règles d’enchaînement sous `home` si elles manquent.

    N’écrit que sous la racine réelle de `home` (pas de traversée `..`).
    """
    racine = os.path.realpath(home.expanduser())
    _fusionner_claude(sous_racine(racine, *_CLAUDE_RELATIF))
    _fusionner_cursor(sous_racine(racine, *_CURSOR_RELATIF))


def _fusionner_claude(chemin: Path) -> None:
    data = lire_json(chemin)
    permissions = data.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError(f"{chemin} : permissions doit être un objet")
    allow = permissions.setdefault("allow", [])
    if not isinstance(allow, list):
        raise ValueError(f"{chemin} : permissions.allow doit être une liste")
    for regle in CLAUDE_ALLOW:
        if regle not in allow:
            allow.append(regle)
    ecrire_json(chemin, data)


def _fusionner_cursor(chemin: Path) -> None:
    data = lire_json(chemin)
    allowlist = data.setdefault("terminalAllowlist", [])
    if not isinstance(allowlist, list):
        raise ValueError(f"{chemin} : terminalAllowlist doit être une liste")
    for prefixe in CURSOR_TERMINAL_ALLOWLIST:
        if prefixe not in allowlist:
            allowlist.append(prefixe)
    ecrire_json(chemin, data)


def main() -> int:
    """Point d’entrée conteneur : uniquement le HOME du processus (pas d’argv)."""
    assurer(Path.home())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
