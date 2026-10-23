"""`sudo wap-runtime update` : Release choisie, garde-fous, paquet, Compose, pull, recreate."""

from pathlib import Path

import pytest

from wap_runtime import cli
from wap_runtime.mise_a_jour import appliquer, mettre_a_jour
from wap_runtime.sessions import Sessions

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

PAQUET = "git+https://github.com/UlyssouLV/workflow-agents-pack@orchestrator-v{}#subdirectory=orchestrator"
# Images locales du faux `docker image ls` : l’ancienne version, d’autres services, un orphelin.
IMAGES_LOCALES = """\
ghcr.io/ulyssoulv/wap-runtime:0.7.1 aaa
ghcr.io/ulyssoulv/wap-runtime:0.8.0 bbb
ghcr.io/ulyssoulv/wap-runtime:<none> ccc
ghcr.io/ulyssoulv/wap-runner:0.7.1 ddd
ghcr.io/ulyssoulv/wap-runner:0.8.0 eee
"""


def release(tag: str, prerelease: bool = False, draft: bool = False) -> dict:
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft}


class Hote:
    """Hôte joué par un PATH de faux `docker`, `pipx` et `runuser` qui journalisent leurs appels."""

    def __init__(self, tmp_path: Path):
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.appels = tmp_path / "appels.log"
        self.journal = tmp_path / "log" / "update.log"
        self.home = tmp_path / "home-orchestrator"
        self.instance = self.home / ".wap-runtime"
        self.instance.mkdir(parents=True)
        (self.instance / "config.toml").write_text(
            'port = 8787\npack_ref = "main"\nversion = "0.7.1"\nexposition = false\ndomaine = ""\n'
        )
        (self.instance / "secrets.env").write_text("GH_TOKEN=secret\n")
        (self.instance / "repos.toml").write_text('[[repos]]\nslug = "o/r"\n')
        (self.instance / "jobs").mkdir()
        (self.instance / "clones").mkdir()
        self.releases = [
            release("orchestrator-v0.7.1"),
            release("orchestrator-v0.8.0"),
            release("orchestrator-v0.10.0-rc1"),
            release("orchestrator-v0.9.0", prerelease=True),
            release("orchestrator-v0.9.1", draft=True),
            release("v1.0.0"),
        ]
        self.images_publiees = None  # toutes
        self.binaire("pipx")
        self.binaire("runuser", 'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"')
        self.docker()

    def binaire(self, nom: str, script: str = "exit 0") -> None:
        chemin = self.bin / nom
        chemin.write_text(f'#!/bin/sh\necho "{nom} $*" >> "{self.appels}"\n{script}\n')
        chemin.chmod(0o755)

    def docker(self, pull: int = 0, up: int = 0, en_marche: str = "runtime\nrunner\ncaddy") -> None:
        self.binaire(
            "docker",
            'case "$*" in\n'
            f'  *" pull") exit {pull} ;;\n'
            f'  *" up -d --wait --force-recreate") exit {up} ;;\n'
            f'  *" ps --status running --services") printf "{en_marche}\\n" ;;\n'
            f'  "image ls"*) printf "{IMAGES_LOCALES}" ;;\n'
            "esac",
        )

    def update(self, force: bool = False) -> int:
        publiees = self.images_publiees
        return mettre_a_jour(
            home=self.home,
            force=force,
            env={"PATH": f"{self.bin}:/usr/bin:/bin"},
            releases=lambda: self.releases,
            image_existe=lambda image: publiees is None or image in publiees,
            journal=self.journal,
        )

    def lignes_appels(self) -> list[str]:
        return self.appels.read_text().splitlines() if self.appels.exists() else []

    def config(self) -> dict:
        return tomllib.loads((self.instance / "config.toml").read_text())

    def compose(self) -> str:
        return (self.instance / "compose.yaml").read_text()

    def session_ouverte(self, repo: str = "o/r") -> dict:
        return Sessions(self.instance / "jobs").creer(repo, 12, "claude", "claude")


@pytest.fixture
def hote(tmp_path):
    return Hote(tmp_path)


def test_succes_installe_le_paquet_au_tag_regenere_tire_recree_et_ecrit_la_version(hote, capsys):
    assert hote.update() == 0

    appels = hote.lignes_appels()
    pipx = next(a for a in appels if a.startswith("pipx "))
    assert pipx == f"pipx install --force {PAQUET.format('0.8.0')}"
    assert any(a.startswith("runuser -u orchestrator --") and "pipx install" in a for a in appels)
    compose = hote.compose()
    assert "image: ghcr.io/ulyssoulv/wap-runtime:0.8.0" in compose
    assert "image: ghcr.io/ulyssoulv/wap-runner:0.8.0" in compose
    docker = [a for a in appels if a.startswith("docker compose")]
    assert docker[0].endswith(" pull")
    assert docker[1].endswith(" up -d --wait --force-recreate")
    assert hote.config()["version"] == "0.8.0"
    assert "0.8.0" in capsys.readouterr().out


