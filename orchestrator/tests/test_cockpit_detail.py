"""API détail du cockpit : `GET /api/repos/{owner}/{name}` contre un faux GitHub."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from faux_github import JETON, FauxGitHub
from wap_runtime.registry import ajouter
from wap_runtime.server import creer_app

SLUG = "o/r"
DEBUT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


class Horloge:
    def __init__(self):
        self.maintenant = DEBUT

    def __call__(self):
        return self.maintenant

    def avancer(self, secondes):
        self.maintenant += timedelta(seconds=secondes)


@pytest.fixture
def github():
    return FauxGitHub()


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def registry(tmp_path):
    chemin = tmp_path / "repos.toml"
    ajouter(chemin, SLUG, "Mon repo")
    return chemin


def client(registry, github, horloge, jeton=JETON):
    app = creer_app(registry=registry, jeton=jeton, transport=github.transport(), horloge=horloge)
    return TestClient(app)


def detail(registry, github, horloge, slug=SLUG, jeton=JETON):
    reponse = client(registry, github, horloge, jeton).get(f"/api/repos/{slug}")
    assert reponse.status_code == 200
    return reponse.json()


def test_identite_du_repo_et_heure_de_lecture(registry, github, horloge):
    github.repo(SLUG)

    corps = detail(registry, github, horloge)

    assert corps["slug"] == SLUG
    assert corps["nom"] == "Mon repo"
    assert corps["url"] == "https://github.com/o/r"
    assert corps["lu_a"] == DEBUT.isoformat()
    assert corps["pilote"] is False
    assert corps["agent"] == "claude"
    assert corps["erreur"] is None
    assert corps["versions"] == []
    assert corps["bugs"] == []
    assert corps["etape"]["numero"] == 9
    assert corps["branches"] == {"proposees": ["main"], "defaut": "main"}


def test_le_slug_du_registry_est_retrouve_sans_tenir_compte_de_la_casse(registry, github, horloge):
    github.repo(SLUG)

    assert detail(registry, github, horloge, slug="O/R")["slug"] == SLUG


def test_parent_et_enfants_avec_etat_labels_et_blocage(registry, github, horloge):
    github.repo(SLUG).version(
        17,
        [
            (18, "closed", []),
            (21, "open", ["ready-for-agent"]),
            (23, "open", ["ready-for-human"]),
        ],
        titre="V0.3.0 — Registry",
        bloques={23},
    )

    (version,) = detail(registry, github, horloge)["versions"]

    assert version["numero"] == 17
    assert version["titre"] == "V0.3.0 — Registry"
    assert version["url"] == "https://github.com/o/r/issues/17"
    assert version["progression"] == {"completed": 1, "total": 3}
    assert version["enfants"] == [
        {
            "numero": 18,
            "titre": "Enfant 18",
            "url": "https://github.com/o/r/issues/18",
            "ouvert": False,
            "labels": [],
            "bloque": False,
            "lancement": {"claude": "enfant fermé", "cursor": "enfant fermé"},
        },
        {
            "numero": 21,
            "titre": "Enfant 21",
            "url": "https://github.com/o/r/issues/21",
            "ouvert": True,
            "labels": ["ready-for-agent"],
            "bloque": False,
            "lancement": {"claude": "pas de PR de version", "cursor": "pas de PR de version"},
        },
        {
            "numero": 23,
            "titre": "Enfant 23",
            "url": "https://github.com/o/r/issues/23",
            "ouvert": True,
            "labels": ["ready-for-human"],
            "bloque": True,
            "lancement": {"claude": "pas `ready-for-agent`", "cursor": "pas `ready-for-agent`"},
        },
    ]


def test_pr_de_version_brouillon_avec_ses_checks(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    repo.pr(
        24,
        "Fixes #17",
        "sha24",
        checks=[("completed", "success"), ("in_progress", None), ("completed", "failure")],
        statuts=["pending"],
        brouillon=True,
    )

    (version,) = detail(registry, github, horloge)["versions"]

    assert version["pr"] == {
        "numero": 24,
        "titre": "PR 24",
        "url": "https://github.com/o/r/pull/24",
        "brouillon": True,
        "branche": "branche-24",
        "ci": "echec",
        "checks": [
            {"nom": "check 0", "etat": "ok", "url": "https://github.com/o/r/runs/0"},
            {"nom": "check 1", "etat": "en_cours", "url": "https://github.com/o/r/runs/1"},
            {"nom": "check 2", "etat": "echec", "url": "https://github.com/o/r/runs/2"},
            {"nom": "statut 0", "etat": "en_cours", "url": "https://ci.example/0"},
        ],
    }


def test_sans_pr_de_version_la_pr_est_nulle(registry, github, horloge):
    github.repo(SLUG).version(17, [(18, "open", ["ready-for-agent"])])

    (version,) = detail(registry, github, horloge)["versions"]

    assert version["pr"] is None


def test_tous_les_signaux_en_plus_de_l_etape_retenue(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent", "needs-info", "in-agent-test"])])
    repo.pr(24, "Fixes #17", "sha24", checks=[("queued", None)])

    corps = detail(registry, github, horloge)

    (version,) = corps["versions"]
    assert version["etape"] == {"numero": 1, "libelle": "Question en attente", "humain": True}
    assert [s["numero"] for s in version["signaux"]] == [1, 5, 6, 7]
    assert version["signaux"][0] == version["etape"]
    assert corps["etape"] == version["etape"]
    assert corps["humain_requis"] is True


def test_aucun_signal_rend_l_etape_indeterminee(registry, github, horloge):
    github.repo(SLUG).version(17, [(18, "closed", [])])

    (version,) = detail(registry, github, horloge)["versions"]

    assert version["signaux"] == []
    assert version["etape"]["numero"] is None


def test_bugs_ouverts_seulement_le_label_bug(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    repo.bug(40, "Plante au démarrage", labels=["bug", "needs-triage"])
    repo.bug(41, "Idée", labels=["enhancement"])
    repo.pr(24, "Fixes #17", "sha24")

    assert detail(registry, github, horloge)["bugs"] == [
        {
            "numero": 40,
            "titre": "Plante au démarrage",
            "url": "https://github.com/o/r/issues/40",
            "labels": ["bug", "needs-triage"],
        }
    ]


def test_deux_appels_successifs_relisent_github(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    api = client(registry, github, horloge)
    premier = api.get(f"/api/repos/{SLUG}").json()
    appels = len(github.appels)
    assert appels > 0

    repo.sous_issues[17][0]["labels"].append({"name": "needs-info"})
    second = api.get(f"/api/repos/{SLUG}").json()

    assert len(github.appels) == 2 * appels
    assert premier["etape"]["numero"] == 7
    assert second["etape"]["numero"] == 1


def test_le_detail_ne_touche_pas_au_cache_de_la_liste(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    api = client(registry, github, horloge)
    api.get("/api/repos")

    repo.sous_issues[17][0]["labels"].append({"name": "needs-info"})

    assert api.get(f"/api/repos/{SLUG}").json()["etape"]["numero"] == 1
    assert api.get("/api/repos").json()["repos"][0]["etape"]["numero"] == 7


def test_repo_hors_registry_rend_404(registry, github, horloge):
    github.repo("o/autre")

    reponse = client(registry, github, horloge).get("/api/repos/o/autre")

    assert reponse.status_code == 404
    assert "o/autre" in reponse.json()["detail"]
    assert github.appels == []


def test_registry_illisible_rend_une_erreur(tmp_path, github, horloge):
    chemin = tmp_path / "repos.toml"
    chemin.write_text("[[repos]\n")

    reponse = client(chemin, github, horloge).get(f"/api/repos/{SLUG}")

    assert reponse.status_code == 500
    assert "illisible" in reponse.json()["detail"]


@pytest.mark.parametrize(
    "panne, message",
    [
        ((404, {}, "Not Found"), "introuvable"),
        ((403, {}, "Resource not accessible by personal access token"), "accès refusé"),
        ((401, {}, "Bad credentials"), "token refusé"),
        ((429, {"retry-after": "60"}, "You have exceeded a secondary rate limit"), "limite d’appels"),
    ],
)
def test_erreur_github_rend_un_message_court(registry, github, horloge, panne, message):
    github.repo(SLUG).panne = panne

    corps = detail(registry, github, horloge)

    assert message in corps["erreur"] and "\n" not in corps["erreur"]
    assert corps["versions"] == [] and corps["bugs"] == []
    assert corps["etape"] is None


def test_sans_token_github_n_est_pas_appele(registry, github, horloge):
    corps = detail(registry, github, horloge, jeton=None)

    assert "sudo wap-runtime auth" in corps["erreur"]
    assert github.appels == []


def test_branches_base_du_canal_et_prs_de_version_defaut_pr(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.default_branch = "develop"
    repo.fichiers["agents/integration-channel.yml"] = "base_branch: feat/runtime-orchestrator\n"
    repo.version(17, [(30, "open", ["ready-for-agent"])])
    repo.pr(24, "Fixes #17", "sha24", branche="v0.4.0")
    repo.version(18, [(40, "open", ["ready-for-agent"])])
    repo.pr(25, "Fixes #18", "sha25", branche="v0.5.0")

    corps = detail(registry, github, horloge)

    assert corps["branches"] == {
        "proposees": ["feat/runtime-orchestrator", "v0.4.0", "v0.5.0"],
        "defaut": "v0.4.0",
    }


def test_branches_sans_canal_ni_pr_la_branche_par_defaut(registry, github, horloge):
    github.repo(SLUG).default_branch = "develop"

    assert detail(registry, github, horloge)["branches"] == {"proposees": ["develop"], "defaut": "develop"}
