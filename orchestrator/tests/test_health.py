"""Healthcheck du runtime : `GET /health` et `wap-runtime health`."""

import json
import socket
import threading
import urllib.request
from importlib.metadata import version

import pytest

from wap_runtime.server import creer_serveur


@pytest.fixture
def serveur():
    srv = creer_serveur("127.0.0.1", 0)
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def port_de(srv) -> int:
    return srv.server_address[1]


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
