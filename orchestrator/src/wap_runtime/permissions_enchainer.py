"""Règles de permission étroites pour l’enchaînement dans le runner (bug #69).

Le `HOME` du runner (`runner-home/`) est persistant : on fusionne ces règles à
chaque démarrage du conteneur, sans écraser le reste des settings agent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Préfixes / motifs étroits — jamais Bash(*) ni allow-all.
CLAUDE_ALLOW = (
    "Bash(bash agents/scripts/enchainer-implement.sh *)",
    "Bash(wap-runtime enchainer *)",
)
CURSOR_TERMINAL_ALLOWLIST = (
    "bash agents/scripts/enchainer-implement.sh",
    "wap-runtime enchainer",
)

_CLAUDE_RELATIF = (".claude", "settings.json")
_CURSOR_RELATIF = (".cursor", "permissions.json")


def assurer(home: Path) -> None:
    """Ajoute les règles d’enchaînement sous `home` si elles manquent.

    N’écrit que sous la racine réelle de `home` (pas de traversée `..`).
    """
    racine = os.path.realpath(home.expanduser())
    _fusionner_claude(_sous_racine(racine, *_CLAUDE_RELATIF))
    _fusionner_cursor(_sous_racine(racine, *_CURSOR_RELATIF))


def _sous_racine(racine: str, *parties: str) -> Path:
    """Chemin sous `racine` uniquement — `realpath` + `commonpath` (S2083)."""
    cible = os.path.realpath(os.path.join(racine, *parties))
    if os.path.commonpath([racine, cible]) != racine:
        raise ValueError(f"refus d’écrire hors de {racine} : {cible}")
    return Path(cible)


def _lire_json(chemin: Path) -> dict:
    if not chemin.is_file():
        return {}
    texte = chemin.read_text(encoding="utf-8").strip()
    if not texte:
        return {}
    data = json.loads(texte)
    if not isinstance(data, dict):
        raise ValueError(f"{chemin} : JSON objet attendu")
    return data


def _ecrire_json(chemin: Path, data: dict) -> None:
    dossier = os.path.dirname(os.fspath(chemin))
    os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as sortie:
        sortie.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _fusionner_claude(chemin: Path) -> None:
    data = _lire_json(chemin)
    permissions = data.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError(f"{chemin} : permissions doit être un objet")
    allow = permissions.setdefault("allow", [])
    if not isinstance(allow, list):
        raise ValueError(f"{chemin} : permissions.allow doit être une liste")
    for regle in CLAUDE_ALLOW:
        if regle not in allow:
            allow.append(regle)
    _ecrire_json(chemin, data)


def _fusionner_cursor(chemin: Path) -> None:
    data = _lire_json(chemin)
    allowlist = data.setdefault("terminalAllowlist", [])
    if not isinstance(allowlist, list):
        raise ValueError(f"{chemin} : terminalAllowlist doit être une liste")
    for prefixe in CURSOR_TERMINAL_ALLOWLIST:
        if prefixe not in allowlist:
            allowlist.append(prefixe)
    _ecrire_json(chemin, data)


def main() -> int:
    """Point d’entrée conteneur : uniquement le HOME du processus (pas d’argv)."""
    assurer(Path.home())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
