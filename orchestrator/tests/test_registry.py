"""Registry des repos liés : `wap-runtime repo add|remove|list` et module de lecture."""

import os
import stat
from pathlib import Path

import pytest

from wap_runtime.registry import RepoLie, lire_registry

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


@pytest.fixture
def instance(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    instance = home / ".wap-runtime"
    instance.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return instance


def repo(*args: str) -> int:
    from wap_runtime.cli import main

    return main(["repo", *args])


def test_lecture_d_un_registry_absent_rend_une_liste_vide(tmp_path):
    assert lire_registry(tmp_path / "repos.toml") == []


def test_add_cree_repos_toml_et_list_affiche_le_repo(instance, capsys):
    assert not (instance / "repos.toml").exists()

    assert repo("add", "mon-org/mon-repo") == 0
    assert repo("add", "autre-org/outil_2", "--nom", "Outil « deux »") == 0
    capsys.readouterr()

    assert repo("list") == 0
    sortie = capsys.readouterr().out
    assert "mon-org/mon-repo" in sortie
    assert "autre-org/outil_2" in sortie
    assert "Outil « deux »" in sortie
    assert lire_registry(instance / "repos.toml") == [
        RepoLie("mon-org/mon-repo"),
        RepoLie("autre-org/outil_2", "Outil « deux »"),
    ]


def test_repos_toml_est_du_toml_lisible_par_le_conteneur(instance):
    repo("add", "mon-org/mon-repo", "--nom", 'a "guillemet" \\ et\nsaut')

    chemin = instance / "repos.toml"
    assert tomllib.loads(chemin.read_text())["repos"] == [
        {
            "slug": "mon-org/mon-repo",
            "nom": 'a "guillemet" \\ et\nsaut',
            "pilote": False,
            "agent": "claude",
        }
    ]
    assert stat.S_IMODE(chemin.stat().st_mode) & 0o044 == 0o044


def test_remove_retire_le_repo(instance, capsys):
    repo("add", "mon-org/a")
    repo("add", "mon-org/b")

    assert repo("remove", "mon-org/a") == 0

    assert lire_registry(instance / "repos.toml") == [RepoLie("mon-org/b")]


def test_list_d_un_registry_vide_le_dit(instance, capsys):
    assert repo("list") == 0

    assert "aucun repo lié" in capsys.readouterr().out.lower()


@pytest.mark.parametrize(
    "slug",
    ["mon-repo", "a/b/c", "/repo", "org/", "org/re po", "org-/repo", "o--rg/repo", "o" * 40 + "/repo", "org/..", ""],
)
def test_add_refuse_un_owner_name_invalide(instance, slug, capsys):
    assert repo("add", "--", slug) != 0

    assert "owner/name" in capsys.readouterr().out
    assert not (instance / "repos.toml").exists()


def test_add_refuse_un_doublon_insensible_a_la_casse(instance, capsys):
    repo("add", "mon-org/mon-repo")
    capsys.readouterr()

    assert repo("add", "Mon-Org/Mon-Repo") != 0

    assert "déjà" in capsys.readouterr().out
    assert lire_registry(instance / "repos.toml") == [RepoLie("mon-org/mon-repo")]


def test_remove_d_un_repo_absent_le_dit(instance, capsys):
    repo("add", "mon-org/mon-repo")
    capsys.readouterr()

    assert repo("remove", "mon-org/autre") != 0

    sortie = capsys.readouterr().out
    assert "mon-org/autre" in sortie
    assert "absent" in sortie


def test_commandes_sans_instance_renvoient_vers_setup(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))

    assert repo("add", "mon-org/mon-repo") != 0

    assert "setup" in capsys.readouterr().out
    assert not (tmp_path / ".wap-runtime").exists()


def test_repos_toml_illisible_donne_un_message_clair(instance, capsys):
    (instance / "repos.toml").write_text("repos = [pas du toml\n")

    assert repo("list") != 0

    assert "repos.toml" in capsys.readouterr().out


