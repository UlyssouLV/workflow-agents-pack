"""Runner en process : clone géré, lancement de l’agent dans tmux, API interne.

`gh`, `tmux`, `claude` et `agent` sont de faux exécutables dans le `PATH` : le faux `tmux`
exécute la commande de la session tout de suite (la session est donc close au retour).
GitHub est un dépôt nu local.
"""

import json
import os
import stat
import subprocess
import time
from dataclasses import dataclass
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
            f'echo "$WAP_ENCHAINER|$WAP_SESSION|$WAP_SESSION_JETON" >> {tmp_path / "env.log"}\n'
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


def lancer(runner, agent="claude", ticket=30, branche=BRANCHE):
    return runner.lancer(SLUG, ticket, agent, branche, IDENTITE)


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
    jobs = Sessions(instance / "jobs")
    ouverte = jobs.creer(SLUG, 29, "claude", 'claude "/implement #29"')
    autre = jobs.creer("o/autre", 3, "claude", 'claude "/implement #3"')

    redemarre = Runner(instance / "clones", instance / "jobs", depot=str(tmp_path / "github" / "{slug}.git"))

    interrompue = redemarre.session(ouverte["id"])
    assert interrompue["etat"] == "interrompue"
    assert interrompue["fin"] is not None
    assert redemarre.session(autre["id"])["etat"] == "interrompue"
    assert lancer(redemarre)["ticket"] == 30


def test_le_runner_ne_pose_aucun_label(runner, faux_bin):
    lancer(runner)

    assert not [l for l in appels(faux_bin) if l.startswith("gh ") and l != "gh auth setup-git"]


def test_deuxieme_session_sur_le_meme_repo_refusee(runner, instance):
    from wap_runtime.runner import SessionOuverte

    ouverte = Sessions(instance / "jobs").creer(SLUG, 3, "claude", 'claude "/implement #3"')

    with pytest.raises(SessionOuverte) as refus:
        lancer(runner)

    assert refus.value.session == ouverte


def test_session_sur_un_autre_repo_acceptee(runner, instance):
    Sessions(instance / "jobs").creer("o/autre", 3, "claude", 'claude "/implement #3"')

    lancee = lancer(runner)

    assert lancee["repo"] == SLUG
    assert lancee["etat"] == "terminée"


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


def test_api_interne_409_avec_la_session_ouverte_du_meme_repo(runner, instance):
    ouverte = Sessions(instance / "jobs").creer(SLUG, 3, "claude", 'claude "/implement #3"')
    client = TestClient(creer_app_runner(runner))

    reponse = client.post(
        "/sessions",
        json={"repo": SLUG, "ticket": 30, "agent": "claude", "branche": BRANCHE,
              "login": "octocat", "email": "e"},
    )

    assert reponse.status_code == 409
    assert reponse.json()["session"] == ouverte


def test_api_interne_accepte_un_autre_repo(runner, instance):
    Sessions(instance / "jobs").creer("o/autre", 3, "claude", 'claude "/implement #3"')
    client = TestClient(creer_app_runner(runner))

    reponse = client.post(
        "/sessions",
        json={"repo": SLUG, "ticket": 30, "agent": "claude", "branche": BRANCHE,
              "login": IDENTITE.login, "email": IDENTITE.email},
    )

    assert reponse.status_code == 201
    assert reponse.json()["repo"] == SLUG


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
    assert refus.value.branche == BRANCHE
    assert "+après" in refus.value.diff and "+non suivi" in refus.value.diff
    assert Sessions(instance / "jobs").toutes() == avant
    assert (clone_sale / "nouveau.txt").exists()


def test_reprendre_lance_la_session_sur_l_arbre_tel_quel_sans_changer_de_branche(runner, clone_sale, faux_bin):
    git("switch", "--quiet", "-c", "travail-en-cours", cwd=clone_sale)

    session = runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE, choix="reprendre")

    assert session["ticket"] == 30
    assert session["branche"] == "travail-en-cours"
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
    assert session["branche"] == BRANCHE
    assert not (instance / "jobs" / session["id"] / "abandon.patch").exists()


