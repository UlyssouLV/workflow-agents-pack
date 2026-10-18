"""Helpers partagés : dépôt pack local, home d’instance, Compose (tests 0.6.0+)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from wap_runtime.instance import preparer_instance

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def git(*args, cwd) -> str:
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
    config = instance / "config.toml"
    texte = config.read_text()
    ligne = f"{cle} = {json.dumps(valeur)}"
    if re.search(rf"^{re.escape(cle)} = ", texte, re.MULTILINE):
        config.write_text(
            re.sub(rf"^{re.escape(cle)} = .*$", ligne, texte, flags=re.MULTILINE)
        )
    else:
        config.write_text(texte + ligne + "\n")


def activer_exposition(instance: Path) -> None:
    ecrire_cle(instance, "exposition", True)


def service(compose: str, nom: str) -> str:
    blocs = re.split(r"^  (?=\S)", compose.split("\nservices:\n", 1)[1], flags=re.MULTILINE)
    return next(b for b in blocs if b.startswith(f"{nom}:"))


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
