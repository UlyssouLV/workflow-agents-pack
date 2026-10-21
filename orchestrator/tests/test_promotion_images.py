"""Promotion (ADR 0013) : la Release `orchestrator-vX.Y.Z` retaggue `:sha-<sha>` sans rebuild."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "promouvoir-images-release.sh"
SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGES = ("ghcr.io/ulyssoulv/wap-runtime", "ghcr.io/ulyssoulv/wap-runner")


class Registre:
    """Faux `docker` sur le PATH : `buildx imagetools` journalisé, `inspect` échoue pour les absentes."""

    def __init__(self, tmp_path: Path):
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.appels = tmp_path / "appels.log"
        self.absentes = tmp_path / "absentes"
        self.absentes.write_text("")
        docker = self.bin / "docker"
        docker.write_text(
            f'#!/bin/sh\necho "docker $*" >> "{self.appels}"\n'
            f'if [ "$3" = inspect ] && grep -qxF "$4" "{self.absentes}"; then\n'
            '    echo "ERROR: $4: not found" >&2; exit 1\nfi\nexit 0\n'
        )
        docker.chmod(0o755)

    def sans(self, reference: str) -> None:
        with self.absentes.open("a") as f:
            f.write(reference + "\n")

    def promouvoir(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env={"PATH": f"{self.bin}:/usr/bin:/bin"},
        )

    def creations(self) -> list[str]:
        if not self.appels.exists():
            return []
        return [l for l in self.appels.read_text().splitlines() if " imagetools create " in l]


@pytest.fixture
def registre(tmp_path):
    return Registre(tmp_path)


def test_promouvoir_est_un_script_bash_valide():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck absent")
def test_promouvoir_passe_shellcheck():
    subprocess.run(["shellcheck", str(SCRIPT)], check=True)


def test_promotion_retaggue_le_digest_du_sha_en_version_et_latest(registre):
    resultat = registre.promouvoir("orchestrator-v0.7.1", SHA)

    assert resultat.returncode == 0, resultat.stderr
    assert registre.creations() == [
        f"docker buildx imagetools create --tag {image}:0.7.1 --tag {image}:latest {image}:sha-{SHA}"
        for image in IMAGES
    ]
    assert "build " not in registre.appels.read_text()


@pytest.mark.parametrize(
    "etiquette",
    ["v0.7.1", "orchestrator-v0.7", "orchestrator-v0.7.1-rc1", "orchestrator-v0.7.1 ", "0.7.1", ""],
)
def test_promotion_refuse_une_etiquette_hors_orchestrator_vXYZ(registre, etiquette):
    resultat = registre.promouvoir(etiquette, SHA)

    assert resultat.returncode != 0
    assert "orchestrator-vX.Y.Z" in resultat.stderr
    assert not registre.appels.exists()


@pytest.mark.parametrize("image", IMAGES)
def test_promotion_sans_image_au_sha_echoue_sans_creer_de_tag(registre, image):
    registre.sans(f"{image}:sha-{SHA}")

    resultat = registre.promouvoir("orchestrator-v0.7.1", SHA)

    assert resultat.returncode != 0
    assert f"{image}:sha-{SHA}" in resultat.stderr
    assert "job `images`" in resultat.stderr
    assert registre.creations() == []


def test_promotion_refuse_un_sha_qui_n_est_pas_un_commit_complet(registre):
    resultat = registre.promouvoir("orchestrator-v0.7.1", "abc123")

    assert resultat.returncode != 0
    assert not registre.appels.exists()