def test_api_interne_409_avec_le_clone_sale(runner, clone_sale):
    client = TestClient(creer_app_runner(runner))
    demande = {"repo": SLUG, "ticket": 30, "agent": "claude", "branche": BRANCHE,
               "login": "octocat", "email": "e"}

    reponse = client.post("/sessions", json=demande)

    assert reponse.status_code == 409
    assert reponse.json()["clone"]["fichiers"][0] == {"statut": "M", "chemin": "suivi.txt"}
    assert reponse.json()["clone"]["branche"] == BRANCHE
    assert "+après" in reponse.json()["clone"]["diff"]

    assert client.post("/sessions", json={**demande, "choix": "jeter"}).status_code == 201


# Un `dispatch.py` réduit : copie `agents/skills/*` sous `.claude/skills/` et `.cursor/skills/`,
# et sort selon `FAUX_DISPATCH` (`echec` : code 3 ; `suivi` : modifie un fichier suivi).
DISPATCH = """\
import os, shutil, sys
from pathlib import Path

racine = Path(__file__).resolve().parents[2]
with open(os.environ["FAUX_LOG"], "a") as log:
    log.write(f"dispatch @ {Path.cwd()}\\n")
if os.environ.get("FAUX_DISPATCH") == "echec":
    sys.exit(3)
if os.environ.get("FAUX_DISPATCH") == "suivi":
    (racine / "README.md").write_text("réécrit\\n")
for destination in (".claude/skills", ".cursor/skills"):
    shutil.copytree(racine / "agents" / "skills", racine / destination, dirs_exist_ok=True)
"""


def pousser_pack(github: Path, skills=True, dispatch=True) -> None:
    """La branche de version suit `agents/skills/` et/ou `agents/scripts/dispatch.py` ; les
    adaptateurs sont ignorés, comme dans un repo qui suit le pack."""
    (github / ".gitignore").write_text("/.claude/skills/\n/.cursor/skills/\n")
    (github / "README.md").write_text("repo\n")
    if skills:
        (github / "agents" / "skills" / "process" / "tdd").mkdir(parents=True)
        (github / "agents" / "skills" / "process" / "tdd" / "SKILL.md").write_text("# tdd\n")
    if dispatch:
        (github / "agents" / "scripts").mkdir(parents=True)
        (github / "agents" / "scripts" / "dispatch.py").write_text(DISPATCH)
    git("add", ".", cwd=github)
    git("commit", "--quiet", "-m", "pack", cwd=github)
    git("push", "--quiet", "origin", BRANCHE, cwd=github)


@pytest.fixture
def faux_dispatch(faux_bin, monkeypatch):
    monkeypatch.setenv("FAUX_LOG", str(faux_bin))
    return faux_bin


def dispatchs(log: Path) -> list[str]:
    return [l for l in appels(log) if l.startswith("dispatch ")]


@pytest.mark.parametrize("agent, programme", [("claude", "claude"), ("cursor", "agent")])
def test_skills_du_pack_dispatches_avant_l_agent_sans_fichier_suivi_modifie(
    runner, instance, github, faux_dispatch, agent, programme
):
    pousser_pack(github)

    lancer(runner, agent=agent)

    clone = instance / "clones" / "o" / "r"
    lignes = appels(faux_dispatch)
    assert dispatchs(faux_dispatch) == [f"dispatch @ {clone.resolve()}"]
    assert lignes.index(dispatchs(faux_dispatch)[0]) < next(
        i for i, l in enumerate(lignes) if l.startswith(f"{programme} ")
    )
    for adaptateur in (".claude", ".cursor"):
        assert (clone / adaptateur / "skills" / "process" / "tdd" / "SKILL.md").read_text() == "# tdd\n"
    assert git("status", "--porcelain", cwd=clone) == ""


@pytest.mark.parametrize("skills, dispatch", [(False, True), (True, False), (False, False)])
def test_sans_skills_ou_sans_dispatch_l_agent_demarre_tel_quel(
    runner, instance, github, faux_dispatch, skills, dispatch
):
    if skills or dispatch:
        pousser_pack(github, skills=skills, dispatch=dispatch)

    session = lancer(runner)

    clone = instance / "clones" / "o" / "r"
    assert dispatchs(faux_dispatch) == []
    assert not (clone / ".claude").exists() and not (clone / ".cursor").exists()
    assert session["etat"] == "terminée"
    assert any(l.startswith("claude ") for l in appels(faux_dispatch))


