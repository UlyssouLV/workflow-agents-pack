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
# Où chaque fausse CLI écrit sa transcription, sous `HOME`.
TRANSCRIPTIONS = {
    "claude": ".claude/projects/-clones-o-r",
    "agent": ".cursor/projects/clones-o-r/agent-transcripts/c1",
}


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
            f' >> {log}\n'
            # Affiché dans son terminal, et sa transcription native sous `HOME`.
            f'echo "{agent} prêt : $*"\n'
            f'mkdir -p "$HOME/{TRANSCRIPTIONS[agent]}"\n'
            f'echo \'{{"agent": "{agent}"}}\' > "$HOME/{TRANSCRIPTIONS[agent]}/t.jsonl"\n'
            'exit "${FAUX_CODE:-0}"\n',
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


@pytest.mark.parametrize(
    "repo, branche, identite, motif",
    [
        ("../o/r", BRANCHE, IDENTITE, "repo invalide"),
        (SLUG, "--upload-pack=x", IDENTITE, "branche invalide"),
        (SLUG, "v1/../main", IDENTITE, "branche invalide"),
        (SLUG, BRANCHE, Identite("--global", IDENTITE.email), "identité git invalide"),
        (SLUG, BRANCHE, Identite("octocat", "-e"), "identité git invalide"),
    ],
)
def test_arguments_de_git_refuses_s_ils_ressemblent_a_une_option(runner, instance, faux_bin, repo, branche, identite, motif):
    """Rien de la requête n’arrive à `git` sous forme d’option, ni hors de `clones/`."""
    from wap_runtime.runner import RunnerErreur

    with pytest.raises(RunnerErreur, match=motif):
        runner.lancer(repo, 30, "claude", branche, identite)

    assert appels(faux_bin) == []
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


@pytest.mark.parametrize("agent, programme", [("claude", "claude"), ("cursor", "agent")])
def test_session_enregistree_terminal_et_transcription(runner, instance, agent, programme):
    session = lancer(runner, agent=agent)

    dossier = instance / "jobs" / session["id"]
    entete, *evenements = (json.loads(l) for l in (dossier / "terminal.cast").read_text().splitlines())
    assert entete["version"] == 2 and entete["width"] > 0 and entete["height"] > 0
    assert f"{programme} prêt : /implement #30" in "".join(e[2] for e in evenements if e[1] == "o")
    copiee = next((dossier / "transcription").rglob("t.jsonl"))
    assert json.loads(copiee.read_text()) == {"agent": programme}


def test_redemarrage_session_ouverte_interrompue_et_nouvelle_session_possible(runner, instance, tmp_path):
    ouverte = Sessions(instance / "jobs").creer(SLUG, 29, "claude", 'claude "/implement #29"')

    redemarre = Runner(instance / "clones", instance / "jobs", depot=str(tmp_path / "github" / "{slug}.git"))

    interrompue = redemarre.session(ouverte["id"])
    assert interrompue["etat"] == "interrompue"
    assert interrompue["fin"] is not None
    assert lancer(redemarre)["ticket"] == 30


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


@pytest.fixture
def clone_sale(runner, instance):
    """Clone d’une session précédente laissé avec une modification et un fichier non suivi."""
    lancer(runner)
    clone = instance / "clones" / "o" / "r"
    (clone / "suivi.txt").write_text("avant\n")
    git("add", "suivi.txt", cwd=clone)
    git("commit", "--quiet", "-m", "suivi", cwd=clone)
    (clone / "suivi.txt").write_text("après\n")
    (clone / "nouveau.txt").write_text("non suivi\n")
    return clone


def test_clone_sale_sans_choix_ne_lance_rien_et_rend_fichiers_et_diff(runner, instance, clone_sale):
    from wap_runtime.runner import CloneSale

    avant = Sessions(instance / "jobs").toutes()

    with pytest.raises(CloneSale) as refus:
        lancer(runner)

    assert refus.value.fichiers == [{"statut": "M", "chemin": "suivi.txt"}, {"statut": "??", "chemin": "nouveau.txt"}]
    assert "+après" in refus.value.diff and "+non suivi" in refus.value.diff
    assert Sessions(instance / "jobs").toutes() == avant
    assert (clone_sale / "nouveau.txt").exists()


def test_reprendre_lance_la_session_sur_l_arbre_tel_quel_sans_changer_de_branche(runner, clone_sale, faux_bin):
    git("switch", "--quiet", "-c", "travail-en-cours", cwd=clone_sale)

    session = runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE, choix="reprendre")

    assert session["ticket"] == 30
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone_sale) == "travail-en-cours"
    assert (clone_sale / "suivi.txt").read_text() == "après\n"
    assert (clone_sale / "nouveau.txt").exists()


def test_jeter_enregistre_le_patch_nettoie_l_arbre_et_lance(runner, instance, clone_sale):
    session = runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE, choix="jeter")

    patch = (instance / "jobs" / session["id"] / "abandon.patch").read_text()
    assert "-avant" in patch and "+après" in patch
    assert "nouveau.txt" in patch and "+non suivi" in patch
    assert git("status", "--porcelain", cwd=clone_sale) == ""
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone_sale) == BRANCHE
    # Le patch rejoue les modifications jetées.
    git("apply", str(instance / "jobs" / session["id"] / "abandon.patch"), cwd=clone_sale)
    assert (clone_sale / "suivi.txt").read_text() == "après\n"
    assert (clone_sale / "nouveau.txt").read_text() == "non suivi\n"


@pytest.mark.parametrize("choix", [None, "reprendre", "jeter"])
def test_clone_propre_aucun_choix_demande(runner, instance, choix):
    lancer(runner)

    session = runner.lancer(SLUG, 31, "claude", BRANCHE, IDENTITE, choix=choix)

    assert session["ticket"] == 31
    assert not (instance / "jobs" / session["id"] / "abandon.patch").exists()


def test_api_interne_409_avec_le_clone_sale(runner, clone_sale):
    client = TestClient(creer_app_runner(runner))
    demande = {"repo": SLUG, "ticket": 30, "agent": "claude", "branche": BRANCHE,
               "login": "octocat", "email": "e"}

    reponse = client.post("/sessions", json=demande)

    assert reponse.status_code == 409
    assert reponse.json()["clone"]["fichiers"][0] == {"statut": "M", "chemin": "suivi.txt"}
    assert "+après" in reponse.json()["clone"]["diff"]

    assert client.post("/sessions", json={**demande, "choix": "jeter"}).status_code == 201
