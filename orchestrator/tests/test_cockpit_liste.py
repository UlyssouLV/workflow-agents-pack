"""API liste du cockpit : `GET /api/repos` contre un faux GitHub."""

from datetime import datetime, timedelta, timezone
from importlib.metadata import version

import pytest

from client_cockpit import avec_session
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
    ajouter(chemin, SLUG)
    return chemin


def client(registry, github, horloge, jeton=JETON):
    app = creer_app(registry=registry, jeton=jeton, transport=github.transport(), horloge=horloge)
    return avec_session(app, registry.parent)


def liste(registry, github, horloge, jeton=JETON):
    reponse = client(registry, github, horloge, jeton).get("/api/repos")
    assert reponse.status_code == 200
    return reponse.json()


def entree(corps, slug=SLUG):
    return next(r for r in corps["repos"] if r["slug"] == slug)


def test_health_rend_le_statut_et_la_version(registry, github, horloge):
    reponse = client(registry, github, horloge).get("/health")

    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok", "version": version("wap-runtime")}
    assert version("wap-runtime") == "0.6.0"


def test_une_entree_par_repo_lie_dans_l_ordre_du_registry(registry, github, horloge):
    ajouter(registry, "o/autre", "Autre")
    github.repo(SLUG)
    github.repo("o/autre")

    corps = liste(registry, github, horloge)

    assert [(r["slug"], r["nom"]) for r in corps["repos"]] == [(SLUG, None), ("o/autre", "Autre")]
    assert entree(corps)["url"] == "https://github.com/o/r"
    assert entree(corps)["lu_a"] == DEBUT.isoformat()
    assert entree(corps)["pilote"] is False
    assert entree(corps)["agent"] == "claude"


def test_le_registry_est_relu_a_chaque_requete(registry, github, horloge):
    github.repo(SLUG)
    github.repo("o/nouveau")
    api = client(registry, github, horloge)
    assert [r["slug"] for r in api.get("/api/repos").json()["repos"]] == [SLUG]

    ajouter(registry, "o/nouveau")

    assert [r["slug"] for r in api.get("/api/repos").json()["repos"]] == [SLUG, "o/nouveau"]


def test_registry_absent_rend_une_liste_vide(tmp_path, github, horloge):
    corps = liste(tmp_path / "repos.toml", github, horloge)

    assert corps["repos"] == []
    assert corps["erreur"] is None


def test_registry_illisible_rend_une_erreur_globale(tmp_path, github, horloge):
    chemin = tmp_path / "repos.toml"
    chemin.write_text("[[repos]\n")

    corps = liste(chemin, github, horloge)

    assert corps["repos"] == []
    assert "illisible" in corps["erreur"]


def test_version_ouverte_et_progression(registry, github, horloge):
    github.repo(SLUG).version(
        17,
        [(18, "closed", []), (19, "closed", []), (20, "open", ["ready-for-agent"])],
        titre="V0.3.0 — Registry",
    )

    (version,) = entree(liste(registry, github, horloge))["versions"]

    assert version["numero"] == 17
    assert version["titre"] == "V0.3.0 — Registry"
    assert version["url"] == "https://github.com/o/r/issues/17"
    assert version["progression"] == {"completed": 2, "total": 3}


def test_issue_sans_sub_issues_ni_pr_ne_sont_pas_des_versions(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [])
    repo.pr(30, "Fixes #17", "abc")

    corps = entree(liste(registry, github, horloge))

    assert corps["versions"] == []
    assert corps["etape"]["numero"] == 9


ETAPES = {
    1: ("Question en attente", True),
    2: ("CI en échec", True),
    3: ("Tests humains en cours", True),
    4: ("Tests humains à faire", True),
    5: ("Tests agent en cours", False),
    6: ("CI en cours", False),
    7: ("Implement", False),
    8: ("Code review / Finalise à faire", True),
}

