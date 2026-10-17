"""Connexion des agents de l’instance : `auth claude`, `auth agent --with-token`, `auth status`."""

import os

import pytest

from test_auth import FAUX_GH, Faux, auth, mode

# Faux `claude setup-token` : écrit comme le vrai (couleurs, invite) puis rend son token.
FAUX_CLAUDE = """\
case "$*" in
  "setup-token")
    printf '\\033[1mOpen this URL in your browser\\033[0m\\r\\n'
    printf 'Your OAuth token (valid for 1 year):\\r\\n\\r\\n'
    printf '\\033[32msk-ant-oat01-abc_DEF-123\\033[39m\\r\\n'
    printf 'Store this token securely.\\r\\n' ;;
esac
"""


@pytest.fixture
def faux(tmp_path, monkeypatch) -> Faux:
    faux = Faux(tmp_path, monkeypatch)
    faux.binaire("claude", FAUX_CLAUDE)
    for cle in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "CURSOR_API_KEY"):
        monkeypatch.delenv(cle, raising=False)
    return faux


@pytest.fixture
def instance(tmp_path, monkeypatch):
    home = tmp_path / "home"
    instance = home / ".wap-runtime"
    instance.mkdir(parents=True)
    (instance / "compose.yaml").write_text("services: {}\n")
    (instance / "secrets.env").write_text("GH_TOKEN=ghp_abc\n")
    (instance / "secrets.env").chmod(0o600)
    monkeypatch.setenv("HOME", str(home))
    return instance


def secrets(instance) -> str:
    return (instance / "secrets.env").read_text()


def redemarrages(faux) -> list[str]:
    return faux.lignes("docker ")


def test_auth_claude_lance_setup_token_et_ecrit_le_token(faux, instance, capsys):
    assert auth("claude") == 0

    assert secrets(instance) == "GH_TOKEN=ghp_abc\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abc_DEF-123\n"
    assert mode(instance / "secrets.env") == 0o600
    appel = faux.lignes("claude setup-token")
    assert len(appel) == 1
    assert f"HOME={instance.parent} " in appel[0]
    [redemarrage] = redemarrages(faux)
    assert redemarrage.split(" | ")[0].endswith(
        f"compose -f {instance / 'compose.yaml'} up -d --force-recreate"
    )
    sortie = capsys.readouterr().out
    # L’utilisateur voit ce que `claude` affiche (URL, code) pendant la connexion.
    assert "Open this URL in your browser" in sortie
    assert "OK — Claude Code connecté" in sortie


def en_root(tmp_path, instance, monkeypatch, path_appelant: str):
    """Root avec `path_appelant` ; `runuser` dans un faux `/usr/sbin`, hors de ce PATH."""
    from wap_runtime import cli, socle

    monkeypatch.setenv("HOME", str(tmp_path / "root"))
    monkeypatch.setenv("PATH", path_appelant)
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "HOME_UTILISATEUR", instance.parent)
    monkeypatch.setattr("wap_runtime.fichiers.os.chown", lambda *a: None)
    sbin = tmp_path / "usr-sbin"
    sbin.mkdir()
    monkeypatch.setattr(socle, "REPERTOIRES_SYSTEME", (str(sbin),))
    return sbin


def test_auth_claude_en_root_avec_un_path_minimal_trouve_claude_chez_orchestrator(
    faux, tmp_path, instance, monkeypatch
):
    from wap_runtime import cli

    # `setup` installe `claude` dans `~orchestrator/.local/bin` ; `runuser` vit sous `/usr/sbin`.
    sbin = en_root(tmp_path, instance, monkeypatch, f"{faux.bin}{os.pathsep}/usr/bin{os.pathsep}/bin")
    local_bin = instance.parent / ".local" / "bin"
    local_bin.mkdir(parents=True)
    (faux.bin / "claude").rename(local_bin / "claude")
    (faux.bin / "runuser").rename(sbin / "runuser")

    assert cli.main(["auth", "claude"]) == 0

    assert faux.lignes(f"runuser -u orchestrator -- {local_bin / 'claude'} setup-token")
    assert faux.lignes("claude setup-token")
    assert "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abc_DEF-123" in secrets(instance)


def test_auth_claude_sans_claude_installe_renvoie_vers_setup(faux, tmp_path, instance, monkeypatch, capsys):
    from wap_runtime import cli

    en_root(tmp_path, instance, monkeypatch, str(faux.bin))
    (faux.bin / "claude").unlink()

    assert cli.main(["auth", "claude"]) != 0

    sortie = capsys.readouterr().out
    assert sortie.startswith("KO")
    assert "claude introuvable" in sortie and "sudo wap-runtime setup" in sortie
    assert not faux.lignes("runuser ")
    assert secrets(instance) == "GH_TOKEN=ghp_abc\n"


def test_setup_token_en_echec_nomme_l_etape_sans_toucher_secrets_env(faux, instance, capsys):
    faux.binaire("claude", 'echo "login annulé"; exit 3')

    assert auth("claude") != 0

    assert "« claude setup-token »" in capsys.readouterr().out
    assert secrets(instance) == "GH_TOKEN=ghp_abc\n"
    assert not redemarrages(faux)


