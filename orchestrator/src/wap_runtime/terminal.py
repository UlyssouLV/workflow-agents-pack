"""Terminal en direct d’une session (spec 0.4.0, « Terminal ») : websocket ↔ session tmux.

Chaque client websocket du runner est un client `tmux attach` dans son propre pseudo-terminal :
tmux redessine l’écran courant à chaque attache (on retrouve l’écran en revenant) et la session
survit au départ du client. Un seul client écrit, le premier connecté ; les autres s’attachent en
lecture seule et leur saisie est jetée. Quand celui qui écrit part, le plus ancien des autres
prend la main (un onglet rechargé n’attend pas que le runner ait vu partir l’ancien).

Messages du websocket :
- serveur → client : la sortie du terminal en binaire ; `{"role": "ecriture"|"lecture"}` au début
  et quand le client prend la main.
- client → serveur : `{"saisie": "<texte>"}`, `{"taille": {"colonnes": n, "lignes": n}}`.
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
            try:
                self._processus.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._processus.kill()
                self._processus.wait()
        os.close(self.maitre)


class Ecrivains:
    """Par session, les clients dans l’ordre d’arrivée : le premier écrit."""

    def __init__(self):
        self._files: dict[str, list[asyncio.Event]] = {}

    @contextmanager
    def connexion(self, id_: str) -> Iterator[asyncio.Event]:
        """L’événement est posé quand ce client écrit : tout de suite s’il est seul, sinon au
        départ de ceux arrivés avant lui."""
        file = self._files.setdefault(id_, [])
        ecrit = asyncio.Event()
        file.append(ecrit)
        file[0].set()
        try:
            yield ecrit
        finally:
            file.remove(ecrit)
            if file:
                file[0].set()
            else:
                del self._files[id_]


async def relayer(websocket, nom: str, ecrit: asyncio.Event) -> None:
    """Relaie le websocket (Starlette, déjà accepté) et la session tmux `nom` jusqu’à ce que
    l’un des deux s’arrête ; ferme le websocket si c’est la session.

    Un lecteur qui prend la main est rattaché en écriture (tmux redessine l’écran).
    """
    while True:
        ecriture = ecrit.is_set()
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
                if ecriture and message.get("text") is not None:
                    await _appliquer(terminal, message["text"])

        taches = [descendre(), monter()] if ecriture else [descendre(), monter(), ecrit.wait()]
        try:
            premiere = await premier_fini(*taches)
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


async def _appliquer(terminal: Pty, texte: str) -> None:
    try:
        message = json.loads(texte)
    except ValueError:
        return
    if not isinstance(message, dict):
        return
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
