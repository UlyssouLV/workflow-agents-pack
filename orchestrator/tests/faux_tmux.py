"""Faux `tmux` des tests du terminal : un multiplexeur réduit, sans pseudo-terminal côté agent.

Installé dans le `PATH` par `installer(bin_, etat)`. Chaque session vit sous `etat/<nom>/` :
`sortie` (tout ce que la commande a écrit), `entree` (FIFO lue par la commande), `pid` (son groupe
de processus), `fin` (posé quand la commande est sortie). Les appels sont notés dans
`etat/appels.log`.

- `new-session -d -s <nom> -c <dossier> <commande>` : lance la commande en arrière-plan et rend la
  main ; ce qui suit un `;` (options de la session) est ignoré.
- `attach-session [-f read-only,…] -t <nom>` : réécrit tout `sortie` (l’écran retrouvé à la
  reconnexion), puis le suit jusqu’à `fin` ; la saisie va dans `entree` (`\\r` → `\\n`, comme la
  discipline de ligne du vrai terminal), sauf en lecture seule.
- `kill-session -t <nom>` : `SIGHUP` au groupe de la commande, comme la fermeture de son terminal.
- `has-session -t <nom>` : code 0 si la commande tourne.
"""

import os
import signal
import stat
import subprocess
import sys
import termios
import threading
import time
import tty
from pathlib import Path


def installer(bin_: Path, etat: Path) -> None:
    etat.mkdir(parents=True, exist_ok=True)
    chemin = bin_ / "tmux"
    chemin.write_text(
        f"#!/bin/sh\nFAUX_TMUX_ETAT={etat} exec {sys.executable} {Path(__file__).resolve()} \"$@\"\n"
    )
    chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)


def _option(args: list[str], nom: str) -> str | None:
    return args[args.index(nom) + 1] if nom in args else None


def _tourne(dossier: Path) -> bool:
    return (dossier / "pid").exists() and not (dossier / "fin").exists()


def nouvelle_session(etat: Path, args: list[str]) -> int:
    args = args[: args.index(";")] if ";" in args else args
    dossier = etat / _option(args, "-s")
    dossier.mkdir()
    os.mkfifo(dossier / "entree")
    serveur = subprocess.Popen(
        [sys.executable, __file__, "_serveur", str(dossier), _option(args, "-c"), args[-1]],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    (dossier / "pid").write_text(str(serveur.pid))
    return 0


def serveur(dossier: Path, cwd: str, commande: str) -> None:
    # Le gestionnaire (contrairement à SIG_IGN) n’est pas hérité : la commande reçoit SIGHUP.
    signal.signal(signal.SIGHUP, lambda *_: None)
    # O_RDWR : la FIFO ne voit jamais de fin de fichier, même sans client attaché.
    entree = os.open(dossier / "entree", os.O_RDWR)
    with open(dossier / "sortie", "ab", buffering=0) as sortie:
        subprocess.run(["sh", "-c", commande], cwd=cwd, stdin=entree, stdout=sortie, stderr=sortie)
    (dossier / "fin").touch()


def attacher(dossier: Path, lecture_seule: bool) -> int:
    if not _tourne(dossier):
        print(f"can't find session: {dossier.name}", file=sys.stderr)
        return 1
    if os.isatty(0):
        # TCSANOW : ce qui est déjà tapé n’est pas jeté.
        tty.setraw(0, termios.TCSANOW)
    threading.Thread(target=_saisie, args=(dossier, lecture_seule), daemon=True).start()
    with open(dossier / "sortie", "rb") as sortie:
        while True:
            if donnees := sortie.read(65536):
                os.write(1, donnees)
            elif (dossier / "fin").exists():
                return 0
            else:
                time.sleep(0.02)


def _saisie(dossier: Path, lecture_seule: bool) -> None:
    entree = os.open(dossier / "entree", os.O_WRONLY)
    while donnees := os.read(0, 4096):
        if not lecture_seule:
            os.write(entree, donnees.replace(b"\r", b"\n"))


def tuer(dossier: Path) -> int:
    if not _tourne(dossier):
        return 1
    os.killpg(int((dossier / "pid").read_text()), signal.SIGHUP)
    return 0


def tout_arreter(etat: Path) -> None:
    """Fin de test : aucune session ne survit."""
    for dossier in etat.iterdir():
        if dossier.is_dir() and _tourne(dossier):
            try:
                os.killpg(int((dossier / "pid").read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def main(args: list[str]) -> int:
    if args[0] == "_serveur":
        serveur(Path(args[1]), args[2], args[3])
        return 0
    etat = Path(os.environ["FAUX_TMUX_ETAT"])
    with open(etat / "appels.log", "a") as log:
        log.write(" ".join(["tmux", *args]) + "\n")
    commande, cible = args[0], _option(args, "-t")
    if commande == "new-session":
        return nouvelle_session(etat, args[1:])
    if commande == "attach-session":
        return attacher(etat / cible, "read-only" in (_option(args, "-f") or ""))
    if commande == "kill-session":
        return tuer(etat / cible)
    if commande == "has-session":
        return 0 if _tourne(etat / cible) else 1
    print(f"faux tmux : {commande} non simulé", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
