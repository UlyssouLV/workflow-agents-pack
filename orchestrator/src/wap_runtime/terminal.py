"""Terminal en direct d’une session (spec 0.4.0, « Terminal ») : websocket ↔ session tmux.

Chaque client websocket du runner est un client `tmux attach` dans son propre pseudo-terminal :
tmux redessine l’écran courant à chaque attache (on retrouve l’écran en revenant) et la session
survit au départ du client. Un seul client écrit (il a la *main*), d’abord le premier connecté ;
les autres s’attachent en lecture seule et leur saisie est jetée. Un lecteur peut prendre la
main : celui qui écrivait repasse en lecture seule. Quand celui qui écrit part, le plus ancien des
autres prend la main (un onglet rechargé n’attend pas que le runner ait vu partir l’ancien).

Messages du websocket :
- serveur → client : la sortie du terminal en binaire ; `{"role": "ecriture"|"lecture"}` au début
  et à chaque changement de main.
- client → serveur : `{"saisie": "<texte>"}`, `{"taille": {"colonnes": n, "lignes": n}}` (écrivain
  seulement), `{"prendre": true}`.
"""

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import termios
from contextlib import contextmanager, suppress
from typing import Awaitable, Iterator

ECRITURE, LECTURE = "ecriture", "lecture"


def commande_attache(nom: str, lecture_seule: bool) -> list[str]:
    # `ignore-size` : un lecteur ne redimensionne pas l’écran de celui qui écrit.
    options = ["-f", "read-only,ignore-size"] if lecture_seule else []
    return ["tmux", "attach-session", *options, "-t", nom]


class Pty:
    """`argv` dans un pseudo-terminal dont il est le terminal de contrôle (tmux l’exige)."""

    def __init__(self, argv: list[str]):
        maitre, esclave = pty.openpty()

        def controler() -> None:
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        try:
            self._processus = subprocess.Popen(
                argv,
                stdin=esclave,
                stdout=esclave,
                stderr=esclave,
                preexec_fn=controler,
                env={**os.environ, "TERM": "xterm-256color"},
            )
        except OSError:
            os.close(maitre)
            raise
        finally:
            os.close(esclave)
        self.maitre = maitre
        os.set_blocking(maitre, False)

    async def lire(self) -> bytes:
        """Prochaine sortie ; `b""` quand plus rien n’écrit (le client tmux est sorti)."""
        boucle = asyncio.get_running_loop()
        while True:
            try:
                return os.read(self.maitre, 65536)
            except BlockingIOError:
                pass
            except OSError:
                # EIO : l’esclave est fermé.
                return b""
            pret = boucle.create_future()
            boucle.add_reader(self.maitre, lambda: pret.done() or pret.set_result(None))
            try:
                await pret
            finally:
                boucle.remove_reader(self.maitre)

    async def ecrire(self, donnees: bytes) -> None:
        while donnees:
            try:
                donnees = donnees[os.write(self.maitre, donnees) :]
            except BlockingIOError:
                await asyncio.sleep(0.01)

    def redimensionner(self, colonnes: int, lignes: int) -> None:
        fcntl.ioctl(self.maitre, termios.TIOCSWINSZ, struct.pack("HHHH", lignes, colonnes, 0, 0))

    def fermer(self) -> None:
        """Détache le client (SIGHUP, comme un terminal fermé) ; la session tmux continue."""
        if self._processus.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(self._processus.pid, signal.SIGHUP)
        # Avant d’attendre : sur macOS, un client qui sort reste bloqué à la fermeture de son
        # terminal tant que sa sortie non lue y attend, même tué.
        os.close(self.maitre)
        try:
            self._processus.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._processus.kill()
            self._processus.wait()


