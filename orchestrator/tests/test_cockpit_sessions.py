"""Lancement d’une session depuis le cockpit : `POST /api/sessions` contre un faux GitHub et un
faux runner ; éligibilité dans le détail, badge dans la liste, lecture d’une session."""

import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from faux_github import JETON, FauxGitHub
from wap_runtime.registry import ajouter
from wap_runtime.server import creer_app
from wap_runtime.sessions import Sessions, publique

SLUG = "o/r"
COCKPIT = "http://testserver"
CONNECTES = {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"}


class FauxRunner:
    """`POST /sessions` du runner : crée la session dans `jobs/` et note la demande.

    `sale` : le clone a ces changements non commités, la demande doit porter un `choix`.
    """

    def __init__(self, jobs):
        self.sessions = Sessions(jobs)
        self.demandes: list[dict] = []
        self.sale: dict | None = None
        self.echec: str | None = None

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="http://runner:8788", transport=httpx.MockTransport(self._repondre))

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        assert (requete.method, requete.url.path) == ("POST", "/sessions")
        demande = json.loads(requete.content)
        self.demandes.append(demande)
        if self.echec:
            return httpx.Response(422, json={"detail": self.echec})
        if self.sale and "choix" not in demande:
            return httpx.Response(409, json={"detail": "clone sale", "clone": self.sale})
        ticket = demande.get("ticket")
        commande = f'claude "/implement #{ticket}"' if ticket is not None else "claude"
        session = self.sessions.creer(
            demande["repo"], ticket, demande["agent"], commande, branche=demande.get("branche")
        )
        return httpx.Response(201, json=session)


@pytest.fixture
def jobs(tmp_path):
    return tmp_path / "jobs"


@pytest.fixture
def runner(jobs):
    return FauxRunner(jobs)


@pytest.fixture
def github():
    """`o/r` : version 17, PR 24 sur `v0.4.0`, enfant 30 éligible, 31 bloqué."""
    github = FauxGitHub()
    repo = github.repo(SLUG)
    repo.version(
        17,
        [(30, "open", ["ready-for-agent"]), (31, "open", ["ready-for-agent"]), (29, "closed", [])],
        bloques=(31,),
    )
    repo.pr(24, "Fixes #17", "sha24", branche="v0.4.0")
    return github


@pytest.fixture
def api(tmp_path, github, jobs, runner):
    registry = tmp_path / "repos.toml"
    ajouter(registry, SLUG, None)
    app = creer_app(
        registry=registry, jeton=JETON, transport=github.transport(), env=CONNECTES,
        jobs=jobs, runner=runner.client(),
    )
    return TestClient(app)


def lancer(api, agent="claude", origine=COCKPIT, repo=SLUG, branche="v0.4.0", **choix):
    entetes = {"Origin": origine} if origine else {}
    demande = {"repo": repo, "agent": agent, "branche": branche, **choix}
    return api.post("/api/sessions", json=demande, headers=entetes)


def test_lancement_demande_au_runner_agent_branche_et_identite_sans_ticket(api, runner):
    reponse = lancer(api)

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["etat"] == "ouverte"
    assert corps["ticket"] is None
    assert corps["branche"] == "v0.4.0"
    assert corps["url"] == f"/sessions/{corps['id']}"
    assert runner.demandes == [
        {
            "repo": SLUG,
            "agent": "claude",
            "branche": "v0.4.0",
            "login": "octocat",
            "email": "583231+octocat@users.noreply.github.com",
        }
    ]


@pytest.mark.parametrize("origine", [None, "http://evil.example", "http://testserver:9999"])
def test_origine_autre_que_le_cockpit_refusee(api, runner, origine):
    reponse = lancer(api, origine=origine)

    assert reponse.status_code == 403
    assert runner.demandes == []


