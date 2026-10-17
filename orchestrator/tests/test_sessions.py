"""Sessions de l’instance : `jobs/<id>/session.json`, et sa clôture selon le code de sortie."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

from wap_runtime.sessions import Sessions

DEBUT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


class Horloge:
    def __init__(self):
        self.maintenant = DEBUT

    def __call__(self):
        return self.maintenant


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def sessions(tmp_path, horloge):
    return Sessions(tmp_path / "jobs", horloge)


def creer(sessions, repo="o/r", ticket=30):
    return sessions.creer(repo, ticket, "claude", 'claude "/implement #30"')


def test_creer_ecrit_session_json_ouverte(sessions, tmp_path):
    session = creer(sessions)

    sur_disque = json.loads((tmp_path / "jobs" / session["id"] / "session.json").read_text())
    assert sur_disque == session
    assert session == {
        "id": session["id"],
        "repo": "o/r",
        "ticket": 30,
        "agent": "claude",
        "commande": 'claude "/implement #30"',
        "debut": DEBUT.isoformat(),
        "fin": None,
        "etat": "ouverte",
        "code_sortie": None,
    }


def test_ouverte_rend_la_session_ouverte_de_l_instance(sessions):
    assert sessions.ouverte() is None
    session = creer(sessions)

    assert sessions.ouverte() == session


@pytest.mark.parametrize("code, etat", [(0, "terminée"), (3, "échouée")])
def test_clore_selon_le_code_de_sortie(sessions, horloge, code, etat):
    session = creer(sessions)
    horloge.maintenant = DEBUT + timedelta(minutes=5)

    close = sessions.clore(session["id"], code)

    assert close["etat"] == etat
    assert close["code_sortie"] == code
    assert close["fin"] == (DEBUT + timedelta(minutes=5)).isoformat()
    assert sessions.lire(session["id"]) == close
    assert sessions.ouverte() is None


def test_toutes_les_sessions_de_la_plus_recente_a_la_plus_ancienne(sessions, horloge):
    premiere = creer(sessions)
    sessions.clore(premiere["id"], 0)
    horloge.maintenant = DEBUT + timedelta(hours=1)
    seconde = creer(sessions, repo="o/autre")

    assert [s["id"] for s in sessions.toutes()] == [seconde["id"], premiere["id"]]


@pytest.mark.parametrize("id_", ["inconnue", "../etc", "a/b"])
def test_lire_une_session_inconnue_ou_hors_de_jobs(sessions, id_):
    creer(sessions)

    assert sessions.lire(id_) is None


def test_jobs_absent_aucune_session(tmp_path, horloge):
    assert Sessions(tmp_path / "absent", horloge).toutes() == []


@pytest.mark.parametrize("code, etat", [(0, "terminée"), (2, "échouée")])
def test_l_executeur_lance_la_commande_puis_clot_la_session(sessions, tmp_path, code, etat):
    session = creer(sessions)

    sortie = subprocess.run(
        [sys.executable, "-m", "wap_runtime.sessions", str(tmp_path / "jobs"), session["id"],
         sys.executable, "-c", f"import sys; sys.exit({code})"],
    ).returncode

    assert sortie == code
    close = sessions.lire(session["id"])
    assert (close["etat"], close["code_sortie"]) == (etat, code)
    assert close["fin"] is not None


def test_une_session_close_garde_son_etat_final(sessions, horloge):
    session = creer(sessions)
    close = sessions.clore(session["id"], 129)
    horloge.maintenant = DEBUT + timedelta(minutes=5)

    assert sessions.clore(session["id"], 0) == close
    assert sessions.lire(session["id"]) == close


def test_sighup_arrete_l_agent_et_l_executeur_clot_la_session(sessions, tmp_path):
    """**Terminer** : la session tmux se ferme, l’exécuteur et l’agent reçoivent SIGHUP."""
    session = creer(sessions)
    pret = tmp_path / "pret"
    agent = f"import pathlib, time; pathlib.Path({str(pret)!r}).touch(); time.sleep(30)"
    executeur = subprocess.Popen(
        [sys.executable, "-m", "wap_runtime.sessions", str(tmp_path / "jobs"), session["id"],
         sys.executable, "-c", agent],
        start_new_session=True,
    )
    while not pret.exists():
        time.sleep(0.02)

    os.killpg(executeur.pid, signal.SIGHUP)

    assert executeur.wait(timeout=10) == 129
    close = sessions.lire(session["id"])
    assert (close["etat"], close["code_sortie"]) == ("échouée", 129)
