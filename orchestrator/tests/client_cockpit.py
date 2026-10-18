"""Client HTTP de test déjà authentifié sur l’instance (garde #91)."""

from pathlib import Path

from fastapi.testclient import TestClient

from wap_runtime.garde_http import NOM_COOKIE
from wap_runtime.identifiants_cockpit import creer_session, definir, est_configure

LOGIN_TEST = "ops"
MDP_TEST = "test-cockpit-mdp"


def avec_session(app, instance: Path) -> TestClient:
    """Pose des identifiants cockpit (une fois) et un cookie de session valide."""
    if not est_configure(instance):
        definir(instance, LOGIN_TEST, MDP_TEST)
    client = TestClient(app)
    client.cookies.set(NOM_COOKIE, creer_session(instance))
    return client
