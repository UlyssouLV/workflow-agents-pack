"""Anti-échappement : proxy Caddy + surface cockpit ne relaient hors instance (#95, ADR 0011)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from helpers_pack import activer_exposition, ecrire_cle, passe, service
from wap_runtime.identifiants_cockpit import definir
from wap_runtime.instance import PORT_CONTENEUR
from wap_runtime.server import creer_app

LOGIN = "ops"
MOT_DE_PASSE = "s3cret-ops"

# Cibles qu’une config / surface fuitée ne doit jamais joindre via le chemin public.
CIBLES_INTERDITES = (
    "runner",
    "127.0.0.1",
    "0.0.0.0",
    "localhost",
    "192.168.",
    "10.0.",
    "172.16.",
    "169.254.",
    "forward_proxy",
)


def amont_reverse_proxy(caddyfile: str) -> str:
    """Extrait la ligne `reverse_proxy …` (cible unique attendue)."""
    import re

    m = re.search(r"^\s*reverse_proxy\s+(.+)$", caddyfile, re.MULTILINE)
    assert m, f"pas de reverse_proxy dans {caddyfile!r}"
    return m.group(1).strip()


def test_caddy_ne_permet_pas_d_echapper_vers_hors_cockpit(home, depot_pack):
    """Tentatives d’échappement via la config proxy : autres hôtes/ports, runner, open-proxy."""
    instance = passe(home, depot_pack)
    activer_exposition(instance)
    passe(home, depot_pack)

    caddyfile = (instance / "Caddyfile").read_text()
    amont = amont_reverse_proxy(caddyfile)

    assert amont == f"runtime:{PORT_CONTENEUR}"
    # Une seule directive de relais ; pas de second upstream « de secours ».
    assert caddyfile.count("reverse_proxy") == 1
    for interdit in CIBLES_INTERDITES:
        assert interdit not in caddyfile, f"cible interdite présente : {interdit}"
    # Pas d’upstream dynamique / catch-all (open proxy).
    assert "{" not in amont
    assert "*" not in amont
    assert "http://" not in amont
    assert "https://" not in amont


def test_compose_expo_ne_publie_pas_de_chemin_vers_runner_ou_lan(home, depot_pack):
    """Sans domaine : 80/443 sur loopback seulement ; runner/runtime hors Internet."""
    instance = passe(home, depot_pack)
    activer_exposition(instance)
    passe(home, depot_pack)

    compose = (instance / "compose.yaml").read_text()
    caddy = service(compose, "caddy")
    runtime = service(compose, "runtime")
    runner = service(compose, "runner")

    assert '"127.0.0.1:80:80"' in caddy
    assert '"127.0.0.1:443:443"' in caddy
    assert "ports:" not in runtime
    assert "ports:" not in runner
    assert "network_mode: host" not in caddy
    assert "network_mode: host" not in runtime
    assert "network_mode: host" not in runner


def test_caddy_avec_domaine_reste_borne_au_cockpit(home, depot_pack):
    """HTTPS nommé : même bornage — pas d’échappement vers runner / LAN."""
    instance = passe(home, depot_pack)
    ecrire_cle(instance, "exposition", True)
    ecrire_cle(instance, "domaine", "cockpit.exemple.test")
    passe(home, depot_pack)

    caddyfile = (instance / "Caddyfile").read_text()
    assert "cockpit.exemple.test" in caddyfile
    assert amont_reverse_proxy(caddyfile) == f"runtime:{PORT_CONTENEUR}"
    assert caddyfile.count("reverse_proxy") == 1
    for interdit in CIBLES_INTERDITES:
        assert interdit not in caddyfile, f"cible interdite présente : {interdit}"


# --- Couture 2 : surface HTTP du cockpit (derrière le proxy) ---


class JournalRunner:
    """Transport runner qui journalise toute tentative d’appel amont."""

    def __init__(self):
        self.requetes: list[httpx.Request] = []

    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url="http://runner:8788",
            transport=httpx.MockTransport(self._repondre),
        )

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        return httpx.Response(503, json={"detail": "runner injoignable en test d’échappement"})


@pytest.fixture
def surface(tmp_path):
    """Cockpit authentifié + runner journalisé (aucune sortie LAN réelle)."""
    journal = JournalRunner()
    app = creer_app(
        registry=tmp_path / "repos.toml",
        jeton="",
        jobs=tmp_path / "jobs",
        runner=journal.client(),
        env={},
    )
    definir(tmp_path, LOGIN, MOT_DE_PASSE)
    client = TestClient(app)
    assert (
        client.post(
            "/api/cockpit/login",
            json={"login": LOGIN, "password": MOT_DE_PASSE},
        ).status_code
        == 204
    )
    return client, journal


def test_surface_n_expose_pas_de_route_proxy_ni_vers_le_runner(surface):
    """Chemins style open-proxy / API runner : inaccessibles depuis la surface servie."""
    client, journal = surface
    tentatives = (
        "/proxy",
        "/forward",
        "/api/proxy",
        "/api/forward",
        "/api/runner",
        # Forme API runner (sans préfixe /api) : ne doit pas traverser vers le runner.
        "/sessions",
        "/modeles",
        "/sessions/x/terminal",
    )
    for chemin in tentatives:
        reponse = client.get(chemin)
        assert reponse.status_code in (404, 405, 401, 302), (
            f"{chemin} → {reponse.status_code} (échappement possible)"
        )
        # Pas de corps runner (ex. liste de modèles / session runner).
        corps = reponse.text.lower()
        assert "wap-runner" not in corps
        assert '"modeles"' not in corps or chemin.startswith("/api/")

    assert journal.requetes == [], "le runtime a contacté le runner hors flux cockpit"


def test_demande_http_ne_redirige_pas_le_runtime_vers_le_lan(surface):
    """Headers / corps hostiles : le client runner reste borné à son base_url Compose."""
    client, journal = surface
    entetes_hostiles = {
        "Host": "192.168.1.50",
        "X-Forwarded-Host": "10.0.0.1",
        "X-Forwarded-For": "8.8.8.8",
        "Forwarded": "host=172.16.0.1",
        "Origin": "http://192.168.1.50",
    }
    # Lecture API : ne doit pas déclencher d’appel runner ni fuite LAN.
    reponse = client.get("/api/repos", headers=entetes_hostiles)
    assert reponse.status_code == 200
    assert journal.requetes == []

    # Lancement avec URL cible injectée : champs hors contrat ignorés / refusés.
    reponse = client.post(
        "/api/sessions",
        headers={**entetes_hostiles, "Origin": "http://testserver"},
        json={
            "repo": "o/r",
            "agent": "claude",
            "branche": "main",
            "url": "http://192.168.1.50:8788/sessions",
            "runner": "http://runner:8788",
            "target": "http://10.0.0.1/",
            "base_url": "http://169.254.169.254/",
        },
    )
    # 422 (repo/agent) ou 403 — jamais un 2xx qui aurait relayé vers le LAN.
    assert reponse.status_code in (403, 422, 404, 502)
    for requete in journal.requetes:
        assert requete.url.host == "runner"
        assert requete.url.port == 8788
        assert requete.url.scheme == "http"
