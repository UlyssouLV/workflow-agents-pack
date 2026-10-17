"""Enregistrement d’une session (spec 0.4.0, « Enregistrement ») : le terminal de l’agent dans
`jobs/<id>/terminal.cast` (asciinema v2), sa transcription native copiée à la fin.

L’agent tourne dans un pseudo-terminal tenu par l’exécuteur, qui relaie entre celui de la session
tmux et le sien, et note au passage chaque sortie et chaque changement de taille.
"""

import codecs
import fcntl
import json
import os
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
from contextlib import suppress
from pathlib import Path

from wap_runtime.agents import agent_par_id
from wap_runtime.pseudo_terminal import brut, controler, restaurer

CAST = "terminal.cast"
TRANSCRIPTION = "transcription"
# Hors d’un terminal (tests) : la taille d’un terminal par défaut.
TAILLE_PAR_DEFAUT = (80, 24)
# Code de sortie d’un agent qui n’a pas pu être lancé, comme le rend un shell.
CODE_NON_LANCE = 127


class Cast:
    """asciicast v2 : l’en-tête, puis une ligne `[secondes, "o"|"r", données]` par événement,
    écrite aussitôt (le cast se lit pendant la session)."""

    def __init__(self, chemin: Path, colonnes: int, lignes: int):
        self._fichier = open(chemin, "w", encoding="utf-8")
        self._debut = time.monotonic()
        # Une lecture peut couper un caractère UTF-8 en deux.
        self._decodeur = codecs.getincrementaldecoder("utf-8")("replace")
        self._ligne({"version": 2, "width": colonnes, "height": lignes, "timestamp": int(time.time())})

    def sortie(self, donnees: bytes) -> None:
        if texte := self._decodeur.decode(donnees):
            self._evenement("o", texte)

    def taille(self, colonnes: int, lignes: int) -> None:
        self._evenement("r", f"{colonnes}x{lignes}")

    def fermer(self) -> None:
        if reste := self._decodeur.decode(b"", final=True):
            self._evenement("o", reste)
        self._fichier.close()

    def __enter__(self) -> "Cast":
        return self

    def __exit__(self, *_) -> None:
        self.fermer()

    def _evenement(self, type_: str, donnees: str) -> None:
        self._ligne([round(time.monotonic() - self._debut, 6), type_, donnees])

    def _ligne(self, valeur: object) -> None:
        self._fichier.write(json.dumps(valeur, ensure_ascii=False) + "\n")
        self._fichier.flush()


def enregistrer(commande: list[str], cast: Path) -> int:
    """Lance `commande` dans un pseudo-terminal, relaie l’entrée et la sortie standard, et
    enregistre le terminal dans `cast` ; rend le code de sortie de l’agent.

    **Terminer** ferme la session tmux : SIGHUP arrête l’agent, et l’exécuteur, qui y survit,
    rend son code (un agent tué par un signal sort en `128 + signal`).
    """
    entree, sortie = sys.stdin.fileno(), sys.stdout.fileno()
    colonnes, lignes = _taille(sortie)
    maitre, esclave = os.openpty()
    _redimensionner(maitre, colonnes, lignes)
    agent: subprocess.Popen | None = None
    arretee = False

    def arreter(*_) -> None:
        nonlocal arretee
        arretee = True
        if agent is not None:
            with suppress(ProcessLookupError):
                os.killpg(agent.pid, signal.SIGHUP)

    # Un gestionnaire, pas SIG_IGN : l’agent, lui, garde le comportement par défaut.
    signal.signal(signal.SIGHUP, arreter)
    with Cast(cast, colonnes, lignes) as enregistrement:

        def redimensionner(*_) -> None:
            taille = _taille(sortie)
            _redimensionner(maitre, *taille)
            enregistrement.taille(*taille)

        def afficher(donnees: bytes) -> None:
            enregistrement.sortie(donnees)
            # Le terminal de la session est parti (Terminer) : l’enregistrement continue.
            with suppress(OSError):
                _ecrire(sortie, donnees)

        try:
            agent = subprocess.Popen(
                commande, stdin=esclave, stdout=esclave, stderr=esclave, preexec_fn=controler
            )
        except OSError as erreur:
            afficher(f"KO — {commande[0]} : {erreur}\r\n".encode())
            os.close(maitre)
            os.close(esclave)
            return CODE_NON_LANCE
        if arretee:
            # Terminé avant que l’agent ne démarre.
            arreter()
        signal.signal(signal.SIGWINCH, redimensionner)
        avant = brut(entree)
        try:
            _relayer(agent, entree, maitre, afficher)
        finally:
            restaurer(entree, avant)
            # L’esclave reste ouvert jusqu’ici : la sortie de l’agent est lue jusqu’au bout.
            os.close(maitre)
            os.close(esclave)
    code = agent.wait()
    return 128 - code if code < 0 else code


def _relayer(agent: subprocess.Popen, entree: int, maitre: int, afficher) -> None:
    """Jusqu’à la sortie de l’agent : sa sortie vers `afficher`, l’entrée standard vers lui."""
    lectures = [maitre, entree]
    while agent.poll() is None:
        prets, _, _ = select.select(lectures, [], [], 0.1)
        if maitre in prets:
            if donnees := _lire(maitre):
                afficher(donnees)
        if entree in prets:
            if donnees := _lire(entree):
                _ecrire(maitre, donnees)
            else:
                # Plus d’entrée (fin de fichier, terminal fermé) : l’agent continue.
                lectures.remove(entree)
    while select.select([maitre], [], [], 0.05)[0] and (donnees := _lire(maitre)):
        afficher(donnees)


def _taille(fd: int) -> tuple[int, int]:
    try:
        taille = os.get_terminal_size(fd)
    except OSError:
        return TAILLE_PAR_DEFAUT
    return taille.columns, taille.lines


def _redimensionner(fd: int, colonnes: int, lignes: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", lignes, colonnes, 0, 0))


def _lire(fd: int) -> bytes:
    """`b""` à la fin de fichier ou si le terminal est fermé (EIO)."""
    try:
        return os.read(fd, 65536)
    except OSError:
        return b""


def _ecrire(fd: int, donnees: bytes) -> None:
    while donnees:
        donnees = donnees[os.write(fd, donnees) :]


def copier_transcription(agent: str, home: Path, depuis: float, cible: Path) -> list[Path]:
    """Copie sous `cible` (chemins relatifs gardés) les fichiers de transcription de `agent`
    modifiés depuis `depuis` (horodatage) ; rend les copies.

    Une seule session à la fois et un `HOME` propre au runner : ce qui a bougé pendant la session
    est à elle. Un fichier illisible est signalé et passé, la session se clôt quand même.
    """
    racine, motif = agent_par_id(agent).transcriptions
    racine = home / racine
    copiees = []
    for source in sorted(racine.glob(motif)) if racine.is_dir() else []:
        try:
            if not source.is_file() or source.stat().st_mtime < depuis:
                continue
            copie = cible / source.relative_to(racine)
            copie.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copie)
        except OSError as erreur:
            print(f"transcription non copiée : {source} ({erreur})", file=sys.stderr)
            continue
        copiees.append(copie)
    return copiees
