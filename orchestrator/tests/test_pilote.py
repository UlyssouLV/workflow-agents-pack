"""Boucle pilote : un tour lance `/implement #n` (spec 0.5.0, ADR 0008)."""

import json
import time
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from client_cockpit import avec_session
from faux_github import JETON, FauxGitHub
from wap_runtime.agents import etat_agents
from wap_runtime.cockpit import Cockpit
from wap_runtime.github import ClientGitHub
from wap_runtime.pilote import tourner
from wap_runtime.registry import ajouter, enregistrer
from wap_runtime.runner import ClientRunner
from wap_runtime.server import creer_app
from wap_runtime.sessions import ATTEND, Sessions

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
        self.occupe = False

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
        if self.occupe:
            autre = {
                "id": "autre",
                "repo": "o/autre",
                "agent": "claude",
                "etat": "ouverte",
                "activite": "travaille",
            }
            return httpx.Response(409, json={"detail": "occupe", "travaille": True, "session": autre})
        ticket = demande.get("ticket")
        commande = f'claude "/implement #{ticket}"' if ticket is not None else "claude"
        session = self.sessions.creer(
            demande["repo"],
            ticket,
            demande["agent"],
            commande,
            branche=demande.get("branche"),
            modele=demande.get("modele"),
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
    return avec_session(
        creer_app(
            registry=registry,
            jeton=JETON,
            transport=github.transport(),
            env=env,
            jobs=jobs,
            runner=runner.client(),
        ),
        registry.parent,
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


def test_tour_cursor_sans_predecesseur_utilise_la_preference_modele(registry, github, jobs, runner):
    enregistrer(registry, SLUG, pilote=True, agent="cursor", modele="composer-2")

    session = tourner(**monde(registry, github, jobs, runner, env={"CURSOR_API_KEY": "key_x"}))

    assert session["modele"] == "composer-2"
    assert runner.demandes[-1]["agent"] == "cursor"
    assert runner.demandes[-1]["modele"] == "composer-2"
    assert runner.saisies == [(session["id"], "/implement #30\r")]


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


def test_tour_reprend_quand_le_clone_n_est_plus_sale(registry, github, jobs, runner):
    """CloneSale notifie mais ne bloque pas la reprise une fois le clone propre (US6, US12)."""
    echecs: dict[str, bool] = {}
    runner.sale = {
        "fichiers": [{"statut": "M", "chemin": "a.py"}],
        "diff": "-avant\n+après\n",
        "branche": "travail",
    }
    kwargs = monde(registry, github, jobs, runner)

    assert tourner(**kwargs, echecs=echecs) is None
    assert echecs.get(SLUG.lower()) is True

    runner.sale = None
    session = tourner(**kwargs, echecs=echecs)

    assert session is not None
    assert runner.saisies == [(session["id"], "/implement #30\r")]
    assert SLUG.lower() not in echecs


def test_tour_attend_son_tour_si_une_autre_session_travaille(registry, github, jobs, runner):
    """SessionQuiTravaille : file d’attente, pas un stop permanent (US13)."""
    echecs: dict[str, bool] = {}
    runner.occupe = True
    kwargs = monde(registry, github, jobs, runner)

    assert tourner(**kwargs, echecs=echecs) is None
    assert echecs == {}

    runner.occupe = False
    session = tourner(**kwargs, echecs=echecs)

    assert session is not None
    assert runner.saisies[-1] == (session["id"], "/implement #30\r")


def test_tour_reprend_apres_session_echouee_si_le_pilote_est_acquitte(
    registry, github, jobs, runner
):
    """échouée notifie ; PATCH (acquittement) débloque la reprise (US11–12)."""
    sessions = Sessions(jobs)
    ratee = sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")
    sessions.clore(ratee["id"], 1)
    kwargs = monde(registry, github, jobs, runner)
    acquittements: dict[str, str] = {}

    assert tourner(**kwargs, acquittements=acquittements) is None

    acquittements[SLUG.lower()] = ratee["id"]
    session = tourner(**kwargs, acquittements=acquittements)

    assert session is not None
    assert session["id"] != ratee["id"]


def test_tour_ne_lance_pas_sans_pr_de_version(registry, github, jobs, runner):
    github.repo(SLUG).pulls.clear()

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_tour_ne_lance_pas_si_humain_requis(registry, github, jobs, runner):
    github.repo(SLUG).sous_issues[17][0]["labels"].append({"name": "needs-info"})

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []
    assert runner.saisies == []


def test_tour_ne_lance_pas_si_la_session_attend_et_la_laisse_ouverte(registry, github, jobs, runner):
    sessions = Sessions(jobs)
    ouverte = sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")
    sessions.enregistrer_etat(ouverte["id"], ATTEND)

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []
    assert sessions.ouverte(SLUG)["id"] == ouverte["id"]
    assert sessions.lire(ouverte["id"])["activite"] == ATTEND


def test_tour_ne_lance_pas_apres_une_session_echouee(registry, github, jobs, runner):
    sessions = Sessions(jobs)
    sessions.clore(sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")["id"], 1)

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_tour_ne_lance_pas_apres_une_session_interrompue(registry, github, jobs, runner):
    Sessions(jobs).creer(SLUG, None, "claude", "claude", branche="v0.5.0")
    Sessions(jobs).interrompre()

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_tour_ne_lance_pas_sans_enfant_eligible(registry, github, jobs, runner):
    for enfant in github.repo(SLUG).sous_issues[17]:
        enfant["labels"] = [l for l in enfant["labels"] if l["name"] != "ready-for-agent"]

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert runner.demandes == []


def test_tour_reprend_apres_fermeture_si_un_enfant_est_eligible(registry, github, jobs, runner):
    session = tourner(**monde(registry, github, jobs, runner))
    Sessions(jobs).clore(session["id"], 0)

    suivante = tourner(**monde(registry, github, jobs, runner))

    assert suivante is not None
    assert suivante["id"] != session["id"]
    assert runner.saisies[-1] == (suivante["id"], "/implement #30\r")


def test_couper_le_pilote_laisse_la_session_courante_et_ne_relance_pas(registry, github, jobs, runner):
    session = tourner(**monde(registry, github, jobs, runner))
    enregistrer(registry, SLUG, pilote=False, agent="claude")

    assert tourner(**monde(registry, github, jobs, runner)) is None
    assert Sessions(jobs).ouverte(SLUG)["id"] == session["id"]
    assert len(runner.demandes) == 1


def test_l_api_expose_le_stop_humain_requis_sur_liste_et_detail(registry, github, jobs, runner):
    github.repo(SLUG).sous_issues[17][0]["labels"].append({"name": "needs-info"})

    client = api(registry, github, jobs, runner)
    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "humain_requis"
    assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] == "humain_requis"


def test_l_api_expose_le_stop_attend_sans_fermer_la_session(registry, github, jobs, runner):
    sessions = Sessions(jobs)
    ouverte = sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")
    sessions.enregistrer_etat(ouverte["id"], ATTEND)

    client = api(registry, github, jobs, runner)
    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "attend"
    assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] == "attend"
    assert sessions.ouverte(SLUG)["id"] == ouverte["id"]


def test_l_api_expose_le_stop_si_l_agent_prefere_n_est_pas_connecte(registry, github, jobs, runner):
    enregistrer(registry, SLUG, pilote=True, agent="cursor")

    client = api(registry, github, jobs, runner)
    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "echec_lancement"
    assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] == "echec_lancement"


