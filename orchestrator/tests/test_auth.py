"""Connexion GitHub de l’instance : `wap-runtime auth`, `--with-token`, `auth status` (ADR 0003)."""

import io
import os
import stat
from pathlib import Path

import pytest

# Faux `gh` : garde son token dans `$HOME/.config/gh/token`, comme le vrai garde sa
# connexion dans le HOME de l’utilisateur qui le lance. Un token valide commence par
# `gh` ou `github_pat_` ; `api user` rend `compte-<token>`.
FAUX_GH = """\
/bin/mkdir -p "$HOME/.config/gh"
case "$*" in
  "auth login"*--with-token*)
    read -r t
    case "$t" in
      gh*_* | github_pat_*) printf %s "$t" > "$HOME/.config/gh/token" ;;
      *) echo "error validating token" >&2; exit 1 ;;
    esac ;;
  "auth login"*) printf %s gho_device > "$HOME/.config/gh/token" ;;
  "auth token") /bin/cat "$HOME/.config/gh/token" 2>/dev/null || { echo "no oauth token" >&2; exit 1; } ;;
  "api user"*)
    case "$GH_TOKEN" in
      gh*_* | github_pat_*) echo "compte-$GH_TOKEN" ;;
      *) echo "HTTP 401: Bad credentials" >&2; exit 1 ;;
    esac ;;
esac
"""


