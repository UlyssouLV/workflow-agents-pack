"""Identifiants cockpit + sessions serveur : CLI et stockage instance (ADR 0010, #90)."""

import io
import stat
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from wap_runtime.identifiants_cockpit import (
    creer_session_serveur,
    est_configure,
    session_serveur_valide,
    verifier,
)


@pytest.fixture
def instance(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    instance = home / ".wap-runtime"
    instance.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return instance


def cockpit_auth(*args: str, stdin: str = "", monkeypatch=None) -> int:
    from wap_runtime.cli import main

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return main(["cockpit-auth", *args])


def mode(chemin: Path) -> int:
    return stat.S_IMODE(chemin.stat().st_mode)


def test_sans_identifiants_le_cockpit_n_est_pas_configure(instance):
    assert est_configure(instance) is False


def test_cli_cree_les_identifiants_hashes_et_configure_le_cockpit(
    instance, capsys, monkeypatch
):
    assert (
        cockpit_auth(
            "--login", "ops", "--with-password", stdin="s3cret\n", monkeypatch=monkeypatch
        )
        == 0
    )

    assert "OK — identifiants cockpit créés" in capsys.readouterr().out
    assert est_configure(instance) is True
    chemin = instance / "cockpit-credentials.toml"
    assert mode(chemin) == 0o600
    data = tomllib.loads(chemin.read_text())
    assert data["login"] == "ops"
    assert "s3cret" not in chemin.read_text()
    assert data["password_hash"].startswith("scrypt$")
    assert "password" not in data
    assert verifier(instance, "ops", "s3cret") is True
    assert verifier(instance, "ops", "autre") is False


def test_cli_change_le_mot_de_passe_et_invalide_les_sessions(
    instance, capsys, monkeypatch
):
    assert (
        cockpit_auth(
            "--login", "ops", "--with-password", stdin="ancien\n", monkeypatch=monkeypatch
        )
        == 0
    )
    id_session = creer_session_serveur(instance)
    assert session_serveur_valide(instance, id_session) is True
    capsys.readouterr()

    assert (
        cockpit_auth(
            "--login", "ops", "--with-password", stdin="nouveau\n", monkeypatch=monkeypatch
        )
        == 0
    )

    sortie = capsys.readouterr().out
    assert "mot de passe cockpit changé" in sortie
    assert "sessions serveur invalidées" in sortie
    assert verifier(instance, "ops", "nouveau") is True
    assert verifier(instance, "ops", "ancien") is False
    assert session_serveur_valide(instance, id_session) is False
    assert "nouveau" not in (instance / "cockpit-credentials.toml").read_text()
    assert (instance / "cockpit-sessions.sqlite").is_file()


def test_sessions_serveur_vivent_dans_sqlite_sous_l_instance(instance):
    id_a = creer_session_serveur(instance)
    id_b = creer_session_serveur(instance)
    assert id_a != id_b
    assert session_serveur_valide(instance, id_a) is True
    assert session_serveur_valide(instance, id_b) is True
    assert session_serveur_valide(instance, "inconnu") is False
    assert mode(instance / "cockpit-sessions.sqlite") == 0o600
