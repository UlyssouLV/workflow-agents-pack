"""`wap-runtime setup` : socle → instance → `docker compose up -d --build` → `/health`."""

import os
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from wap_runtime.provisionnement import demarrer_instance, setup

DEBIAN_12 = "ID=debian\nVERSION_ID=\"12\"\nVERSION_CODENAME=bookworm\n"
INSTALL_SH = Path(__file__).resolve().parents[1] / "install.sh"


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Hote:
    """Machine hôte jouée par un PATH de faux binaires qui journalisent leurs appels.

    Le faux `docker compose … up` lance le vrai service HTTP en arrière-plan : `/health`
    ne répond que si Compose a été démarré.
    """

    def __init__(self, tmp_path: Path):
        self.racine = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.appels = tmp_path / "appels.log"
        self.pid = tmp_path / "runtime.pid"
        self.home = tmp_path / "home-orchestrator"
        self.home.mkdir()
        self.journal = tmp_path / "log" / "install.log"
        self.os_release = tmp_path / "os-release"
        self.os_release.write_text(DEBIAN_12)
        self.port = port_libre()
        self.env = {"PATH": str(self.bin), "WAP_PORT": str(self.port)}
        for nom in ("systemctl", "gh", "curl", "claude", "agent", "useradd", "usermod"):
            self.binaire(nom)
        self.binaire("runuser", 'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"')
        # Le clone réel est couvert par test_instance : ici on ne fait que le simuler.
        self.binaire(
            "git",
            'if [ "$1" = clone ]; then for a; do d="$a"; done; /bin/mkdir -p "$d/.git"; fi',
        )
        self.utilisateur_absent()
        self.docker_qui_demarre()

    def binaire(self, nom: str, script: str = "exit 0") -> None:
        chemin = self.bin / nom
        chemin.write_text(f'#!/bin/sh\necho "{nom} $*" >> "{self.appels}"\n{script}\n')
        chemin.chmod(0o755)

    def utilisateur_absent(self) -> None:
        self.binaire("id", "exit 1")

    def utilisateur_pret(self) -> None:
        self.binaire("id", 'echo "orchestrator docker"')

    def docker_qui_demarre(self) -> None:
        serveur = (
            f"{sys.executable} -c 'from wap_runtime.cli import main; "
            f'main(["serve", "--port", "{self.port}"])\''
        )
        self.binaire(
            "docker",
            'case "$*" in *" up "*)\n'
            f'  {serveur} > /dev/null 2>&1 < /dev/null &\n'
            f'  echo $! > "{self.pid}" ;;\n'
            "esac",
        )

    def docker_muet(self) -> None:
        self.binaire("docker")

    def setup(self, **env) -> int:
        return setup(
            os_release=self.os_release,
            journal=self.journal,
            env={**self.env, **env},
            home_orchestrator=self.home,
        )

    def lignes_appels(self) -> list[str]:
        return self.appels.read_text().splitlines() if self.appels.exists() else []

    def arreter(self) -> None:
        if self.pid.exists():
            try:
                os.kill(int(self.pid.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.pid.unlink()


@pytest.fixture
def hote(tmp_path):
    h = Hote(tmp_path)
    yield h
    h.arreter()


def indice(lignes: list[str], debut: str) -> int:
    return next(i for i, ligne in enumerate(lignes) if ligne.startswith(debut))


def test_setup_enchaine_socle_instance_compose_puis_health(hote, capsys):
    code = hote.setup()

    sortie = capsys.readouterr().out
    assert code == 0, sortie
    lignes = hote.lignes_appels()
    instance = hote.home / ".wap-runtime"
    ordre = [
        indice(lignes, "useradd "),
        indice(lignes, "usermod "),
        indice(lignes, "runuser -u orchestrator -- "),
        indice(lignes, "git clone "),
        indice(lignes, f"docker compose -f {instance / 'compose.yaml'} up -d --build"),
    ]
    assert ordre == sorted(ordre)
    etapes = [ligne for ligne in sortie.splitlines() if ligne.startswith("→ ")]
    assert etapes[-3:] == ["→ instance", "→ docker compose up -d --build", "→ attente /health"]
    assert sortie.strip().splitlines()[-1].startswith("OK")
    assert f"127.0.0.1:{hote.port}" in sortie.strip().splitlines()[-1]


def test_setup_journalise_les_etapes_de_l_instance(hote):
    assert hote.setup() == 0

    journal = hote.journal.read_text()
    for etape in ("instance", "docker compose up -d --build", "attente /health"):
        assert f"→ {etape}" in journal


def test_second_setup_sur_une_machine_prete_ne_touche_ni_au_socle_ni_aux_secrets(hote):
    assert hote.setup() == 0
    hote.arreter()
    secrets = hote.home / ".wap-runtime" / "secrets.env"
    secrets.write_text("GH_TOKEN=garde-moi\n")
    avant = secrets.stat().st_mtime_ns
    hote.utilisateur_pret()
    hote.appels.unlink()

    assert hote.setup() == 0

    lignes = hote.lignes_appels()
    assert not any(ligne.startswith(("useradd", "usermod", "curl", "apt-get")) for ligne in lignes)
    assert secrets.read_text() == "GH_TOKEN=garde-moi\n"
    assert secrets.stat().st_mtime_ns == avant
    assert any(" up -d --build" in ligne for ligne in lignes)


def test_echec_du_socle_arrete_avant_l_instance(hote, capsys):
    hote.binaire("useradd", "exit 9")

    code = hote.setup()

    assert code != 0
    assert not (hote.home / ".wap-runtime").exists()
    assert "« utilisateur orchestrator »" in capsys.readouterr().out


def test_health_qui_ne_repond_pas_avant_le_delai_echoue_en_nommant_l_etape(
    hote, monkeypatch, capsys
):
    hote.docker_muet()
    monkeypatch.setenv("PATH", str(hote.bin))

    code = demarrer_instance(hote.home, env=hote.env, delai=0.5)

    sortie = capsys.readouterr().out
    assert code != 0
    assert "KO — l’étape « attente /health » a échoué" in sortie
    assert f"127.0.0.1:{hote.port}" in sortie


def test_compose_qui_echoue_nomme_l_etape_et_n_attend_pas_health(hote, monkeypatch, capsys):
    hote.binaire("docker", 'case "$*" in *" up "*) exit 3 ;; esac')
    monkeypatch.setenv("PATH", str(hote.bin))

    code = demarrer_instance(hote.home, env=hote.env, delai=30)

    sortie = capsys.readouterr().out
    assert code != 0
    assert "KO — l’étape « docker compose up -d --build » a échoué" in sortie
    assert "→ attente /health" not in sortie


def test_instance_qui_echoue_nomme_l_etape(hote, monkeypatch, capsys):
    monkeypatch.setenv("PATH", str(hote.bin))

    code = demarrer_instance(hote.home, env={**hote.env, "WAP_PORT": "pas-un-port"})

    sortie = capsys.readouterr().out
    assert code != 0
    assert "KO — l’étape « instance » a échoué" in sortie
    assert "docker" not in "".join(hote.lignes_appels())


def test_wap_runtime_setup_refuse_de_tourner_sans_root(monkeypatch, capsys):
    from wap_runtime.cli import main

    monkeypatch.setattr(os, "geteuid", lambda: 1000)

    assert main(["setup"]) != 0
    assert "sudo" in capsys.readouterr().out


def test_install_sh_est_un_script_bash_valide():
    subprocess.run(["bash", "-n", str(INSTALL_SH)], check=True)


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck absent")
def test_install_sh_passe_shellcheck():
    subprocess.run(["shellcheck", str(INSTALL_SH)], check=True)


def test_install_sh_refuse_de_tourner_sans_root(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("le test doit tourner sans root")
    resultat = subprocess.run(
        ["bash", str(INSTALL_SH)], capture_output=True, text=True, cwd=tmp_path
    )

    assert resultat.returncode != 0
    assert "| sudo bash" in resultat.stderr
