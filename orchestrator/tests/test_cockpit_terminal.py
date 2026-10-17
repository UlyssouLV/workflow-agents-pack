"""Terminal en direct, côté cockpit : le `runtime` relaie le websocket du navigateur jusqu’au
runner, refuse toute autre origine que le cockpit et relaie **Terminer**.

Le runner tourne pour de vrai (uvicorn, dans un fil) avec le faux `tmux` et la fausse CLI de
`test_terminal`.
"""

import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from test_terminal import attendre, etat_tmux, jobs, jusqu_a_la_fermeture, prendre, role, runner, taper  # noqa: F401 (fixtures)
from wap_runtime.registry import ajouter
from wap_runtime.runner import Identite, creer_app_runner
from wap_runtime.server import creer_app
from wap_runtime.sessions import Sessions

COCKPIT = "http://testserver"


@pytest.fixture
def adresse_runner(runner):
    serveur = uvicorn.Server(uvicorn.Config(creer_app_runner(runner), host="127.0.0.1", port=0, log_level="warning"))
    fil = threading.Thread(target=serveur.run, daemon=True)
    fil.start()
    while not serveur.started:
        time.sleep(0.01)
    hote, port = serveur.servers[0].sockets[0].getsockname()[:2]
    yield f"http://{hote}:{port}"
    serveur.should_exit = True
    fil.join(5)


@pytest.fixture
def api(tmp_path, jobs, adresse_runner):
    registry = tmp_path / "repos.toml"
    ajouter(registry, "o/r", None)
    app = creer_app(registry=registry, jeton="x", env={}, jobs=jobs, runner=httpx.Client(base_url=adresse_runner))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def session(runner):
    return runner.lancer("o/r", 30, "claude", "v0.4.0", Identite("octocat", "e"))


def terminal(api, session, origine=COCKPIT):
    entetes = {"Origin": origine} if origine else {}
    return api.websocket_connect(f"/api/sessions/{session['id']}/terminal", headers=entetes)


def test_le_runtime_relaie_sortie_et_saisie_jusqu_au_runner(api, session):
    with terminal(api, session) as ws:
        assert role(ws) == "ecriture"
        attendre(ws, "claude prêt : /implement #30")

        taper(ws, "/implement #32\r")

        attendre(ws, "reçu : /implement #32")


def test_deuxieme_onglet_en_lecture_seule_a_travers_le_runtime(api, session, etat_tmux):
    with terminal(api, session) as premier, terminal(api, session) as second:
        assert (role(premier), role(second)) == ("ecriture", "lecture")
        attendre(second, "prêt")

        taper(second, "intrus\r")
        taper(premier, "ami\r")

        attendre(second, "reçu : ami")
    assert "intrus" not in (etat_tmux / f"wap-{session['id']}" / "sortie").read_text()


def test_un_onglet_en_lecture_prend_la_main_a_travers_le_runtime(api, session):
    with terminal(api, session) as premier, terminal(api, session) as second:
        assert (role(premier), role(second)) == ("ecriture", "lecture")
        attendre(second, "prêt")

        prendre(second)

        assert (role(second), role(premier)) == ("ecriture", "lecture")
        taper(second, "repris\r")
        attendre(premier, "reçu : repris")


def test_fermer_l_onglet_garde_la_session_et_revenir_rend_l_ecran(api, session, jobs):
    with terminal(api, session) as ws:
        role(ws)
        attendre(ws, "prêt")
        taper(ws, "avant\r")
        attendre(ws, "reçu : avant")

    assert Sessions(jobs).lire(session["id"])["etat"] == "ouverte"
    with terminal(api, session) as ws:
        # Le runner a pu ne pas avoir encore vu partir l’ancien onglet : la main suit.
        if role(ws) != "ecriture":
            assert role(ws) == "ecriture"
        attendre(ws, "reçu : avant")
        taper(ws, "après\r")
        attendre(ws, "reçu : après")


@pytest.mark.parametrize("origine", [None, "http://evil.example", "http://testserver:9999"])
def test_websocket_refuse_hors_origine_du_cockpit(api, session, etat_tmux, origine):
    with pytest.raises(WebSocketDisconnect):
        with terminal(api, session, origine=origine) as ws:
            ws.receive_json()

    assert not [a for a in (etat_tmux / "appels.log").read_text().splitlines() if "attach-session" in a]


def test_websocket_refuse_sur_une_session_inconnue(api):
    with pytest.raises(WebSocketDisconnect):
        with api.websocket_connect("/api/sessions/20261017-090000-abcdef/terminal", headers={"Origin": COCKPIT}) as ws:
            ws.receive_json()


def test_terminer_arrete_l_agent_et_rend_la_session_close(api, session):
    with terminal(api, session) as ws:
        role(ws)
        attendre(ws, "prêt")

        reponse = api.post(f"/api/sessions/{session['id']}/terminer", headers={"Origin": COCKPIT})

        assert reponse.status_code == 200
        close = reponse.json()
        assert (close["etat"], close["code_sortie"]) == ("échouée", 129)
        assert close["url"] == f"/sessions/{session['id']}"
        jusqu_a_la_fermeture(ws)


@pytest.mark.parametrize("origine", [None, "http://evil.example"])
def test_terminer_refuse_hors_origine_du_cockpit(api, session, jobs, origine):
    entetes = {"Origin": origine} if origine else {}

    reponse = api.post(f"/api/sessions/{session['id']}/terminer", headers=entetes)

    assert reponse.status_code == 403
    assert Sessions(jobs).lire(session["id"])["etat"] == "ouverte"


def test_terminer_session_inconnue_404(api):
    reponse = api.post("/api/sessions/20261017-090000-abcdef/terminer", headers={"Origin": COCKPIT})

    assert reponse.status_code == 404