def test_l_api_expose_le_stop_apres_echec_de_lancement(registry, github, jobs, runner):
    runner.sale = {
        "fichiers": [{"statut": "M", "chemin": "a.py"}],
        "diff": "-avant\n+après\n",
        "branche": "travail",
    }
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

    with avec_session(app, registry.parent) as client:
        limite = time.monotonic() + 2
        while client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] != "echec_lancement":
            if time.monotonic() >= limite:
                break
            time.sleep(0.02)
        assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "echec_lancement"
        assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] == "echec_lancement"


def test_l_api_expose_le_stop_apres_une_session_echouee(registry, github, jobs, runner):
    sessions = Sessions(jobs)
    sessions.clore(sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")["id"], 1)

    assert api(registry, github, jobs, runner).get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "echouee"


def test_l_api_acquitte_le_stop_echouee_via_patch_pilote(registry, github, jobs, runner):
    sessions = Sessions(jobs)
    sessions.clore(sessions.creer(SLUG, None, "claude", "claude", branche="v0.5.0")["id"], 1)
    client = api(registry, github, jobs, runner)

    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] == "echouee"
    assert (
        client.patch(
            f"/api/repos/{SLUG}",
            json={"pilote": True, "agent": "claude"},
            headers={"Origin": "http://testserver"},
        ).status_code
        == 200
    )
    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] is None
    assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] is None


def test_l_api_expose_le_stop_sans_enfant_eligible(registry, github, jobs, runner):
    for enfant in github.repo(SLUG).sous_issues[17]:
        enfant["labels"] = [l for l in enfant["labels"] if l["name"] != "ready-for-agent"]

    assert (
        api(registry, github, jobs, runner).get(f"/api/repos/{SLUG}").json()["pilote_stop"]
        == "aucun_eligible"
    )


def test_l_api_n_expose_pas_de_stop_si_le_pilote_est_off(registry, github, jobs, runner):
    enregistrer(registry, SLUG, pilote=False, agent="claude")

    client = api(registry, github, jobs, runner)
    assert client.get(f"/api/repos/{SLUG}").json()["pilote_stop"] is None
    assert client.get("/api/repos").json()["repos"][0]["pilote_stop"] is None


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
