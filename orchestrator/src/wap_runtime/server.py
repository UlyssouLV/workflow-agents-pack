"""Service HTTP du runtime (FastAPI) : `GET /health`, l’API du cockpit sous `/api/` et son front."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from wap_runtime import __version__
from wap_runtime.agents import etat_agents
from wap_runtime.cockpit import Cockpit
from wap_runtime.github import API_GITHUB, ClientGitHub
from wap_runtime.instance import chemin_instance
from wap_runtime.registry import RegistryErreur, chemin_registry


def _registry_par_defaut() -> Path:
    # Dans le conteneur, Compose monte l’instance en lecture seule sur `WAP_INSTANCE`.
    instance = os.environ.get("WAP_INSTANCE")
    return chemin_registry(Path(instance) if instance else chemin_instance(Path.home()))


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
) -> FastAPI:
    """Sans `jeton`, celui de `GH_TOKEN` (lu au démarrage : `env_file` de Compose).

    `front` : build Vite du cockpit (`WAP_COCKPIT` par défaut) ; absent, seules `/health` et
    `/api/` sont servies.
    `env` : d’où lire les tokens des agents (`secrets.env`, reçu par `env_file`).
    """
    jeton = jeton if jeton is not None else os.environ.get("GH_TOKEN") or None
    client = ClientGitHub(jeton, api_github, transport) if jeton else None
    agents = etat_agents(env)
    cockpit = Cockpit(registry or _registry_par_defaut(), client, horloge)
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
        return {**cockpit.liste(), "agents": agents}

    @app.get("/api/repos/{owner}/{name}")
    def repo(owner: str, name: str) -> dict:
        slug = f"{owner}/{name}"
        try:
            detail = cockpit.detail(slug)
        except RegistryErreur as erreur:
            raise HTTPException(500, str(erreur)) from erreur
        if detail is None:
            raise HTTPException(404, f"{slug} absent du registry : `sudo wap-runtime repo add {slug}`")
        return detail

    front = front or _front_par_defaut()
    if front is not None and (front / "index.html").is_file():
        _servir_front(app, front)
    return app


def _servir_front(app: FastAPI, front: Path) -> None:
    """Les routes du front rendent `index.html` ; le routage se fait dans le navigateur."""
    index = front / "index.html"

    @app.get("/", include_in_schema=False)
    def liste() -> FileResponse:
        return FileResponse(index)

    @app.get("/repos/{owner}/{name}", include_in_schema=False)
    def detail(owner: str, name: str) -> FileResponse:
        return FileResponse(index)

    if (front / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=front / "assets"), name="assets")


def servir(hote: str, port: int) -> None:
    uvicorn.run(creer_app(), host=hote, port=port, log_level="warning")
