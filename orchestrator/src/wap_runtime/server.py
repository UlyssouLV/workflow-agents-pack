"""Service HTTP du runtime (FastAPI) : `GET /health`, l’API du cockpit sous `/api/` et son front.

Le terminal en direct d’une session (websocket `/api/sessions/{id}/terminal`) est relayé jusqu’au
runner (`wap_runtime.terminal`).
"""

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wap_runtime import __version__
from wap_runtime.agents import etat_agents
from wap_runtime.cockpit import Cockpit
from wap_runtime.enregistrement import CAST
from wap_runtime.eligibilite import lancements
from wap_runtime.github import API_GITHUB, ClientGitHub, GitHubErreur
from wap_runtime.instance import chemin_instance
from wap_runtime.pilote import stop_du_pilote, tourner
from wap_runtime.registry import AGENTS, RegistryErreur, chemin_registry, enregistrer, lire_registry
from wap_runtime.runner import (
    PORT_RUNNER,
    Choix,
    ClientRunner,
    CloneSale,
    Identite,
    RunnerErreur,
    SessionOuverte,
    SessionQuiTravaille,
    email_noreply,
)
from wap_runtime.sessions import OUVERTE, Sessions, publique
from wap_runtime.terminal import relayer_runner


class Lancement(BaseModel):
    repo: str
    agent: str
    branche: str
    # Réponse au clone sale (`409` avec `clone`) ; absente, un clone sale ne lance rien.
    choix: Choix | None = None


class PreferencePilote(BaseModel):
    pilote: bool
    agent: str


def _instance_par_defaut() -> Path:
    # Dans le conteneur, Compose monte l’instance (le runtime y écrit `repos.toml`).
    instance = os.environ.get("WAP_INSTANCE")
    return Path(instance) if instance else chemin_instance(Path.home())


def _runner_par_defaut() -> httpx.Client:
    # Réseau Compose interne à l’instance, port non publié (ADR 0004) : pas de TLS entre services.
    defaut = httpx.URL(scheme="http", host="runner", port=PORT_RUNNER)
    return httpx.Client(base_url=os.environ.get("WAP_RUNNER", defaut))


def _prefs_registry(chemin: Path) -> dict[str, dict]:
    """Toggle et agent préféré, relu hors cache GitHub de la liste."""
    return {r.slug.lower(): {"pilote": r.pilote, "agent": r.agent} for r in lire_registry(chemin)}


def _lien(session: dict) -> dict:
    vue = publique(session)
    return {
        "id": vue["id"],
        "url": f"/sessions/{vue['id']}",
        "repo": vue["repo"],
        "activite": vue["activite"],
    }


def _avec_url(session: dict) -> dict:
    """La session, avec l’adresse de sa page dans le cockpit."""
    return {**publique(session), "url": _lien(session)["url"]}


def _du_cockpit(entetes: Mapping[str, str], schema: str) -> bool:
    """Pas de CORS : seule une page servie par ce cockpit agit (requêtes d’action, websocket)."""
    http = {"ws": "http", "wss": "https"}.get(schema, schema)
    return entetes.get("origin") == f"{http}://{entetes.get('host')}"


def _verifier_origine(requete: Request) -> None:
    if not _du_cockpit(requete.headers, requete.url.scheme):
        raise HTTPException(403, "origine refusée : agis depuis le cockpit")


def _front_par_defaut() -> Path | None:
    # Dans l’image, le build Vite du cockpit est copié sur `WAP_COCKPIT`.
    dossier = os.environ.get("WAP_COCKPIT")
    return Path(dossier) if dossier else None