def test_setup_token_sans_token_dans_la_sortie_renvoie_vers_with_token(faux, instance, capsys):
    faux.binaire("claude", 'echo "rien ici"')

    assert auth("claude") != 0

    assert "--with-token" in capsys.readouterr().out
    assert secrets(instance) == "GH_TOKEN=ghp_abc\n"


def test_auth_claude_with_token_lit_stdin_sans_lancer_claude(faux, instance, monkeypatch):
    assert auth("claude", "--with-token", stdin="sk-ant-oat01-stdin\n", monkeypatch=monkeypatch) == 0

    assert secrets(instance) == "GH_TOKEN=ghp_abc\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-stdin\n"
    assert not faux.lignes("claude ")
    assert redemarrages(faux)


def test_auth_claude_with_token_accepte_une_cle_api_anthropic(faux, instance, monkeypatch):
    (instance / "secrets.env").write_text("GH_TOKEN=ghp_abc\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-x\n")

    assert auth("claude", "--with-token", stdin="sk-ant-api03-cle\n", monkeypatch=monkeypatch) == 0

    # Une seule identité Claude à la fois : la clé API remplace le token OAuth.
    assert secrets(instance) == "GH_TOKEN=ghp_abc\nANTHROPIC_API_KEY=sk-ant-api03-cle\n"


def test_auth_claude_with_token_est_idempotent_et_remplace_le_token(faux, instance, monkeypatch):
    (instance / "secrets.env").write_text("AUTRE=1\nCLAUDE_CODE_OAUTH_TOKEN=ancien\nGH_TOKEN=ghp_abc\n")

    for _ in range(2):
        assert auth("claude", "--with-token", stdin="sk-ant-oat01-neuf\n", monkeypatch=monkeypatch) == 0

    assert secrets(instance) == "AUTRE=1\nGH_TOKEN=ghp_abc\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-neuf\n"
    assert mode(instance / "secrets.env") == 0o600


def test_auth_agent_with_token_ecrit_cursor_api_key(faux, instance, monkeypatch, capsys):
    (instance / "secrets.env").write_text("GH_TOKEN=ghp_abc\nCURSOR_API_KEY=ancienne\n")

    for _ in range(2):
        assert auth("agent", "--with-token", stdin="key_cursor-1\n", monkeypatch=monkeypatch) == 0

    assert secrets(instance) == "GH_TOKEN=ghp_abc\nCURSOR_API_KEY=key_cursor-1\n"
    assert mode(instance / "secrets.env") == 0o600
    assert len(redemarrages(faux)) == 2
    assert "OK — Cursor connecté" in capsys.readouterr().out


def test_auth_agent_sans_with_token_explique_pourquoi(faux, instance, capsys):
    assert auth("agent") != 0

    assert "--with-token" in capsys.readouterr().out
    assert secrets(instance) == "GH_TOKEN=ghp_abc\n"


@pytest.mark.parametrize("agent", ["claude", "agent"])
@pytest.mark.parametrize("stdin", ["\n", "deux mots\n", "a=b\n"])
def test_with_token_vide_ou_inattendu_est_refuse(faux, instance, monkeypatch, capsys, agent, stdin):
    assert auth(agent, "--with-token", stdin=stdin, monkeypatch=monkeypatch) != 0

    assert capsys.readouterr().out.startswith("KO")
    assert secrets(instance) == "GH_TOKEN=ghp_abc\n"
    assert not redemarrages(faux)


def test_redemarrage_des_services_en_echec_nomme_l_etape(faux, instance, monkeypatch, capsys):
    faux.binaire("docker", "exit 1")

    assert auth("agent", "--with-token", stdin="key_x\n", monkeypatch=monkeypatch) != 0

    assert "« redémarrage des services »" in capsys.readouterr().out


def test_auth_github_ne_touche_pas_aux_tokens_des_agents(faux, instance):
    faux.binaire("gh", FAUX_GH)
    (instance / "secrets.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-x\nGH_TOKEN=ancien\n")

    assert auth() == 0

    assert secrets(instance) == "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-x\nGH_TOKEN=gho_device\n"


def test_status_affiche_github_claude_et_cursor(faux, instance, capsys):
    faux.binaire("gh", FAUX_GH)
    (instance / "secrets.env").write_text("GH_TOKEN=ghp_abc\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-x\n")

    assert auth("status") == 0

    lignes = capsys.readouterr().out.splitlines()
    assert len(lignes) == 3
    assert lignes[0].startswith("OK — ") and "compte-ghp_abc" in lignes[0]
    assert lignes[1].startswith("OK — Claude Code connecté")
    assert lignes[2].startswith("KO — Cursor non connecté")
    assert "sudo wap-runtime auth agent --with-token" in lignes[2]


def test_status_d_une_cle_api_anthropic_est_connecte(faux, instance, capsys):
    faux.binaire("gh", FAUX_GH)
    (instance / "secrets.env").write_text("GH_TOKEN=ghp_abc\nANTHROPIC_API_KEY=sk-ant-api03-x\n")

    auth("status")

    assert "OK — Claude Code connecté" in capsys.readouterr().out


def test_status_sans_rien_affiche_trois_ko(faux, instance, capsys):
    (instance / "secrets.env").write_text("")

    assert auth("status") != 0

    lignes = capsys.readouterr().out.splitlines()
    assert [l[:2] for l in lignes] == ["KO", "KO", "KO"]
    assert "sudo wap-runtime auth claude" in lignes[1]
