"""Instantané de fin de session (ADR 0014) : l’arbre de travail figé dans un commit privé du clone,
puis relu par le codespace d’une session close.

La prise passe par un index provisoire (`GIT_INDEX_FILE`) : l’arbre de travail, l’index, la branche
et le distant ne changent pas. Le commit (parent : HEAD, aucun sans commit) va sous
`refs/wap/sessions/<id>`, hors de `refs/heads/` : jamais poussé. `jobs/<id>/instantane.json` dit
`sha`, `head`, `branche`, `pris_le`, `ignores` (les entrées ignorées par dossier, non conservées) et
`non_suivis` (fichiers et dossiers non suivis, que le commit ne distingue pas des ajoutés), ou
`pris_le` et `erreur`.
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from wap_runtime.codespace import (
    AJOUTE,
    DOSSIER,
    FICHIER,
    LIEN,
    MODIFIE,
    NON_SUIVI,
    TAILLE_MAX,
    CheminRefuse,
    CodespaceErreur,
    chemin_relatif,
    fichier_lu,
    git_ou_none,
    marquer,
    texte,
    trier,
)
from wap_runtime.fichiers import remplacer

INSTANTANE = "instantane.json"
PRESENT, ABSENT, PERDU, ERREUR = "present", "absent", "perdu", "erreur"
# Le commit privé est le même quelle que soit l’identité configurée (ou absente) du clone.
AUTEUR = {
    "GIT_AUTHOR_NAME": "wap-runtime", "GIT_AUTHOR_EMAIL": "wap-runtime@localhost",
    "GIT_COMMITTER_NAME": "wap-runtime", "GIT_COMMITTER_EMAIL": "wap-runtime@localhost",
}


class _Echec(Exception):
    pass


def ref(id_: str) -> str:
    return f"refs/wap/sessions/{id_}"


def prendre(clone: Path, dossier_session: Path, id_: str, pris_le: datetime) -> dict:
    """Fige l’arbre de travail de `clone` et écrit `instantane.json` ; ne lève jamais (l’échec est
    noté dans le fichier) : la session se ferme quand même."""
    try:
        lu = {**_figer(clone, id_), "pris_le": pris_le.isoformat()}
    except (_Echec, OSError) as erreur:
        lu = {"pris_le": pris_le.isoformat(), "erreur": str(erreur) or type(erreur).__name__}
    try:
        remplacer(dossier_session / INSTANTANE, json.dumps(lu, ensure_ascii=False, indent=2) + "\n", 0o644)
    except OSError:
        pass
    return lu


def _figer(clone: Path, id_: str) -> dict:
    if not (clone / ".git").is_dir():
        raise _Echec(f"clone absent : {clone.name}")
    head = git_ou_none(clone, "rev-parse", "--verify", "--quiet", "HEAD")
    with tempfile.TemporaryDirectory() as provisoire:
        index = Path(provisoire) / "index"
        # Repart de l’index réel : un fichier suivi bien qu’ignoré reste dans l’instantané.
        if (clone / ".git" / "index").is_file():
            shutil.copyfile(clone / ".git" / "index", index)
        env = {"GIT_INDEX_FILE": str(index)}
        _git(clone, env, "add", "--all")
        arbre = _git(clone, env, "write-tree").strip()
    parent = [] if head is None else ["-p", head]
    sha = _git(clone, AUTEUR, "commit-tree", arbre, *parent, "-m", f"instantané session {id_}").strip()
    _git(clone, {}, "update-ref", ref(id_), sha)
    ignores = _git(clone, {}, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    non_suivis = _git(clone, {}, "ls-files", "--others", "--exclude-standard", "--directory", "-z")
    return {
        "sha": sha,
        "head": head,
        "branche": git_ou_none(clone, "symbolic-ref", "--short", "--quiet", "HEAD"),
        "ignores": _par_dossier(filter(None, ignores.split("\0"))),
        "non_suivis": sorted(filter(None, non_suivis.split("\0"))),
    }


def _par_dossier(chemins) -> dict[str, list[str]]:
    """`{"": [".env", "node_modules/"], "src": ["__pycache__/"]}` : un dossier finit par `/`."""
    groupes: dict[str, list[str]] = {}
    for chemin in chemins:
        parent, _, nom = chemin.rstrip("/").rpartition("/")
        groupes.setdefault(parent, []).append(nom + ("/" if chemin.endswith("/") else ""))
    return {dossier: sorted(noms) for dossier, noms in sorted(groupes.items())}


class Relecture:
    """Le codespace d’une session close, lu dans son instantané : mêmes lectures que le codespace en
    direct, marqueurs et diff par rapport au HEAD de l’époque. Sans instantané lisible, l’identité
    en dit la raison et les autres lectures la rendent en 404."""

    def __init__(self, session: dict, clone: Path, dossier_session: Path):
        self._session = session
        self._clone = clone
        try:
            self._lu = json.loads((dossier_session / INSTANTANE).read_text())
        except (OSError, ValueError):
            self._lu = None
        self.etat, self._raison = self._etat()

    def _etat(self) -> tuple[str, str | None]:
        if self._lu is None:
            return ABSENT, "pas d’instantané (session antérieure à la 0.8.0)"
        if "erreur" in self._lu:
            return ERREUR, f"instantané non pris : {self._lu['erreur']}"
        present = (self._clone / ".git").is_dir() and git_ou_none(
            self._clone, "rev-parse", "--verify", "--quiet", f"{ref(self._session['id'])}^{{commit}}"
        ) == self._lu["sha"]
        return (PRESENT, None) if present else (PERDU, "instantané perdu")

    def identite(self) -> dict:
        etat = {"etat": self.etat}
        if self._lu is not None:
            etat["pris_le"] = self._lu["pris_le"]
            if self.etat == ERREUR:
                etat["erreur"] = self._lu["erreur"]
        complet = self._lu if self._lu is not None and self.etat in (PRESENT, PERDU) else {}
        head = complet.get("head")
        return {
            "repo": self._session["repo"],
            "branche": complet.get("branche", self._session.get("branche")),
            "head": head[:7] if head else None,
            "source": "instantane",
            "instantane": etat,
        }

    def arbre(self, chemin: str) -> list[dict]:
        """Entrées du dossier : celles de l’instantané, puis les ignorées et `.git/` (à la racine),
        `non_conserve`."""
        relatif = self._chemin(chemin)
        if self._type(relatif) != "tree":
            raise CheminRefuse(f"{chemin} n’est pas un dossier")
        sortie = self._git("ls-tree", "-z", "--long", f"{self._sha}:{relatif}")
        entrees = []
        for ligne in filter(None, sortie.split("\0")):
            meta, _, nom = ligne.partition("\t")
            mode, type_, _, taille = meta.split()
            if type_ == "tree":
                genre = DOSSIER
            elif type_ == "blob" and mode != "120000":
                genre = FICHIER
            else:
                # Symlink ou sous-module : jamais suivi.
                genre = LIEN
            entrees.append({
                "nom": nom, "type": genre, "taille": int(taille) if genre == FICHIER else None,
                "statut": None, "ignore": False, "non_conserve": False,
            })
        self._marquer(relatif, entrees)
        for nom in self._lu["ignores"].get(relatif, []):
            entrees.append(_non_conserve(nom.rstrip("/"), nom.endswith("/"), ignore=True))
        if relatif == "":
            entrees.append(_non_conserve(".git", True, ignore=False))
        return trier(entrees)

    def fichier(self, chemin: str) -> dict:
        relatif = self._blob(chemin)
        taille = int(self._git("cat-file", "-s", f"{self._sha}:{relatif}").strip())
        return fichier_lu(chemin, taille, self._contenu(self._sha, relatif) if taille <= TAILLE_MAX else None)

    def diff(self, chemin: str) -> dict:
        """Versions du HEAD de l’époque et de l’instantané ; mêmes règles que le diff en direct."""
        relatif = self._blob(chemin)
        lu = {"chemin": chemin, "head": None, "courant": None}
        courant = self._contenu(self._sha, relatif)
        courant, non_affiche = texte(courant if len(courant) <= TAILLE_MAX else None, len(courant))
        if non_affiche is not None:
            return {**lu, "non_affiche": non_affiche}
        head = self._lu["head"]
        avant = None if head is None else self._contenu(head, relatif, absent_ok=True)
        if avant is None:
            return {**lu, "courant": courant}
        avant, non_affiche = texte(avant if len(avant) <= TAILLE_MAX else None, len(avant))
        if non_affiche is not None:
            return {**lu, "non_affiche": non_affiche}
        return {**lu, "head": avant, "courant": courant}

    @property
    def _sha(self) -> str:
        if self.etat != PRESENT:
            raise CodespaceErreur(self._raison)
        return self._lu["sha"]

    def _chemin(self, chemin: str) -> str:
        """Le chemin normalisé, relatif à la racine de l’instantané (`""` : la racine)."""
        relatif = chemin_relatif(chemin)
        self._sha  # Sans instantané lisible : sa raison, avant tout le reste.
        return "" if str(relatif) == "." else str(relatif)

    def _type(self, relatif: str) -> str:
        """`tree`, `blob`… ; `CodespaceErreur` si absent de l’instantané (un ignoré, `.git/`)."""
        sortie = subprocess.run(
            ["git", "-C", str(self._clone), "cat-file", "-t", f"{self._sha}:{relatif}"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        if sortie.returncode != 0:
            raise CodespaceErreur(f"{relatif} absent de l’instantané")
        return sortie.stdout.strip()

    def _blob(self, chemin: str) -> str:
        relatif = self._chemin(chemin)
        if self._type(relatif) != "blob":
            raise CheminRefuse(f"{chemin} n’est pas un fichier")
        return relatif

    def _contenu(self, commit: str, relatif: str, absent_ok: bool = False) -> bytes | None:
        sortie = subprocess.run(
            ["git", "-C", str(self._clone), "cat-file", "blob", f"{commit}:{relatif}"],
            capture_output=True, stdin=subprocess.DEVNULL,
        )
        if sortie.returncode != 0:
            if absent_ok:
                return None
            raise CodespaceErreur(f"{relatif} illisible dans l’instantané")
        return sortie.stdout

    def _marquer(self, relatif: str, entrees: list[dict]) -> None:
        """Statut par rapport au HEAD de l’époque (sans HEAD : tout est ajouté), un ajouté non suivi à
        la prise restant non suivi ; un dossier prend le plus fort de ce qu’il contient."""
        par_nom = {e["nom"]: e for e in entrees}
        # Avant la liste des non suivis (premiers instantanés de la 0.8.0) : tout est ajouté.
        non_suivis = self._lu.get("non_suivis", [])
        prefixe = relatif + "/" if relatif else ""
        sortie = self._git(
            "diff-tree", "--no-commit-id", "-r", "-z", "--no-renames", "--name-status", "--root", self._sha,
            "--", *([relatif] if relatif else []),
        )
        champs = iter(sortie.split("\0"))
        for lettre in champs:
            chemin = next(champs, "")
            if not lettre or not chemin.startswith(prefixe):
                continue
            entree = par_nom.get(chemin.removeprefix(prefixe).split("/")[0])
            if lettre != "A":
                statut = MODIFIE
            elif any(chemin == n or (n.endswith("/") and chemin.startswith(n)) for n in non_suivis):
                statut = NON_SUIVI
            else:
                statut = AJOUTE
            if entree is not None:
                marquer(entree, statut)

    def _git(self, *args: str) -> str:
        sortie = subprocess.run(
            ["git", "-C", str(self._clone), *args],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_LITERAL_PATHSPECS": "1"},
        )
        if sortie.returncode != 0:
            raise CodespaceErreur("instantané illisible")
        return sortie.stdout


def _non_conserve(nom: str, dossier: bool, ignore: bool) -> dict:
    return {
        "nom": nom, "type": DOSSIER if dossier else FICHIER, "taille": None,
        "statut": None, "ignore": ignore, "non_conserve": True,
    }


def _git(clone: Path, env: dict, *args: str) -> str:
    sortie = subprocess.run(
        ["git", "-C", str(clone), *args],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        # Lire sans réécrire l’index réel (rafraîchissement opportuniste de `git status`…).
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", **env},
    )
    if sortie.returncode != 0:
        detail = sortie.stderr.strip().splitlines()
        raise _Echec(f"git {args[0]} a échoué" + (f" : {detail[-1]}" if detail else ""))
    return sortie.stdout