# (enfants, checks de la PR de version ou None sans PR, étape attendue)
SCENARIOS = {
    "1 question en attente": ([(18, "open", ["ready-for-agent", "needs-info"])], None, 1),
    "2 CI en échec": ([(18, "open", ["ready-for-agent"])], [("completed", "failure")], 2),
    "3 tests humains en cours": (
        [(18, "closed", []), (23, "open", ["ready-for-human", "in-human-test"])],
        None,
        3,
    ),
    "4 tests humains à faire": ([(18, "closed", []), (23, "open", ["ready-for-human"])], None, 4),
    "5 tests agent en cours": ([(18, "open", ["ready-for-agent", "in-agent-test"])], None, 5),
    "6 CI en cours": ([(18, "open", ["ready-for-agent"])], [("in_progress", None)], 6),
    "7 implement": ([(18, "open", ["ready-for-agent"]), (23, "open", ["ready-for-human"])], None, 7),
    "8 code review / finalise": (
        [(18, "closed", []), (23, "closed", [])],
        [("completed", "success")],
        8,
    ),
    # Priorité : la première règle qui s’applique l’emporte.
    "1 avant 2": ([(18, "open", ["needs-info"])], [("completed", "failure")], 1),
    "2 avant 3": ([(23, "open", ["ready-for-human", "in-human-test"])], [("completed", "failure")], 2),
    "3 avant 5": ([(23, "open", ["in-human-test", "in-agent-test"])], None, 3),
    "4 avant 6": ([(18, "closed", []), (23, "open", ["ready-for-human"])], [("queued", None)], 4),
    "5 avant 6": ([(18, "open", ["ready-for-agent", "in-agent-test"])], [("queued", None)], 5),
    "6 avant 7": ([(18, "open", ["ready-for-agent"])], [("queued", None)], 6),
    "6 avant 8": ([(18, "closed", [])], [("completed", "success"), ("in_progress", None)], 6),
    "2 avant 6": ([(18, "open", [])], [("completed", "timed_out"), ("queued", None)], 2),
}


@pytest.mark.parametrize("enfants, checks, attendue", SCENARIOS.values(), ids=SCENARIOS.keys())
def test_etape_choisie_par_priorite(registry, github, horloge, enfants, checks, attendue):
    repo = github.repo(SLUG)
    repo.version(17, enfants)
    if checks is not None:
        repo.pr(24, "Version 0.3.0.\n\nFixes #17", "sha24", checks=checks)

    corps = entree(liste(registry, github, horloge))

    libelle, humain = ETAPES[attendue]
    assert corps["versions"][0]["etape"] == {"numero": attendue, "libelle": libelle, "humain": humain}
    assert corps["etape"] == corps["versions"][0]["etape"]
    assert corps["humain_requis"] is humain
    assert corps["erreur"] is None


def test_pas_de_version_ouverte(registry, github, horloge):
    github.repo(SLUG).issues.append(
        {"number": 5, "title": "Bug", "state": "open", "labels": [{"name": "bug"}]}
    )

    corps = entree(liste(registry, github, horloge))

    assert corps["versions"] == []
    assert corps["etape"] == {"numero": 9, "libelle": "Pas de version ouverte", "humain": False}
    assert corps["humain_requis"] is False


def test_aucune_regle_ne_s_applique(registry, github, horloge):
    github.repo(SLUG).version(17, [(18, "closed", [])])

    corps = entree(liste(registry, github, horloge))

    assert corps["etape"] == {"numero": None, "libelle": "Étape indéterminée", "humain": False}


@pytest.mark.parametrize(
    "statuts, attendue", [(["failure"], 2), (["error"], 2), (["pending"], 6), (["success"], 8)]
)
def test_les_statuts_de_commit_comptent_comme_les_checks(registry, github, horloge, statuts, attendue):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "closed", [])])
    repo.pr(24, "Fixes #17", "sha24", statuts=statuts)

    assert entree(liste(registry, github, horloge))["etape"]["numero"] == attendue


def test_pr_de_version_liee_par_fixes_du_parent(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "closed", [])])
    repo.pr(30, "Fixes #170", "autre", checks=[("completed", "failure")])
    repo.pr(24, "Fixes #18\nfixes #17", "sha24", checks=[("completed", "success")])

    (version,) = entree(liste(registry, github, horloge))["versions"]

    assert version["pr"] == {
        "numero": 24,
        "url": "https://github.com/o/r/pull/24",
        "brouillon": False,
        "ci": "ok",
    }
    assert version["etape"]["numero"] == 8


