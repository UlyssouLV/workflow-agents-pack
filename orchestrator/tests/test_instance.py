"""Instance `~/.wap-runtime/` : création, idempotence, Compose, pack, `wap-runtime uninstall`."""

import os
import re
import stat
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
    """Dépôt git local qui joue le pack : `main` et une branche `autre`."""
    depot = tmp_path / "depot-pack"
    depot.mkdir()
    git("init", "--quiet", "--initial-branch=main", cwd=depot)
    git("config", "user.email", "test@example.com", cwd=depot)
    git("config", "user.name", "Test", cwd=depot)
    commit(depot, "main 1")
    git("branch", "autre", cwd=depot)
    git("checkout", "--quiet", "autre", cwd=depot)
    commit(depot, "autre 1")
    git("checkout", "--quiet", "main", cwd=depot)
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
    return preparer_instance(home, env=env, depot_pack=str(depot_pack))


def lire_config(instance: Path) -> dict:
    return tomllib.loads((instance / "config.toml").read_text())


def test_premiere_passe_sur_un_home_vide_cree_les_quatre_elements(home, depot_pack):
    instance = passe(home, depot_pack)

    assert instance == home / ".wap-runtime"
    for nom in ("config.toml", "secrets.env", "compose.yaml", "pack"):
        assert (instance / nom).exists(), nom
    secrets = instance / "secrets.env"
    assert secrets.read_text() == ""
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o600


def test_config_par_defaut(home, depot_pack):
    from wap_runtime import __version__

    instance = passe(home, depot_pack)

    assert lire_config(instance) == {
        "port": 8787,
        "pack_ref": "main",
        "pack_path": str(instance / "pack"),
        "version": __version__,
    }


def test_wap_port_et_wap_pack_ref_s_appliquent_a_la_creation(home, depot_pack):
    instance = passe(home, depot_pack, WAP_PORT="9001", WAP_PACK_REF="autre")

    config = lire_config(instance)
    assert config["port"] == 9001
    assert config["pack_ref"] == "autre"


def test_wap_port_invalide_est_refuse(home, depot_pack):
    with pytest.raises(ValueError, match="WAP_PORT"):
        passe(home, depot_pack, WAP_PORT="huit")


def test_seconde_passe_garde_secrets_et_valeur_editee_et_complete_une_cle(
    home, depot_pack
):
    instance = passe(home, depot_pack)
    secrets = instance / "secrets.env"
    secrets.write_text("GH_TOKEN=secret\n")
    config = instance / "config.toml"
    lignes = config.read_text().splitlines()
    lignes = [
        "port = 9100" if ligne.startswith("port") else ligne
        for ligne in lignes
        if not ligne.startswith("pack_ref")
    ]
    config.write_text("# mon commentaire\n" + "\n".join(lignes) + "\n")

    passe(home, depot_pack, WAP_PORT="1234")

    assert secrets.read_text() == "GH_TOKEN=secret\n"
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o600
    texte = config.read_text()
    assert texte.startswith("# mon commentaire\n")
    valeurs = lire_config(instance)
    assert valeurs["port"] == 9100
    assert valeurs["pack_ref"] == "main"


def test_cle_manquante_ajoutee_avant_une_table(home, depot_pack):
    instance = passe(home, depot_pack)
    config = instance / "config.toml"
    lignes = [
        ligne for ligne in config.read_text().splitlines() if not ligne.startswith("version")
    ]
    config.write_text("\n".join(lignes) + "\n\n[perso]\ncle = 1\n")

    passe(home, depot_pack)

    valeurs = lire_config(instance)
    assert "version" in valeurs
    assert valeurs["perso"] == {"cle": 1}


def test_compose_publie_sur_localhost_avec_restart_unless_stopped(home, depot_pack):
    instance = passe(home, depot_pack, WAP_PORT="9002")

    compose = (instance / "compose.yaml").read_text()
    assert "runtime:" in compose
    assert "dockerfile: Dockerfile" in compose
    assert '"127.0.0.1:9002:8787"' in compose
    assert "restart: unless-stopped" in compose


