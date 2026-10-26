"""Codespace côté cockpit : le `runtime` relaie au runner les lectures du codespace d’une session,
derrière l’authentification du cockpit, et sert la route front de l’onglet.

Le runner tourne pour de vrai (uvicorn, dans un fil) sur le clone Git de `test_codespace`.
"""

import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from client_cockpit import avec_session
from test_codespace import clone, jobs  # noqa: F401 (fixtures)
from wap_runtime.registry import ajouter
from wap_runtime.runner import Runner, creer_app_runner
from wap_runtime.server import creer_app
from wap_runtime.sessions import Sessions


@pytest.fixture
def adresse_runner(tmp_path, jobs, clone):
    runner = Runner(tmp_path / "clones", jobs)
    serveur = uvicorn.Server(uvicorn.Config(creer_app_runner(runner), host="127.0.0.1", port=0, log_level="warning"))
    fil = threading.Thread(target=serveur.run, daemon=True)
    fil.start()
    while not serveur.started:
        time.sleep(0.01)
    hote, port = serveur.servers[0].sockets[0].getsockname()[:2]
    yield f"http://{hote}:{port}"
    serveur.should_exit = True
    fil.join(5)


def app(tmp_path, jobs, adresse_runner):
    registry = tmp_path / "repos.toml"
    ajouter(registry, "o/r", None)
    return creer_app(registry=registry, jeton="x", env={}, jobs=jobs, runner=httpx.Client(base_url=adresse_runner))


@pytest.fixture
def api(tmp_path, jobs, adresse_runner):
    with avec_session(app(tmp_path, jobs, adresse_runner), tmp_path) as client:
        yield client


@pytest.fixture
def session(adresse_runner, jobs):
    return Sessions(jobs).creer("o/r", 30, "claude", 'claude "/implement #30"', branche="v0.8.0-codespace")


def test_identite_relayee(api, session):
    reponse = api.get(f"/api/sessions/{session['id']}/codespace")

    assert reponse.status_code == 200
    assert reponse.json()["repo"] == "o/r"
    assert reponse.json()["source"] == "direct"


def test_arbre_et_fichier_relayes(api, session):
    arbre = api.get(f"/api/sessions/{session['id']}/codespace/arbre", params={"chemin": "src"})
    fichier = api.get(f"/api/sessions/{session['id']}/codespace/fichier", params={"chemin": "src/app.py"})

    assert [e["nom"] for e in arbre.json()["entrees"]] == ["app.py"]
    assert fichier.json()["contenu"] == "print('bonjour')\n"


def test_statuts_et_diff_relayes(api, session, clone):
    (clone / "src" / "app.py").write_text("print('au revoir')\n")

    arbre = api.get(f"/api/sessions/{session['id']}/codespace/arbre", params={"chemin": ""})
    diff = api.get(f"/api/sessions/{session['id']}/codespace/diff", params={"chemin": "src/app.py"})

    assert {e["nom"]: e["statut"] for e in arbre.json()["entrees"]}["src"] == "modifie"
    assert diff.json() == {"chemin": "src/app.py", "head": "print('bonjour')\n", "courant": "print('au revoir')\n"}


@pytest.mark.parametrize("suite, chemin, code", [
    ("/arbre", "..", 400), ("/fichier", "/etc/passwd", 400), ("/fichier", "absent", 404),
    ("/diff", "../..", 400), ("/diff", "absent", 404),
])
def test_refus_du_runner_relayes_avec_leur_message(api, session, suite, chemin, code):
    reponse = api.get(f"/api/sessions/{session['id']}/codespace{suite}", params={"chemin": chemin})

    assert reponse.status_code == code
    assert reponse.json()["detail"]


def test_session_inconnue_404(api):
    assert api.get("/api/sessions/20261017-090000-abcdef/codespace").status_code == 404


@pytest.mark.parametrize("suite", ["", "/arbre", "/fichier?chemin=README.md", "/diff?chemin=README.md"])
def test_routes_refusees_sans_authentification_cockpit(tmp_path, jobs, adresse_runner, session, suite):
    client = TestClient(app(tmp_path, jobs, adresse_runner))

    reponse = client.get(f"/api/sessions/{session['id']}/codespace{suite}")

    assert reponse.status_code == 401
    assert "README" not in reponse.text


def test_runner_injoignable_502(tmp_path, jobs, session):
    registry = tmp_path / "repos.toml"
    injoignable = httpx.Client(base_url="http://127.0.0.1:9")
    client = avec_session(creer_app(registry=registry, jeton="x", env={}, jobs=jobs, runner=injoignable), tmp_path)

    assert client.get(f"/api/sessions/{session['id']}/codespace").status_code == 502
