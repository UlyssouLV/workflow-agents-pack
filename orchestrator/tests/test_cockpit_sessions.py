"""Lancement d’une session depuis le cockpit : `POST /api/sessions` contre un faux GitHub et un
faux runner ; éligibilité dans le détail, badge dans la liste, lecture d’une session."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from faux_github import JETON, FauxGitHub
from wap_runtime.registry import ajouter
from wap_runtime.server import creer_app
from wap_runtime.sessions import Sessions

SLUG = "o/r"
COCKPIT = "http://testserver"
CONNECTES = {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"}


class FauxRunner:
    """`POST /sessions` du runner : crée la session dans `jobs/` et note la demande."""

    def __init__(self, jobs):
        self.sessions = Sessions(jobs)
        self.demandes: list[dict] = []

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="http://runner:8788", transport=httpx.MockTransport(self._repondre))

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        assert (requete.method, requete.url.path) == ("POST", "/sessions")
        demande = json.loads(requete.content)
        self.demandes.append(demande)
        if demande["branche"] == "casse":
            return httpx.Response(422, json={"detail": "git fetch a échoué"})
        session = self.sessions.creer(
            demande["repo"], demande["ticket"], demande["agent"], f'claude "/implement #{demande["ticket"]}"'
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


def lancer(api, ticket=30, agent="claude", origine=COCKPIT, repo=SLUG):
    entetes = {"Origin": origine} if origine else {}
    return api.post("/api/sessions", json={"repo": repo, "ticket": ticket, "agent": agent}, headers=entetes)


def test_lancement_demande_au_runner_la_branche_de_la_pr_et_l_identite(api, runner):
    reponse = lancer(api)

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["etat"] == "ouverte"
    assert corps["url"] == f"/sessions/{corps['id']}"
    assert runner.demandes == [
        {
            "repo": SLUG,
            "ticket": 30,
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

    reponse = lancer(api, ticket=30)

    assert reponse.status_code == 409
    assert reponse.json()["session"] == {"id": premiere["id"], "url": premiere["url"], "repo": SLUG}
    assert len(runner.demandes) == 1


@pytest.mark.parametrize(
    "ticket, agent, attendue",
    [
        (31, "claude", "enfant bloqué"),
        (29, "claude", "enfant fermé"),
        (30, "cursor", "agent non connecté"),
    ],
)
def test_enfant_non_eligible_refuse_avec_la_raison(api, runner, ticket, agent, attendue):
    reponse = lancer(api, ticket=ticket, agent=agent)

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == attendue
    assert runner.demandes == []


def test_sans_pr_de_version_refuse(api, github, runner):
    github.repo(SLUG).pulls.clear()

    reponse = lancer(api)

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == "pas de PR de version"
    assert runner.demandes == []


def test_ticket_hors_des_versions_ouvertes_404(api):
    assert lancer(api, ticket=99).status_code == 404


def test_repo_hors_registry_404(api):
    assert lancer(api, repo="o/inconnu").status_code == 404


def test_agent_inconnu_422(api):
    assert lancer(api, agent="vim").status_code == 422


def test_refus_du_runner_relaye(api, github):
    github.repo(SLUG).pulls[0]["head"]["ref"] = "casse"

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
    assert [a["id"] for a in detail["agents"]] == ["claude", "cursor"]
    assert detail["session"] is None

    session = lancer(api).json()
    detail = api.get(f"/api/repos/{SLUG}").json()

    assert detail["versions"][0]["enfants"][0]["lancement"]["claude"] == "session déjà ouverte"
    assert detail["session"] == {"id": session["id"], "url": session["url"], "repo": SLUG}


def test_liste_badge_session_en_cours_sur_le_repo_de_la_session(api, tmp_path):
    ajouter(tmp_path / "repos.toml", "o/autre", None)
    assert all(r["session"] is None for r in api.get("/api/repos").json()["repos"])

    session = lancer(api).json()
    repos = {r["slug"]: r["session"] for r in api.get("/api/repos").json()["repos"]}

    assert repos == {SLUG: {"id": session["id"], "url": session["url"], "repo": SLUG}, "o/autre": None}
