"""Exposition web opt-in : Caddy Compose, CLI on/off (ADR 0011, #93)."""

import os
import re
from pathlib import Path

import pytest

from wap_runtime.instance import preparer_instance

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def git(*args, cwd) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(depot: Path, message: str) -> str:
    (depot / "trace.txt").write_text(message)
    git("add", "trace.txt", cwd=depot)
    git("commit", "--quiet", "-m", message, cwd=depot)
    return git("rev-parse", "HEAD", cwd=depot)


@pytest.fixture
def depot_pack(tmp_path) -> Path:
    depot = tmp_path / "depot-pack"
    depot.mkdir()
    git("init", "--quiet", "--initial-branch=main", cwd=depot)
    git("config", "user.email", "test@example.com", cwd=depot)
    git("config", "user.name", "Test", cwd=depot)
    commit(depot, "main 1")
    return depot


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("WAP_PORT", raising=False)
    monkeypatch.delenv("WAP_PACK_REF", raising=False)
    return home


def passe(home: Path, depot_pack: Path, **env) -> Path:
    return preparer_instance(home, env=env, depot_pack=str(depot_pack), direct_url=None)


def lire_config(instance: Path) -> dict:
    return tomllib.loads((instance / "config.toml").read_text())


def service(compose: str, nom: str) -> str:
    blocs = re.split(r"^  (?=\S)", compose.split("\nservices:\n", 1)[1], flags=re.MULTILINE)
    return next(b for b in blocs if b.startswith(f"{nom}:"))


def activer_exposition(instance: Path) -> None:
    config = instance / "config.toml"
    texte = config.read_text()
    if "exposition" in texte:
        config.write_text(re.sub(r"^exposition = .+$", "exposition = true", texte, flags=re.M))
    else:
        config.write_text(texte + "exposition = true\n")


@pytest.fixture
def faux_docker(tmp_path, monkeypatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    journal = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(f'#!/bin/sh\necho "$*" >> "{journal}"\n')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return journal


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
    config = instance / "config.toml"
    texte = config.read_text()
    if "domaine" in texte:
        config.write_text(re.sub(r"^domaine = .+$", 'domaine = "cockpit.exemple.test"', texte, flags=re.M))
    else:
        config.write_text(texte + 'domaine = "cockpit.exemple.test"\n')
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
    assert "compose" in journal and "up" in journal

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
