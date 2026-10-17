"""Terminal en direct, côté runner : websocket ↔ `tmux attach` dans un pseudo-terminal, Terminer.

`tmux` est le faux multiplexeur de `faux_tmux` ; l’agent est une fausse CLI interactive qui
répète chaque ligne reçue. Le clone n’est pas préparé : la session tourne dans `tmp_path`.
"""

import fcntl
import json
import os
import struct
import subprocess
import termios

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import faux_tmux
from wap_runtime.runner import Identite, Runner, creer_app_runner
from wap_runtime.sessions import Sessions
from wap_runtime.terminal import Pty

FAUSSE_CLI = """#!/bin/sh
echo "$(basename "$0") prêt : $*"
while IFS= read -r ligne; do
  echo "reçu : $ligne"
  [ "$ligne" = "/exit" ] && exit 0
done
"""


@pytest.fixture
def etat_tmux(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    faux_tmux.installer(bin_, tmp_path / "tmux")
    for agent in ("claude", "agent"):
        (bin_ / agent).write_text(FAUSSE_CLI)
        (bin_ / agent).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    yield tmp_path / "tmux"
    faux_tmux.tout_arreter(tmp_path / "tmux")


@pytest.fixture
def jobs(tmp_path):
    return tmp_path / "jobs"


@pytest.fixture
def runner(tmp_path, jobs, etat_tmux, monkeypatch):
    runner = Runner(tmp_path / "clones", jobs)
    monkeypatch.setattr(runner, "recuperer_clone", lambda *_: tmp_path)
    monkeypatch.setattr(runner, "positionner_clone", lambda *_, **__: None)
    return runner


@pytest.fixture
def client(runner):
    with TestClient(creer_app_runner(runner)) as client:
        yield client


@pytest.fixture
def session(runner):
    return runner.lancer("o/r", 30, "claude", "v0.4.0", Identite("octocat", "e"))


def terminal(client, session):
    return client.websocket_connect(f"/sessions/{session['id']}/terminal")


def recevoir(ws) -> dict:
    message = ws.receive()
    if message["type"] == "websocket.close":
        raise WebSocketDisconnect(message.get("code", 1000))
    return message


def role(ws) -> str:
    """Prochain rôle annoncé ; la sortie reçue avant est ignorée."""
    while (message := recevoir(ws)).get("text") is None:
        pass
    return json.loads(message["text"])["role"]


def attendre(ws, texte: str) -> str:
    """Sortie du terminal reçue jusqu’à contenir `texte` ; les messages de rôle sont ignorés."""
    sortie = b""
    while texte not in (ecran := sortie.decode(errors="replace")):
        sortie += recevoir(ws).get("bytes") or b""
    return ecran


def jusqu_a_la_fermeture(ws) -> None:
    with pytest.raises(WebSocketDisconnect):
        while True:
            recevoir(ws)


def taper(ws, texte: str) -> None:
    ws.send_text(json.dumps({"saisie": texte}))


def pret(client, session) -> None:
    """L’agent a démarré (sa première ligne est à l’écran)."""
    with terminal(client, session) as ws:
        role(ws)
        attendre(ws, "prêt")


def tmux_tourne(session) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", f"wap-{session['id']}"]).returncode == 0


def appels(etat_tmux) -> list[str]:
    return (etat_tmux / "appels.log").read_text().splitlines()


def test_le_terminal_relaie_la_sortie_et_la_saisie(client, session):
    with terminal(client, session) as ws:
        assert role(ws) == "ecriture"
        attendre(ws, "claude prêt : /implement #30")

        taper(ws, "/clear\r")

        attendre(ws, "reçu : /clear")


def test_le_deuxieme_client_est_en_lecture_seule(client, session, etat_tmux):
    with terminal(client, session) as premier, terminal(client, session) as second:
        assert (role(premier), role(second)) == ("ecriture", "lecture")
        attendre(second, "prêt")

        taper(second, "intrus\r")
        taper(premier, "ami\r")

        attendre(second, "reçu : ami")
    sortie = (etat_tmux / f"wap-{session['id']}" / "sortie").read_text()
    assert "intrus" not in sortie
    attaches = [a for a in appels(etat_tmux) if a.startswith("tmux attach-session")]
    assert attaches == [
        f"tmux attach-session -t wap-{session['id']}",
        f"tmux attach-session -f read-only,ignore-size -t wap-{session['id']}",
    ]


def test_le_depart_de_celui_qui_ecrit_donne_la_main_au_suivant(client, session, etat_tmux):
    with terminal(client, session) as premier, terminal(client, session) as second:
        assert (role(premier), role(second)) == ("ecriture", "lecture")
        attendre(second, "prêt")

        premier.close()

        assert role(second) == "ecriture"
        taper(second, "relève\r")
        attendre(second, "reçu : relève")
    attaches = [a for a in appels(etat_tmux) if a.startswith("tmux attach-session")]
    assert attaches[-1] == f"tmux attach-session -t wap-{session['id']}"


def test_deconnexion_garde_la_session_et_la_reconnexion_rend_l_ecran(client, session, jobs, etat_tmux):
    with terminal(client, session) as ws:
        role(ws)
        attendre(ws, "prêt")
        taper(ws, "avant\r")
        attendre(ws, "reçu : avant")

    assert Sessions(jobs).lire(session["id"])["etat"] == "ouverte"
    assert tmux_tourne(session)

    with terminal(client, session) as ws:
        assert role(ws) == "ecriture"
        assert "reçu : avant" in attendre(ws, "reçu : avant")


def test_la_fin_de_l_agent_ferme_le_terminal(client, session, jobs):
    with terminal(client, session) as ws:
        role(ws)
        attendre(ws, "prêt")
        taper(ws, "/exit\r")
        attendre(ws, "reçu : /exit")

        jusqu_a_la_fermeture(ws)

    assert Sessions(jobs).lire(session["id"])["etat"] == "terminée"


def test_terminer_arrete_l_agent_et_clot_la_session(client, session, etat_tmux):
    with terminal(client, session) as ws:
        role(ws)
        attendre(ws, "prêt")

        reponse = client.post(f"/sessions/{session['id']}/terminer")

        assert reponse.status_code == 200
        close = reponse.json()
        assert (close["etat"], close["code_sortie"]) == ("échouée", 129)
        assert close["fin"] is not None
        jusqu_a_la_fermeture(ws)
    assert not tmux_tourne(session)


def test_terminer_une_session_close_la_rend_telle_quelle(client, session):
    pret(client, session)
    premiere = client.post(f"/sessions/{session['id']}/terminer").json()

    assert client.post(f"/sessions/{session['id']}/terminer").json() == premiere


def test_terminer_session_inconnue_404(client):
    assert client.post("/sessions/20261017-090000-abcdef/terminer").status_code == 404


def test_terminer_force_la_cloture_si_l_agent_ne_s_arrete_pas(tmp_path, jobs):
    """tmux déjà parti (ou agent sourd à SIGHUP) : la session ne reste pas ouverte."""
    runner = Runner(tmp_path / "clones", jobs, arreteur=lambda nom: None, attente=0)
    ouverte = Sessions(jobs).creer("o/r", 30, "claude", 'claude "/implement #30"')

    close = runner.terminer(ouverte["id"])

    assert (close["etat"], close["code_sortie"]) == ("échouée", 129)


def test_terminal_refuse_sur_une_session_close(client, session):
    pret(client, session)
    client.post(f"/sessions/{session['id']}/terminer")

    with pytest.raises(WebSocketDisconnect):
        with terminal(client, session) as ws:
            ws.receive_json()


def test_terminal_refuse_sur_une_session_inconnue(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/pas-un-id/terminal") as ws:
            ws.receive_json()


def test_la_taille_du_pseudo_terminal_suit_le_client(tmp_path):
    pty = Pty(["sleep", "5"])
    try:
        pty.redimensionner(132, 40)

        lignes, colonnes, *_ = struct.unpack("HHHH", fcntl.ioctl(pty.maitre, termios.TIOCGWINSZ, b"\0" * 8))
        assert (colonnes, lignes) == (132, 40)
    finally:
        pty.fermer()