@pytest.mark.parametrize("panne, motif", [("echec", "dispatch.py a échoué"), ("suivi", "fichier suivi modifié")])
def test_dispatch_en_echec_ou_fichier_suivi_modifie_l_agent_n_est_pas_lance(
    runner, instance, github, faux_dispatch, monkeypatch, panne, motif
):
    from wap_runtime.runner import RunnerErreur

    pousser_pack(github)
    monkeypatch.setenv("FAUX_DISPATCH", panne)

    with pytest.raises(RunnerErreur, match=motif):
        lancer(runner)

    assert len(dispatchs(faux_dispatch)) == 1
    assert not [l for l in appels(faux_dispatch) if l.startswith(("claude ", "tmux "))]
    (session,) = Sessions(instance / "jobs").toutes()
    assert session["etat"] != "ouverte"


def test_reprendre_dispatch_sans_compter_les_changements_deja_la(runner, instance, github, faux_dispatch):
    pousser_pack(github)
    lancer(runner)
    clone = instance / "clones" / "o" / "r"
    (clone / "README.md").write_text("en cours\n")

    session = runner.lancer(SLUG, 31, "claude", BRANCHE, IDENTITE, choix="reprendre")

    assert session["etat"] == "terminée"
    assert len(dispatchs(faux_dispatch)) == 2
    assert (clone / "README.md").read_text() == "en cours\n"


def test_session_libre_lance_l_agent_sans_argument_sur_la_branche(runner, instance, faux_bin):
    session = runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    clone = instance / "clones" / "o" / "r"
    lancee = next(l for l in appels(faux_bin) if l.startswith("claude "))
    assert lancee == (
        f"claude  @ {clone.resolve()} @ octocat <583231+octocat@users.noreply.github.com>"
    )
    assert (session["ticket"], session["branche"], session["commande"]) == (None, BRANCHE, "claude")
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone) == BRANCHE


def test_l_agent_recoit_l_enchaineur_et_un_jeton_propre_a_la_session(runner, tmp_path):
    premiere, seconde = lancer(runner), lancer(runner, ticket=31)

    lignes = [l.split("|") for l in (tmp_path / "env.log").read_text().splitlines()]
    assert [(e, s) for e, s, _ in lignes] == [
        ("wap-runtime enchainer", premiere["id"]), ("wap-runtime enchainer", seconde["id"])
    ]
    jetons = [j for _, _, j in lignes]
    assert all(len(j) >= 32 for j in jetons) and jetons[0] != jetons[1]
    # Le jeton n’est ni dans `session.json` ni rendu par l’API.
    assert jetons[0] not in json.dumps(premiere)


@pytest.fixture
def faux_gh():
    """`o/r` : version 17, PR 24 sur `BRANCHE` ; 31 éligible, 32 bloqué, 33 sans `ready-for-agent`.
    `o/autre` : version 5, PR 6 sur `BRANCHE`, enfant 40 éligible. `o/r` : version 18, PR 25 sur
    une autre branche, enfant 50 éligible."""
    from faux_github import FauxGitHub

    github = FauxGitHub()
    repo = github.repo(SLUG)
    repo.version(
        17,
        [(30, "closed", []), (31, "open", ["ready-for-agent"]), (32, "open", ["ready-for-agent"]),
         (33, "open", [])],
        bloques=(32,),
    )
    repo.pr(24, "Fixes #17", "sha24", branche=BRANCHE)
    repo.version(18, [(50, "open", ["ready-for-agent"])])
    repo.pr(25, "Fixes #18", "sha25", branche="v0.5.0")
    autre = github.repo("o/autre")
    autre.version(5, [(40, "open", ["ready-for-agent"])])
    autre.pr(6, "Fixes #5", "sha6", branche=BRANCHE)
    return github


