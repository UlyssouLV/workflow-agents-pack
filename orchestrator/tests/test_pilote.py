"""Boucle pilote : un tour lance `/implement #n` (spec 0.5.0, ADR 0008)."""

import json
import time
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from faux_github import JETON, FauxGitHub
from wap_runtime.agents import etat_agents
from wap_runtime.cockpit import Cockpit
from wap_runtime.github import ClientGitHub
from wap_runtime.pilote import tourner
from wap_runtime.registry import ajouter, enregistrer
from wap_runtime.runner import ClientRunner
from wap_runtime.server import creer_app
from wap_runtime.sessions import Sessions

SLUG = "o/r"
CONNECTES = {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"}
DEBUT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


class FauxRunner:
    """API interne du runner : session libre + saisie, jamais `enchainer`."""

    def __init__(self, jobs):
        self.sessions = Sessions(jobs)
        self.demandes: list[dict] = []
        self.saisies: list[tuple[str, str]] = []
        self.enchainements: list[dict] = []
        self.sale: dict | None = None

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="http://runner:8788", transport=httpx.MockTransport(self._repondre))

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if requete.method == "POST" and chemin.endswith("/suivante"):
            self.enchainements.append(json.loads(requete.content))
            return httpx.Response(500, json={"detail": "enchainer ne doit pas être appelé"})
        if requete.method == "POST" and chemin.endswith("/saisie"):
            demande = json.loads(requete.content)
            id_ = chemin.split("/")[2]
            self.saisies.append((id_, demande["texte"]))
            return httpx.Response(204)
        assert (requete.method, chemin) == ("POST", "/sessions")
        demande = json.loads(requete.content)
        self.demandes.append(demande)
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
    github = FauxGitHub()
    repo = github.repo(SLUG)
    repo.version(
        17,
        [(42, "open", ["ready-for-agent"]), (30, "open", ["ready-for-agent"]), (31, "open", ["ready-for-agent"])],
        bloques=(31,),
    )
    repo.pr(24, "Fixes #17", "sha24", branche="v0.5.0")
    return github


@pytest.fixture
def registry(tmp_path):
    chemin = tmp_path / "repos.toml"
    ajouter(chemin, SLUG)
    enregistrer(chemin, SLUG, pilote=True, agent="claude")
    return chemin


def monde(registry, github, jobs, runner, env=CONNECTES):
    client = ClientGitHub(JETON, transport=github.transport())
    return dict(
        registry=registry,
        cockpit=Cockpit(registry, client, lambda: DEBUT),
        sessions=Sessions(jobs),
        runner=ClientRunner(runner.client()),
        agents=etat_agents(env),
        github=client,
    )


def api(registry, github, jobs, runner, env=CONNECTES):
    return TestClient(
        creer_app(
            registry=registry,
            jeton=JETON,
            transport=github.transport(),
            env=env,
            jobs=jobs,
            runner=runner.client(),
        )
    )


def test_tour_ouvre_une_session_libre_puis_implement_du_plus_petit_eligible(registry, github, jobs, runner):
    session = tourner(**monde(registry, github, jobs, runner))

    assert session["ticket"] is None
    assert session["branche"] == "v0.5.0"
    assert session["commande"] == "claude"
    assert runner.demandes == [
        {
            "repo": SLUG,
            "agent": "claude",
            "branche": "v0.5.0",
            "login": "octocat",
            "email": "583231+octocat@users.noreply.github.com",
        }
    ]
    assert runner.saisies == [(session["id"], "/implement #30\r")]
    assert runner.enchainements == []
    lue = api(registry, github, jobs, runner).get("/api/sessions").json()["sessions"][0]
    assert (lue["id"], lue["ticket"], lue["url"]) == (session["id"], None, f"/sessions/{session['id']}")


def test_tour_ne_lance_pas_si_le_pilote_est_off(registry, github, jobs, runner):
    enregistrer(registry, SLUG, pilote=False, agent="claude")

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []
    assert runner.saisies == []


def test_tour_ne_lance_pas_si_une_session_est_deja_ouverte(registry, github, jobs, runner):
    Sessions(jobs).creer(SLUG, None, "claude", "claude", branche="v0.5.0")

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []
    assert runner.enchainements == []


def test_tour_ne_lance_pas_si_l_agent_prefere_n_est_pas_connecte(registry, github, jobs, runner):
    enregistrer(registry, SLUG, pilote=True, agent="cursor")

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_tour_ne_lance_pas_si_le_clone_est_sale(registry, github, jobs, runner):
    runner.sale = {
        "fichiers": [{"statut": "M", "chemin": "a.py"}],
        "diff": "-avant\n+après\n",
        "branche": "travail",
    }

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.saisies == []
    assert api(registry, github, jobs, runner).get("/api/sessions").json()["sessions"] == []


def test_tour_ne_lance_pas_sans_pr_de_version(registry, github, jobs, runner):
    github.repo(SLUG).pulls.clear()

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_le_runtime_lance_sans_requete_cockpit(registry, github, jobs, runner):
    app = creer_app(
        registry=registry,
        jeton=JETON,
        transport=github.transport(),
        env=CONNECTES,
        jobs=jobs,
        runner=runner.client(),
        boucle_pilote=True,
        intervalle_pilote=0.05,
    )

    with TestClient(app):
        limite = time.monotonic() + 2
        while not runner.saisies and time.monotonic() < limite:
            time.sleep(0.02)

    assert runner.demandes and "ticket" not in runner.demandes[0]
    assert runner.saisies[0][1] == "/implement #30\r"
    assert runner.enchainements == []
