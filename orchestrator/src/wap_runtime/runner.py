"""Service `runner` (ADR 0004) : prépare le clone géré et y lance l’agent dans une session tmux.

API interne, non publiée : le `runtime` l’appelle sur le réseau Compose. Le runner ne pose
aucun label.
"""

import os
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from wap_runtime.sessions import CODE_ARRETEE, OUVERTE, Sessions

DEPOT_GITHUB = "https://github.com/{slug}.git"
PORT_RUNNER = 8788
# Programme de chaque agent, lancé en mode interactif sur `/implement #n`.
PROGRAMMES = {"claude": "claude", "cursor": "agent"}


class RunnerErreur(Exception):
    """Lancement impossible ; le message tient sur une ligne."""


class SessionOuverte(Exception):
    def __init__(self, session: dict):
        super().__init__(f"session {session['id']} déjà ouverte")
        self.session = session


@dataclass(frozen=True)
class Identite:
    """Identité git des commits : le compte de `GH_TOKEN` et son adresse noreply."""

    login: str
    email: str


def email_noreply(login: str, id_: int) -> str:
    return f"{id_}+{login}@users.noreply.github.com"


def commande_agent(agent: str, ticket: int) -> list[str]:
    return [PROGRAMMES[agent], f"/implement #{ticket}"]