class Main:
    """La place d’un client dans la file de sa session : le premier de la file écrit."""

    def __init__(self, file: list["Main"]):
        self._file = file
        # Posé quand ce client gagne ou perd la main.
        self.changee = asyncio.Event()

    @property
    def ecrit(self) -> bool:
        return self._file[0] is self

    def prendre(self) -> None:
        """Passe en tête ; l’ancien écrivain garde son rang parmi les autres (il est le plus
        ancien d’entre eux et reprendra la main au départ de ce client)."""
        if self.ecrit:
            return
        ancien = self._file[0]
        self._file.remove(self)
        self._file.insert(0, self)
        ancien.changee.set()
        self.changee.set()


class Ecrivains:
    """Par session, les clients dans l’ordre d’arrivée, sauf celui qui a pris la main en tête."""

    def __init__(self):
        self._files: dict[str, list[Main]] = {}

    @contextmanager
    def connexion(self, id_: str) -> Iterator[Main]:
        file = self._files.setdefault(id_, [])
        main = Main(file)
        file.append(main)
        try:
            yield main
        finally:
            ecrivait = main.ecrit
            file.remove(main)
            if not file:
                del self._files[id_]
            elif ecrivait:
                file[0].changee.set()


async def relayer(websocket, nom: str, main: Main) -> None:
    """Relaie le websocket (Starlette, déjà accepté) et la session tmux `nom` jusqu’à ce que
    l’un des deux s’arrête ; ferme le websocket si c’est la session.

    À chaque changement de main, le client est rattaché dans son nouveau rôle (tmux redessine
    l’écran).
    """
    while True:
        main.changee.clear()
        ecriture = main.ecrit
        await websocket.send_json({"role": ECRITURE if ecriture else LECTURE})
        terminal = Pty(commande_attache(nom, lecture_seule=not ecriture))

        async def descendre() -> None:
            while donnees := await terminal.lire():
                await websocket.send_bytes(donnees)
            await websocket.close()

        async def monter() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if (texte := message.get("text")) is None:
                    continue
                if _lire(texte).get("prendre") is True:
                    main.prendre()
                elif ecriture:
                    await _appliquer(terminal, texte)

        try:
            premiere = await premier_fini(descendre(), monter(), main.changee.wait())
        finally:
            await asyncio.to_thread(terminal.fermer)
        if premiere != 2:
            return


async def relayer_runner(websocket, amont) -> None:
    """Côté `runtime` : relaie le websocket du navigateur (Starlette, accepté) et celui du runner
    (client `websockets`), messages inchangés, jusqu’à ce que l’un des deux se ferme."""

    async def descendre() -> None:
        try:
            async for message in amont:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)
        finally:
            await websocket.close()

    async def monter() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                await amont.send(message["text"])

    await premier_fini(descendre(), monter())


def _lire(texte: str) -> dict:
    """Le message JSON d’un client ; `{}` s’il n’en est pas un."""
    try:
        message = json.loads(texte)
    except ValueError:
        return {}
    return message if isinstance(message, dict) else {}


async def _appliquer(terminal: Pty, texte: str) -> None:
    message = _lire(texte)
    if isinstance(saisie := message.get("saisie"), str):
        await terminal.ecrire(saisie.encode())
    elif isinstance(taille := message.get("taille"), dict):
        colonnes, lignes = taille.get("colonnes"), taille.get("lignes")
        if isinstance(colonnes, int) and isinstance(lignes, int) and 0 < colonnes < 1000 and 0 < lignes < 1000:
            terminal.redimensionner(colonnes, lignes)


async def premier_fini(*taches: Awaitable[object]) -> int:
    """Attend la première tâche finie, annule les autres ; rend son rang.

    La déconnexion d’un côté se manifeste souvent par une exception de l’autre : un relais qui
    s’arrête n’est pas une erreur.
    """
    lancees = [asyncio.ensure_future(t) for t in taches]
    try:
        finies, _ = await asyncio.wait(lancees, return_when=asyncio.FIRST_COMPLETED)
        return next(i for i, tache in enumerate(lancees) if tache in finies)
    finally:
        for tache in lancees:
            tache.cancel()
        await asyncio.gather(*lancees, return_exceptions=True)