def test_pas_de_cors(api):
    reponse = api.options(
        "/api/sessions",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in reponse.headers


def test_deuxieme_session_409_avec_le_lien_de_la_session_ouverte(api, runner):
    premiere = lancer(api).json()

    reponse = lancer(api)

    assert reponse.status_code == 409
    assert reponse.json()["session"] == {
        "id": premiere["id"],
        "url": premiere["url"],
        "repo": SLUG,
        "activite": "inconnue",
    }
    assert len(runner.demandes) == 1


def test_lancement_409_si_un_autre_repo_travaille(api, github, tmp_path, jobs, runner):
    github.repo("o/autre")
    ajouter(tmp_path / "repos.toml", "o/autre", None)
    autre = lancer(api, repo="o/autre", branche="main").json()
    Sessions(jobs).enregistrer_etat(autre["id"], "travaille")

    reponse = lancer(api)

    assert reponse.status_code == 409
    assert len(runner.demandes) == 1
    assert reponse.json()["session"] == {
        "id": autre["id"],
        "url": autre["url"],
        "repo": "o/autre",
        "activite": "travaille",
    }
    assert "une session travaille sur o/autre" in reponse.json()["detail"]


@pytest.mark.parametrize("activite", ["attend", "inconnue"])
def test_lancement_accepte_si_un_autre_repo_attend_ou_inconnue(api, github, tmp_path, jobs, activite):
    github.repo("o/autre")
    ajouter(tmp_path / "repos.toml", "o/autre", None)
    autre = lancer(api, repo="o/autre", branche="main").json()
    if activite != "inconnue":
        Sessions(jobs).enregistrer_etat(autre["id"], activite)

    reponse = lancer(api)

    assert reponse.status_code == 201
    assert reponse.json()["repo"] == SLUG


def test_lancement_sur_un_autre_repo_accepte(api, github, tmp_path, runner):
    github.repo("o/autre")
    ajouter(tmp_path / "repos.toml", "o/autre", None)
    premiere = lancer(api).json()

    reponse = lancer(api, repo="o/autre", branche="main")

    assert reponse.status_code == 201
    assert reponse.json()["repo"] == "o/autre"
    assert {d["repo"] for d in runner.demandes} == {SLUG, "o/autre"}
    assert lancer(api).status_code == 409
    assert lancer(api).json()["session"]["id"] == premiere["id"]


def test_agent_non_connecte_refuse(api, runner):
    reponse = lancer(api, agent="cursor")

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == "agent non connecté"
    assert runner.demandes == []


def test_session_sur_la_base_sans_pr_de_version(api, github, runner):
    github.repo(SLUG).pulls.clear()

    reponse = lancer(api, branche="main")

    assert reponse.status_code == 201
    assert runner.demandes[-1]["branche"] == "main"
    assert reponse.json()["ticket"] is None


def test_branche_hors_liste_refusee(api, runner):
    reponse = lancer(api, branche="hors-liste")

    assert reponse.status_code == 422
    assert "non proposée" in reponse.json()["detail"]
    assert runner.demandes == []


def test_repo_hors_registry_404(api):
    assert lancer(api, repo="o/inconnu").status_code == 404


def test_agent_inconnu_422(api):
    assert lancer(api, agent="vim").status_code == 422


def test_refus_du_runner_relaye(api, runner):
    runner.echec = "git fetch a échoué"

    reponse = lancer(api)

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == "git fetch a échoué"


def test_lire_une_session(api):
    session = lancer(api).json()

    reponse = api.get(f"/api/sessions/{session['id']}")

    assert reponse.status_code == 200
    assert reponse.json() == session


def test_session_inconnue_404(api):
    assert api.get("/api/sessions/20261017-090000-abcdef").status_code == 404


def test_detail_porte_l_eligibilite_par_agent_et_la_session_ouverte(api):
    detail = api.get(f"/api/repos/{SLUG}").json()

    enfants = {e["numero"]: e["lancement"] for e in detail["versions"][0]["enfants"]}
    assert enfants == {
        30: {"claude": None, "cursor": "agent non connecté"},
        31: {"claude": "enfant bloqué", "cursor": "enfant bloqué"},
        29: {"claude": "enfant fermé", "cursor": "enfant fermé"},
    }
    assert detail["versions"][0]["pr"]["branche"] == "v0.4.0"
    assert detail["branches"] == {"proposees": ["main", "v0.4.0"], "defaut": "v0.4.0"}
    assert [a["id"] for a in detail["agents"]] == ["claude", "cursor"]
    assert detail["session"] is None

    session = lancer(api).json()
    detail = api.get(f"/api/repos/{SLUG}").json()

    assert detail["versions"][0]["enfants"][0]["lancement"]["claude"] == "session déjà ouverte"
    assert detail["session"] == {
        "id": session["id"],
        "url": session["url"],
        "repo": SLUG,
        "activite": "inconnue",
    }


def test_liste_badge_session_en_cours_sur_le_repo_de_la_session(api, github, tmp_path):
    github.repo("o/autre")
    ajouter(tmp_path / "repos.toml", "o/autre", None)
    assert all(r["session"] is None for r in api.get("/api/repos").json()["repos"])

    session = lancer(api).json()
    autre = lancer(api, repo="o/autre", branche="main").json()
    repos = {r["slug"]: r["session"] for r in api.get("/api/repos").json()["repos"]}

    assert repos == {
        SLUG: {"id": session["id"], "url": session["url"], "repo": SLUG, "activite": "inconnue"},
        "o/autre": {"id": autre["id"], "url": autre["url"], "repo": "o/autre", "activite": "inconnue"},
    }
    assert api.get(f"/api/repos/{SLUG}").json()["session"]["id"] == session["id"]
    assert api.get("/api/repos/o/autre").json()["session"]["id"] == autre["id"]


SALE = {"fichiers": [{"statut": "M", "chemin": "a.py"}], "diff": "-avant\n+après\n", "branche": "travail"}


def test_clone_sale_sans_choix_409_avec_fichiers_et_diff_sans_session(api, runner, jobs):
    runner.sale = SALE

    reponse = lancer(api)

    assert reponse.status_code == 409
    assert reponse.json()["clone"] == SALE
    assert "session" not in reponse.json()
    assert Sessions(jobs).toutes() == []


@pytest.mark.parametrize("choix", ["reprendre", "jeter"])
def test_choix_relaye_au_runner(api, runner, choix):
    runner.sale = SALE

    reponse = lancer(api, choix=choix)

    assert reponse.status_code == 201
    assert runner.demandes[-1]["choix"] == choix


def test_choix_inconnu_422(api, runner):
    assert lancer(api, choix="effacer").status_code == 422
    assert runner.demandes == []


def test_liste_toutes_les_sessions_plus_recentes_d_abord(api, jobs):
    a_9h, a_10h = (Sessions(jobs, lambda h=h: datetime(2026, 10, 17, h, tzinfo=timezone.utc)) for h in (9, 10))
    premiere = a_9h.creer(SLUG, None, "claude", "claude", branche="main")
    a_9h.clore(premiere["id"], 0)
    seconde = a_10h.creer("o/autre", None, "cursor", "agent", branche="feat")

    reponse = api.get("/api/sessions")

    assert reponse.status_code == 200
    lues = reponse.json()["sessions"]
    assert [s["id"] for s in lues] == [seconde["id"], premiere["id"]]
    assert lues[0] == {**publique(seconde), "url": f"/sessions/{seconde['id']}"}
    assert lues[1]["repo"] == SLUG


def test_sessions_d_un_repo_plus_recente_d_abord(api, jobs):
    a_9h, a_10h = (Sessions(jobs, lambda h=h: datetime(2026, 10, 17, h, tzinfo=timezone.utc)) for h in (9, 10))
    seconde = a_10h.creer(SLUG, 31, "cursor", 'agent "/implement #31"')
    premiere = a_9h.creer(SLUG, 30, "claude", 'claude "/implement #30"')
    a_9h.clore(premiere["id"], 0)
    a_9h.creer("o/autre", 3, "claude", 'claude "/implement #3"')

    reponse = api.get("/api/repos/o/r/sessions")

    assert reponse.status_code == 200
    lues = reponse.json()["sessions"]
    assert [s["ticket"] for s in lues] == [31, 30]
    assert lues[0] == {**publique(seconde), "url": f"/sessions/{seconde['id']}"}


def test_sessions_d_un_repo_sans_session(api):
    assert api.get("/api/repos/o/r/sessions").json() == {"sessions": []}


def test_contenu_du_cast_d_une_session(api, jobs):
    session = Sessions(jobs).creer(SLUG, 30, "claude", 'claude "/implement #30"')
    cast = '{"version": 2, "width": 80, "height": 24}\n[0.1, "o", "prêt"]\n'
    (jobs / session["id"] / "terminal.cast").write_text(cast)

    reponse = api.get(f"/api/sessions/{session['id']}/terminal.cast")

    assert reponse.status_code == 200
    assert reponse.text == cast
    assert reponse.headers["content-type"].startswith("application/x-asciicast")


def test_cast_absent_ou_session_inconnue_404(api, jobs):
    session = Sessions(jobs).creer(SLUG, 30, "claude", 'claude "/implement #30"')

    assert api.get(f"/api/sessions/{session['id']}/terminal.cast").status_code == 404
    assert api.get("/api/sessions/20261017-090000-ffffff/terminal.cast").status_code == 404


def test_chaine_de_sessions_exposee_dans_la_session_et_la_liste(api, jobs):
    sessions = Sessions(jobs)
    premiere = sessions.creer(SLUG, 30, "claude", 'claude "/implement #30"')
    seconde = sessions.creer(SLUG, 31, "claude", 'claude "/implement #31"', precedente=premiere["id"])
    sessions.enchainer(premiere["id"], seconde["id"])

    lue = api.get(f"/api/sessions/{premiere['id']}").json()
    liste = {s["id"]: s for s in api.get("/api/repos/o/r/sessions").json()["sessions"]}

    assert (lue["etat"], lue["precedente"], lue["suivante"]) == ("enchaînée", None, seconde["id"])
    assert liste[premiere["id"]] == lue
    assert (liste[seconde["id"]]["etat"], liste[seconde["id"]]["precedente"]) == ("ouverte", premiere["id"])
    assert liste[seconde["id"]]["suivante"] is None


def test_session_expose_activite_skill_et_titre_par_defaut_nom_agent(api, jobs):
    sessions = Sessions(jobs)
    session = sessions.creer(SLUG, None, "claude", "claude", branche="main")
    sessions.enregistrer_etat(session["id"], "attend", skill="grilling", prompt="Ouvre la version")

    lue = api.get(f"/api/sessions/{session['id']}").json()

    assert (lue["activite"], lue["skill"], lue["titre"]) == ("attend", "grilling", "Ouvre la version")
    sans = sessions.creer("o/autre", None, "cursor", "agent", branche="main")
    assert api.get(f"/api/sessions/{sans['id']}").json()["titre"] == "Cursor"


def test_session_d_avant_la_chaine_sans_precedente_ni_suivante(api, jobs):
    """Un `session.json` écrit par une 0.4.0 n’a pas ces champs."""
    session = Sessions(jobs).creer(SLUG, 30, "claude", 'claude "/implement #30"')
    chemin = jobs / session["id"] / "session.json"
    ancien = {k: v for k, v in json.loads(chemin.read_text()).items() if k not in ("precedente", "suivante")}
    chemin.write_text(json.dumps(ancien))

    lue = api.get(f"/api/sessions/{session['id']}").json()
    (listee,) = api.get("/api/repos/o/r/sessions").json()["sessions"]

    assert (lue["precedente"], lue["suivante"]) == (None, None)
    assert listee == lue