@dataclass
class Chaine:
    runner: Runner
    # `(commande, dossier)` de chaque session lancée : tmux ne lance rien, la session reste ouverte.
    lances: list
    arretes: list

    def jeton(self, index=-1) -> str:
        return next(a.split("=", 1)[1] for a in self.lances[index][0] if a.startswith("WAP_SESSION_JETON="))


@pytest.fixture
def chaine(instance, tmp_path, faux_bin, github, faux_gh):
    from faux_github import JETON
    from wap_runtime.github import ClientGitHub

    lances, arretes = [], []
    runner = Runner(
        instance / "clones",
        instance / "jobs",
        lanceur=lambda nom, commande, dossier: lances.append((commande, dossier)),
        depot=str(tmp_path / "github" / "{slug}.git"),
        arreteur=arretes.append,
        github=ClientGitHub(JETON, transport=faux_gh.transport()),
    )
    return Chaine(runner, lances, arretes)


def test_session_sur_la_base_acceptee_sans_pr_de_version(chaine, faux_gh):
    faux_gh.repo(SLUG).pulls.clear()

    session = chaine.runner.lancer(SLUG, None, "claude", "main", IDENTITE)

    assert session["branche"] == "main"
    assert session["ticket"] is None


def test_branche_hors_liste_refusee_sans_session(chaine, instance):
    from wap_runtime.runner import RunnerErreur

    with pytest.raises(RunnerErreur, match="non proposée"):
        chaine.runner.lancer(SLUG, None, "claude", "travail-en-cours", IDENTITE)

    assert Sessions(instance / "jobs").toutes() == []


def test_enchaînement_depuis_une_session_libre_sur_la_branche_de_pr(chaine, github):
    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    suivante = chaine.runner.enchainer(courante["id"], 31, chaine.jeton())()

    assert (courante := chaine.runner.session(courante["id"]))["etat"] == "enchaînée"
    assert courante["ticket"] is None
    assert (suivante["ticket"], suivante["commande"], suivante["branche"]) == (
        31, 'claude "/implement #31"', BRANCHE,
    )


def test_suivante_acceptee_enchaine_sur_le_meme_agent_et_la_meme_branche(chaine, instance, github):
    courante = chaine.runner.lancer(SLUG, 30, "cursor", BRANCHE, IDENTITE)
    git("commit", "--quiet", "--allow-empty", "-m", "poussé par l’agent", cwd=github)
    git("push", "--quiet", "origin", BRANCHE, cwd=github)

    ouvrir = chaine.runner.enchainer(courante["id"], 31, chaine.jeton())
    # Accepté, rien n’a encore bougé : l’agent reçoit la réponse avant.
    assert chaine.runner.session(courante["id"])["etat"] == "ouverte"
    assert chaine.arretes == []
    suivante = ouvrir()

    enchainee = chaine.runner.session(courante["id"])
    assert (enchainee["etat"], enchainee["suivante"], enchainee["precedente"]) == ("enchaînée", suivante["id"], None)
    assert enchainee["fin"] is not None
    assert chaine.arretes == [f"wap-{courante['id']}"]
    assert suivante["etat"] == "ouverte"
    assert (suivante["repo"], suivante["ticket"], suivante["agent"]) == (SLUG, 31, "cursor")
    assert suivante["commande"] == 'agent "/implement #31"'
    assert (suivante["precedente"], suivante["suivante"]) == (courante["id"], None)
    sur_disque = json.loads((instance / "jobs" / suivante["id"] / "session.json").read_text())
    assert sur_disque["precedente"] == courante["id"]
    clone = instance / "clones" / "o" / "r"
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone) == BRANCHE
    assert git("log", "-1", "--format=%s", cwd=clone) == "poussé par l’agent"
    assert git("config", "user.name", cwd=clone) == "octocat"
    # Nouveau processus, nouveau jeton ; l’exécuteur relit la commande dans `session.json`.
    commande, dossier = chaine.lances[-1]
    assert dossier == clone
    assert f"WAP_SESSION={suivante['id']}" in commande
    assert chaine.jeton() != chaine.jeton(0)
    assert commande[-2:] == [str(instance / "jobs"), suivante["id"]]
    assert not any(option in " ".join(commande) for option in ("--continue", "--resume"))


