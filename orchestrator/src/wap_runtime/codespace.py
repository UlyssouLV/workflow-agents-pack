"""Codespace d’une session (ADR 0014) : le clone géré lu en lecture seule par le runner.

Tout chemin reçu est relatif au clone ; résolu (symlinks compris), il doit y rester. Un symlink
qui sort du clone est listé comme lien, jamais suivi.

En direct (websocket `…/codespace/evenements`) :
- client → serveur : l’abonnement, qui remplace le précédent : `{"dossiers": ["", "src"],
  "fichier": "src/app.py"}` (dossiers dépliés, fichier ouvert ou `null`).
- serveur → client : `{"dossiers": [...], "fichier": bool, "entete": bool}` après une rafale de
  changements (dossiers abonnés à relire, fichier ouvert changé, HEAD ou ref courante changé) ;
  `{"surveillance": "indisponible"}` si le disque ne peut pas être surveillé, puis la fermeture.
"""

import asyncio
import json
import os
import subprocess
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from watchfiles import awatch

from wap_runtime.terminal import premier_fini

# Au-delà, ou binaire : « non affiché », avec la taille.
TAILLE_MAX = 1024 * 1024
# Comme Git : un octet nul dans le début du fichier le dit binaire.
DEBUT_BINAIRE = 8000
DOSSIER, FICHIER, LIEN = "dossier", "fichier", "lien"
MODIFIE, AJOUTE, NON_SUIVI, IGNORE = "modifie", "ajoute", "non_suivi", "ignore"
# Du plus fort au plus faible : un dossier prend le plus fort de ce qu’il contient.
STATUTS = (MODIFIE, AJOUTE, NON_SUIVI)
# Une rafale (un `npm install`) donne un seul événement : rien de neuf pendant ce délai, ou
# `ATTENTE_MAX_MS` écoulées depuis le premier changement.
REGROUPEMENT_MS = 300
ATTENTE_MAX_MS = 1600


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

    `statut` : `modifie`, `ajoute`, `non_suivi` ou `None` (un dossier prend le plus fort de ce qu’il
    contient). `ignore` : ignoré par `.gitignore` (jamais sous `.git/`). `taille` : celle d’un fichier."""
    racine, dossier = _resoudre(clone, chemin)
    if not dossier.is_dir():
        raise CheminRefuse(f"{chemin} n’est pas un dossier")
    entrees = [_entree(racine, element) for element in os.scandir(dossier)]
    _marquer(racine, dossier, entrees)
    return sorted(entrees, key=lambda e: (e["type"] != DOSSIER, e["nom"].casefold(), e["nom"]))


def fichier(clone: Path, chemin: str) -> dict:
    """Contenu texte, ou `contenu` nul et `non_affiche` (`binaire`, `trop_gros`)."""
    _, cible = _fichier(clone, chemin)
    taille = cible.stat().st_size
    lu = {"chemin": chemin, "taille": taille}
    contenu, non_affiche = _texte(cible.read_bytes() if taille <= TAILLE_MAX else None, taille)
    return {**lu, "contenu": contenu} if non_affiche is None else {**lu, "contenu": None, "non_affiche": non_affiche}


def diff(clone: Path, chemin: str) -> dict:
    """Versions HEAD et courante du fichier ; `head` nul s’il n’est pas dans HEAD (ajouté, non suivi).

    Un côté binaire ou de plus de 1 Mo : les deux nuls, et `non_affiche`."""
    racine, cible = _fichier(clone, chemin)
    lu = {"chemin": chemin, "head": None, "courant": None}
    taille = cible.stat().st_size
    courant, non_affiche = _texte(cible.read_bytes() if taille <= TAILLE_MAX else None, taille)
    if non_affiche is not None:
        return {**lu, "non_affiche": non_affiche}
    relatif = cible.relative_to(racine).as_posix()
    if relatif.split("/")[0] == ".git":
        return {**lu, "courant": courant}
    blob = subprocess.run(
        ["git", "-C", str(racine), "cat-file", "blob", f"HEAD:{relatif}"],
        capture_output=True, stdin=subprocess.DEVNULL,
    )
    if blob.returncode != 0:
        return {**lu, "courant": courant}
    head, non_affiche = _texte(blob.stdout if len(blob.stdout) <= TAILLE_MAX else None, len(blob.stdout))
    if non_affiche is not None:
        return {**lu, "non_affiche": non_affiche}
    return {**lu, "head": head, "courant": courant}


def _fichier(clone: Path, chemin: str) -> tuple[Path, Path]:
    racine, cible = _resoudre(clone, chemin)
    if not cible.is_file():
        raise CheminRefuse(f"{chemin} n’est pas un fichier")
    return racine, cible


def _texte(octets: bytes | None, taille: int) -> tuple[str | None, str | None]:
    """`(contenu, None)`, ou `(None, raison)` : `trop_gros` (`octets` nul, non lus) ou `binaire`."""
    if octets is None or taille > TAILLE_MAX:
        return None, "trop_gros"
    if b"\0" not in octets[:DEBUT_BINAIRE]:
        with suppress(UnicodeDecodeError):
            return octets.decode(), None
    return None, "binaire"


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
        # Pour `git status`, relatif au dossier réel : un symlink interne y est suivi.
        "_nom_git": element.name,
    }


def _marquer(racine: Path, dossier: Path, entrees: list[dict]) -> None:
    """`statut` et `ignore` de chaque entrée, d’après `git status` limité au dossier.

    Git y rend le dossier lui-même (ou un parent) s’il est non suivi ou ignoré : ses entrées en
    héritent ; un changement plus profond marque le sous-dossier qui le contient."""
    par_nom = {}
    for entree in entrees:
        entree.update(statut=None, ignore=False)
        par_nom[entree.pop("_nom_git")] = entree
    relatif = dossier.relative_to(racine).as_posix()
    if not entrees or relatif.split("/")[0] == ".git":
        return
    prefixe = "" if relatif == "." else relatif + "/"
    sortie = subprocess.run(
        ["git", "-C", str(racine), "status", "--porcelain=v2", "--ignored", "--no-renames", "-z",
         "--", relatif],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        # Lire sans réécrire l’index : sous surveillance, `.git/` changerait à chaque lecture.
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    # Git a échoué : rien n’est marqué.
    if sortie.returncode != 0:
        return
    for chemin, statut in _statuts(sortie.stdout):
        if prefixe.startswith(chemin + "/"):
            # Le dossier listé, ou un parent : toutes ses entrées.
            touchees = list(par_nom.values())
        else:
            nom, _, reste = chemin.removeprefix(prefixe).partition("/")
            # L’ignoré ne remonte pas : un dossier qui contient un ignoré n’est pas grisé.
            touchees = [par_nom[nom]] if nom in par_nom and not (reste and statut == IGNORE) else []
        for entree in touchees:
            if statut == IGNORE:
                entree["ignore"] = True
            elif entree["statut"] is None or STATUTS.index(statut) < STATUTS.index(entree["statut"]):
                entree["statut"] = statut
    for entree in entrees:
        if entree["ignore"]:
            entree["statut"] = None


def _statuts(porcelaine: str):
    """`(chemin, statut)` de la sortie `git status --porcelain=v2 -z --no-renames`, sans `/` final."""
    for ligne in porcelaine.split("\0"):
        genre, _, suite = ligne.partition(" ")
        if genre == "1":
            xy, chemin = suite[:2], suite.split(" ", 7)[7]
            statut = AJOUTE if xy[0] == "A" and "D" not in xy else MODIFIE
        elif genre == "u":
            chemin, statut = suite.split(" ", 9)[9], MODIFIE
        elif genre == "?":
            chemin, statut = suite, NON_SUIVI
        elif genre == "!":
            chemin, statut = suite, IGNORE
        else:
            continue
        yield chemin.rstrip("/"), statut


def _git_ou_none(clone: Path, *args: str) -> str | None:
    sortie = subprocess.run(
        ["git", "-C", str(clone), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    return sortie.stdout.strip() or None if sortie.returncode == 0 else None


@dataclass(frozen=True)
class Abonnement:
    """Ce que le cockpit montre : dossiers dépliés (`""` : la racine) et fichier ouvert."""

    dossiers: frozenset[str] = frozenset()
    fichier: str | None = None


def lire_abonnement(texte: str | None) -> Abonnement | None:
    """L’abonnement d’un message client ; `None` s’il n’en est pas un."""
    try:
        message = json.loads(texte or "")
    except ValueError:
        return None
    if not isinstance(message, dict):
        return None
    dossiers, fichier = message.get("dossiers", []), message.get("fichier")
    if not isinstance(dossiers, list) or not all(isinstance(d, str) for d in dossiers):
        return None
    if fichier is not None and not isinstance(fichier, str):
        return None
    return Abonnement(frozenset(dossiers), fichier)


@dataclass
class Veille:
    """Ce qu’un abonnement fait surveiller sur le disque (chemins réels, jamais hors du clone), et
    l’événement qu’en donne une rafale de changements."""

    racine: Path
    # Dossier réel surveillé → dossiers abonnés qu’il montre (un symlink interne en est un autre).
    dossiers: dict[Path, set[str]] = field(default_factory=dict)
    abonnes: frozenset[str] = frozenset()
    fichier: Path | None = None

    @classmethod
    def de(cls, clone: Path, abonnement: Abonnement) -> "Veille":
        veille = cls(clone.resolve(), abonnes=abonnement.dossiers)
        for chemin in abonnement.dossiers:
            with suppress(CodespaceErreur):
                _, dossier = _resoudre(clone, chemin)
                if dossier.is_dir():
                    veille.dossiers.setdefault(dossier, set()).add(chemin)
        if abonnement.fichier is not None:
            with suppress(CodespaceErreur):
                veille.fichier = _fichier(clone, abonnement.fichier)[1]
        return veille

    def chemins(self) -> list[Path]:
        """Les dossiers à surveiller, sans récursion : les dossiers abonnés, celui du fichier ouvert
        (un fichier remplacé par renommage reste vu), `.git/` pour HEAD et le dossier de la ref
        courante."""
        git = self.racine / ".git"
        chemins = {*self.dossiers, git}
        if self.fichier is not None:
            chemins.add(self.fichier.parent)
        if (branche := _git_ou_none(self.racine, "symbolic-ref", "--quiet", "HEAD")) is not None:
            ref = Path(os.path.realpath(git / branche)).parent
            if ref.is_relative_to(git) and ref.is_dir():
                chemins.add(ref)
        return sorted(chemins)

    def evenement(self, changes: set[tuple[object, str]]) -> dict | None:
        """`None` si rien de ce que montre le cockpit n’a changé."""
        dossiers, fichier, entete = set(), False, False
        refs = self.racine / ".git" / "refs" / "heads"
        for _, brut in changes:
            chemin = Path(brut)
            if chemin.parent == self.racine / ".git" and chemin.name in ("HEAD", "packed-refs"):
                entete = True
            elif chemin.is_relative_to(refs):
                entete = True
            touche = set(self.dossiers.get(chemin.parent, ()))
            if self.fichier is not None and chemin == self.fichier:
                fichier = True
                touche.add(self.fichier.parent.relative_to(self.racine).as_posix())
            for abonne in touche:
                dossiers |= {d for d in self.abonnes if _contient(d, abonne)}
        if not (dossiers or fichier or entete):
            return None
        return {"dossiers": sorted(dossiers), "fichier": fichier, "entete": entete}


def _contient(dossier: str, chemin: str) -> bool:
    """`dossier` est `chemin` ou l’un de ses parents (`""` et `"."` : la racine)."""
    if dossier in ("", "."):
        return True
    return chemin == dossier or chemin.startswith(dossier + "/")


async def pousser_evenements(websocket, clone: Path) -> None:
    """Websocket (Starlette, déjà accepté) : surveille le clone selon l’abonnement reçu et pousse
    les événements, jusqu’à la déconnexion ; ferme le websocket si la surveillance est impossible.

    Un nouvel abonnement, ou un changement d’en-tête (la ref courante a pu changer), relance la
    surveillance sur les nouveaux chemins."""
    abonnement = Abonnement()
    relancer = asyncio.Event()

    async def recevoir() -> None:
        nonlocal abonnement
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if (lu := lire_abonnement(message.get("text"))) is not None:
                abonnement = lu
                relancer.set()

    async def pousser() -> None:
        while True:
            relancer.clear()
            veille = Veille.de(clone, abonnement)
            try:
                async for changes in awatch(
                    *veille.chemins(),
                    watch_filter=None,
                    recursive=False,
                    step=REGROUPEMENT_MS,
                    debounce=ATTENTE_MAX_MS,
                    stop_event=relancer,
                ):
                    if (evenement := veille.evenement(changes)) is not None:
                        await websocket.send_json(evenement)
                        if evenement["entete"]:
                            relancer.set()
            except FileNotFoundError:
                # Un dossier surveillé a disparu entre-temps : on relance sur ceux qui restent.
                await asyncio.sleep(REGROUPEMENT_MS / 1000)
            except (OSError, RuntimeError):
                # Limite inotify atteinte, système de fichiers sans notification… : le cockpit
                # se rabat sur un polling lent.
                await websocket.send_json({"surveillance": "indisponible"})
                await websocket.close()
                return

    await premier_fini(recevoir(), pousser())