def test_plusieurs_versions_ouvertes_toutes_rendues(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    repo.version(30, [(31, "closed", []), (32, "open", ["ready-for-human"])])

    corps = entree(liste(registry, github, horloge))

    assert [(v["numero"], v["etape"]["numero"]) for v in corps["versions"]] == [(17, 7), (30, 4)]
    # L’étape du repo est la plus avancée dans la priorité ; un humain est requis.
    assert corps["etape"]["numero"] == 4
    assert corps["humain_requis"] is True


def test_une_version_qui_attend_un_humain_passe_avant_une_plus_prioritaire(registry, github, horloge):
    repo = github.repo(SLUG)
    repo.version(17, [(18, "open", ["ready-for-agent"])])
    repo.version(30, [(31, "closed", [])])
    repo.pr(24, "Fixes #30", "sha24", checks=[("completed", "success")])

    corps = entree(liste(registry, github, horloge))

    assert [(v["numero"], v["etape"]["numero"]) for v in corps["versions"]] == [(17, 7), (30, 8)]
    # Le badge suit l’étape affichée : celle qui attend quelqu’un l’emporte.
    assert corps["etape"]["numero"] == 8
    assert corps["humain_requis"] is True


@pytest.mark.parametrize(
    "panne, message",
    [
        ((404, {}, "Not Found"), "introuvable"),
        ((403, {}, "Resource not accessible by personal access token"), "accès refusé"),
        ((401, {}, "Bad credentials"), "token refusé"),
        (
            (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792227600"}, "API rate limit exceeded"),
            "limite d’appels",
        ),
        ((429, {"retry-after": "60"}, "You have exceeded a secondary rate limit"), "limite d’appels"),
    ],
)
def test_une_erreur_github_ne_touche_que_son_repo(registry, github, horloge, panne, message):
    ajouter(registry, "o/sain")
    github.repo(SLUG).panne = panne
    github.repo("o/sain").version(17, [(18, "open", ["ready-for-agent"])])

    corps = liste(registry, github, horloge)

    erreur = entree(corps)["erreur"]
    assert message in erreur and "\n" not in erreur
    assert entree(corps)["versions"] == [] and entree(corps)["etape"] is None
    assert entree(corps, "o/sain")["erreur"] is None
    assert entree(corps, "o/sain")["etape"]["numero"] == 7


def test_repo_inconnu_de_github_est_introuvable(registry, github, horloge):
    corps = liste(registry, github, horloge)

    assert "introuvable" in entree(corps)["erreur"]


def test_connecte_expose_le_compte(registry, github, horloge):
    github.repo(SLUG)

    assert liste(registry, github, horloge)["auth"] == {"etat": "connecte", "compte": "octocat"}


def test_sans_token_l_etat_d_auth_le_dit_et_github_n_est_pas_appele(registry, github, horloge):
    corps = liste(registry, github, horloge, jeton=None)

    assert corps["auth"] == {"etat": "sans_token", "compte": None}
    assert "sudo wap-runtime auth" in entree(corps)["erreur"]
    assert github.appels == []


def test_token_refuse_l_etat_d_auth_le_dit(registry, github, horloge):
    github.repo(SLUG)

    corps = liste(registry, github, horloge, jeton="revoque")

    assert corps["auth"] == {"etat": "token_refuse", "compte": None}
    assert "token refusé" in entree(corps)["erreur"]


def test_api_auth_rend_l_etat_d_auth(registry, github, horloge):
    api = client(registry, github, horloge, jeton=None)

    assert api.get("/api/auth").json() == {"etat": "sans_token", "compte": None}


def test_cache_de_60_s_sur_la_liste(registry, github, horloge):
    github.repo(SLUG).version(17, [(18, "open", ["ready-for-agent"])])
    api = client(registry, github, horloge)
    premier = api.get("/api/repos").json()
    appels = len(github.appels)
    assert appels > 0

    horloge.avancer(59)
    second = api.get("/api/repos").json()

    assert len(github.appels) == appels
    assert second == premier

    horloge.avancer(2)
    troisieme = api.get("/api/repos").json()

    assert len(github.appels) > appels
    assert entree(troisieme)["lu_a"] == (DEBUT + timedelta(seconds=61)).isoformat()


def test_repo_ajoute_pendant_le_cache_est_lu_tout_de_suite(registry, github, horloge):
    github.repo(SLUG)
    github.repo("o/nouveau").version(17, [(18, "open", ["ready-for-agent"])])
    api = client(registry, github, horloge)
    api.get("/api/repos")

    ajouter(registry, "o/nouveau")
    horloge.avancer(10)

    assert entree(api.get("/api/repos").json(), "o/nouveau")["etape"]["numero"] == 7
