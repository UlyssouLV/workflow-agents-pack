"""Exposition web opt-in : Caddy Compose, CLI on/off (ADR 0011, #93)."""

from helpers_pack import (
    activer_exposition,
    ecrire_cle,
    lire_config,
    passe,
    service,
)


def test_config_par_defaut_desactive_l_exposition(home, depot_pack):
    instance = passe(home, depot_pack)

    assert lire_config(instance)["exposition"] is False


def test_compose_sans_exposition_n_a_pas_de_caddy(home, depot_pack):
    instance = passe(home, depot_pack)

    compose = (instance / "compose.yaml").read_text()
    assert "caddy:" not in compose
    assert '"127.0.0.1:8787:8787"' in service(compose, "runtime")
    assert "ports:" not in service(compose, "runner")
    assert not (instance / "Caddyfile").exists()


def test_compose_avec_exposition_sans_domaine_borne_caddy_au_loopback(home, depot_pack):
    """Sans domaine : pas de HTTP public — 80/443 seulement sur 127.0.0.1."""
    instance = passe(home, depot_pack)
    activer_exposition(instance)
    passe(home, depot_pack)

    compose = (instance / "compose.yaml").read_text()
    runtime = service(compose, "runtime")
    runner = service(compose, "runner")
    caddy = service(compose, "caddy")

    assert "ports:" not in runtime
    assert "ports:" not in runner
    assert '"127.0.0.1:80:80"' in caddy
    assert '"127.0.0.1:443:443"' in caddy
    assert '"80:80"' not in caddy.replace('"127.0.0.1:80:80"', "")
    assert "image: caddy:" in caddy
    assert "restart: unless-stopped" in caddy


def test_compose_avec_exposition_et_domaine_publie_80_443(home, depot_pack):
    instance = passe(home, depot_pack)
    activer_exposition(instance)
    ecrire_cle(instance, "domaine", "cockpit.exemple.test")
    passe(home, depot_pack)

    caddy = service((instance / "compose.yaml").read_text(), "caddy")
    assert '"80:80"' in caddy
    assert '"443:443"' in caddy
    assert "127.0.0.1" not in caddy.split("ports:", 1)[1].split("volumes:", 1)[0]


def test_caddy_relaie_uniquement_vers_le_runtime_de_l_instance(home, depot_pack):
    instance = passe(home, depot_pack)
    activer_exposition(instance)
    passe(home, depot_pack)

    caddyfile = (instance / "Caddyfile").read_text()
    assert "reverse_proxy runtime:8787" in caddyfile
    assert "runner" not in caddyfile
    assert "*" not in caddyfile.split("reverse_proxy", 1)[1]


def test_cli_active_et_desactive_l_exposition(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main

    passe(home, depot_pack)

    assert main(["exposition", "on"]) == 0
    sortie_on = capsys.readouterr().out
    assert "OK — exposition web activée" in sortie_on
    assert "127.0.0.1" in sortie_on
    assert "pas de HTTP public" in sortie_on
    assert lire_config(home / ".wap-runtime")["exposition"] is True
    compose = (home / ".wap-runtime" / "compose.yaml").read_text()
    assert "caddy:" in compose
    assert "ports:" not in service(compose, "runtime")
    assert '"127.0.0.1:80:80"' in service(compose, "caddy")
    assert (home / ".wap-runtime" / "Caddyfile").is_file()
    journal = faux_docker.read_text()
    assert "compose" in journal
    assert "up" in journal

    assert main(["exposition", "off"]) == 0
    assert "OK — exposition web désactivée" in capsys.readouterr().out
    assert lire_config(home / ".wap-runtime")["exposition"] is False
    compose = (home / ".wap-runtime" / "compose.yaml").read_text()
    assert "caddy:" not in compose
    assert '"127.0.0.1:8787:8787"' in service(compose, "runtime")
    assert not (home / ".wap-runtime" / "Caddyfile").exists()


def test_cli_exposition_sans_instance_echoue(home, capsys):
    from wap_runtime.cli import main

    assert main(["exposition", "on"]) == 1
    assert "aucune instance" in capsys.readouterr().out
