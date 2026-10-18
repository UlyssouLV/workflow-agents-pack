"""Garde HTTP + login / logout : session cookie, refus sans session, rate-limit (ADR 0010, #91)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wap_runtime.identifiants_cockpit import definir, creer_session, session_valide
from wap_runtime.server import creer_app

LOGIN = "ops"
MOT_DE_PASSE = "s3cret-ops"
COOKIE = "wap_cockpit_session"


@pytest.fixture
def instance(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def app(instance):
    return creer_app(registry=instance / "repos.toml", jeton="")


def client(app) -> TestClient:
    return TestClient(app)


def preparer(instance: Path) -> None:
    definir(instance, LOGIN, MOT_DE_PASSE)


def test_health_reste_accessible_sans_session_et_sans_secrets(app, instance):
    preparer(instance)
    reponse = client(app).get("/health")

    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok", "version": reponse.json()["version"]}
    assert "password" not in reponse.text.lower()
    assert "login" not in reponse.json()
    assert COOKIE not in reponse.cookies


def test_api_protegee_refuse_sans_session(app, instance):
    preparer(instance)
    reponse = client(app).get("/api/repos")

    assert reponse.status_code == 401
    assert "repos" not in reponse.json()


def test_login_etablit_une_session_httponly_puis_autorise_l_api(app, instance):
    preparer(instance)
    c = client(app)

    reponse = c.post("/api/cockpit/login", json={"login": LOGIN, "password": MOT_DE_PASSE})

    assert reponse.status_code == 204
    morsure = reponse.cookies.get(COOKIE)
    assert morsure
    assert session_valide(instance, morsure) is True
    # httpOnly : le Set-Cookie le déclare (TestClient expose le cookie, pas le flag JS).
    set_cookie = reponse.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()

    assert c.get("/api/repos").status_code == 200


def test_logout_invalide_la_session_et_refuse_ensuite(app, instance):
    preparer(instance)
    c = client(app)
    c.post("/api/cockpit/login", json={"login": LOGIN, "password": MOT_DE_PASSE})
    id_session = c.cookies.get(COOKIE)

    reponse = c.post("/api/cockpit/logout")

    assert reponse.status_code == 204
    assert session_valide(instance, id_session) is False
    assert c.get("/api/repos").status_code == 401


def test_changement_de_mot_de_passe_coupe_la_session_http(app, instance):
    preparer(instance)
    c = client(app)
    c.post("/api/cockpit/login", json={"login": LOGIN, "password": MOT_DE_PASSE})
    assert c.get("/api/repos").status_code == 200

    definir(instance, LOGIN, "nouveau-mdp")

    assert c.get("/api/repos").status_code == 401


def test_login_rate_limite_apres_echecs(app, instance):
    preparer(instance)
    c = client(app)

    for _ in range(5):
        mauvais = c.post("/api/cockpit/login", json={"login": LOGIN, "password": "mauvais"})
        assert mauvais.status_code == 401

    verrouille = c.post("/api/cockpit/login", json={"login": LOGIN, "password": MOT_DE_PASSE})
    assert verrouille.status_code == 429

    # Même le bon mot de passe reste refusé pendant le verrouillage.
    assert c.get("/api/repos").status_code == 401


def test_surface_login_et_assets_restent_publics(app, instance, tmp_path):
    preparer(instance)
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=\"racine\"></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    app_front = creer_app(registry=instance / "repos.toml", jeton="", front=dist)
    c = client(app_front)

    assert c.get("/login").status_code == 200
    assert c.get("/assets/app.js").status_code == 200
    assert c.get("/").status_code == 401


def test_session_injectee_autorise_sur_loopback(app, instance):
    """Auth aussi sur 127.0.0.1 : pas d’exception localhost."""
    preparer(instance)
    id_ = creer_session(instance)
    c = client(app)
    c.cookies.set(COOKIE, id_)

    assert c.get("/api/repos").status_code == 200
