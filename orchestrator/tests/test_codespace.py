"""Codespace d’une session ouverte, côté runner : identité, entrées d’un dossier, contenu d’un
fichier, en lecture seule et sans jamais sortir du clone géré.

Le clone est un vrai dépôt Git sous `clones/o/r` ; la session est écrite dans `jobs/` sans lancer
d’agent.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

from wap_runtime.runner import Runner, creer_app_runner
from wap_runtime.sessions import Sessions

BRANCHE = "v0.8.0-codespace"


def git(dossier, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(dossier), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    dossier = tmp_path / "clones" / "o" / "r"
    dossier.mkdir(parents=True)
    git(dossier, "init", "--quiet", "-b", BRANCHE)
    git(dossier, "config", "user.name", "t")
    git(dossier, "config", "user.email", "t@t")
    (dossier / ".gitignore").write_text("node_modules/\n.env\n")
    (dossier / "README.md").write_text("# r\n")
    (dossier / "src").mkdir()
    (dossier / "src" / "app.py").write_text("print('bonjour')\n")
    git(dossier, "add", ".")
    git(dossier, "commit", "--quiet", "-m", "init")
    (dossier / "node_modules" / "paquet").mkdir(parents=True)
    (dossier / "node_modules" / "paquet" / "index.js").write_text("module.exports = 1;\n")
    (dossier / ".env").write_text("SECRET=1\n")
    return dossier


@pytest.fixture
def jobs(tmp_path):
    return tmp_path / "jobs"


@pytest.fixture
def client(tmp_path, jobs, clone):
    runner = Runner(tmp_path / "clones", jobs)
    with TestClient(creer_app_runner(runner)) as client:
        yield client


@pytest.fixture
def session(client, jobs):
    # Après le runner : il interrompt au démarrage les sessions restées ouvertes.
    return Sessions(jobs).creer("o/r", 30, "claude", 'claude "/implement #30"', branche=BRANCHE)


def codespace(client, session, suite="", **params):
    return client.get(f"/sessions/{session['id']}/codespace{suite}", params=params)


def entrees(client, session, chemin="") -> dict:
    reponse = codespace(client, session, "/arbre", chemin=chemin)
    assert reponse.status_code == 200, reponse.text
    return {e["nom"]: e for e in reponse.json()["entrees"]}


def test_identite_repo_branche_et_head_court(client, session, clone):
    reponse = codespace(client, session)

    assert reponse.status_code == 200
    assert reponse.json() == {
        "repo": "o/r",
        "branche": BRANCHE,
        "head": git(clone, "rev-parse", "--short", "HEAD"),
        "source": "direct",
    }


def test_racine_listee_avec_git_et_les_ignores(client, session):
    racine = entrees(client, session)

    assert set(racine) == {".git", ".gitignore", ".env", "README.md", "node_modules", "src"}
    assert (racine["src"]["type"], racine["src"]["taille"]) == ("dossier", None)
    assert (racine["README.md"]["type"], racine["README.md"]["taille"]) == ("fichier", 4)
    assert racine[".git"]["type"] == "dossier"
    ignores = {nom for nom, e in racine.items() if e["ignore"]}
    assert ignores == {".env", "node_modules"}


def test_dossiers_d_abord_puis_par_nom(client, session):
    reponse = codespace(client, session, "/arbre", chemin="")

    noms = [e["nom"] for e in reponse.json()["entrees"]]
    assert noms == [".git", "node_modules", "src", ".env", ".gitignore", "README.md"]


def test_un_dossier_se_charge_a_son_ouverture(client, session):
    assert set(entrees(client, session, "src")) == {"app.py"}
    paquet = entrees(client, session, "node_modules/paquet")
    assert paquet["index.js"]["ignore"] is True
    assert "HEAD" in entrees(client, session, ".git")


def test_fichier_texte(client, session):
    reponse = codespace(client, session, "/fichier", chemin="src/app.py")

    assert reponse.status_code == 200
    assert reponse.json() == {"chemin": "src/app.py", "taille": 17, "contenu": "print('bonjour')\n"}


def test_fichier_binaire_non_affiche_avec_sa_taille(client, session, clone):
    (clone / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

    reponse = codespace(client, session, "/fichier", chemin="logo.png")

    assert reponse.json() == {"chemin": "logo.png", "taille": 11, "contenu": None, "non_affiche": "binaire"}


def test_fichier_de_plus_d_un_mo_non_affiche(client, session, clone):
    (clone / "gros.txt").write_text("a" * (1024 * 1024 + 1))

    reponse = codespace(client, session, "/fichier", chemin="gros.txt")

    assert reponse.json() == {
        "chemin": "gros.txt", "taille": 1024 * 1024 + 1, "contenu": None, "non_affiche": "trop_gros",
    }


@pytest.mark.parametrize("chemin", ["..", "../..", "src/../../r", "/etc/passwd", "src/../../../jobs"])
def test_chemin_qui_sort_du_clone_refuse(client, session, chemin):
    for suite in ("/arbre", "/fichier", "/diff"):
        reponse = codespace(client, session, suite, chemin=chemin)

        assert reponse.status_code == 400, (suite, chemin)


def test_symlink_sortant_liste_comme_lien_et_jamais_suivi(client, session, clone, tmp_path):
    (tmp_path / "secret.txt").write_text("secret")
    (clone / "fuite").symlink_to(tmp_path / "secret.txt")
    (clone / "fuite-dossier").symlink_to(tmp_path)
    (clone / "interne").symlink_to(clone / "src")

    racine = entrees(client, session)

    assert (racine["fuite"]["type"], racine["fuite"]["taille"]) == ("lien", None)
    assert racine["fuite-dossier"]["type"] == "lien"
    assert racine["interne"]["type"] == "dossier"
    assert codespace(client, session, "/fichier", chemin="fuite").status_code == 400
    assert codespace(client, session, "/arbre", chemin="fuite-dossier").status_code == 400
    assert codespace(client, session, "/fichier", chemin="fuite-dossier/secret.txt").status_code == 400
    assert "secret" not in codespace(client, session, "/fichier", chemin="fuite").text
    assert set(entrees(client, session, "interne")) == {"app.py"}


def test_chemin_absent_404(client, session):
    assert codespace(client, session, "/arbre", chemin="absent").status_code == 404
    assert codespace(client, session, "/fichier", chemin="absent.txt").status_code == 404


def test_un_dossier_n_est_pas_un_fichier_et_inversement(client, session):
    assert codespace(client, session, "/fichier", chemin="src").status_code == 400
    assert codespace(client, session, "/arbre", chemin="README.md").status_code == 400


def test_session_inconnue_404(client):
    for suite in ("", "/arbre", "/fichier", "/diff"):
        reponse = client.get(f"/sessions/20261017-090000-abcdef/codespace{suite}", params={"chemin": "README.md"})

        assert reponse.status_code == 404


def test_session_close_pas_de_codespace_en_direct(client, session, jobs):
    Sessions(jobs).clore(session["id"], 0)

    assert codespace(client, session).status_code == 404


def test_clone_absent_404(client, jobs):
    autre = Sessions(jobs).creer("o/absent", None, "claude", "claude", branche="main")

    assert codespace(client, autre).status_code == 404


def test_clone_sans_commit_identite_sans_head(client, jobs, tmp_path):
    dossier = tmp_path / "clones" / "o" / "vide"
    dossier.mkdir(parents=True)
    git(dossier, "init", "--quiet", "-b", "main")
    vide = Sessions(jobs).creer("o/vide", None, "claude", "claude", branche="main")

    reponse = codespace(client, vide)

    assert reponse.json() == {"repo": "o/vide", "branche": "main", "head": None, "source": "direct"}


def test_statuts_git_des_entrees(client, session, clone):
    (clone / "README.md").write_text("# r modifié\n")
    (clone / "src" / "ajout.py").write_text("a = 1\n")
    git(clone, "add", "src/ajout.py")
    (clone / "notes.txt").write_text("brouillon\n")

    racine = entrees(client, session)
    src = entrees(client, session, "src")

    assert racine["README.md"]["statut"] == "modifie"
    assert racine["notes.txt"]["statut"] == "non_suivi"
    assert src["ajout.py"]["statut"] == "ajoute"
    assert src["app.py"]["statut"] is None
    assert racine[".gitignore"]["statut"] is None
    assert (racine[".env"]["statut"], racine[".env"]["ignore"]) == (None, True)


def test_un_dossier_qui_contient_des_changements_est_marque(client, session, clone):
    (clone / "src" / "app.py").write_text("print('modifié')\n")
    (clone / "src" / "profond").mkdir()
    (clone / "src" / "profond" / "neuf.py").write_text("")
    (clone / "docs" / "guide").mkdir(parents=True)
    (clone / "docs" / "guide" / "neuf.md").write_text("")

    racine = entrees(client, session)

    assert racine["src"]["statut"] == "modifie"
    assert racine["docs"]["statut"] == "non_suivi"
    assert racine["node_modules"]["statut"] is None
    assert racine[".git"]["statut"] is None
    assert entrees(client, session, "src")["profond"]["statut"] == "non_suivi"


def test_les_entrees_d_un_dossier_non_suivi_ou_ignore_en_heritent(client, session, clone):
    (clone / "docs" / "guide").mkdir(parents=True)
    (clone / "docs" / "guide" / "neuf.md").write_text("")

    assert entrees(client, session, "docs/guide")["neuf.md"]["statut"] == "non_suivi"
    assert entrees(client, session, "node_modules")["paquet"]["ignore"] is True
    assert entrees(client, session, ".git")["HEAD"]["ignore"] is False


def test_diff_d_un_fichier_modifie_head_et_courant(client, session, clone):
    (clone / "src" / "app.py").write_text("print('au revoir')\n")

    reponse = codespace(client, session, "/diff", chemin="src/app.py")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "chemin": "src/app.py", "head": "print('bonjour')\n", "courant": "print('au revoir')\n",
    }


@pytest.mark.parametrize("indexe", [True, False], ids=["ajoute", "non_suivi"])
def test_diff_d_un_fichier_absent_de_head_cote_head_vide(client, session, clone, indexe):
    (clone / "neuf.py").write_text("x = 1\n")
    if indexe:
        git(clone, "add", "neuf.py")

    reponse = codespace(client, session, "/diff", chemin="neuf.py")

    assert reponse.json() == {"chemin": "neuf.py", "head": None, "courant": "x = 1\n"}


def test_diff_d_un_fichier_binaire_non_affiche(client, session, clone):
    (clone / "README.md").write_bytes(b"\x89PNG\x00")

    reponse = codespace(client, session, "/diff", chemin="README.md")

    assert reponse.json() == {"chemin": "README.md", "head": None, "courant": None, "non_affiche": "binaire"}


def test_diff_garde_des_chemins(client, session, clone, tmp_path):
    (tmp_path / "secret.txt").write_text("secret")
    (clone / "fuite").symlink_to(tmp_path / "secret.txt")

    for chemin in ("..", "/etc/passwd", "src/../../../jobs", "fuite", "src"):
        assert codespace(client, session, "/diff", chemin=chemin).status_code == 400, chemin
    assert codespace(client, session, "/diff", chemin="absent.py").status_code == 404
