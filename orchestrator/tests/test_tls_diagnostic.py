"""TLS / domaine + diagnostic CLI (ADR 0011, #94)."""

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


def ecrire_cle(instance: Path, cle: str, valeur) -> None:
    import json

    config = instance / "config.toml"
    texte = config.read_text()
    ligne = f"{cle} = {json.dumps(valeur)}"
    if re.search(rf"^{re.escape(cle)} = ", texte, re.MULTILINE):
        config.write_text(
            re.sub(rf"^{re.escape(cle)} = .*$", ligne, texte, flags=re.MULTILINE)
        )
    else:
        config.write_text(texte + ligne + "\n")


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


def test_avec_domaine_caddy_prend_le_chemin_https_lets_encrypt(home, depot_pack):
    instance = passe(home, depot_pack)
    ecrire_cle(instance, "exposition", True)
    ecrire_cle(instance, "domaine", "cockpit.exemple.test")
    passe(home, depot_pack)

    caddyfile = (instance / "Caddyfile").read_text()
    assert "cockpit.exemple.test" in caddyfile
    assert "reverse_proxy runtime:8787" in caddyfile
    # Pas de mode HTTP public clair : le site est nommé (TLS auto Caddy / Let’s Encrypt).
    assert not re.search(r"^:80\b", caddyfile, re.MULTILINE)
    compose = (instance / "compose.yaml").read_text()
    assert "./caddy-data:/data" in compose
    caddy = re.search(r"caddy:.*?(?=\n  \S|\Z)", compose, re.S)
    assert caddy is not None
    ports = caddy.group(0)
    assert '"80:80"' in ports
    assert '"443:443"' in ports
    assert "127.0.0.1" not in ports.split("ports:", 1)[1].split("volumes:", 1)[0]


def test_cli_domaine_regenerer_caddyfile_https(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main

    passe(home, depot_pack)
    assert main(["exposition", "on"]) == 0
    capsys.readouterr()

    assert main(["domaine", "cockpit.exemple.test"]) == 0
    assert "OK — domaine" in capsys.readouterr().out
    assert lire_config(home / ".wap-runtime")["domaine"] == "cockpit.exemple.test"
    caddyfile = (home / ".wap-runtime" / "Caddyfile").read_text()
    assert "cockpit.exemple.test {" in caddyfile
    assert not re.search(r"^:80\b", caddyfile, re.MULTILINE)


def test_diagnostic_separe_instance_et_operateur(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    assert main(["domaine", "cockpit.exemple.test"]) == 0
    capsys.readouterr()

    # Faux docker : `compose ps` → Caddy running (script enrichi pour ce test).
    bin_dir = Path(os.environ["PATH"].split(os.pathsep)[0])
    docker = bin_dir / "docker"
    journal = home.parent / "docker-diag.log"
    docker.write_text(
        f"""#!/bin/sh
echo "$*" >> "{journal}"
if echo "$*" | grep -q "compose.*ps"; then
  echo 'caddy running'
  exit 0
fi
exit 0
"""
    )
    docker.chmod(0o755)

    assert main(["diagnostic"]) == 0
    sortie = capsys.readouterr().out
    assert "Côté instance" in sortie
    assert "OK — Caddy" in sortie
    assert "OK — ports 80/443" in sortie
    assert "OK — identifiants cockpit" in sortie
    assert "Côté opérateur" in sortie
    assert "DNS" in sortie
    assert "NAT" in sortie
    assert "CGNAT" in sortie


def test_diagnostic_signale_reste_instance_sans_domaine(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    capsys.readouterr()

    code = main(["diagnostic"])
    sortie = capsys.readouterr().out
    assert code == 1
    assert "KO — aucun domaine" in sortie or "domaine" in sortie.lower()
    assert "HTTP public" in sortie or "non supporté" in sortie
    assert "Côté opérateur" in sortie
