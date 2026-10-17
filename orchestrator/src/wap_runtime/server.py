"""Service HTTP du runtime (FastAPI) : `GET /health`, l’API du cockpit sous `/api/` et son front."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wap_runtime import __version__
from wap_runtime.agents import etat_agents
from wap_runtime.cockpit import Cockpit
from wap_runtime.eligibilite import lancements, raison_grisee
from wap_runtime.github import API_GITHUB, ClientGitHub, GitHubErreur
from wap_runtime.instance import chemin_instance
from wap_runtime.registry import RegistryErreur, chemin_registry
from wap_runtime.runner import (
    PORT_RUNNER,
    ClientRunner,
    Identite,
    RunnerErreur,
    SessionOuverte,
    email_noreply,
)
from wap_runtime.sessions import Sessions


class Lancement(BaseModel):
    repo: str
    ticket: int
    agent: str


def _instance_par_defaut() -> Path:
    # Dans le conteneur, Compose monte l’instance en lecture seule sur `WAP_INSTANCE`.
    instance = os.environ.get("WAP_INSTANCE")
    return Path(instance) if instance else chemin_instance(Path.home())


def _runner_par_defaut() -> httpx.Client:
    return httpx.Client(base_url=os.environ.get("WAP_RUNNER", f"http://runner:{PORT_RUNNER}"))


def _lien(session: dict) -> dict:
    return {"id": session["id"], "url": f"/sessions/{session['id']}", "repo": session["repo"]}


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
) -> FastAPI:
    """Sans `jeton`, celui de `GH_TOKEN` (lu au démarrage : `env_file` de Compose).

    `front` : build Vite du cockpit (`WAP_COCKPIT` par défaut) ; absent, seules `/health` et
    `/api/` sont servies.
    `env` : d’où lire les tokens des agents (`secrets.env`, reçu par `env_file`).
    `jobs` : sessions écrites par le runner (défaut : à côté du registry) ; `runner` : son API
    interne (`WAP_RUNNER`).
    """
    jeton = jeton if jeton is not None else os.environ.get("GH_TOKEN") or None
    client = ClientGitHub(jeton, api_github, transport) if jeton else None
    agents = etat_agents(env)
    registry = registry or chemin_registry(_instance_par_defaut())
    cockpit = Cockpit(registry, client, horloge)
    # `repos.toml` et `jobs/` vivent tous deux à la racine de l’instance.
    sessions = Sessions(jobs or registry.parent / "jobs")
    client_runner = ClientRunner(runner or _runner_par_defaut())
    app = FastAPI(title="wap-runtime", version=__version__, docs_url=None, redoc_url=None)

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
        ouverte = sessions.ouverte()
        # Badge « Session en cours » : la session ouverte de l’instance, sur son repo.
        sur = ouverte["repo"].lower() if ouverte else None
        repos_ = [
            {**r, "session": _lien(ouverte) if r["slug"].lower() == sur else None}
            for r in liste["repos"]
        ]
        return {**liste, "repos": repos_, "agents": agents}

    @app.get("/api/repos/{owner}/{name}")
    def repo(owner: str, name: str) -> dict:
        ouverte = sessions.ouverte()
        detail = lancements(_detail(f"{owner}/{name}"), ouverte, agents)
        return {**detail, "agents": agents, "session": ouverte and _lien(ouverte)}

    def _detail(slug: str) -> dict:
        try:
            detail = cockpit.detail(slug)
        except RegistryErreur as erreur:
            raise HTTPException(500, str(erreur)) from erreur
        if detail is None:
            raise HTTPException(404, f"{slug} absent du registry : `sudo wap-runtime repo add {slug}`")
        return detail

    @app.get("/api/sessions/{id_}")
    def session(id_: str) -> dict:
        lue = sessions.lire(id_)
        if lue is None:
            raise HTTPException(404, f"session {id_} inconnue")
        return {**lue, "url": _lien(lue)["url"]}

    @app.post("/api/sessions", status_code=201, response_model=None)
    def lancer(demande: Lancement, requete: Request) -> dict | JSONResponse:
        # Pas de CORS : seule une page servie par ce cockpit peut lancer une session.
        if requete.headers.get("origin") != f"{requete.url.scheme}://{requete.headers.get('host')}":
            raise HTTPException(403, "origine refusée : lance la session depuis le cockpit")
        agent = next((a for a in agents if a["id"] == demande.agent), None)
        if agent is None:
            raise HTTPException(422, f"agent inconnu : {demande.agent}")
        if (ouverte := sessions.ouverte()) is not None:
            return _deja_ouverte(ouverte)
        detail = _detail(demande.repo)
        if detail["erreur"]:
            raise HTTPException(502, detail["erreur"])
        trouve = next(
            ((e, v["pr"]) for v in detail["versions"] for e in v["enfants"] if e["numero"] == demande.ticket),
            None,
        )
        if trouve is None:
            raise HTTPException(404, f"#{demande.ticket} n’est l’enfant d’aucune version ouverte")
        enfant, pr = trouve
        if raison := raison_grisee(enfant, pr, None, agent["connecte"]):
            raise HTTPException(422, raison)
        try:
            compte = client.utilisateur()
            identite = Identite(compte["login"], email_noreply(compte["login"], compte["id"]))
            lancee = client_runner.lancer(detail["slug"], demande.ticket, demande.agent, pr["branche"], identite)
        except GitHubErreur as erreur:
            raise HTTPException(502, str(erreur)) from erreur
        except SessionOuverte as refus:
            return _deja_ouverte(refus.session)
        except RunnerErreur as erreur:
            raise HTTPException(422, str(erreur)) from erreur
        return {**lancee, "url": _lien(lancee)["url"]}

    front = front or _front_par_defaut()
    if front is not None and (front / "index.html").is_file():
        _servir_front(app, front)
    return app


def _deja_ouverte(session: dict) -> JSONResponse:
    lien = _lien(session)
    return JSONResponse(
        {"detail": f"une session est déjà ouverte : {lien['url']}", "session": lien}, status_code=409
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

    @app.get("/sessions/{id_}", include_in_schema=False)
    def session(id_: str) -> FileResponse:
        return FileResponse(index)

    if (front / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=front / "assets"), name="assets")


def servir(hote: str, port: int) -> None:
    uvicorn.run(creer_app(), host=hote, port=port, log_level="warning")
