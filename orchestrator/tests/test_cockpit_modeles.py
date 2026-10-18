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
