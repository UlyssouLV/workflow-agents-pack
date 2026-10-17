"""Lecture / écriture JSON sous le HOME du runner (hooks, permissions)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def sous_racine(racine: str, *parties: str) -> Path:
    """Chemin sous `racine` uniquement — `realpath` + `commonpath` (S2083)."""
    cible = os.path.realpath(os.path.join(racine, *parties))
    if os.path.commonpath([racine, cible]) != racine:
        raise ValueError(f"refus d’écrire hors de {racine} : {cible}")
    return Path(cible)


def lire_json(chemin: Path) -> dict:
    if not chemin.is_file():
        return {}
    texte = chemin.read_text(encoding="utf-8").strip()
    if not texte:
        return {}
    data = json.loads(texte)
    if not isinstance(data, dict):
        raise ValueError(f"{chemin} : JSON objet attendu")
    return data


def ecrire_json(chemin: Path, data: dict) -> None:
    dossier = os.path.dirname(os.fspath(chemin))
    os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as sortie:
        sortie.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