def test_succes_ne_supprime_que_les_anciennes_images_wap(hote):
    hote.update()

    suppressions = [a for a in hote.lignes_appels() if a.startswith("docker image rm")]
    assert suppressions == [
        "docker image rm ghcr.io/ulyssoulv/wap-runtime:0.7.1",
        "docker image rm ccc",
        "docker image rm ghcr.io/ulyssoulv/wap-runner:0.7.1",
    ]
    assert not any("prune" in a for a in hote.lignes_appels())


def test_succes_ne_touche_ni_aux_secrets_ni_au_registry_ni_aux_jobs(hote):
    session = Sessions(hote.instance / "jobs").creer("o/r", 1, "claude", "claude")
    Sessions(hote.instance / "jobs").clore(session["id"], 0)
    (hote.instance / "clones" / "trace").write_text("x")

    assert hote.update() == 0

    assert (hote.instance / "secrets.env").read_text() == "GH_TOKEN=secret\n"
    assert (hote.instance / "repos.toml").read_text() == '[[repos]]\nslug = "o/r"\n'
    assert (hote.instance / "clones" / "trace").read_text() == "x"
    assert Sessions(hote.instance / "jobs").lire(session["id"])["etat"] == "terminée"
    assert hote.config()["pack_ref"] == "main"


def test_deja_a_jour_rend_2_sans_rien_toucher(hote, capsys):
    hote.releases = [release("orchestrator-v0.7.1"), release("orchestrator-v0.7.0")]

    assert hote.update() == 2

    assert hote.lignes_appels() == []
    assert "rien à faire" in capsys.readouterr().out


def test_choisit_le_semver_le_plus_haut_et_pas_l_ordre_alphabetique(hote):
    hote.releases = [release("orchestrator-v0.9.0"), release("orchestrator-v0.10.0")]

    assert hote.update() == 0

    assert hote.config()["version"] == "0.10.0"


def test_une_prerelease_plus_haute_est_ignoree(hote):
    hote.releases = [release("orchestrator-v0.7.1"), release("orchestrator-v0.8.0", prerelease=True)]

    assert hote.update() == 2


@pytest.mark.parametrize("version", ["feat/runtime-orchestrator", "abc1234", "0.7"])
def test_version_locale_non_semver_rend_2_avec_le_message(hote, capsys, version):
    texte = (hote.instance / "config.toml").read_text().replace('"0.7.1"', f'"{version}"')
    (hote.instance / "config.toml").write_text(texte)

    assert hote.update() == 2

    assert "pas une version de production : rien à faire" in capsys.readouterr().out
    assert hote.lignes_appels() == []


def test_images_absentes_sur_ghcr_rend_2_sans_rien_toucher(hote, capsys):
    hote.images_publiees = {"ghcr.io/ulyssoulv/wap-runtime:0.8.0"}

    assert hote.update() == 2

    assert hote.lignes_appels() == []
    assert hote.config()["version"] == "0.7.1"
    assert not (hote.instance / "compose.yaml").exists()
    assert "wap-runner:0.8.0" in capsys.readouterr().out


def test_session_ouverte_refuse_avec_la_liste(hote, capsys):
    session = hote.session_ouverte()

    assert hote.update() == 1

    sortie = capsys.readouterr().out
    assert session["id"] in sortie
    assert "--force" in sortie
    assert hote.lignes_appels() == []


def test_session_ouverte_avec_force_met_a_jour(hote):
    hote.session_ouverte()

    assert hote.update(force=True) == 0

    assert hote.config()["version"] == "0.8.0"


def test_echec_du_pull_rend_1_journalise_sans_rollback(hote, capsys):
    hote.docker(pull=1)

    assert hote.update() == 1

    assert "pull" in capsys.readouterr().out
    assert not any("up -d" in a for a in hote.lignes_appels())
    assert not any(a.startswith("docker image rm") for a in hote.lignes_appels())
    assert hote.config()["version"] == "0.7.1"
    assert "pull" in hote.journal.read_text()


def test_echec_du_recreate_rend_1(hote):
    hote.docker(up=1, en_marche="runner")

    assert hote.update() == 1

    assert hote.config()["version"] == "0.7.1"
    assert not any(a.startswith("docker image rm") for a in hote.lignes_appels())
    assert "KO" in hote.journal.read_text()