def test_l_executeur_lance_la_suivante_sans_reprise(chaine, instance, faux_bin):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)
    chaine.runner.enchainer(courante["id"], 31, chaine.jeton())()

    commande, dossier = chaine.lances[-1]
    subprocess.run(commande, cwd=dossier, check=True, capture_output=True)

    lancee = [l for l in appels(faux_bin) if l.startswith("claude ")]
    assert lancee == [f"claude /implement #31 @ {dossier.resolve()} @ octocat <{IDENTITE.email}>"]


def refus(chaine, courante, ticket=31, jeton=None):
    from wap_runtime.runner import RunnerErreur

    with pytest.raises(RunnerErreur) as erreur:
        chaine.runner.enchainer(courante["id"], ticket, jeton or chaine.jeton())
    return str(erreur.value)


def rien_n_a_bouge(chaine, instance, courante, lances=1):
    assert chaine.runner.session(courante["id"])["etat"] == "ouverte"
    assert chaine.arretes == []
    assert len(chaine.lances) == lances
    assert len(Sessions(instance / "jobs").toutes()) == lances


def test_mauvais_jeton_refuse(chaine, instance):
    from wap_runtime.runner import JetonRefuse

    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)

    with pytest.raises(JetonRefuse, match="jeton refusé"):
        chaine.runner.enchainer(courante["id"], 31, "pas-le-bon")

    rien_n_a_bouge(chaine, instance, courante)


def test_jeton_d_une_autre_session_refuse(chaine, instance):
    from wap_runtime.runner import JetonRefuse

    ancienne = chaine.runner.lancer(SLUG, 29, "claude", BRANCHE, IDENTITE)
    jeton_ancien = chaine.jeton()
    Sessions(instance / "jobs").clore(ancienne["id"], 0)
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)

    with pytest.raises(JetonRefuse):
        chaine.runner.enchainer(courante["id"], 31, jeton_ancien)
    with pytest.raises(JetonRefuse):
        chaine.runner.enchainer(ancienne["id"], 31, jeton_ancien)

    rien_n_a_bouge(chaine, instance, courante, lances=2)


def test_jeton_deja_utilise_refuse(chaine, instance):
    from wap_runtime.runner import JetonRefuse

    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)
    jeton = chaine.jeton()
    chaine.runner.enchainer(courante["id"], 31, jeton)

    # Avant même l’ouverture de la suivante : usage unique.
    with pytest.raises(JetonRefuse):
        chaine.runner.enchainer(courante["id"], 31, jeton)

    rien_n_a_bouge(chaine, instance, courante)


@pytest.mark.parametrize(
    "ticket, motif",
    [
        (30, "enfant fermé"),
        (32, "enfant bloqué"),
        (33, "pas `ready-for-agent`"),
        (40, "aucune version ouverte de o/r"),
        (50, "pas dans la version de la branche"),
        (99, "aucune version ouverte de o/r"),
    ],
)
def test_enfant_non_eligible_ou_d_un_autre_repo_refuse(chaine, instance, ticket, motif):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)

    assert motif in refus(chaine, courante, ticket)

    rien_n_a_bouge(chaine, instance, courante)
    # Refusé, le jeton reste valable.
    chaine.runner.enchainer(courante["id"], 31, chaine.jeton())


def test_clone_sale_refuse(chaine, instance):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)
    (instance / "clones" / "o" / "r" / "oublie.txt").write_text("non commité\n")

    assert "clone sale" in refus(chaine, courante)

    rien_n_a_bouge(chaine, instance, courante)


def test_github_injoignable_refuse(chaine, instance, faux_gh):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)
    faux_gh.repo(SLUG).panne = (500, {}, "panne")

    assert "GitHub a répondu 500" in refus(chaine, courante)

    rien_n_a_bouge(chaine, instance, courante)


@pytest.fixture
def client_chaine(chaine):
    return TestClient(creer_app_runner(chaine.runner))


def test_api_interne_suivante_202_puis_enchainement(chaine, client_chaine, instance):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)

    reponse = client_chaine.post(
        f"/sessions/{courante['id']}/suivante", json={"ticket": 31, "jeton": chaine.jeton(0)}
    )

    assert reponse.status_code == 202
    assert reponse.json()["detail"] == "session suivante : /implement #31"
    enchainee = chaine.runner.session(courante["id"])
    assert enchainee["etat"] == "enchaînée"
    assert chaine.runner.session(enchainee["suivante"])["ticket"] == 31