def test_compose_regenere_depuis_config(home, depot_pack):
    instance = passe(home, depot_pack)
    config = instance / "config.toml"
    config.write_text(config.read_text().replace("port = 8787", "port = 9200"))
    (instance / "compose.yaml").write_text("bricolé\n")

    passe(home, depot_pack)

    assert '"127.0.0.1:9200:8787"' in (instance / "compose.yaml").read_text()


def test_pack_clone_puis_aligne_sur_pack_ref(home, depot_pack):
    instance = passe(home, depot_pack)
    pack = instance / "pack"
    assert git("rev-parse", "HEAD", cwd=pack) == git("rev-parse", "main", cwd=depot_pack)

    nouveau = commit(depot_pack, "main 2")
    (pack / "trace.txt").write_text("modif locale")
    passe(home, depot_pack)
    assert git("rev-parse", "HEAD", cwd=pack) == nouveau
    assert (pack / "trace.txt").read_text() == "main 2"

    config = instance / "config.toml"
    config.write_text(config.read_text().replace('"main"', '"autre"'))
    passe(home, depot_pack)
    assert git("rev-parse", "HEAD", cwd=pack) == git("rev-parse", "autre", cwd=depot_pack)


@pytest.fixture
def faux_docker(tmp_path, monkeypatch) -> Path:
    """Faux `docker` en tête du PATH : note ses arguments et son répertoire."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    journal = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(f'#!/bin/sh\necho "$*" >> "{journal}"\n')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return journal


def test_uninstall_appelle_compose_down_et_garde_l_instance(
    home, depot_pack, faux_docker
):
    from wap_runtime.cli import main

    instance = passe(home, depot_pack)

    assert main(["uninstall"]) == 0

    appel = faux_docker.read_text().strip()
    assert appel.startswith("compose")
    assert f"{instance / 'compose.yaml'}" in appel
    assert appel.endswith("down")
    assert (instance / "config.toml").exists()


def test_uninstall_purge_supprime_l_instance(home, depot_pack, faux_docker):
    from wap_runtime.cli import main

    instance = passe(home, depot_pack)

    assert main(["uninstall", "--purge"]) == 0

    assert "down" in faux_docker.read_text()
    assert not instance.exists()


def test_uninstall_sans_instance_ne_fait_rien(home, faux_docker, capsys):
    from wap_runtime.cli import main

    assert main(["uninstall", "--purge"]) == 0

    assert not faux_docker.exists()
    assert "aucune instance" in capsys.readouterr().out.lower()


def test_uninstall_echoue_si_compose_down_echoue(home, depot_pack, faux_docker):
    from wap_runtime.cli import main

    instance = passe(home, depot_pack)
    docker = Path(os.environ["PATH"].split(os.pathsep)[0]) / "docker"
    docker.write_text("#!/bin/sh\nexit 3\n")

    assert main(["uninstall", "--purge"]) != 0

    assert instance.exists()


def test_uninstall_en_root_retire_l_instance_d_orchestrator(
    tmp_path, home, depot_pack, faux_docker, monkeypatch
):
    from wap_runtime import cli

    instance = passe(home, depot_pack)
    monkeypatch.setenv("HOME", str(tmp_path / "root"))
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "HOME_UTILISATEUR", home)

    assert cli.main(["uninstall", "--purge"]) == 0

    assert "down" in faux_docker.read_text()
    assert not instance.exists()


def test_compose_monte_l_instance_et_donc_repos_toml_en_lecture_seule(home, depot_pack):
    instance = passe(home, depot_pack)

    compose = (instance / "compose.yaml").read_text()
    # Le dossier, pas le fichier : un bind mount de fichier absent créerait un dossier
    # `repos.toml` sur l’hôte, et ne verrait pas un fichier remplacé.
    assert '- ".:/instance:ro"' in compose
    assert "WAP_INSTANCE: /instance" in compose


def test_une_passe_ne_cree_ni_ne_reecrit_repos_toml(home, depot_pack):
    instance = passe(home, depot_pack)
    assert not (instance / "repos.toml").exists()

    registry = instance / "repos.toml"
    registry.write_text('[[repos]]\nslug = "mon-org/mon-repo"\n')
    avant = registry.stat().st_mtime_ns

    passe(home, depot_pack)

    assert registry.read_text() == '[[repos]]\nslug = "mon-org/mon-repo"\n'
    assert registry.stat().st_mtime_ns == avant


def service(compose: str, nom: str) -> str:
    """Le bloc d’un service : de `  nom:` jusqu’au service suivant."""
    blocs = re.split(r"^  (?=\S)", compose.split("\nservices:\n", 1)[1], flags=re.MULTILINE)
    return next(b for b in blocs if b.startswith(f"{nom}:"))


def test_compose_ajoute_runner_borne(home, depot_pack):
    instance = passe(home, depot_pack)

    runner = service((instance / "compose.yaml").read_text(), "runner")
    assert f'user: "{os.getuid()}:{os.getgid()}"' in runner
    assert "dockerfile: runner/Dockerfile" in runner
    assert "- secrets.env" in runner
    montages = re.findall(r'^      - "(.+)"$', runner, re.MULTILINE)
    assert sorted(montages) == [
        "./clones:/clones",
        "./jobs:/jobs",
        "./runner-home:/home/runner",
    ]
    assert "HOME: /home/runner" in runner
    assert "docker.sock" not in runner
    assert "ports:" not in runner
    assert "restart: unless-stopped" in runner


def test_runtime_inchange_par_le_runner(home, depot_pack):
    instance = passe(home, depot_pack, WAP_PORT="9003")

    runtime = service((instance / "compose.yaml").read_text(), "runtime")
    assert re.findall(r'^      - "(.+)"$', runtime, re.MULTILINE) == [
        ".:/instance:ro",
        "127.0.0.1:9003:8787",
    ]
    assert "user:" not in runtime


def test_dockerfile_du_runner_existe_dans_le_contexte_de_build(home, depot_pack):
    from wap_runtime import instance as module

    contexte = Path(module.__file__).parents[2]
    runner = service((passe(home, depot_pack) / "compose.yaml").read_text(), "runner")
    chemin = re.search(r"dockerfile: (\S+)", runner).group(1)
    assert module.CONTEXTE_RUNTIME in runner
    assert (contexte / chemin).is_file()


def test_dockerfile_du_runner_epingle_claude_et_les_skills_de_matt():
    from wap_runtime import instance as module

    dockerfile = (Path(module.__file__).parents[2] / "runner" / "Dockerfile").read_text()
    assert re.search(r"^ARG CLAUDE_VERSION=\d+\.\d+\.\d+$", dockerfile, re.MULTILINE)
    assert "@anthropic-ai/claude-code@${CLAUDE_VERSION}" in dockerfile
    assert re.search(r"^ARG SKILLS_MATT_COMMIT=[0-9a-f]{40}$", dockerfile, re.MULTILINE)
    assert 'checkout --quiet "${SKILLS_MATT_COMMIT}"' in dockerfile
    for outil in ("git", "gh", "tmux", "python3-venv", "https://cursor.com/install"):
        assert outil in dockerfile, outil


def test_setup_cree_les_dossiers_du_runner_sans_les_ecraser(home, depot_pack):
    instance = passe(home, depot_pack)
    for nom in ("clones", "jobs", "runner-home"):
        dossier = instance / nom
        assert dossier.is_dir(), nom
        assert dossier.stat().st_uid == os.getuid(), nom
        (dossier / "trace").write_text(nom)

    passe(home, depot_pack)

    for nom in ("clones", "jobs", "runner-home"):
        assert (instance / nom / "trace").read_text() == nom


def test_uninstall_purge_supprime_les_dossiers_du_runner(home, depot_pack, faux_docker):
    from wap_runtime.cli import main

    instance = passe(home, depot_pack)
    (instance / "jobs" / "1").mkdir()
    (instance / "runner-home" / ".claude.json").write_text("{}")

    assert main(["uninstall", "--purge"]) == 0

    for nom in ("clones", "jobs", "runner-home"):
        assert not (instance / nom).exists(), nom