def test_edition_a_la_main_est_relue(instance):
    (instance / "repos.toml").write_text(
        '# mes repos\n[[repos]]\nslug = "mon-org/a"\nnom = "A"\n'
    )

    assert repo("add", "mon-org/b") == 0

    assert lire_registry(instance / "repos.toml") == [
        RepoLie("mon-org/a", "A"),
        RepoLie("mon-org/b"),
    ]


def test_pilote_et_agent_preferes_sont_lus_ecrits_et_relus_sur_disque(instance):
    from wap_runtime.registry import enregistrer

    repo("add", "mon-org/a")
    chemin = instance / "repos.toml"
    assert lire_registry(chemin) == [RepoLie("mon-org/a")]

    enregistre = enregistrer(chemin, "mon-org/a", pilote=True, agent="cursor")

    assert enregistre == RepoLie("mon-org/a", pilote=True, agent="cursor")
    assert tomllib.loads(chemin.read_text())["repos"] == [
        {"slug": "mon-org/a", "pilote": True, "agent": "cursor"}
    ]
    assert lire_registry(chemin) == [RepoLie("mon-org/a", pilote=True, agent="cursor")]


def test_edition_a_la_main_de_pilote_et_agent_est_relue(instance):
    (instance / "repos.toml").write_text(
        '[[repos]]\nslug = "mon-org/a"\npilote = true\nagent = "cursor"\n'
    )

    assert lire_registry(instance / "repos.toml") == [
        RepoLie("mon-org/a", pilote=True, agent="cursor")
    ]


def test_preference_modele_cursor_est_lue_ecrite_et_relue_sur_disque(instance):
    from wap_runtime.registry import enregistrer

    repo("add", "mon-org/a")
    chemin = instance / "repos.toml"

    enregistre = enregistrer(
        chemin, "mon-org/a", pilote=True, agent="cursor", modele="composer-2"
    )

    assert enregistre == RepoLie(
        "mon-org/a", pilote=True, agent="cursor", modele="composer-2"
    )
    assert tomllib.loads(chemin.read_text())["repos"] == [
        {
            "slug": "mon-org/a",
            "pilote": True,
            "agent": "cursor",
            "modele": "composer-2",
        }
    ]
    assert lire_registry(chemin) == [
        RepoLie("mon-org/a", pilote=True, agent="cursor", modele="composer-2")
    ]


def test_preference_modele_absente_ou_auto_n_est_pas_ecrite_dans_le_toml(instance):
    from wap_runtime.registry import enregistrer

    repo("add", "mon-org/a")
    chemin = instance / "repos.toml"

    for valeur in (None, "", "auto", "Auto"):
        enregistre = enregistrer(
            chemin, "mon-org/a", pilote=False, agent="cursor", modele=valeur
        )
        assert enregistre.modele is None
        assert "modele" not in tomllib.loads(chemin.read_text())["repos"][0]
        assert lire_registry(chemin)[0].modele is None


def test_edition_a_la_main_du_modele_est_relue(instance):
    (instance / "repos.toml").write_text(
        '[[repos]]\nslug = "mon-org/a"\nagent = "cursor"\nmodele = "composer-2"\n'
    )

    assert lire_registry(instance / "repos.toml") == [
        RepoLie("mon-org/a", agent="cursor", modele="composer-2")
    ]


def test_en_root_les_commandes_visent_l_instance_d_orchestrator(
    tmp_path, instance, monkeypatch
):
    from wap_runtime import cli

    root = tmp_path / "root"
    (root / ".wap-runtime").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "HOME_UTILISATEUR", instance.parent)
    proprietaires = []
    monkeypatch.setattr(
        "wap_runtime.fichiers.os.chown",
        lambda chemin, uid, gid: proprietaires.append((Path(chemin), uid, gid)),
    )

    assert cli.main(["repo", "add", "mon-org/mon-repo"]) == 0

    assert lire_registry(instance / "repos.toml") == [RepoLie("mon-org/mon-repo")]
    assert not (root / ".wap-runtime" / "repos.toml").exists()
    st = instance.stat()
    assert proprietaires == [(instance / ".repos.toml.tmp", st.st_uid, st.st_gid)]
