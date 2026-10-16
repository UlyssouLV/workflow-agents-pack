"""Service HTTP du runtime (FastAPI) : `GET /health` et l’API du cockpit sous `/api/`."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
import uvicorn
from fastapi import FastAPI

from wap_runtime import __version__
from wap_runtime.cockpit import Cockpit
from wap_runtime.github import API_GITHUB, ClientGitHub
from wap_runtime.instance import chemin_instance
from wap_runtime.registry import chemin_registry


def _registry_par_defaut() -> Path:
    # Dans le conteneur, Compose monte l’instance en lecture seule sur `WAP_INSTANCE`.
    instance = os.environ.get("WAP_INSTANCE")
    return chemin_registry(Path(instance) if instance else chemin_instance(Path.home()))


def creer_app(
    registry: Path | None = None,
    jeton: str | None = None,
    api_github: str = API_GITHUB,
    transport: httpx.BaseTransport | None = None,
    horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> FastAPI:
    """Sans `jeton`, celui de `GH_TOKEN` (lu au démarrage : `env_file` de Compose)."""
    jeton = jeton if jeton is not None else os.environ.get("GH_TOKEN") or None
    client = ClientGitHub(jeton, api_github, transport) if jeton else None
    cockpit = Cockpit(registry or _registry_par_defaut(), client, horloge)
    app = FastAPI(title="wap-runtime", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/auth")
    def auth() -> dict:
        return cockpit.auth()

    @app.get("/api/repos")
    def repos() -> dict:
        return cockpit.liste()

    return app


def servir(hote: str, port: int) -> None:
    uvicorn.run(creer_app(), host=hote, port=port, log_level="warning")