@pytest.mark.parametrize("jeton, ticket, code, motif", [("faux", 31, 403, "jeton refusé"), (None, 32, 422, "bloqué")])
def test_api_interne_suivante_refusee_avec_la_raison(chaine, client_chaine, instance, jeton, ticket, code, motif):
    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)

    reponse = client_chaine.post(
        f"/sessions/{courante['id']}/suivante", json={"ticket": ticket, "jeton": jeton or chaine.jeton()}
    )

    assert reponse.status_code == code
    assert motif in reponse.json()["detail"]
    rien_n_a_bouge(chaine, instance, courante)


def test_api_interne_suivante_session_inconnue_403(client_chaine):
    reponse = client_chaine.post("/sessions/..%2Fx/suivante", json={"ticket": 31, "jeton": "j"})

    assert reponse.status_code in (403, 404)


def test_etat_avec_le_jeton_met_a_jour_activite_et_reste_reutilisable(chaine):
    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    premiere = chaine.runner.enregistrer_etat(
        courante["id"], chaine.jeton(), "travaille", prompt="Ouvre la version"
    )
    seconde = chaine.runner.enregistrer_etat(
        courante["id"], chaine.jeton(), "attend", skill="grilling", prompt="autre"
    )

    assert (premiere["activite"], premiere["titre"]) == ("travaille", "Ouvre la version")
    assert (seconde["activite"], seconde["skill"], seconde["titre"]) == (
        "attend", "grilling", "Ouvre la version",
    )


def test_etat_mauvais_jeton_ou_session_close_refuse(chaine):
    from wap_runtime.runner import JetonRefuse

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    with pytest.raises(JetonRefuse, match="jeton refusé"):
        chaine.runner.enregistrer_etat(courante["id"], "pas-le-bon", "travaille")

    chaine.runner.terminer(courante["id"])
    with pytest.raises(JetonRefuse, match="jeton refusé"):
        chaine.runner.enregistrer_etat(courante["id"], chaine.jeton(), "travaille")
    assert chaine.runner.session(courante["id"])["activite"] == "inconnue"


def test_api_interne_etat_met_a_jour_la_session(chaine, client_chaine):
    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    reponse = client_chaine.post(
        f"/sessions/{courante['id']}/etat",
        json={"jeton": chaine.jeton(), "activite": "travaille", "prompt": "Ouvre la version"},
    )

    assert reponse.status_code == 200
    assert reponse.json()["activite"] == "travaille"
    assert chaine.runner.session(courante["id"])["titre"] == "Ouvre la version"


def test_api_interne_etat_mauvais_jeton_403(chaine, client_chaine):
    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)

    reponse = client_chaine.post(
        f"/sessions/{courante['id']}/etat",
        json={"jeton": "faux", "activite": "travaille"},
    )

    assert reponse.status_code == 403
    assert chaine.runner.session(courante["id"])["activite"] == "inconnue"


@pytest.fixture
def runner_servi(chaine):
    import threading

    import uvicorn

    srv = uvicorn.Server(
        uvicorn.Config(creer_app_runner(chaine.runner), host="127.0.0.1", port=0, log_level="warning")
    )
    fil = threading.Thread(target=srv.run, daemon=True)
    fil.start()
    while not srv.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{srv.servers[0].sockets[0].getsockname()[1]}"
    srv.should_exit = True
    fil.join()


