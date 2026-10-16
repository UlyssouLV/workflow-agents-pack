"""Front du cockpit servi par le runtime : `/`, `/repos/<owner>/<name>` et les assets construits."""

import pytest
from fastapi.testclient import TestClient

from wap_runtime.server import creer_app

INDEX = "<!doctype html><div id=\"racine\"></div>"


@pytest.fixture
def front(tmp_path):
    """Un build Vite minimal : `index.html` et un asset."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "index-abc.js").write_text("console.log('cockpit')")
    return dist


def client(tmp_path, front):
    return TestClient(creer_app(registry=tmp_path / "repos.toml", jeton="", front=front))


@pytest.mark.parametrize("chemin", ["/", "/repos/o/r", "/repos/mon-org/mon.repo"])
def test_les_routes_du_front_rendent_index_html(tmp_path, front, chemin):
    reponse = client(tmp_path, front).get(chemin)

    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/html")
    assert reponse.text == INDEX


def test_les_assets_construits_sont_servis(tmp_path, front):
    reponse = client(tmp_path, front).get("/assets/index-abc.js")

    assert reponse.status_code == 200
    assert reponse.text == "console.log('cockpit')"


def test_health_et_l_api_restent_servis_a_cote_du_front(tmp_path, front):
    c = client(tmp_path, front)

    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/api/repos").json()["repos"] == []
    assert c.get("/api/auth").json()["etat"] == "sans_token"


def test_une_route_inconnue_reste_en_404(tmp_path, front):
    c = client(tmp_path, front)

    assert c.get("/inconnue").status_code == 404
    assert c.get("/api/inconnue").status_code == 404
    assert c.get("/assets/absent.js").status_code == 404


def test_un_asset_hors_du_build_n_est_pas_servi(tmp_path, front):
    (tmp_path / "secret.txt").write_text("secret")

    reponse = client(tmp_path, front).get("/assets/..%2F..%2Fsecret.txt")

    assert "secret" not in reponse.text


def test_sans_build_du_front_seules_l_api_et_health_sont_servies(tmp_path):
    c = TestClient(creer_app(registry=tmp_path / "repos.toml", jeton="", front=tmp_path / "absent"))

    assert c.get("/health").status_code == 200
    assert c.get("/").status_code == 404


def test_le_front_par_defaut_vient_de_wap_cockpit(tmp_path, front, monkeypatch):
    monkeypatch.setenv("WAP_COCKPIT", str(front))

    c = TestClient(creer_app(registry=tmp_path / "repos.toml", jeton=""))

    assert c.get("/repos/o/r").text == INDEX
