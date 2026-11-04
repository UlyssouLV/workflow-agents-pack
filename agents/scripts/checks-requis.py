#!/usr/bin/env python3
"""Refuse de squasher tant qu’un check exigé n’est pas vert.

Usage : python3 agents/scripts/checks-requis.py [<pr>]
(sans argument : la PR de la branche courante, comme `gh pr checks`).

Lit agents/checks-requis.yml, puis `gh pr checks --json name,bucket`.
Chaque check exigé doit être présent, et chacune de ses lignes `pass` ou
`skipping` (un job sauté par `if:` compte comme vert).

Sortie : 0 tous verts ; 1 un check exigé rouge, en attente ou absent (nommé
sur stderr) ; 2 liste ou sortie de gh illisible. Stdlib seulement.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LISTE = Path(__file__).resolve().parents[1] / "checks-requis.yml"

_VERT = {"pass", "skipping"}
_ROUGE = {"fail", "cancel"}


def lire_requis(chemin: Path) -> list[str]:
    """Les noms sous `checks:`, une ligne `  - nom` chacun."""
    noms: list[str] = []
    dans_checks = False
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        brute = ligne.split(" #", 1)[0].rstrip()
        if not brute.strip() or brute.lstrip().startswith("#"):
            continue
        if not brute.startswith((" ", "-")):
            dans_checks = brute == "checks:"
            continue
        if dans_checks and brute.lstrip().startswith("- "):
            noms.append(brute.lstrip()[2:].strip())
    if not noms:
        raise ValueError(f"aucun check exigé dans {chemin}")
    return noms


def fautifs(requis: list[str], checks: list[dict[str, str]]) -> list[tuple[str, str]]:
    """(nom, « rouge » | « en attente » | « absent ») pour chaque check exigé non vert."""
    resultat: list[tuple[str, str]] = []
    for nom in requis:
        buckets = {c.get("bucket", "") for c in checks if c.get("name") == nom}
        if not buckets:
            resultat.append((nom, "absent"))
        elif buckets & _ROUGE:
            resultat.append((nom, "rouge"))
        elif not buckets <= _VERT:
            resultat.append((nom, "en attente"))
    return resultat


def main(argv: list[str]) -> int:
    try:
        requis = lire_requis(LISTE)
    except (OSError, ValueError) as erreur:
        print(f"checks-requis : {erreur}", file=sys.stderr)
        return 2

    # Un numéro de PR seulement : rien d’autre ne part en argument de gh.
    if argv and not argv[0].isdecimal():
        print(f"checks-requis : numéro de PR attendu, reçu {argv[0]!r}", file=sys.stderr)
        return 2
    pr = [str(int(argv[0]))] if argv else []

    # gh sort en 1 (check rouge) ou 8 (en attente) : seule la sortie compte.
    commande = ["gh", "pr", "checks", *pr, "--json", "name,bucket"]
    gh = subprocess.run(commande, capture_output=True, text=True, check=False)
    try:
        checks = json.loads(gh.stdout)
        if not isinstance(checks, list):
            raise ValueError
    except ValueError:
        message = (gh.stderr or gh.stdout).strip() or "sortie vide"
        print(f"checks-requis : `gh pr checks` illisible : {message}", file=sys.stderr)
        return 2

    liste = fautifs(requis, checks)
    if liste:
        print("Squash refusé : check exigé non vert.", file=sys.stderr)
        for nom, etat in liste:
            print(f"- {nom} : {etat}", file=sys.stderr)
        return 1
    print(f"Checks exigés verts : {', '.join(requis)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
