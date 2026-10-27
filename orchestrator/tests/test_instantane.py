"""Instantané de fin de session (ADR 0014) : pris à la fermeture sans rien changer au clone, puis
relu par le codespace d’une session close.

Le clone est un vrai dépôt Git sous `clones/o/r`, avec un `origin` nu ; les sessions sont écrites
dans `jobs/` sans lancer d’agent.
"""

import hashlib
import json
import subprocess
import threading
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from wap_runtime.runner import Runner, creer_app_runner
from wap_runtime.sessions import Sessions

BRANCHE = "v0.8.0-codespace"
FIN = datetime(2026, 10, 26, 15, 30, tzinfo=timezone.utc)


def git(dossier, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(dossier), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--quiet", "--bare", str(origin))
    dossier = tmp_path / "clones" / "o" / "r"
    dossier.mkdir(parents=True)
    git(dossier, "init", "--quiet", "-b", BRANCHE)
    git(dossier, "config", "user.name", "t")
    git(dossier, "config", "user.email", "t@t")
    git(dossier, "remote", "add", "origin", str(origin))
    (dossier / ".gitignore").write_text("node_modules/\n.env\n__pycache__/\n")
    (dossier / "README.md").write_text("# r\n")
    (dossier / "src").mkdir()
    (dossier / "src" / "app.py").write_text("print('bonjour')\n")
    (dossier / "src" / "vieux.py").write_text("x = 0\n")
    git(dossier, "add", ".")
    git(dossier, "commit", "--quiet", "-m", "init")
    git(dossier, "push", "--quiet", "origin", BRANCHE)
    return dossier


def salir(clone) -> None:
    """Ce qu’un agent laisse : un fichier modifié, un ajouté, un non suivi, un supprimé, et des ignorés."""
    (clone / "README.md").write_text("# r modifié\n")
    (clone / "src" / "ajout.py").write_text("a = 1\n")
    git(clone, "add", "src/ajout.py")
    (clone / "docs").mkdir()
    (clone / "docs" / "notes.md").write_text("brouillon\n")
    (clone / "src" / "brouillon.py").write_text("b = 2\n")
    (clone / "src" / "vieux.py").unlink()
    (clone / "node_modules" / "paquet").mkdir(parents=True)
    (clone / "node_modules" / "paquet" / "index.js").write_text("module.exports = 1;\n")
    (clone / ".env").write_text("SECRET=1\n")
    (clone / "src" / "__pycache__").mkdir()
    (clone / "src" / "__pycache__" / "app.pyc").write_bytes(b"\0")


@pytest.fixture
def jobs(tmp_path):
    return tmp_path / "jobs"


@pytest.fixture
def sessions(tmp_path, jobs):
    return Sessions(jobs, lambda: FIN, clones=tmp_path / "clones")


@pytest.fixture
def session(sessions, clone):
    return sessions.creer("o/r", 30, "claude", 'claude "/implement #30"', branche=BRANCHE)


def instantane(jobs, session) -> dict:
    return json.loads((jobs / session["id"] / "instantane.json").read_text())


def etat_du_clone(clone) -> dict:
    """Tout ce que la prise ne doit pas changer."""
    return {
        "status": git(clone, "status", "--porcelain=v2", "--ignored", "--branch"),
        "index": hashlib.sha256((clone / ".git" / "index").read_bytes()).hexdigest(),
        "branche": git(clone, "symbolic-ref", "HEAD"),
        "head": git(clone, "rev-parse", "HEAD"),
        "readme": (clone / "README.md").read_text(),
        "branches": git(clone, "for-each-ref", "refs/heads", "refs/remotes"),
    }


@pytest.mark.parametrize("code, etat", [(0, "terminée"), (1, "échouée")])
def test_instantane_pris_a_la_fermeture(sessions, session, clone, jobs, code, etat):
    salir(clone)
    head = git(clone, "rev-parse", "HEAD")

    close = sessions.clore(session["id"], code)

    assert close["etat"] == etat
    lu = instantane(jobs, session)
    sha = git(clone, "rev-parse", f"refs/wap/sessions/{session['id']}")
    assert lu == {
        "sha": sha,
        "head": head,
        "branche": BRANCHE,
        "pris_le": FIN.isoformat(),
        "ignores": {"": [".env", "node_modules/"], "src": ["__pycache__/"]},
        "non_suivis": ["docs/", "src/brouillon.py"],
    }
    assert git(clone, "rev-parse", f"{sha}^") == head
    fichiers = git(clone, "ls-tree", "-r", "--name-only", sha).splitlines()
    assert sorted(fichiers) == [".gitignore", "README.md", "docs/notes.md", "src/ajout.py", "src/app.py", "src/brouillon.py"]
    assert git(clone, "show", f"{sha}:README.md") == "# r modifié"


def test_instantane_pris_a_l_arret(sessions, session, clone, jobs):
    """**Terminer** : la session passe `arrêtée` et laisse son instantané, comme les autres fins."""
    salir(clone)

    sessions.demander_arret(session["id"])
    close = sessions.clore(session["id"], 129)

    assert close["etat"] == "arrêtée"
    assert instantane(jobs, session)["sha"] == git(clone, "rev-parse", f"refs/wap/sessions/{session['id']}")


def test_terminer_pendant_une_prise_lente_attend_la_cloture_en_cours(sessions, session, clone, jobs, monkeypatch):
    """**Terminer** clôt après son délai pendant que l’exécuteur prend encore l’instantané : une seule
    prise, et la session garde l’état de la première clôture."""
    from wap_runtime import instantane as module

    prendre, prises, commencee = module.prendre, [], threading.Event()

    def lente(*args):
        prises.append(args)
        commencee.set()
        time.sleep(0.3)
        return prendre(*args)

    monkeypatch.setattr(module, "prendre", lente)
    sessions.demander_arret(session["id"])
    executeur = threading.Thread(target=sessions.clore, args=(session["id"], 129))
    executeur.start()
    commencee.wait(5)

    close = sessions.clore(session["id"], 129)
    executeur.join()

    assert len(prises) == 1
    assert close == Sessions(jobs).lire(session["id"])
    assert close["etat"] == "arrêtée"
    assert instantane(jobs, session)["sha"] == git(clone, "rev-parse", f"refs/wap/sessions/{session['id']}")


def test_la_prise_ne_change_ni_arbre_ni_index_ni_branche_ni_distant(sessions, session, clone):
    salir(clone)
    avant = etat_du_clone(clone)

    sessions.clore(session["id"], 0)
    git(clone, "push", "--quiet", "origin", BRANCHE)

    assert etat_du_clone(clone) == avant
    assert "refs/wap/" not in git(clone, "ls-remote", "origin")


def test_instantane_pris_a_l_interruption(tmp_path, jobs, session, clone):
    salir(clone)

    Runner(tmp_path / "clones", jobs)

    assert Sessions(jobs).lire(session["id"])["etat"] == "interrompue"
    assert instantane(jobs, session)["sha"] == git(clone, "rev-parse", f"refs/wap/sessions/{session['id']}")


def test_une_session_enchainee_a_son_propre_instantane(sessions, session, clone, jobs):
    (clone / "src" / "app.py").write_text("print('ticket 30')\n")
    git(clone, "commit", "--quiet", "-am", "ticket 30")
    suivante = sessions.creer("o/r", 31, "claude", 'claude "/implement #31"', session["id"], BRANCHE)

    sessions.enchainer(session["id"], suivante["id"])
    (clone / "src" / "app.py").write_text("print('ticket 31')\n")
    sessions.clore(suivante["id"], 0)

    premier, second = instantane(jobs, session), instantane(jobs, suivante)
    assert premier["sha"] != second["sha"]
    assert git(clone, "show", f"{premier['sha']}:src/app.py") == "print('ticket 30')"
    assert git(clone, "show", f"{second['sha']}:src/app.py") == "print('ticket 31')"


def test_clone_sans_commit_instantane_sans_parent(sessions, tmp_path, jobs):
    vide = tmp_path / "clones" / "o" / "vide"
    vide.mkdir(parents=True)
    git(vide, "init", "--quiet", "-b", "main")
    (vide / "neuf.py").write_text("x = 1\n")
    session = sessions.creer("o/vide", None, "claude", "claude", branche="main")

    sessions.clore(session["id"], 0)

    lu = instantane(jobs, session)
    assert (lu["head"], lu["branche"]) == (None, "main")
    assert git(vide, "rev-list", "--count", lu["sha"]) == "1"
    assert git(vide, "status", "--porcelain") == "?? neuf.py"


def bloquer_la_ref(clone, session) -> None:
    """Un dossier non vide à la place de la ref : `update-ref` échoue."""
    dossier = clone / ".git" / "refs" / "wap" / "sessions" / session["id"]
    dossier.mkdir(parents=True)
    (dossier / "x").write_text("bloque\n")


def test_un_echec_de_la_prise_est_note_et_la_session_se_ferme(sessions, session, clone, jobs):
    bloquer_la_ref(clone, session)

    close = sessions.clore(session["id"], 0)

    assert close["etat"] == "terminée"
    lu = instantane(jobs, session)
    assert lu["pris_le"] == FIN.isoformat()
    assert lu["erreur"]


def test_clone_absent_echec_note(sessions, jobs, clone):
    autre = sessions.creer("o/absent", None, "claude", "claude", branche="main")

    assert sessions.clore(autre["id"], 0)["etat"] == "terminée"
    assert "erreur" in instantane(jobs, autre)


# Relecture : le codespace d’une session close.


@pytest.fixture
def client(tmp_path, jobs, clone):
    runner = Runner(tmp_path / "clones", jobs)
    with TestClient(creer_app_runner(runner)) as client:
        yield client


@pytest.fixture
def close(client, sessions, session, clone):
    """Session close sur un clone sali, puis le clone qui passe à autre chose (« jeter »)."""
    salir(clone)
    sessions.clore(session["id"], 0)
    git(clone, "reset", "--quiet", "--hard")
    git(clone, "clean", "--quiet", "-fd")
    (clone / "src" / "app.py").write_text("print('session suivante')\n")
    git(clone, "commit", "--quiet", "-am", "suite")
    return session


def codespace(client, session, suite="", **params):
    return client.get(f"/sessions/{session['id']}/codespace{suite}", params=params)


def entrees(client, session, chemin="") -> dict:
    reponse = codespace(client, session, "/arbre", chemin=chemin)
    assert reponse.status_code == 200, reponse.text
    return {e["nom"]: e for e in reponse.json()["entrees"]}


def test_identite_d_une_session_close_depuis_l_instantane(client, close, clone, jobs):
    head = instantane(jobs, close)["head"]

    reponse = codespace(client, close)

    assert reponse.status_code == 200
    assert reponse.json() == {
        "repo": "o/r",
        "branche": BRANCHE,
        "head": head[:7],
        "source": "instantane",
        "instantane": {"etat": "present", "pris_le": FIN.isoformat()},
    }


def test_arbre_de_l_instantane_avec_marqueurs_et_non_conserves(client, close):
    racine = entrees(client, close)
    src = entrees(client, close, "src")

    assert list(racine) == [".git", "docs", "node_modules", "src", ".env", ".gitignore", "README.md"]
    assert racine["README.md"] == {
        "nom": "README.md", "type": "fichier", "taille": len("# r modifié\n".encode()),
        "statut": "modifie", "ignore": False, "non_conserve": False,
    }
    assert racine["docs"]["statut"] == "non_suivi"
    assert racine["src"]["statut"] == "modifie"
    assert src["ajout.py"]["statut"] == "ajoute"
    assert src["brouillon.py"]["statut"] == "non_suivi"
    assert src["app.py"]["statut"] is None
    assert "vieux.py" not in src
    for nom in (".git", "node_modules"):
        assert (racine[nom]["type"], racine[nom]["non_conserve"]) == ("dossier", True)
    assert (racine[".env"]["type"], racine[".env"]["ignore"], racine[".env"]["non_conserve"]) == ("fichier", True, True)
    assert src["__pycache__"]["non_conserve"] is True


def test_instantane_sans_liste_des_non_suivis_les_marque_ajoutes(client, close, jobs):
    """Instantané pris avant que les non suivis soient notés : tout ce qui manque à HEAD est ajouté."""
    chemin = jobs / close["id"] / "instantane.json"
    lu = json.loads(chemin.read_text())
    del lu["non_suivis"]
    chemin.write_text(json.dumps(lu))

    assert entrees(client, close)["docs"]["statut"] == "ajoute"
    assert entrees(client, close, "src")["brouillon.py"]["statut"] == "ajoute"


def test_fichier_et_diff_de_l_instantane_par_rapport_au_head_de_l_epoque(client, close):
    fichier = codespace(client, close, "/fichier", chemin="src/app.py")
    diff = codespace(client, close, "/diff", chemin="README.md")
    ajoute = codespace(client, close, "/diff", chemin="src/ajout.py")

    assert fichier.json() == {"chemin": "src/app.py", "taille": 17, "contenu": "print('bonjour')\n"}
    assert diff.json() == {"chemin": "README.md", "head": "# r\n", "courant": "# r modifié\n"}
    assert ajoute.json() == {"chemin": "src/ajout.py", "head": None, "courant": "a = 1\n"}


def test_garde_des_chemins_de_l_instantane(client, close):
    for chemin in ("..", "/etc/passwd", "src/../../../jobs"):
        for suite in ("/arbre", "/fichier", "/diff"):
            assert codespace(client, close, suite, chemin=chemin).status_code == 400, (suite, chemin)
    assert codespace(client, close, "/fichier", chemin="src").status_code == 400
    assert codespace(client, close, "/arbre", chemin="README.md").status_code == 400
    for chemin in ("node_modules", ".git", "absent.py"):
        assert codespace(client, close, "/arbre", chemin=chemin).status_code == 404, chemin
    assert codespace(client, close, "/fichier", chemin=".env").status_code == 404


def test_pas_d_instantane_session_anterieure(client, sessions, session, jobs):
    # Close avant la 0.8.0 : ni prise, ni `instantane.json`.
    Sessions(jobs).clore(session["id"], 0)

    identite = codespace(client, session).json()
    arbre = codespace(client, session, "/arbre")

    assert (identite["source"], identite["instantane"]) == ("instantane", {"etat": "absent"})
    assert identite["branche"] == BRANCHE
    assert arbre.status_code == 404
    assert arbre.json()["detail"] == "pas d’instantané (session antérieure à la 0.8.0)"


def test_instantane_perdu_ref_absente_du_clone(client, close, clone):
    git(clone, "update-ref", "-d", f"refs/wap/sessions/{close['id']}")

    identite = codespace(client, close).json()
    arbre = codespace(client, close, "/arbre")

    assert identite["instantane"] == {"etat": "perdu", "pris_le": FIN.isoformat()}
    assert (arbre.status_code, arbre.json()["detail"]) == (404, "instantané perdu")


def test_echec_de_la_prise_affiche(client, sessions, session, clone):
    bloquer_la_ref(clone, session)
    sessions.clore(session["id"], 0)

    identite = codespace(client, session).json()
    arbre = codespace(client, session, "/arbre")

    assert identite["instantane"]["etat"] == "erreur"
    assert identite["instantane"]["erreur"]
    assert arbre.status_code == 404
    assert arbre.json()["detail"].startswith("instantané non pris : ")
