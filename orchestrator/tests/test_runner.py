"""Runner en process : clone géré, lancement de l’agent dans tmux, API interne.

`gh`, `tmux`, `claude` et `agent` sont de faux exécutables dans le `PATH` : le faux `tmux`
exécute la commande de la session tout de suite (la session est donc close au retour).
GitHub est un dépôt nu local.
"""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wap_runtime.runner import Identite, Runner, creer_app_runner
from wap_runtime.sessions import Sessions

SLUG = "o/r"
BRANCHE = "v0.4.0-runner"
IDENTITE = Identite("octocat", "583231+octocat@users.noreply.github.com")


def executable(dossier: Path, nom: str, script: str) -> None:
    chemin = dossier / nom
    chemin.write_text("#!/bin/sh\n" + script)
    chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)


def git(*args, cwd=None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def faux_bin(tmp_path, monkeypatch):
    """Chaque appel est noté dans `appels.log` : `<programme> <args…>` (et le dossier courant)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    log = tmp_path / "appels.log"
    executable(bin_, "gh", f'echo "gh $*" >> {log}\n')
    executable(
        bin_,
        "tmux",
        # tmux new-session -d -s <nom> -c <dossier> <commande shell>
        f'echo "tmux $1 $2 $3 $4 $5 $6" >> {log}\n'
        # Le vrai rend la main tout de suite, quel que soit le sort de la commande.
        'cd "$6" && eval "$7"\nexit 0\n',
    )
    for agent in ("claude", "agent"):
        executable(
            bin_,
            agent,
            f'echo "{agent} $* @ $(pwd) @ $(git config user.name) <$(git config user.email)>"'
            f' >> {log}\nexit "${{FAUX_CODE:-0}}"\n',
        )
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return log


@pytest.fixture
def github(tmp_path):
    """`o/r` : `main` et la branche de la PR de version, sur un dépôt nu."""
    nu = tmp_path / "github" / f"{SLUG}.git"
    travail = tmp_path / "travail"
    git("init", "--quiet", "--bare", "-b", "main", str(nu))
    git("init", "--quiet", "-b", "main", str(travail))
    for cle, valeur in (("user.name", "t"), ("user.email", "t@t")):
        git("config", cle, valeur, cwd=travail)
    git("commit", "--quiet", "--allow-empty", "-m", "init", cwd=travail)
    git("switch", "--quiet", "-c", BRANCHE, cwd=travail)
    git("commit", "--quiet", "--allow-empty", "-m", "ouvrir la version", cwd=travail)
    git("remote", "add", "origin", str(nu), cwd=travail)
    git("push", "--quiet", "origin", "main", BRANCHE, cwd=travail)
    return travail


@pytest.fixture
def instance(tmp_path):
    return tmp_path / "instance"


@pytest.fixture
def runner(instance, tmp_path, faux_bin, github):
    return Runner(
        instance / "clones",
        instance / "jobs",
        depot=str(tmp_path / "github" / "{slug}.git"),
    )


def appels(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def lancer(runner, agent="claude", ticket=30):
    return runner.lancer(SLUG, ticket, agent, BRANCHE, IDENTITE)


def test_premier_lancement_clone_sur_la_branche_de_la_pr_avec_l_identite(runner, instance, faux_bin):
    lancer(runner)

    clone = instance / "clones" / "o" / "r"
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone) == BRANCHE
    assert git("config", "user.name", cwd=clone) == "octocat"
    assert git("config", "user.email", cwd=clone) == "583231+octocat@users.noreply.github.com"
    assert "gh auth setup-git" in appels(faux_bin)


def test_lancement_suivant_fetch_sans_recloner(runner, instance, github, faux_bin):
    lancer(runner)
    clone = instance / "clones" / "o" / "r"
    (clone / ".git" / "marque").write_text("même clone")
    git("commit", "--quiet", "--allow-empty", "-m", "poussé entre-temps", cwd=github)
    git("push", "--quiet", "origin", BRANCHE, cwd=github)

    lancer(runner)

    assert (clone / ".git" / "marque").exists()
    assert git("log", "-1", "--format=%s", cwd=clone) == "poussé entre-temps"
    assert appels(faux_bin).count("gh auth setup-git") == 1


def test_branche_absente_sur_github_refusee_sans_session(runner, instance):
    from wap_runtime.runner import RunnerErreur

    with pytest.raises(RunnerErreur, match="inexistante"):
        runner.lancer(SLUG, 30, "claude", "pas-de-branche", IDENTITE)

    assert Sessions(instance / "jobs").toutes() == []


@pytest.mark.parametrize("agent, programme", [("claude", "claude"), ("cursor", "agent")])
def test_commande_lancee_selon_l_agent_dans_le_clone_et_dans_tmux(
    runner, instance, faux_bin, agent, programme
):
    session = lancer(runner, agent=agent)

    clone = instance / "clones" / "o" / "r"
    lignes = appels(faux_bin)
    assert f"tmux new-session -d -s wap-{session['id']} -c {clone}" in lignes
    lancee = next(l for l in lignes if l.startswith(f"{programme} "))
    assert lancee == (
        f"{programme} /implement #30 @ {clone.resolve()} @ octocat "
        "<583231+octocat@users.noreply.github.com>"
    )
    assert session["commande"] == f'{programme} "/implement #30"'
    assert session["agent"] == agent


@pytest.mark.parametrize("code, etat", [("0", "terminée"), ("1", "échouée")])
def test_session_close_selon_le_code_de_sortie_de_l_agent(runner, instance, monkeypatch, code, etat):
    monkeypatch.setenv("FAUX_CODE", code)

    session = lancer(runner)

    sur_disque = json.loads((instance / "jobs" / session["id"] / "session.json").read_text())
    assert (sur_disque["etat"], sur_disque["code_sortie"]) == (etat, int(code))
    assert (sur_disque["repo"], sur_disque["ticket"]) == (SLUG, 30)


def test_le_runner_ne_pose_aucun_label(runner, faux_bin):
    lancer(runner)

    assert not [l for l in appels(faux_bin) if l.startswith("gh ") and l != "gh auth setup-git"]


def test_une_seule_session_ouverte(runner, instance):
    from wap_runtime.runner import SessionOuverte

    ouverte = Sessions(instance / "jobs").creer("o/autre", 3, "claude", 'claude "/implement #3"')

    with pytest.raises(SessionOuverte) as refus:
        lancer(runner)

    assert refus.value.session == ouverte


def test_api_interne_lance_une_session(runner, instance):
    client = TestClient(creer_app_runner(runner))

    reponse = client.post(
        "/sessions",
        json={
            "repo": SLUG,
            "ticket": 30,
            "agent": "cursor",
            "branche": BRANCHE,
            "login": IDENTITE.login,
            "email": IDENTITE.email,
        },
    )

    assert reponse.status_code == 201
    assert reponse.json()["commande"] == 'agent "/implement #30"'


def test_api_interne_409_avec_la_session_ouverte(runner, instance):
    ouverte = Sessions(instance / "jobs").creer("o/autre", 3, "claude", 'claude "/implement #3"')
    client = TestClient(creer_app_runner(runner))

    reponse = client.post(
        "/sessions",
        json={"repo": SLUG, "ticket": 30, "agent": "claude", "branche": BRANCHE,
              "login": "octocat", "email": "e"},
    )

    assert reponse.status_code == 409
    assert reponse.json()["session"] == ouverte


def test_api_interne_422_avec_le_message_du_runner(runner):
    client = TestClient(creer_app_runner(runner))

    reponse = client.post(
        "/sessions",
        json={"repo": SLUG, "ticket": 30, "agent": "claude", "branche": "absente",
              "login": "octocat", "email": "e"},
    )

    assert reponse.status_code == 422
    assert "inexistante" in reponse.json()["detail"]