class Faux:
    """PATH de faux `gh` et `docker` qui journalisent leurs appels (avec HOME et GH_TOKEN)."""

    def __init__(self, tmp_path: Path, monkeypatch):
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.appels = tmp_path / "appels.log"
        self.binaire("gh", FAUX_GH)
        self.binaire("docker")
        self.binaire("runuser", 'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"')
        monkeypatch.setenv("PATH", f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def binaire(self, nom: str, script: str = "exit 0") -> None:
        chemin = self.bin / nom
        chemin.write_text(
            f'#!/bin/sh\necho "{nom} $* | HOME=$HOME GH_TOKEN=${{GH_TOKEN:-}}" >> "{self.appels}"\n'
            f"{script}\n"
        )
        chemin.chmod(0o755)

    def lignes(self, debut: str = "") -> list[str]:
        if not self.appels.exists():
            return []
        return [l for l in self.appels.read_text().splitlines() if l.startswith(debut)]


@pytest.fixture
def faux(tmp_path, monkeypatch) -> Faux:
    return Faux(tmp_path, monkeypatch)


@pytest.fixture
def instance(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    instance = home / ".wap-runtime"
    instance.mkdir(parents=True)
    (instance / "compose.yaml").write_text("services: {}\n")
    secrets = instance / "secrets.env"
    secrets.touch(mode=0o600)
    monkeypatch.setenv("HOME", str(home))
    return instance


def auth(*args: str, stdin: str | None = None, monkeypatch=None) -> int:
    from wap_runtime.cli import main

    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return main(["auth", *args])


def mode(chemin: Path) -> int:
    return stat.S_IMODE(chemin.stat().st_mode)


def test_auth_lance_le_device_flow_copie_le_token_et_redemarre_le_service(
    faux, instance, capsys
):
    assert auth() == 0

    secrets = instance / "secrets.env"
    assert secrets.read_text() == "GH_TOKEN=gho_device\n"
    assert mode(secrets) == 0o600
    login = faux.lignes("gh auth login")
    assert len(login) == 1
    assert "--with-token" not in login[0]
    assert f"HOME={instance.parent} " in login[0]
    redemarrage = faux.lignes("docker ")
    assert len(redemarrage) == 1
    assert f"compose -f {instance / 'compose.yaml'} up -d --force-recreate runtime" in redemarrage[0]
    assert "compte-gho_device" in capsys.readouterr().out


def test_auth_garde_les_autres_lignes_de_secrets_env(faux, instance):
    (instance / "secrets.env").write_text("AUTRE=1\nGH_TOKEN=ancien\n# note\n")

    assert auth() == 0

    assert (instance / "secrets.env").read_text() == "AUTRE=1\n# note\nGH_TOKEN=gho_device\n"
    assert mode(instance / "secrets.env") == 0o600


def test_auth_with_token_lit_stdin_le_fait_valider_et_l_ecrit(faux, instance, monkeypatch):
    assert auth("--with-token", stdin="github_pat_fin\n", monkeypatch=monkeypatch) == 0

    assert (instance / "secrets.env").read_text() == "GH_TOKEN=github_pat_fin\n"
    assert len(faux.lignes("gh auth login --hostname github.com --with-token")) == 1
    assert faux.lignes("docker ")


def test_relancer_auth_remplace_le_token(faux, instance, monkeypatch):
    assert auth("--with-token", stdin="ghp_premier\n", monkeypatch=monkeypatch) == 0
    assert auth("--with-token", stdin="ghp_second\n", monkeypatch=monkeypatch) == 0

    assert (instance / "secrets.env").read_text() == "GH_TOKEN=ghp_second\n"


def test_gh_ne_voit_jamais_un_gh_token_de_l_environnement(faux, instance, monkeypatch):
    # Sinon `gh auth login` refuse de stocker, et `gh auth token` rend ce token-là.
    monkeypatch.setenv("GH_TOKEN", "ghp_environnement")

    assert auth() == 0

    assert all("GH_TOKEN=ghp_environnement" not in l for l in faux.lignes("gh auth"))
    assert (instance / "secrets.env").read_text() == "GH_TOKEN=gho_device\n"


@pytest.mark.parametrize(
    "gh, etape",
    [
        ('case "$*" in "auth login"*) echo "device flow annulé" >&2; exit 1 ;; esac\n' + FAUX_GH, "gh auth login"),
        ('case "$*" in "auth token") exit 4 ;; esac\n' + FAUX_GH, "gh auth token"),
        ('case "$*" in "api user"*) echo "HTTP 401" >&2; exit 1 ;; esac\n' + FAUX_GH, "gh api user"),
    ],
)
def test_gh_en_echec_nomme_l_etape_sans_toucher_secrets_env(faux, instance, capsys, gh, etape):
    (instance / "secrets.env").write_text("GH_TOKEN=ancien\nAUTRE=1\n")
    faux.binaire("gh", gh)

    assert auth() != 0

    assert f"« {etape} »" in capsys.readouterr().out
    assert (instance / "secrets.env").read_text() == "GH_TOKEN=ancien\nAUTRE=1\n"
    assert mode(instance / "secrets.env") == 0o600
    assert not faux.lignes("docker ")
    assert sorted(p.name for p in instance.iterdir()) == ["compose.yaml", "secrets.env"]


def test_with_token_refuse_par_gh_nomme_l_etape(faux, instance, capsys, monkeypatch):
    assert auth("--with-token", stdin="pas-un-token\n", monkeypatch=monkeypatch) != 0

    assert "« gh auth login »" in capsys.readouterr().out
    assert (instance / "secrets.env").read_text() == ""


def test_with_token_vide_est_refuse_sans_appeler_gh(faux, instance, capsys, monkeypatch):
    assert auth("--with-token", stdin="\n", monkeypatch=monkeypatch) != 0

    assert "stdin" in capsys.readouterr().out
    assert not faux.lignes("gh ")


def test_redemarrage_en_echec_nomme_l_etape(faux, instance, capsys):
    faux.binaire("docker", "exit 1")

    assert auth() != 0

    assert "« redémarrage du service runtime »" in capsys.readouterr().out


def test_status_non_connecte_sort_en_erreur(faux, instance, capsys):
    assert auth("status") != 0

    sortie = capsys.readouterr().out
    assert "non connecté" in sortie.lower()
    assert "sudo wap-runtime auth" in sortie


def test_status_connecte_affiche_le_compte(faux, instance, capsys, monkeypatch):
    auth("--with-token", stdin="ghp_abc\n", monkeypatch=monkeypatch)
    capsys.readouterr()

    assert auth("status") == 0

    sortie = capsys.readouterr().out
    assert "connecté" in sortie
    assert "compte-ghp_abc" in sortie


def test_status_d_un_token_revoque_est_non_connecte(faux, instance, capsys):
    (instance / "secrets.env").write_text("GH_TOKEN=revoque\n")

    assert auth("status") != 0

    assert "non connecté" in capsys.readouterr().out.lower()


def test_auth_sans_instance_renvoie_vers_setup(faux, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))

    assert auth() != 0

    assert "setup" in capsys.readouterr().out
    assert not faux.lignes("gh ")


def test_en_root_gh_tourne_en_utilisateur_d_instance(faux, tmp_path, instance, monkeypatch):
    from wap_runtime import cli

    monkeypatch.setenv("HOME", str(tmp_path / "root"))
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "HOME_UTILISATEUR", instance.parent)
    proprietaires = []
    monkeypatch.setattr(
        "wap_runtime.auth.os.chown",
        lambda chemin, uid, gid: proprietaires.append((Path(chemin).name, uid, gid)),
    )

    assert cli.main(["auth"]) == 0

    assert faux.lignes("runuser -u orchestrator -- gh auth login")
    assert (instance / "secrets.env").read_text() == "GH_TOKEN=gho_device\n"
    st = instance.stat()
    assert proprietaires == [(".secrets.env.tmp", st.st_uid, st.st_gid)]
