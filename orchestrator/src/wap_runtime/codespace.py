"""Codespace d’une session (ADR 0014) : le clone géré lu en lecture seule par le runner.

Tout chemin reçu est relatif au clone ; résolu (symlinks compris), il doit y rester. Un symlink
qui sort du clone est listé comme lien, jamais suivi.
"""

import os
import subprocess
from contextlib import suppress
from pathlib import Path, PurePosixPath

# Au-delà, ou binaire : « non affiché », avec la taille.
TAILLE_MAX = 1024 * 1024
# Comme Git : un octet nul dans le début du fichier le dit binaire.
DEBUT_BINAIRE = 8000
DOSSIER, FICHIER, LIEN = "dossier", "fichier", "lien"


class CodespaceErreur(Exception):
    """Lecture impossible ; `code` est le statut HTTP rendu."""

    code = 404


class CheminRefuse(CodespaceErreur):
    """Le chemin sort du clone, ou n’est pas du type attendu."""

    code = 400


def identite(clone: Path, repo: str) -> dict:
    """Repo, branche (`None` si HEAD détaché) et HEAD court (`None` sans commit)."""
    return {
        "repo": repo,
        "branche": _git_ou_none(clone, "symbolic-ref", "--short", "--quiet", "HEAD"),
        "head": _git_ou_none(clone, "rev-parse", "--short", "--quiet", "--verify", "HEAD"),
        "source": "direct",
    }


def arbre(clone: Path, chemin: str) -> list[dict]:
    """Entrées du dossier `chemin` : dossiers d’abord, puis par nom.

    `ignore` : ignoré par `.gitignore` (jamais sous `.git/`). `taille` : celle d’un fichier."""
    racine, dossier = _resoudre(clone, chemin)
    if not dossier.is_dir():
        raise CheminRefuse(f"{chemin} n’est pas un dossier")
    entrees = [_entree(racine, element) for element in os.scandir(dossier)]
    ignores = _ignores(racine, dossier, entrees)
    for entree in entrees:
        entree["ignore"] = entree.pop("_relatif") in ignores
    return sorted(entrees, key=lambda e: (e["type"] != DOSSIER, e["nom"].casefold(), e["nom"]))


def fichier(clone: Path, chemin: str) -> dict:
    """Contenu texte, ou `contenu` nul et `non_affiche` (`binaire`, `trop_gros`)."""
    _, cible = _resoudre(clone, chemin)
    if not cible.is_file():
        raise CheminRefuse(f"{chemin} n’est pas un fichier")
    taille = cible.stat().st_size
    lu = {"chemin": chemin, "taille": taille}
    if taille > TAILLE_MAX:
        return {**lu, "contenu": None, "non_affiche": "trop_gros"}
    octets = cible.read_bytes()
    if b"\0" not in octets[:DEBUT_BINAIRE]:
        with suppress(UnicodeDecodeError):
            return {**lu, "contenu": octets.decode()}
    return {**lu, "contenu": None, "non_affiche": "binaire"}


def _resoudre(clone: Path, chemin: str) -> tuple[Path, Path]:
    """`(racine, cible)` réelles ; `CheminRefuse` hors du clone, `CodespaceErreur` si absente."""
    racine = clone.resolve()
    relatif = PurePosixPath(chemin)
    if "\0" in chemin or relatif.is_absolute() or ".." in relatif.parts:
        raise CheminRefuse(f"chemin refusé : {chemin}")
    cible = Path(os.path.realpath(racine / relatif))
    if not cible.is_relative_to(racine):
        raise CheminRefuse(f"chemin refusé : {chemin}")
    if not cible.exists():
        raise CodespaceErreur(f"{chemin} absent du clone")
    return racine, cible


def _entree(racine: Path, element: os.DirEntry) -> dict:
    chemin = Path(element.path)
    reel = Path(os.path.realpath(chemin))
    if element.is_symlink() and not (reel.is_relative_to(racine) and reel.exists()):
        type_ = LIEN
    else:
        type_ = DOSSIER if reel.is_dir() else FICHIER
    return {
        "nom": element.name,
        "type": type_,
        "taille": reel.stat().st_size if type_ == FICHIER else None,
        # Pour `git check-ignore` : relatif au clone, `/` final pour un dossier.
        "_relatif": chemin.relative_to(racine).as_posix() + ("/" if type_ == DOSSIER else ""),
    }


def _ignores(racine: Path, dossier: Path, entrees: list[dict]) -> set[str]:
    if not entrees or dossier.relative_to(racine).parts[:1] == (".git",):
        return set()
    sortie = subprocess.run(
        ["git", "-C", str(racine), "check-ignore", "--stdin", "-z"],
        input="".join(f"{e['_relatif']}\0" for e in entrees),
        capture_output=True, text=True,
    )
    # 1 : aucun ignoré ; au-delà, Git a échoué : rien n’est marqué.
    if sortie.returncode != 0:
        return set()
    return set(filter(None, sortie.stdout.split("\0")))


def _git_ou_none(clone: Path, *args: str) -> str | None:
    sortie = subprocess.run(
        ["git", "-C", str(clone), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    return sortie.stdout.strip() or None if sortie.returncode == 0 else None
