"""Liste des modèles Cursor de l’instance (spec 0.5.1, ADR 0009)."""

import os
import subprocess
from pathlib import Path
from typing import Mapping

from wap_runtime.agents import CURSOR, connecte
from wap_runtime.socle import resoudre

AUTO = {"id": None, "libelle": "Auto"}


class ModelesErreur(Exception):
    """Liste absente ou inutilisable : pas de catalogue inventé."""

    def __init__(self, detail: str, code: int = 503):
        self.detail = detail
        self.code = code
        super().__init__(detail)


def lister_modeles_cursor(env: Mapping[str, str]) -> list[dict]:
    """Les modèles de `agent models`, plus Auto. Lève si Cursor n’est pas connecté
    ou si l’interrogation CLI échoue.
    """
    if not connecte(CURSOR, env):
        raise ModelesErreur("Cursor non connecté", 422)
    home = Path(env["HOME"]) if env.get("HOME") else Path.home()
    programme = resoudre(CURSOR.programme, env, home)
    if programme is None:
        raise ModelesErreur("liste des modèles Cursor indisponible : agent introuvable")
    fusion = dict(os.environ)
    fusion.update(env)
    try:
        resultat = subprocess.run(
            [programme, "models"], capture_output=True, text=True, env=fusion
        )
    except OSError as erreur:
        raise ModelesErreur(f"liste des modèles Cursor indisponible : {erreur}") from erreur
    if resultat.returncode != 0:
        detail = (resultat.stderr or resultat.stdout or f"code {resultat.returncode}").strip()
        raise ModelesErreur(f"liste des modèles Cursor indisponible : {detail}")
    ids = _ids_depuis_sortie(resultat.stdout)
    if not ids:
        raise ModelesErreur("liste des modèles Cursor indisponible : aucun modèle dans sa sortie")
    return [AUTO, *({"id": i, "libelle": i} for i in ids)]


def _ids_depuis_sortie(sortie: str) -> list[str]:
    """IDs de `agent models` : lignes `id - libellé`, ou un id seul (tests). Ignore Auto et les en-têtes."""
    ids: list[str] = []
    for ligne in sortie.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        if " - " in ligne:
            id_ = ligne.split(" - ", 1)[0].strip()
        elif " " not in ligne:
            id_ = ligne
        else:
            continue
        if not id_ or id_.lower() == "auto":
            continue
        ids.append(id_)
    return ids