def test_caddy_en_echec_runtime_et_runner_sains_rend_0_avec_avertissement(hote, capsys):
    hote.docker(up=1, en_marche="runtime\nrunner")

    assert hote.update() == 0

    assert "Caddy" in capsys.readouterr().out
    assert hote.config()["version"] == "0.8.0"


def test_releases_injoignables_rend_1(hote, capsys):
    def injoignable():
        raise OSError("réseau")

    code = mettre_a_jour(
        home=hote.home,
        env={"PATH": str(hote.bin)},
        releases=injoignable,
        image_existe=lambda image: True,
        journal=hote.journal,
    )

    assert code == 1
    assert "Releases" in capsys.readouterr().out


def test_update_refuse_de_tourner_sans_root(monkeypatch, capsys):
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)

    assert cli.main(["update"]) == 1

    assert "sudo wap-runtime update" in capsys.readouterr().out


# Partie instance, appelée ici dans le processus de test (en vrai : relancée par `runuser`).


@pytest.fixture
def hote_instance(hote, monkeypatch):
    monkeypatch.setenv("PATH", f"{hote.bin}:/usr/bin:/bin")
    return hote


def test_appliquer_regenere_tire_recree_ecrit_la_version_et_supprime_les_anciennes(hote_instance, capsys):
    assert appliquer(hote_instance.home, "0.8.0") == 0

    assert "image: ghcr.io/ulyssoulv/wap-runner:0.8.0" in hote_instance.compose()
    docker = [a for a in hote_instance.lignes_appels() if a.startswith("docker ")]
    assert docker[0].endswith(" pull")
    assert docker[1].endswith(" up -d --wait --force-recreate")
    assert [a for a in docker if a.startswith("docker image rm")] == [
        "docker image rm ghcr.io/ulyssoulv/wap-runtime:0.7.1",
        "docker image rm ccc",
        "docker image rm ghcr.io/ulyssoulv/wap-runner:0.7.1",
    ]
    assert hote_instance.config()["version"] == "0.8.0"
    assert "OK — instance en version 0.8.0" in capsys.readouterr().out


@pytest.mark.parametrize("version", ["../0.8.0", "0.8.0\nport = 1", "latest"])
def test_appliquer_refuse_une_version_non_semver_sans_rien_toucher(hote_instance, capsys, version):
    assert appliquer(hote_instance.home, version) == 1

    assert hote_instance.lignes_appels() == []
    assert hote_instance.config()["version"] == "0.7.1"
    assert "« version »" in capsys.readouterr().out


def test_appliquer_echec_du_pull_rend_1_sans_recreate(hote_instance, capsys):
    hote_instance.docker(pull=1)

    assert appliquer(hote_instance.home, "0.8.0") == 1

    assert not any("up -d" in a for a in hote_instance.lignes_appels())
    assert hote_instance.config()["version"] == "0.7.1"
    assert "docker compose pull" in capsys.readouterr().out


def test_appliquer_runner_absent_rend_1(hote_instance, capsys):
    hote_instance.docker(up=1, en_marche="runtime")

    assert appliquer(hote_instance.home, "0.8.0") == 1

    assert "runner ne tourne pas" in capsys.readouterr().out
    assert hote_instance.config()["version"] == "0.7.1"


def test_appliquer_caddy_absent_rend_0_avec_avertissement(hote_instance, capsys):
    hote_instance.docker(up=1, en_marche="runtime\nrunner")

    assert appliquer(hote_instance.home, "0.8.0") == 0

    assert "Caddy" in capsys.readouterr().out


def test_appliquer_image_non_supprimee_est_signalee(hote_instance, capsys):
    hote_instance.binaire(
        "docker",
        'case "$*" in\n'
        '  "image ls"*) printf "ghcr.io/ulyssoulv/wap-runner:0.7.1 ddd\\n" ;;\n'
        '  "image rm"*) exit 1 ;;\n'
        '  *" ps --status running --services") printf "runtime\\nrunner\\n" ;;\n'
        "esac",
    )

    assert appliquer(hote_instance.home, "0.8.0") == 0

    assert "image ghcr.io/ulyssoulv/wap-runner:0.7.1 non supprimée" in capsys.readouterr().out


def test_config_illisible_rend_1(hote, capsys):
    (hote.instance / "config.toml").write_text("version = \n")

    assert hote.update() == 1

    assert "config de l’instance illisible" in capsys.readouterr().out


def test_echec_du_paquet_rend_1_sans_relance(hote, capsys):
    hote.binaire("pipx", "exit 3")

    assert hote.update() == 1

    assert "pipx install" in capsys.readouterr().out
    assert not any("--instance-seule" in a for a in hote.lignes_appels())