@pytest.mark.parametrize("ticket, code, attendu", [(31, 0, "OK — session suivante : /implement #31"), (32, 1, "KO — #32 non éligible : enfant bloqué")])
def test_wap_runtime_enchainer_relaie_la_reponse_du_runner(chaine, runner_servi, monkeypatch, capsys, ticket, code, attendu):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, 30, "claude", BRANCHE, IDENTITE)
    commande, _ = chaine.lances[-1]
    for affectation in commande[1:4]:
        monkeypatch.setenv(*affectation.split("=", 1))
    monkeypatch.setenv("WAP_RUNNER", runner_servi)

    assert main(["enchainer", str(ticket)]) == code

    assert capsys.readouterr().out.strip() == attendu
    # L’enchaînement suit la réponse.
    attendu_etat = "enchaînée" if code == 0 else "ouverte"
    limite = time.monotonic() + 5
    while chaine.runner.session(courante["id"])["etat"] != attendu_etat and time.monotonic() < limite:
        time.sleep(0.05)
    assert chaine.runner.session(courante["id"])["etat"] == attendu_etat


def test_wap_runtime_enchainer_hors_session_ko(monkeypatch, capsys):
    from wap_runtime.cli import main

    monkeypatch.delenv("WAP_SESSION", raising=False)
    monkeypatch.delenv("WAP_SESSION_JETON", raising=False)

    assert main(["enchainer", "31"]) == 1
    assert capsys.readouterr().out.startswith("KO — ")


def _env_session(chaine, monkeypatch, runner_servi):
    commande, _ = chaine.lances[-1]
    for affectation in commande[1:4]:
        monkeypatch.setenv(*affectation.split("=", 1))
    monkeypatch.setenv("WAP_RUNNER", runner_servi)


def test_wap_runtime_etat_met_a_jour_avec_le_jeton_et_rend_0(chaine, runner_servi, monkeypatch):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)
    _env_session(chaine, monkeypatch, runner_servi)

    assert main(["etat", "travaille"]) == 0
    assert chaine.runner.session(courante["id"])["activite"] == "travaille"
    assert main(["etat", "attend", "--skill", "grilling"]) == 0
    lue = chaine.runner.session(courante["id"])
    assert (lue["activite"], lue["skill"]) == ("attend", "grilling")


def test_wap_runtime_etat_premier_message_devient_le_titre(chaine, runner_servi, monkeypatch):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)
    _env_session(chaine, monkeypatch, runner_servi)
    monkeypatch.setattr(
        "sys.stdin",
        type("Stdin", (), {"read": lambda self: json.dumps({"prompt": "Ouvre la version"})})(),
    )

    assert main(["etat", "travaille"]) == 0
    monkeypatch.setattr(
        "sys.stdin",
        type("Stdin", (), {"read": lambda self: json.dumps({"prompt": "autre"})})(),
    )
    assert main(["etat", "travaille"]) == 0
    assert chaine.runner.session(courante["id"])["titre"] == "Ouvre la version"


def test_wap_runtime_etat_skill_depuis_l_outil(chaine, runner_servi, monkeypatch):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)
    _env_session(chaine, monkeypatch, runner_servi)
    monkeypatch.setattr(
        "sys.stdin",
        type("Stdin", (), {
            "read": lambda self: json.dumps(
                {"tool_name": "Skill", "tool_input": {"skill": "grilling"}}
            )
        })(),
    )

    assert main(["etat", "travaille"]) == 0
    assert chaine.runner.session(courante["id"])["skill"] == "grilling"


@pytest.mark.parametrize("argv, env", [
    (["etat", "travaille"], False),
    (["etat", "travaille"], True),
])
def test_wap_runtime_etat_refus_rend_quand_meme_0(chaine, runner_servi, monkeypatch, argv, env):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)
    if env:
        _env_session(chaine, monkeypatch, runner_servi)
        monkeypatch.setenv("WAP_SESSION_JETON", "pas-le-bon")
    else:
        monkeypatch.delenv("WAP_SESSION", raising=False)
        monkeypatch.delenv("WAP_SESSION_JETON", raising=False)

    assert main(argv) == 0
    assert chaine.runner.session(courante["id"])["activite"] == "inconnue"


def test_wap_runtime_etat_session_close_rend_0(chaine, runner_servi, monkeypatch):
    from wap_runtime.cli import main

    courante = chaine.runner.lancer(SLUG, None, "claude", BRANCHE, IDENTITE)
    _env_session(chaine, monkeypatch, runner_servi)
    chaine.runner.terminer(courante["id"])

    assert main(["etat", "travaille"]) == 0
    assert chaine.runner.session(courante["id"])["activite"] == "inconnue"
