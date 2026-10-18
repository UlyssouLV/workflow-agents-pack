"""Liste des modèles Cursor : `GET /api/modeles` depuis `agent models` (spec 0.5.1)."""

import os
from pathlib import Path

from fastapi.testclient import TestClient

from wap_runtime.server import creer_app

CONNECTE = {"CURSOR_API_KEY": "key_x"}


def api(tmp_path: Path, env: dict) -> TestClient:
    return TestClient(creer_app(registry=tmp_path / "repos.toml", jeton="", env=env))


def faux_agent(tmp_path: Path, monkeypatch, script: str) -> dict:
    """`agent models` de test sur le PATH, avec le token Cursor transmis à `creer_app`."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    chemin = bin_ / "agent"
    chemin.write_text(f"#!/bin/sh\n{script}\n")
    chemin.chmod(0o755)
    path = f"{bin_}{os.pathsep}{os.environ.get('PATH', '')}"
    monkeypatch.setenv("PATH", path)
    env = {**CONNECTE, "PATH": path, "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()
    return env


def test_sans_cursor_connecte_aucune_liste_n_est_servie(tmp_path):
    reponse = api(tmp_path, {}).get("/api/modeles")

    assert reponse.status_code == 422
    assert reponse.json() == {"detail": "Cursor non connecté"}


def test_cursor_connecte_renvoie_auto_et_les_modeles_de_la_cli(tmp_path, monkeypatch):
    env = faux_agent(tmp_path, monkeypatch, "printf 'composer-2\\ngrok-4.6\\n'")

    reponse = api(tmp_path, env).get("/api/modeles")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "modeles": [
            {"id": None, "libelle": "Auto"},
            {"id": "composer-2", "libelle": "composer-2"},
            {"id": "grok-4.6", "libelle": "grok-4.6"},
        ]
    }


def test_sortie_cli_reelle_ignore_en_tete_et_auto(tmp_path, monkeypatch):
    """`agent models` réel : en-tête, `auto - …`, puis `id - libellé`."""
    script = (
        "printf '%s\\n' "
        "'Available models' "
        "'auto - Auto (current, default)' "
        "'composer-2.5 - Composer 2.5' "
        "'grok-4.7-high - Grok 4.7 High'"
    )
    env = faux_agent(tmp_path, monkeypatch, script)

    reponse = api(tmp_path, env).get("/api/modeles")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "modeles": [
            {"id": None, "libelle": "Auto"},
            {"id": "composer-2.5", "libelle": "composer-2.5"},
            {"id": "grok-4.7-high", "libelle": "grok-4.7-high"},
        ]
    }


def test_echec_de_la_cli_renvoie_une_erreur_explicite_sans_inventer_de_liste(
    tmp_path, monkeypatch
):
    env = faux_agent(tmp_path, monkeypatch, "printf 'composer-2\\n'; echo 'quota exceeded' >&2; exit 1")

    reponse = api(tmp_path, env).get("/api/modeles")

    assert reponse.status_code == 503
    assert reponse.json() == {
        "detail": "liste des modèles Cursor indisponible : quota exceeded"
    }


def test_sortie_cli_vide_n_invente_pas_de_liste(tmp_path, monkeypatch):
    env = faux_agent(tmp_path, monkeypatch, "exit 0")

    reponse = api(tmp_path, env).get("/api/modeles")

    assert reponse.status_code == 503
    assert reponse.json() == {
        "detail": "liste des modèles Cursor indisponible : aucun modèle dans sa sortie"
    }


def test_agent_introuvable_est_une_erreur_explicite(tmp_path, monkeypatch):
    vide = tmp_path / "vide"
    vide.mkdir()
    monkeypatch.setenv("PATH", str(vide))
    env = {**CONNECTE, "PATH": str(vide), "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()

    reponse = api(tmp_path, env).get("/api/modeles")

    assert reponse.status_code == 503
    assert reponse.json() == {
        "detail": "liste des modèles Cursor indisponible : agent introuvable"
    }


def test_api_interne_runner_sert_la_liste_des_modeles(tmp_path, monkeypatch):
    """Le runner expose `GET /modeles` (l’image runtime n’a pas `agent`)."""
    from wap_runtime.runner import creer_app_runner

    faux_agent(tmp_path, monkeypatch, "printf 'composer-2\\n'")
    monkeypatch.setenv("CURSOR_API_KEY", "key_x")

    reponse = TestClient(creer_app_runner(object())).get("/modeles")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "modeles": [
            {"id": None, "libelle": "Auto"},
            {"id": "composer-2", "libelle": "composer-2"},
        ]
    }


def test_avec_wap_runner_la_liste_vient_du_runner(tmp_path, monkeypatch):
    """En Compose, `agent` est dans le runner : le runtime délègue `GET /modeles`."""
    import httpx

    attendu = {
        "modeles": [
            {"id": None, "libelle": "Auto"},
            {"id": "composer-2", "libelle": "composer-2"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/modeles"
        return httpx.Response(200, json=attendu)

    monkeypatch.setenv("WAP_RUNNER", "http://runner-test")
    client_http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://runner-test"
    )

    reponse = TestClient(
        creer_app(registry=tmp_path / "repos.toml", jeton="", env=CONNECTE, runner=client_http)
    ).get("/api/modeles")

    assert reponse.status_code == 200
    assert reponse.json() == attendu


def test_avec_wap_runner_une_liste_ko_est_propagee(tmp_path, monkeypatch):
    """Le runtime relais le 503 du runner, sans inventer de liste locale."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/modeles"
        return httpx.Response(503, json={"detail": "liste des modèles Cursor indisponible : quota exceeded"})

    monkeypatch.setenv("WAP_RUNNER", "http://runner-test")
    client_http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://runner-test"
    )

    reponse = TestClient(
        creer_app(registry=tmp_path / "repos.toml", jeton="", env=CONNECTE, runner=client_http)
    ).get("/api/modeles")

    assert reponse.status_code == 503
    assert reponse.json() == {
        "detail": "liste des modèles Cursor indisponible : quota exceeded"
    }