def creer_app(
    registry: Path | None = None,
    jeton: str | None = None,
    api_github: str = API_GITHUB,
    transport: httpx.BaseTransport | None = None,
    horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    front: Path | None = None,
    env: Mapping[str, str] = os.environ,
    jobs: Path | None = None,
    runner: httpx.Client | None = None,
    boucle_pilote: bool = False,
    intervalle_pilote: float = 15,
) -> FastAPI:
    """Sans `jeton`, celui de `GH_TOKEN` (lu au démarrage : `env_file` de Compose).

    `front` : build Vite du cockpit (`WAP_COCKPIT` par défaut) ; absent, seules `/health` et
    `/api/` sont servies.
    `env` : d’où lire les tokens des agents (`secrets.env`, reçu par `env_file`).
    `jobs` : sessions écrites par le runner (défaut : à côté du registry) ; `runner` : son API
    interne (`WAP_RUNNER`).
    `boucle_pilote` : démarre la surveillance (session libre + `/implement #n`) ; `servir()` l’active.
    """
    jeton = jeton if jeton is not None else os.environ.get("GH_TOKEN") or None
    client = ClientGitHub(jeton, api_github, transport) if jeton else None
    agents = etat_agents(env)
    registry = registry or chemin_registry(_instance_par_defaut())
    cockpit = Cockpit(registry, client, horloge)
    # `repos.toml` et `jobs/` vivent tous deux à la racine de l’instance.
    sessions = Sessions(jobs or registry.parent / "jobs")
    client_runner = ClientRunner(runner or _runner_par_defaut())
    echecs_pilote: dict[str, bool] = {}

    def _stop(slug: str, detail: dict | None) -> str | None:
        lie = next((r for r in lire_registry(registry) if r.designe(slug)), None)
        if lie is None:
            return None
        ouverte = sessions.ouverte(lie.slug)
        derniere = next(iter(sessions.du_repo(lie.slug)), None)
        return stop_du_pilote(
            lie, detail, ouverte, derniere, agents, echecs_pilote.get(lie.slug.lower(), False)
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        stop = threading.Event()

        def boucle() -> None:
            while not stop.is_set():
                try:
                    tourner(
                        registry, cockpit, sessions, client_runner, agents, client, echecs_pilote
                    )
                except Exception:
                    # Un tour raté ne tue pas la surveillance.
                    pass
                stop.wait(intervalle_pilote)

        if boucle_pilote:
            fil = threading.Thread(target=boucle, daemon=True)
            fil.start()
        yield
        stop.set()

    app = FastAPI(title="wap-runtime", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/auth")
    def auth() -> dict:
        return cockpit.auth()

    @app.get("/api/agents")
    def agents_() -> dict:
        return {"agents": agents}

    @app.get("/api/repos")
    def repos() -> dict:
        liste = cockpit.liste()
        # Badge « Session en cours » : au plus une session ouverte par repo.
        ouvertes = {s["repo"].lower(): _lien(s) for s in sessions.toutes() if s["etat"] == OUVERTE}
        prefs = _prefs_registry(registry) if liste["erreur"] is None else {}
        repos_ = [
            {
                **r,
                "session": ouvertes.get(r["slug"].lower()),
                **prefs.get(r["slug"].lower(), {}),
                "pilote_stop": _stop(r["slug"], r),
            }
            for r in liste["repos"]
        ]
        return {**liste, "repos": repos_, "agents": agents}

    @app.get("/api/repos/{owner}/{name}")
    def repo(owner: str, name: str) -> dict:
        slug = f"{owner}/{name}"
        ouverte = sessions.ouverte(slug)
        detail = lancements(_detail(slug), ouverte, agents)
        return {
            **detail,
            "agents": agents,
            "session": ouverte and _lien(ouverte),
            "pilote_stop": _stop(slug, detail),
        }

    @app.patch("/api/repos/{owner}/{name}")
    def pilote(owner: str, name: str, demande: PreferencePilote, requete: Request) -> dict:
        _verifier_origine(requete)
        slug = f"{owner}/{name}"
        _detail(slug)
        if demande.agent not in AGENTS:
            raise HTTPException(422, f"agent inconnu : {demande.agent}")
        try:
            repo = enregistrer(registry, slug, demande.pilote, demande.agent)
        except RegistryErreur as erreur:
            raise HTTPException(500, str(erreur)) from erreur
        except OSError as erreur:
            raise HTTPException(500, f"écriture de {registry} impossible ({erreur})") from erreur
        return {"pilote": repo.pilote, "agent": repo.agent}

    @app.get("/api/repos/{owner}/{name}/sessions")
    def sessions_du_repo(owner: str, name: str) -> dict:
        """Sans GitHub : celles de `jobs/`, y compris d’un repo retiré du registry."""
        return {"sessions": [_avec_url(s) for s in sessions.du_repo(f"{owner}/{name}")]}

    def _detail(slug: str) -> dict:
        try:
            detail = cockpit.detail(slug)
        except RegistryErreur as erreur:
            raise HTTPException(500, str(erreur)) from erreur
        if detail is None:
            raise HTTPException(404, f"{slug} absent du registry : `sudo wap-runtime repo add {slug}`")
        return detail

    @app.get("/api/sessions")
    def toutes_les_sessions() -> dict:
        """Toutes les sessions de l’instance, de la plus récente à la plus ancienne."""
        return {"sessions": [_avec_url(s) for s in sessions.toutes()]}

    @app.get("/api/sessions/{id_}")
    def session(id_: str) -> dict:
        lue = sessions.lire(id_)
        if lue is None:
            raise HTTPException(404, f"session {id_} inconnue")
        return _avec_url(lue)

    @app.get("/api/sessions/{id_}/terminal.cast")
    def cast(id_: str) -> FileResponse:
        """Le terminal enregistré (asciinema v2), en cours d’écriture si la session est ouverte."""
        if sessions.lire(id_) is None or not (chemin := sessions.jobs / id_ / CAST).is_file():
            raise HTTPException(404, f"aucun enregistrement pour la session {id_}")
        return FileResponse(chemin, media_type="application/x-asciicast")

    @app.post("/api/sessions", status_code=201, response_model=None)
    def lancer(demande: Lancement, requete: Request) -> dict | JSONResponse:
        _verifier_origine(requete)
        agent = next((a for a in agents if a["id"] == demande.agent), None)
        if agent is None:
            raise HTTPException(422, f"agent inconnu : {demande.agent}")
        if not agent["connecte"]:
            raise HTTPException(422, "agent non connecté")
        if (ouverte := sessions.ouverte(demande.repo)) is not None:
            return _deja_ouverte(ouverte)
        if (autre := sessions.qui_travaille(sauf=demande.repo)) is not None:
            return _session_qui_travaille(autre)
        detail = _detail(demande.repo)
        if detail["erreur"]:
            raise HTTPException(502, detail["erreur"])
        if demande.branche not in detail["branches"]["proposees"]:
            raise HTTPException(422, f"branche {demande.branche} non proposée")
        try:
            compte = client.utilisateur()
            identite = Identite(compte["login"], email_noreply(compte["login"], compte["id"]))
            lancee = client_runner.lancer(
                detail["slug"], None, demande.agent, demande.branche, identite, demande.choix
            )
        except GitHubErreur as erreur:
            raise HTTPException(502, str(erreur)) from erreur
        except SessionOuverte as refus:
            return _deja_ouverte(refus.session)
        except SessionQuiTravaille as refus:
            return _session_qui_travaille(refus.session)
        except CloneSale as refus:
            return JSONResponse(refus.corps(), status_code=409)
        except RunnerErreur as erreur:
            raise HTTPException(422, str(erreur)) from erreur
        return _avec_url(lancee)

    @app.post("/api/sessions/{id_}/terminer")
    def terminer(id_: str, requete: Request) -> dict:
        """**Terminer** : l’agent est arrêté, la session rendue avec son état final."""
        _verifier_origine(requete)
        if sessions.lire(id_) is None:
            raise HTTPException(404, f"session {id_} inconnue")
        try:
            close = client_runner.terminer(id_)
        except RunnerErreur as erreur:
            raise HTTPException(502, str(erreur)) from erreur
        return _avec_url(close)

    @app.websocket("/api/sessions/{id_}/terminal")
    async def terminal(websocket: WebSocket, id_: str) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import WebSocketException

        lue = sessions.lire(id_)
        # Fermer avant `accept` refuse la poignée de main (403).
        if not _du_cockpit(websocket.headers, websocket.url.scheme) or lue is None or lue["etat"] != OUVERTE:
            await websocket.close()
            return
        try:
            amont = await connect(client_runner.url_terminal(id_), max_size=None)
        except (OSError, TimeoutError, WebSocketException):
            await websocket.close()
            return
        async with amont:
            await websocket.accept()
            await relayer_runner(websocket, amont)

    front = front or _front_par_defaut()
    if front is not None and (front / "index.html").is_file():
        _servir_front(app, front)
    return app


def _deja_ouverte(session: dict) -> JSONResponse:
    lien = _lien(session)
    return JSONResponse(
        {"detail": f"une session est déjà ouverte : {lien['url']}", "session": lien}, status_code=409
    )


def _session_qui_travaille(session: dict) -> JSONResponse:
    lien = _lien(session)
    return JSONResponse(
        {
            "detail": f"une session travaille sur {lien['repo']} : {lien['url']}",
            "session": lien,
        },
        status_code=409,
    )


def _servir_front(app: FastAPI, front: Path) -> None:
    """Les routes du front rendent `index.html` ; le routage se fait dans le navigateur."""
    index = front / "index.html"

    @app.get("/", include_in_schema=False)
    def liste() -> FileResponse:
        return FileResponse(index)

    @app.get("/repos/{owner}/{name}", include_in_schema=False)
    def detail(owner: str, name: str) -> FileResponse:
        return FileResponse(index)

    @app.get("/sessions", include_in_schema=False)
    def sessions_page() -> FileResponse:
        return FileResponse(index)

    @app.get("/sessions/{id_}", include_in_schema=False)
    def session(id_: str) -> FileResponse:
        return FileResponse(index)

    if (front / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=front / "assets"), name="assets")


def servir(hote: str, port: int) -> None:
    uvicorn.run(creer_app(boucle_pilote=True), host=hote, port=port, log_level="warning")
