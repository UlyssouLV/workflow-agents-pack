"""Codespace en direct, côté runner : le websocket `…/codespace/evenements` pousse, regroupés, les
changements des dossiers dépliés, du fichier ouvert et de l’en-tête (HEAD, ref courante).

Le runner tourne pour de vrai (uvicorn, dans un fil) sur le clone Git de `test_codespace`, avec la
vraie surveillance du disque ; le client est `websockets` (attentes bornées).
"""

import json
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

from test_codespace import clone, git, jobs  # noqa: F401 (fixtures)
from wap_runtime import codespace
from wap_runtime.runner import Runner, creer_app_runner
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
    yield f"ws://{hote}:{port}"
    serveur.should_exit = True
    fil.join(5)


@pytest.fixture
def session(adresse_runner, jobs):
    return Sessions(jobs).creer("o/r", 30, "claude", 'claude "/implement #30"', branche="v0.8.0-codespace")


def evenements(adresse_runner, session):
    return connect(f"{adresse_runner}/sessions/{session['id']}/codespace/evenements")


def abonner(ws, dossiers=("",), fichier=None) -> None:
    ws.send(json.dumps({"dossiers": list(dossiers), "fichier": fichier}))


def recevoir(ws, delai: float = 2) -> dict | None:
    """Le prochain message, ou `None` s’il n’en vient aucun dans le délai."""
    try:
        return json.loads(ws.recv(timeout=delai))
    except TimeoutError:
        return None


def apres(ws, changer) -> dict:
    """Le premier événement après `changer`, rejoué tant que la surveillance (re)démarre ; puis le
    calme revenu, plus rien en attente."""
    for _ in range(10):
        changer()
        if (evenement := recevoir(ws, 1)) is not None:
            while recevoir(ws, 0.8) is not None:
                pass
            return evenement
    raise AssertionError("aucun événement")


def ecrire(chemin: Path, texte: str = "x\n"):
    return lambda: chemin.write_text(texte)


def test_un_fichier_cree_dans_un_dossier_deplie_le_signale_avec_ses_parents(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])

        evenement = apres(ws, ecrire(clone / "src" / "neuf.py"))

    assert evenement == {"dossiers": ["", "src"], "fichier": False, "entete": False}


def test_supprimer_un_fichier_le_signale(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])
        apres(ws, ecrire(clone / "src" / "neuf.py"))

        evenement = apres(ws, lambda: (clone / "src" / "neuf.py").unlink(missing_ok=True))

    assert evenement["dossiers"] == ["", "src"]


def test_le_fichier_ouvert_modifie_le_signale(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, [""], fichier="src/app.py")

        evenement = apres(ws, ecrire(clone / "src" / "app.py", "print('au revoir')\n"))

    # `src` n’est pas déplié : le fichier ouvert, et la racine où `src` change de marqueur.
    assert evenement == {"dossiers": [""], "fichier": True, "entete": False}


def test_une_rafale_donne_un_seul_evenement(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])
        apres(ws, ecrire(clone / "src" / "pret.py"))

        for i in range(30):
            (clone / "src" / f"f{i}.py").write_text("x\n")
            time.sleep(0.005)

        assert recevoir(ws)["dossiers"] == ["", "src"]
        assert recevoir(ws, 1) is None


def test_un_dossier_non_deplie_n_est_pas_surveille(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])
        apres(ws, ecrire(clone / "src" / "pret.py"))

        (clone / "node_modules" / "paquet" / "autre.js").write_text("x\n")

        assert recevoir(ws, 1) is None


def test_un_nouvel_abonnement_remplace_le_precedent(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])
        apres(ws, ecrire(clone / "src" / "pret.py"))

        abonner(ws, ["", "node_modules"])
        evenement = apres(ws, ecrire(clone / "node_modules" / "neuf.js"))
        (clone / "src" / "plus_suivi.py").write_text("x\n")

        assert evenement["dossiers"] == ["", "node_modules"]
        assert recevoir(ws, 1) is None


def test_un_commit_signale_l_entete(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, [])
        compteur = iter(range(100))

        def commiter():
            git(clone, "commit", "--quiet", "--allow-empty", "-m", f"c{next(compteur)}")

        evenement = apres(ws, commiter)

    assert evenement["entete"] is True


def test_un_changement_de_branche_signale_l_entete_puis_suit_la_nouvelle_ref(adresse_runner, session, clone):
    with evenements(adresse_runner, session) as ws:
        abonner(ws, [])
        branches = iter(range(100))

        evenement = apres(ws, lambda: git(clone, "checkout", "--quiet", "-b", f"autre/b{next(branches)}"))
        assert evenement["entete"] is True

        compteur = iter(range(100))
        evenement = apres(ws, lambda: git(clone, "commit", "--quiet", "--allow-empty", "-m", f"c{next(compteur)}"))

    assert evenement["entete"] is True


def test_un_chemin_hors_du_clone_n_est_jamais_surveille(adresse_runner, session, clone, tmp_path):
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "..", str(dehors), "../.."], fichier="../../dehors/x")
        apres(ws, ecrire(clone / "pret.md"))

        (dehors / "x").write_text("x\n")

        assert recevoir(ws, 1) is None


def test_surveillance_indisponible_annoncee_puis_websocket_ferme(adresse_runner, session, monkeypatch):
    async def en_echec(*chemins, **options):
        raise OSError(28, "inotify watch limit reached")
        yield

    monkeypatch.setattr(codespace, "awatch", en_echec)
    with evenements(adresse_runner, session) as ws:
        abonner(ws, [""])

        assert recevoir(ws) == {"surveillance": "indisponible"}
        with pytest.raises(ConnectionClosed):
            ws.recv(timeout=2)


def test_fermer_le_websocket_arrete_la_surveillance(adresse_runner, session, monkeypatch):
    actives = []
    reelle = codespace.awatch

    async def comptee(*chemins, **options):
        actives.append(chemins)
        try:
            async for lot in reelle(*chemins, **options):
                yield lot
        finally:
            actives.remove(chemins)

    monkeypatch.setattr(codespace, "awatch", comptee)
    with evenements(adresse_runner, session) as ws:
        abonner(ws, ["", "src"])
        for _ in range(100):
            if actives:
                break
            time.sleep(0.02)
        assert actives

    for _ in range(250):
        if not actives:
            break
        time.sleep(0.02)
    assert not actives


def test_refuse_sur_une_session_close(adresse_runner, session, jobs):
    Sessions(jobs).clore(session["id"], 0)

    with pytest.raises(InvalidStatus):
        with evenements(adresse_runner, session):
            pass


def test_refuse_sur_une_session_inconnue(adresse_runner):
    with pytest.raises(InvalidStatus):
        with evenements(adresse_runner, {"id": "20261017-090000-abcdef"}):
            pass