def lanceur_tmux(nom: str, commande: list[str], dossier: Path) -> None:
    """Session tmux détachée : elle survit à la requête, et à l’onglet du cockpit."""
    subprocess.run(
        [
            "tmux", "new-session", "-d", "-s", nom, "-c", str(dossier), shlex.join(commande),
            # Le cockpit montre le terminal de l’agent, sans barre ni raccourcis tmux.
            ";", "set-option", "-t", nom, "status", "off",
            ";", "set-option", "-t", nom, "prefix", "None",
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def arreteur_tmux(nom: str) -> None:
    """Ferme la session tmux : son terminal disparaît, l’agent reçoit SIGHUP."""
    # Déjà partie (agent sorti, runner redémarré) : rien à arrêter.
    subprocess.run(["tmux", "kill-session", "-t", nom], capture_output=True, stdin=subprocess.DEVNULL)


def nom_tmux(id_: str) -> str:
    return f"wap-{id_}"


class Runner:
    def __init__(
        self,
        clones: Path,
        jobs: Path,
        lanceur: Callable[[str, list[str], Path], None] = lanceur_tmux,
        depot: str = DEPOT_GITHUB,
        arreteur: Callable[[str], None] = arreteur_tmux,
        attente: float = 10,
    ):
        """`depot` : URL du dépôt, `{slug}` remplacé (les tests y mettent un dépôt local).

        `attente` : secondes laissées à l’agent pour sortir après **Terminer**.
        """
        self._clones = clones
        self._sessions = Sessions(jobs)
        self._lanceur = lanceur
        self._depot = depot
        self._arreteur = arreteur
        self._attente = attente
        # Deux requêtes simultanées ne doivent pas ouvrir deux sessions.
        self._verrou = threading.Lock()

    def lancer(self, repo: str, ticket: int, agent: str, branche: str, identite: Identite) -> dict:
        """Lève `SessionOuverte` s’il y en a déjà une, `RunnerErreur` si le clone ne se prépare pas."""
        if agent not in PROGRAMMES:
            raise RunnerErreur(f"agent inconnu : {agent}")
        with self._verrou:
            if (ouverte := self._sessions.ouverte()) is not None:
                raise SessionOuverte(ouverte)
            dossier = self.preparer_clone(repo, branche, identite)
            argv = commande_agent(agent, ticket)
            session = self._sessions.creer(repo, ticket, agent, f'{argv[0]} "{argv[1]}"')
            executeur = [sys.executable, "-m", "wap_runtime.sessions", str(self._sessions.jobs), session["id"]]
            try:
                self._lanceur(nom_tmux(session["id"]), [*executeur, *argv], dossier)
            except (OSError, subprocess.CalledProcessError) as erreur:
                self._sessions.clore(session["id"], 127)
                raise RunnerErreur(f"tmux : {erreur}") from erreur
            return self._sessions.lire(session["id"])

    def session(self, id_: str) -> dict | None:
        return self._sessions.lire(id_)

    def terminer(self, id_: str) -> dict | None:
        """**Terminer** : arrête l’agent, rend la session close (`None` si inconnue).

        L’exécuteur clôt la session avec le code de sortie de l’agent ; s’il ne l’a pas fait dans
        le délai (agent sourd à SIGHUP, tmux déjà parti), le runner la clôt lui-même.
        """
        session = self._sessions.lire(id_)
        if session is None or session["etat"] != OUVERTE:
            return session
        self._arreteur(nom_tmux(id_))
        limite = time.monotonic() + self._attente
        while time.monotonic() < limite:
            if (lue := self._sessions.lire(id_))["etat"] != OUVERTE:
                return lue
            time.sleep(0.05)
        return self._sessions.clore(id_, CODE_ARRETEE)

    def preparer_clone(self, repo: str, branche: str, identite: Identite) -> Path:
        """`clones/<owner>/<name>/` sur `branche` à jour de GitHub, avec l’identité git.

        Créé au premier lancement (HTTPS, `GH_TOKEN` par `gh auth setup-git`), sinon `fetch`.
        """
        dossier = self._clones / repo
        if not (dossier / ".git").is_dir():
            dossier.parent.mkdir(parents=True, exist_ok=True)
            _executer(["gh", "auth", "setup-git"], "gh auth setup-git")
            _git("clone", "--quiet", self._depot.format(slug=repo), str(dossier))
        else:
            _git("-C", str(dossier), "fetch", "--quiet", "--prune", "origin")
        try:
            _git("-C", str(dossier), "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branche}")
        except RunnerErreur:
            raise RunnerErreur(f"branche {branche} inexistante sur GitHub") from None
        _git("-C", str(dossier), "switch", "--quiet", branche)
        _git("-C", str(dossier), "merge", "--quiet", "--ff-only", f"origin/{branche}")
        _git("-C", str(dossier), "config", "user.name", identite.login)
        _git("-C", str(dossier), "config", "user.email", identite.email)
        return dossier


def _git(*args: str) -> None:
    _executer(["git", *args], f"git {args[2] if args[0] == '-C' else args[0]}")


def _executer(commande: list[str], etape: str) -> None:
    try:
        subprocess.run(commande, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as erreur:
        raise RunnerErreur(f"{etape} : {erreur}") from erreur
    except subprocess.CalledProcessError as erreur:
        detail = (erreur.stderr or "").strip().splitlines()
        raise RunnerErreur(f"{etape} a échoué" + (f" : {detail[-1]}" if detail else "")) from erreur


class ClientRunner:
    """Côté `runtime` : l’API interne du runner (`WAP_RUNNER`), sur le réseau Compose."""

    def __init__(self, http):
        self._http = http

    def lancer(self, repo: str, ticket: int, agent: str, branche: str, identite: Identite) -> dict:
        """Mêmes erreurs que `Runner.lancer` ; `RunnerErreur` aussi si le runner est injoignable."""
        import httpx

        demande = {"repo": repo, "ticket": ticket, "agent": agent, "branche": branche,
                   "login": identite.login, "email": identite.email}
        try:
            # Le premier clone d’un gros repo peut être long.
            reponse = self._http.post("/sessions", json=demande, timeout=300)
        except httpx.HTTPError as erreur:
            raise RunnerErreur(f"runner injoignable ({erreur})") from erreur
        if reponse.status_code == 409:
            raise SessionOuverte(reponse.json()["session"])
        if not reponse.is_success:
            try:
                detail = reponse.json()["detail"]
            except (ValueError, KeyError, TypeError):
                detail = f"le runner a répondu {reponse.status_code}"
            raise RunnerErreur(str(detail))
        return reponse.json()

    def terminer(self, id_: str) -> dict:
        """`RunnerErreur` si le runner est injoignable ou ne connaît pas la session."""
        import httpx

        try:
            reponse = self._http.post(f"/sessions/{id_}/terminer", timeout=60)
        except httpx.HTTPError as erreur:
            raise RunnerErreur(f"runner injoignable ({erreur})") from erreur
        if not reponse.is_success:
            raise RunnerErreur(f"le runner a répondu {reponse.status_code}")
        return reponse.json()

    def url_terminal(self, id_: str) -> str:
        """Websocket du terminal de la session, sur le réseau Compose."""
        base = str(self._http.base_url).rstrip("/")
        return f"ws{base.removeprefix('http')}/sessions/{id_}/terminal"


def creer_app_runner(runner: Runner):
    """`POST /sessions` : 201 et la session, 409 et la session ouverte, 422 et le message.

    `POST /sessions/{id}/terminer` : la session close ; websocket `/sessions/{id}/terminal` : le
    terminal en direct d’une session ouverte (`wap_runtime.terminal`).
    """
    from fastapi import FastAPI, HTTPException, WebSocket
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    from wap_runtime import __version__
    from wap_runtime.terminal import Ecrivains, relayer

    class Lancement(BaseModel):
        repo: str
        ticket: int
        agent: str
        branche: str
        login: str
        email: str

    app = FastAPI(title="wap-runner", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    # `def` : FastAPI l’exécute hors de la boucle, le clone peut prendre du temps.
    @app.post("/sessions", status_code=201)
    def lancer(demande: Lancement):
        identite = Identite(demande.login, demande.email)
        try:
            return runner.lancer(demande.repo, demande.ticket, demande.agent, demande.branche, identite)
        except SessionOuverte as refus:
            return JSONResponse({"detail": str(refus), "session": refus.session}, status_code=409)
        except RunnerErreur as erreur:
            return JSONResponse({"detail": str(erreur)}, status_code=422)

    @app.post("/sessions/{id_}/terminer")
    def terminer(id_: str) -> dict:
        if (session := runner.terminer(id_)) is None:
            raise HTTPException(404, f"session {id_} inconnue")
        return session

    ecrivains = Ecrivains()

    @app.websocket("/sessions/{id_}/terminal")
    async def terminal(websocket: WebSocket, id_: str) -> None:
        session = runner.session(id_)
        if session is None or session["etat"] != OUVERTE:
            # Avant `accept` : la poignée de main est refusée.
            await websocket.close()
            return
        await websocket.accept()
        with ecrivains.connexion(id_) as ecrit:
            await relayer(websocket, nom_tmux(id_), ecrit)

    return app


def servir_runner(hote: str, port: int) -> None:
    import uvicorn

    runner = Runner(Path(os.environ.get("WAP_CLONES", "/clones")), Path(os.environ.get("WAP_JOBS", "/jobs")))
    uvicorn.run(creer_app_runner(runner), host=hote, port=port, log_level="warning")
