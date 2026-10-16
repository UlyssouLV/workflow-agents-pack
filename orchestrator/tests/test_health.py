"""Healthcheck du runtime : `GET /health` et `wap-runtime health`."""

import json
import socket
import threading
import time
import urllib.request
from importlib.metadata import version

import pytest
import uvicorn

from wap_runtime.server import creer_app


@pytest.fixture
def serveur(tmp_path):
    """Le service FastAPI servi par uvicorn, comme dans l’image, sur un port libre."""
    config = uvicorn.Config(
        creer_app(registry=tmp_path / "repos.toml", jeton=""), host="127.0.0.1", port=0, log_level="warning"
    )
    srv = uvicorn.Server(config)
    fil = threading.Thread(target=srv.run, daemon=True)
    fil.start()
    while not srv.started:
        time.sleep(0.01)
    yield srv
    srv.should_exit = True
    fil.join()


def port_de(srv) -> int:
    return srv.servers[0].sockets[0].getsockname()[1]


def test_get_health_repond_ok_avec_la_version_du_paquet(serveur):
    with urllib.request.urlopen(f"http://127.0.0.1:{port_de(serveur)}/health") as rep:
        assert rep.status == 200
        assert rep.headers["Content-Type"] == "application/json"
        corps = json.loads(rep.read())
    assert corps == {"status": "ok", "version": version("wap-runtime")}


def port_ferme() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_wap_runtime_health_sort_en_0_quand_le_runtime_repond(serveur, capsys):
    from wap_runtime.cli import main

    code = main(["health", "--port", str(port_de(serveur))])

    sortie = capsys.readouterr().out
    assert code == 0
    assert len(sortie.strip().splitlines()) == 1
    assert "OK" in sortie


def test_wap_runtime_health_sort_en_non_zero_contre_un_port_ferme(capsys):
    from wap_runtime.cli import main

    port = port_ferme()
    code = main(["health", "--port", str(port)])

    sortie = capsys.readouterr().out
    assert code != 0
    assert len(sortie.strip().splitlines()) == 1
    assert f"127.0.0.1:{port}" in sortie


def test_wap_runtime_health_lit_le_port_de_l_instance(serveur, tmp_path, monkeypatch, capsys):
    from wap_runtime.cli import main

    instance = tmp_path / ".wap-runtime"
    instance.mkdir()
    (instance / "config.toml").write_text(f"port = {port_de(serveur)}\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert main(["health"]) == 0
    assert f"127.0.0.1:{port_de(serveur)}" in capsys.readouterr().out


def test_wap_runtime_health_en_root_lit_l_instance_d_orchestrator(
    serveur, tmp_path, monkeypatch, capsys
):
    from wap_runtime import cli

    home = tmp_path / "home-orchestrator"
    (home / ".wap-runtime").mkdir(parents=True)
    (home / ".wap-runtime" / "config.toml").write_text(f"port = {port_de(serveur)}\n")
    monkeypatch.setenv("HOME", str(tmp_path / "root"))
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "HOME_UTILISATEUR", home)

    assert cli.main(["health"]) == 0


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_wap_runtime_health_refuse_un_port_hors_plage(port, capsys):
    from wap_runtime.cli import main

    code = main(["health", "--port", str(port)])

    assert code != 0
    assert "port invalide" in capsys.readouterr().out
