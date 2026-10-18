"""Toggle Pilote : écriture HTTP, lecture liste/détail, persistance après redémarrage."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from faux_github import JETON, FauxGitHub
from wap_runtime.registry import ajouter, lire_registry
from wap_runtime.server import creer_app

SLUG = "o/r"
COCKPIT = "http://testserver"
DEBUT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


def github():
    g = FauxGitHub()
    g.repo(SLUG)
    return g


def app(registry, gh=None):
    return creer_app(
        registry=registry,
        jeton=JETON,
        transport=(gh or github()).transport(),
        horloge=lambda: DEBUT,
    )


def test_patch_persiste_pilote_et_agent_sur_le_disque_et_les_lectures(tmp_path):
    registry = tmp_path / "repos.toml"
    ajouter(registry, SLUG)
    api = TestClient(app(registry))

    reponse = api.patch(
        f"/api/repos/{SLUG}",
        json={"pilote": True, "agent": "cursor"},
        headers={"Origin": COCKPIT},
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"pilote": True, "agent": "cursor"}
    assert lire_registry(registry)[0].pilote is True
    assert lire_registry(registry)[0].agent == "cursor"
    detail = api.get(f"/api/repos/{SLUG}").json()
    assert (detail["pilote"], detail["agent"]) == (True, "cursor")
    liste = api.get("/api/repos").json()["repos"][0]
    assert (liste["pilote"], liste["agent"]) == (True, "cursor")


def test_l_etat_pilote_survit_au_redemarrage_du_service(tmp_path):
    registry = tmp_path / "repos.toml"
    ajouter(registry, SLUG)
    TestClient(app(registry)).patch(
        f"/api/repos/{SLUG}",
        json={"pilote": True, "agent": "cursor"},
        headers={"Origin": COCKPIT},
    )

    relance = TestClient(app(registry))

    assert relance.get(f"/api/repos/{SLUG}").json()["pilote"] is True
    assert relance.get("/api/repos").json()["repos"][0]["agent"] == "cursor"


def test_la_liste_relit_le_toggle_meme_si_le_cache_github_est_chaud(tmp_path):
    registry = tmp_path / "repos.toml"
    ajouter(registry, SLUG)
    api = TestClient(app(registry))
    assert api.get("/api/repos").json()["repos"][0]["pilote"] is False

    api.patch(
        f"/api/repos/{SLUG}",
        json={"pilote": True, "agent": "claude"},
        headers={"Origin": COCKPIT},
    )

    assert api.get("/api/repos").json()["repos"][0]["pilote"] is True


def test_patch_sans_origine_cockpit_est_refuse(tmp_path):
    registry = tmp_path / "repos.toml"
    ajouter(registry, SLUG)
    api = TestClient(app(registry))

    reponse = api.patch(f"/api/repos/{SLUG}", json={"pilote": True, "agent": "claude"})

    assert reponse.status_code == 403
    assert lire_registry(registry)[0].pilote is False
