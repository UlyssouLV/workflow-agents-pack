"""Garde HTTP du cockpit : session serveur, login / logout, rate-limit (ADR 0010)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp

from wap_runtime.identifiants_cockpit import (
    DUREE_SESSION,
    creer_session_serveur,
    instant_utc,
    session_serveur_valide,
    supprimer_session_serveur,
    verifier,
)

NOM_COOKIE = "wap_cockpit_session"
MAX_ECHEC = 5
DUREE_VERROU = timedelta(minutes=5)


class IdentifiantsLogin(BaseModel):
    login: str
    password: str


class LimiteurLogin:
    """Compteur d’échecs par clé (IP) ; verrouillage temporaire après `MAX_ECHEC`."""

    def __init__(self) -> None:
        self._echecs: dict[str, int] = {}
        self._verrou_jusqu_a: dict[str, datetime] = {}

    def est_verrouille(self, cle: str, *, maintenant: datetime | None = None) -> bool:
        maintenant = instant_utc(maintenant)
        jusqu_a = self._verrou_jusqu_a.get(cle)
        if jusqu_a is None:
            return False
        if maintenant < jusqu_a:
            return True
        self._verrou_jusqu_a.pop(cle, None)
        self._echecs.pop(cle, None)
        return False

    def noter_echec(self, cle: str, *, maintenant: datetime | None = None) -> None:
        maintenant = instant_utc(maintenant)
        n = self._echecs.get(cle, 0) + 1
        self._echecs[cle] = n
        if n >= MAX_ECHEC:
            self._verrou_jusqu_a[cle] = maintenant + DUREE_VERROU

    def reussite(self, cle: str) -> None:
        self._echecs.pop(cle, None)
        self._verrou_jusqu_a.pop(cle, None)


def est_public(chemin: str, methode: str) -> bool:
    """Routes sans session serveur : health, surface login + assets, login API."""
    if chemin == "/health" and methode == "GET":
        return True
    if chemin == "/login" and methode == "GET":
        return True
    if chemin.startswith("/assets/"):
        return True
    if chemin == "/api/cockpit/login" and methode == "POST":
        return True
    return False


def cle_client(requete: Request) -> str:
    if requete.client is None:
        return "inconnu"
    return requete.client.host


def session_du_cookie(requete: Request) -> str:
    return requete.cookies.get(NOM_COOKIE) or ""


def requete_https(requete: Request) -> bool:
    """HTTPS direct ou derrière reverse proxy (`X-Forwarded-Proto`)."""
    if requete.url.scheme == "https":
        return True
    forwarded = requete.headers.get("x-forwarded-proto", "")
    return forwarded.split(",")[0].strip().lower() == "https"


def poser_cookie_session(reponse: Response, id_session: str, *, secure: bool) -> None:
    reponse.set_cookie(
        NOM_COOKIE,
        id_session,
        httponly=True,
        samesite="lax",
        max_age=int(DUREE_SESSION.total_seconds()),
        path="/",
        secure=secure,
    )


def effacer_cookie_session(reponse: Response) -> None:
    reponse.delete_cookie(NOM_COOKIE, path="/")


def connecter(
    instance: Path,
    limiteur: LimiteurLogin,
    requete: Request,
    demande: IdentifiantsLogin,
    reponse: Response,
) -> None:
    cle = cle_client(requete)
    if limiteur.est_verrouille(cle):
        raise HTTPException(429, "trop de tentatives de connexion")
    if not verifier(instance, demande.login, demande.password):
        limiteur.noter_echec(cle)
        raise HTTPException(401, "identifiants invalides")
    limiteur.reussite(cle)
    id_ = creer_session_serveur(instance)
    poser_cookie_session(reponse, id_, secure=requete_https(requete))


def deconnecter(instance: Path, requete: Request, reponse: Response) -> None:
    id_ = session_du_cookie(requete)
    if id_:
        supprimer_session_serveur(instance, id_)
    effacer_cookie_session(reponse)


class GardeSessionServeur(BaseHTTPMiddleware):
    """Refuse toute requête non publique sans session serveur valide."""

    def __init__(self, app: ASGIApp, instance: Path) -> None:
        super().__init__(app)
        self._instance = instance

    async def dispatch(self, request: Request, call_next):
        if est_public(request.url.path, request.method):
            return await call_next(request)
        id_ = session_du_cookie(request)
        if not session_serveur_valide(self._instance, id_):
            # API : 401 JSON ; pages HTML du cockpit : redirection vers la surface de login.
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "authentification requise"}, status_code=401)
            return RedirectResponse(url="/login", status_code=302)
        return await call_next(request)
