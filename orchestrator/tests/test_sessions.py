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


@pytest.fixture
def faux_claude(tmp_path, monkeypatch):
    """`faux_claude(code)` : un `claude` dans le `PATH` qui exécute ce code Python ; l’exécuteur
    le lance avec les arguments de la session."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")

    def ecrire(code: str) -> None:
        chemin = bin_ / "claude"
        chemin.write_text(f"#!{sys.executable}\n{code}\n")
        chemin.chmod(0o755)

    return ecrire


def executeur(tmp_path, session) -> list[str]:
    return [sys.executable, "-m", "wap_runtime.sessions", str(tmp_path / "jobs"), session["id"]]


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
        "precedente": None,
        "suivante": None,
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
def test_l_executeur_lance_la_commande_puis_clot_la_session(sessions, tmp_path, faux_claude, code, etat):
    session = creer(sessions)
    faux_claude(f"import sys; sys.exit({code})")

    sortie = subprocess.run(
        executeur(tmp_path, session),
        stdin=subprocess.DEVNULL,
    ).returncode

    assert sortie == code
    close = sessions.lire(session["id"])
    assert (close["etat"], close["code_sortie"]) == (etat, code)
    assert close["fin"] is not None


def test_l_executeur_lance_l_agent_de_la_session_sur_son_ticket(sessions, tmp_path, faux_claude):
    """La commande se déduit de `session.json` : l’exécuteur ne prend pas d’arguments d’agent."""
    session = sessions.creer("o/r", 42, "claude", 'claude "/implement #42"')
    recu = tmp_path / "recu"
    faux_claude(f"import json, pathlib, sys; pathlib.Path({str(recu)!r}).write_text(json.dumps(sys.argv[1:]))")

    subprocess.run(executeur(tmp_path, session), stdin=subprocess.DEVNULL, check=True)

    assert json.loads(recu.read_text()) == ["/implement #42"]


@pytest.mark.parametrize("id_", ["../x", "20261017-090000-zzzzzz"])
def test_l_executeur_refuse_une_session_invalide_ou_inconnue(tmp_path, id_):
    sortie = subprocess.run(
        [sys.executable, "-m", "wap_runtime.sessions", str(tmp_path / "jobs"), id_],
        stdin=subprocess.DEVNULL, capture_output=True,
    )

    assert sortie.returncode != 0


def test_une_session_close_garde_son_etat_final(sessions, horloge):
    session = creer(sessions)
    close = sessions.clore(session["id"], 129)
    horloge.maintenant = DEBUT + timedelta(minutes=5)

    assert sessions.clore(session["id"], 0) == close
    assert sessions.lire(session["id"]) == close


def test_sighup_arrete_l_agent_et_l_executeur_clot_la_session(sessions, tmp_path, faux_claude):
    """**Terminer** : la session tmux se ferme, l’exécuteur et l’agent reçoivent SIGHUP."""
    session = creer(sessions)
    pret = tmp_path / "pret"
    faux_claude(f"import pathlib, time; pathlib.Path({str(pret)!r}).touch(); time.sleep(30)")
    processus = subprocess.Popen(
        executeur(tmp_path, session),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
    )
    while not pret.exists():
        time.sleep(0.02)

    os.killpg(processus.pid, signal.SIGHUP)

    assert processus.wait(timeout=10) == 129
    close = sessions.lire(session["id"])
    assert (close["etat"], close["code_sortie"]) == ("échouée", 129)


def test_l_executeur_enregistre_le_terminal_de_l_agent(sessions, tmp_path, faux_claude):
    """L’agent écrit dans un vrai terminal ; ce qu’il affiche va aussi dans `terminal.cast`."""
    session = creer(sessions)
    faux_claude("import os, sys; print('tty' if os.isatty(1) else 'pas de tty'); print('fini é')")

    sortie = subprocess.run(
        executeur(tmp_path, session),
        stdin=subprocess.DEVNULL, capture_output=True,
    )

    assert sortie.returncode == 0
    assert b"fini \xc3\xa9" in sortie.stdout
    entete, *evenements = (
        json.loads(l) for l in (tmp_path / "jobs" / session["id"] / "terminal.cast").read_text().splitlines()
    )
    assert entete["version"] == 2
    ecran = "".join(e[2] for e in evenements if e[1] == "o")
    assert "tty\r\nfini é" in ecran


def test_l_executeur_copie_la_transcription_avant_de_clore(tmp_path, faux_claude):
    # Horloge réelle : seuls les fichiers écrits depuis le début de la session sont copiés.
    session = creer(Sessions(tmp_path / "jobs"))
    home = tmp_path / "home"
    faux_claude(
        "import pathlib; p = pathlib.Path.home() / '.claude/projects/-c/s.jsonl';"
        "p.parent.mkdir(parents=True); p.write_text('{}')"
    )

    subprocess.run(
        executeur(tmp_path, session),
        stdin=subprocess.DEVNULL, env={**os.environ, "HOME": str(home)}, check=True,
    )

    assert (tmp_path / "jobs" / session["id"] / "transcription" / "-c" / "s.jsonl").read_text() == "{}"


def test_interrompre_les_sessions_restees_ouvertes(sessions, horloge):
    close = creer(sessions)
    sessions.clore(close["id"], 0)
    horloge.maintenant = DEBUT + timedelta(minutes=1)
    ouverte = creer(sessions)
    horloge.maintenant = DEBUT + timedelta(minutes=9)

    sessions.interrompre()

    interrompue = sessions.lire(ouverte["id"])
    assert (interrompue["etat"], interrompue["code_sortie"]) == ("interrompue", None)
    assert interrompue["fin"] == (DEBUT + timedelta(minutes=9)).isoformat()
    assert sessions.lire(close["id"])["etat"] == "terminée"
    assert sessions.ouverte() is None
    # L’exécuteur d’avant le redémarrage ne la rouvre pas.
    assert sessions.clore(ouverte["id"], 0) == interrompue


def test_sessions_d_un_repo_de_la_plus_recente_a_la_plus_ancienne(sessions, horloge):
    premiere = creer(sessions)
    horloge.maintenant = DEBUT + timedelta(hours=1)
    creer(sessions, repo="o/autre")
    horloge.maintenant = DEBUT + timedelta(hours=2)
    seconde = creer(sessions, repo="O/R")

    assert [s["id"] for s in sessions.du_repo("o/r")] == [seconde["id"], premiere["id"]]
