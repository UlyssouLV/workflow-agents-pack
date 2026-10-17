"""Service `runner` (ADR 0004) : prépare le clone géré et y lance l’agent dans une session tmux.

API interne, non publiée : le `runtime` l’appelle sur le réseau Compose. Le runner ne pose
aucun label.
"""

import os
import re
import secrets
import shlex
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, get_args
from urllib.parse import quote

from wap_runtime.agents import Agent, agent_par_id, commande_agent
from wap_runtime.eligibilite import enfant_de_version, raison_grisee
from wap_runtime.enregistrement import CODE_NON_LANCE
from wap_runtime.sessions import CODE_ARRETEE, ID_SESSION, OUVERTE, Sessions

if TYPE_CHECKING:
    from wap_runtime.github import ClientGitHub

DEPOT_GITHUB = "https://github.com/{slug}.git"
PORT_RUNNER = 8788
# Dans l’environnement de chaque agent (ADR 0006) : la commande qui ouvre la session suivante.
ENCHAINER = "wap-runtime enchainer"
# Réponses au clone sale ; sans l’une d’elles, rien n’est lancé (pas de remise à zéro automatique).
Choix = Literal["reprendre", "jeter"]
REPRENDRE, JETER = get_args(Choix)
# Ce qui arrive de la requête et finit en argument de `git` : jamais une option (`-…`).
# `owner/name` : chacun commence par un alphanumérique, donc ni `-`, ni `.`/`..` hors de `clones/`.
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._-]*")
_BRANCHE = re.compile(r"(?!.*\.\.)[\w][\w.+/-]*")
_LOGIN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
_EMAIL = re.compile(r"[\w.+][\w.+@-]*")


class RunnerErreur(Exception):
    """Lancement impossible ; le message tient sur une ligne."""


class CloneSale(Exception):
    """Changements non commités dans le clone géré : le lancement attend **Reprendre** ou **Jeter**."""

    def __init__(self, fichiers: list[dict], diff: str):
        super().__init__("le clone a des changements non commités : Reprendre ou Jeter")
        self.fichiers = fichiers
        self.diff = diff

    def corps(self) -> dict:
        """Le corps de la réponse `409`, côté runner comme côté cockpit."""
        return {"detail": str(self), "clone": {"fichiers": self.fichiers, "diff": self.diff}}


class JetonRefuse(RunnerErreur):
    """La demande de session suivante ne vient pas de l’agent de la session ouverte."""


class SessionOuverte(Exception):
    def __init__(self, session: dict):
        super().__init__(f"session {session['id']} déjà ouverte")
        self.session = session


@dataclass(frozen=True)
class Identite:
    """Identité git des commits : le compte de `GH_TOKEN` et son adresse noreply."""

    login: str
    email: str


@dataclass(frozen=True)
class _Lancement:
    """Ce que la session suivante reprend d’une session lancée, et le jeton de son agent. En
    mémoire seulement : un runner qui redémarre interrompt ses sessions."""

    jeton: str
    branche: str
    identite: Identite


def email_noreply(login: str, id_: int) -> str:
    return f"{id_}+{login}@users.noreply.github.com"


def lanceur_tmux(nom: str, commande: list[str], dossier: Path) -> None:
    """Session tmux détachée : elle survit à la requête, et à l’onglet du cockpit."""
    subprocess.run(
        [
            "tmux", "new-session", "-d", "-s", nom, "-c", str(dossier), shlex.join(commande),
            # Le cockpit montre le terminal de l’agent, sans barre ni raccourcis tmux.
            ";", "set-option", "-t", nom, "status", "off",
            ";", "set-option", "-t", nom, "prefix", "None",
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def arreteur_tmux(nom: str) -> None:
    """Ferme la session tmux : son terminal disparaît, l’agent reçoit SIGHUP."""
    # Déjà partie (agent sorti, runner redémarré) : rien à arrêter.
    subprocess.run(["tmux", "kill-session", "-t", nom], capture_output=True, stdin=subprocess.DEVNULL)


def nom_tmux(id_: str) -> str:
    return f"wap-{id_}"


class Runner:
    def __init__(
        self,
        clones: Path,
        jobs: Path,
        lanceur: Callable[[str, list[str], Path], None] = lanceur_tmux,
        depot: str = DEPOT_GITHUB,
        arreteur: Callable[[str], None] = arreteur_tmux,
        attente: float = 10,
        github: "ClientGitHub | None" = None,
    ):
        """`depot` : URL du dépôt, `{slug}` remplacé (les tests y mettent un dépôt local).

        `attente` : secondes laissées à l’agent pour sortir après **Terminer**.

        `github` : de quoi vérifier l’éligibilité d’une session suivante ; sans lui, toute
        demande est refusée.

        Un runner qui démarre n’a aucun agent en cours : les sessions restées ouvertes passent
        `interrompue`.
        """
        self._clones = clones
        self._sessions = Sessions(jobs)
        self._sessions.interrompre()
        self._lanceur = lanceur
        self._depot = depot
        self._arreteur = arreteur
        self._attente = attente
        self._github = github
        # Par session lancée ; retiré quand son jeton a servi.
        self._lancements: dict[str, _Lancement] = {}
        # Deux requêtes simultanées ne doivent pas ouvrir deux sessions.
        self._verrou = threading.Lock()

    def lancer(
        self, repo: str, ticket: int, agent: str, branche: str, identite: Identite, choix: Choix | None = None
    ) -> dict:
        """Lève `SessionOuverte` s’il y en a déjà une, `CloneSale` si le clone a des changements
        non commités et que `choix` ne dit pas quoi en faire, `RunnerErreur` si le clone ne se
        prépare pas.

        `choix` (ignoré sur un clone propre) : `reprendre` lance sur l’arbre tel quel, sans
        changer de branche ; `jeter` enregistre les changements dans `jobs/<id>/abandon.patch`,
        puis `reset --hard` et `clean -fd` avant le lancement normal.
        """
        if (connu := agent_par_id(agent)) is None:
            raise RunnerErreur(f"agent inconnu : {agent}")
        if choix is not None and choix not in (REPRENDRE, JETER):
            raise RunnerErreur(f"choix inconnu : {choix}")
        if not _REPO.fullmatch(repo):
            raise RunnerErreur(f"repo invalide : {repo}")
        if not _BRANCHE.fullmatch(branche):
            raise RunnerErreur(f"branche invalide : {branche}")
        if not (_LOGIN.fullmatch(identite.login) and _EMAIL.fullmatch(identite.email)):
            raise RunnerErreur(f"identité git invalide : {identite.login} <{identite.email}>")
        with self._verrou:
            if (ouverte := self._sessions.ouverte()) is not None:
                raise SessionOuverte(ouverte)
            dossier = self.recuperer_clone(repo, branche)
            fichiers = changements(dossier)
            if fichiers and choix is None:
                raise CloneSale(fichiers, diff_complet(dossier))
            session = self._creer(repo, ticket, connu)
            if fichiers and choix == JETER:
                # Enregistré avant de toucher à l’arbre : rien n’est perdu si la suite échoue.
                patch = self._sessions.jobs / session["id"] / "abandon.patch"
                patch.write_text(diff_complet(dossier))
                try:
                    _git(dossier, "reset", "--quiet", "--hard")
                    _git(dossier, "clean", "--quiet", "-fd")
                except RunnerErreur:
                    self._sessions.clore(session["id"], CODE_NON_LANCE)
                    raise
            sur_place = bool(fichiers) and choix == REPRENDRE
            return self._demarrer(session, dossier, _Lancement("", branche, identite), sur_place)

    def enchainer(self, id_: str, ticket: int, jeton: str) -> Callable[[], dict]:
        """Demande de l’agent de la session `id_` (ADR 0006) : ouvrir `/implement #ticket` à sa suite.

        Lève `JetonRefuse` si `jeton` n’est pas celui de la session ouverte `id_` ou a déjà servi ;
        `RunnerErreur` si le clone est sale, ou si `#ticket` n’est pas un enfant éligible de la
        version de la même branche, dans le même repo. Refusée, rien n’est lancé ni fermé et le
        jeton reste valable.

        Acceptée, le jeton est consommé ; rend l’ouverture, à appeler une fois l’agent prévenu : la
        session passe `enchaînée` (tmux arrêté), puis la suivante démarre avec le même agent, sur la
        même branche, dans un nouveau processus. Elle rend la suivante, ou lève `RunnerErreur`
        (la suivante est alors close).
        """
        with self._verrou:
            session = self._sessions.lire(id_)
            lancement = self._lancements.get(id_)
            if (
                session is None
                or session["etat"] != OUVERTE
                or lancement is None
                or not secrets.compare_digest(jeton.encode(), lancement.jeton.encode())
            ):
                raise JetonRefuse("jeton refusé : pas celui de la session ouverte, ou déjà utilisé")
            dossier = self.recuperer_clone(session["repo"], lancement.branche)
            if fichiers := changements(dossier):
                raise RunnerErreur(
                    f"clone sale ({len(fichiers)} fichier(s) non commité(s)) : commite et pousse avant d’enchaîner"
                )
            self._verifier_eligible(session["repo"], ticket, lancement.branche)
            del self._lancements[id_]
        return lambda: self._ouvrir_suivante(session, ticket, lancement, dossier)

    def _verifier_eligible(self, repo: str, ticket: int, branche: str) -> None:
        """Les règles du bouton `/implement #n` du cockpit, lues en direct sur GitHub."""
        from wap_runtime.cockpit import lire_versions
        from wap_runtime.github import GitHubErreur

        if self._github is None:
            raise RunnerErreur("GitHub non connecté : `sudo wap-runtime auth`")
        try:
            versions = lire_versions(self._github, repo, self._github.issues_ouvertes(repo))
        except GitHubErreur as erreur:
            raise RunnerErreur(str(erreur)) from erreur
        if (trouve := enfant_de_version(versions, ticket)) is None:
            raise RunnerErreur(f"#{ticket} n’est l’enfant d’aucune version ouverte de {repo}")
        enfant, pr = trouve
        # La session ouverte est celle qui demande ; son agent est connecté puisqu’il tourne.
        if raison := raison_grisee(enfant, pr, None, True):
            raise RunnerErreur(f"#{ticket} non éligible : {raison}")
        if pr["branche"] != branche:
            raise RunnerErreur(f"#{ticket} n’est pas dans la version de la branche {branche}")

    def _ouvrir_suivante(self, courante: dict, ticket: int, lancement: _Lancement, dossier: Path) -> dict:
        with self._verrou:
            if self._sessions.lire(courante["id"])["etat"] != OUVERTE:
                raise RunnerErreur(f"session {courante['id']} close avant l’enchaînement")
            suivante = self._creer(courante["repo"], ticket, agent_par_id(courante["agent"]), courante["id"])
            self._sessions.enchainer(courante["id"], suivante["id"])
            self._arreteur(nom_tmux(courante["id"]))
            return self._demarrer(suivante, dossier, lancement)

    def _creer(self, repo: str, ticket: int, agent: Agent, precedente: str | None = None) -> dict:
        argv = commande_agent(agent, ticket)
        return self._sessions.creer(repo, ticket, agent.id, f'{argv[0]} "{argv[1]}"', precedente)

    def _demarrer(self, session: dict, dossier: Path, lancement: _Lancement, sur_place: bool = False) -> dict:
        """Positionne le clone, y expose les skills et lance l’exécuteur dans tmux, avec un nouveau
        jeton ; un échec clôt la session et lève `RunnerErreur`."""
        id_ = session["id"]
        try:
            self.positionner_clone(dossier, lancement.branche, lancement.identite, sur_place)
            exposer_skills(dossier)
        except RunnerErreur:
            self._sessions.clore(id_, CODE_NON_LANCE)
            raise
        jeton = secrets.token_urlsafe(32)
        self._lancements[id_] = _Lancement(jeton, lancement.branche, lancement.identite)
        # L’exécuteur relit l’agent et le ticket dans `session.json` ; l’agent hérite de cet
        # environnement, hors de `session.json` que le cockpit lit.
        executeur = [
            "env", f"WAP_ENCHAINER={ENCHAINER}", f"WAP_SESSION={id_}", f"WAP_SESSION_JETON={jeton}",
            sys.executable, "-m", "wap_runtime.sessions", str(self._sessions.jobs), id_,
        ]
        try:
            self._lanceur(nom_tmux(id_), executeur, dossier)
        except (OSError, subprocess.CalledProcessError) as erreur:
            del self._lancements[id_]
            self._sessions.clore(id_, CODE_NON_LANCE)
            raise RunnerErreur(f"tmux : {erreur}") from erreur
        return self._sessions.lire(id_)

    def session(self, id_: str) -> dict | None:
        return self._sessions.lire(id_)

    def terminer(self, id_: str) -> dict | None:
        """**Terminer** : arrête l’agent, rend la session close (`None` si inconnue).

        L’exécuteur clôt la session avec le code de sortie de l’agent ; s’il ne l’a pas fait dans
        le délai (agent sourd à SIGHUP, tmux déjà parti), le runner la clôt lui-même.
        """
        session = self._sessions.lire(id_)
        if session is None or session["etat"] != OUVERTE:
            return session
        self._arreteur(nom_tmux(id_))
        limite = time.monotonic() + self._attente
        while time.monotonic() < limite:
            if (lue := self._sessions.lire(id_))["etat"] != OUVERTE:
                return lue
            time.sleep(0.05)
        return self._sessions.clore(id_, CODE_ARRETEE)

    def recuperer_clone(self, repo: str, branche: str) -> Path:
        """`clones/<owner>/<name>/` à jour de GitHub, sans toucher à l’arbre ; `branche` doit y exister.

        Créé au premier lancement (HTTPS, `GH_TOKEN` par `gh auth setup-git`), sinon `fetch`.
        """
        dossier = self._clones / repo
        if not (dossier / ".git").is_dir():
            dossier.parent.mkdir(parents=True, exist_ok=True)
            _executer(["gh", "auth", "setup-git"], "gh auth setup-git")
            _git(None, "clone", "--quiet", self._depot.format(slug=repo), str(dossier))
        else:
            _git(dossier, "fetch", "--quiet", "--prune", "origin")
        try:
            _git(dossier, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branche}")
        except RunnerErreur:
            raise RunnerErreur(f"branche {branche} inexistante sur GitHub") from None
        return dossier

    def positionner_clone(self, dossier: Path, branche: str, identite: Identite, sur_place: bool = False) -> None:
        """Sur `branche` à jour de `origin` (`sur_place` : la branche courante, pour **Reprendre**),
        avec l’identité git."""
        if not sur_place:
            _git(dossier, "switch", "--quiet", branche)
            _git(dossier, "merge", "--quiet", "--ff-only", f"origin/{branche}")
        _git(dossier, "config", "user.name", identite.login)
        _git(dossier, "config", "user.email", identite.email)


def exposer_skills(dossier: Path) -> None:
    """Les skills du pack à la version de la branche : `agents/scripts/dispatch.py` du clone les
    copie sous `.claude/skills/` et `.cursor/skills/`.

    Sans `agents/skills/` ou sans `dispatch.py`, rien : le pack ne s’initialise pas ici. Un
    dispatch qui échoue ou modifie un fichier suivi lève `RunnerErreur` (les changements déjà là,
    sur **Reprendre**, ne comptent pas).
    """
    dispatch = Path("agents") / "scripts" / "dispatch.py"
    if not ((dossier / "agents" / "skills").is_dir() and (dossier / dispatch).is_file()):
        return
    avant = _git(dossier, "diff", "--binary", "HEAD")
    _executer(["python3", str(dispatch)], "dispatch.py", dossier)
    if _git(dossier, "diff", "--binary", "HEAD") != avant:
        raise RunnerErreur("fichier suivi modifié par dispatch.py : l’agent n’est pas lancé")


def changements(dossier: Path) -> list[dict]:
    """Changements non commités du clone (fichiers non suivis compris, ignorés exclus) ; `[]` sans clone."""
    if not (dossier / ".git").is_dir():
        return []
    sortie = _git(dossier, "status", "--porcelain", "--untracked-files=all", "-z")
    fichiers, entrees = [], iter(sortie.split("\0"))
    for entree in entrees:
        if not entree:
            continue
        statut = entree[:2].strip()
        if statut[0] in "RC":
            # `-z` : l’ancien chemin d’un renommage suit, dans sa propre entrée.
            next(entrees, None)
        fichiers.append({"statut": statut, "chemin": entree[3:]})
    return fichiers


def diff_complet(dossier: Path) -> str:
    """`git diff HEAD` et les fichiers non suivis, en un patch que `git apply` rejoue."""
    racine = ["git", "-C", str(dossier)]
    diff = _git(dossier, "diff", "--binary", "HEAD")
    sortie = _git(dossier, "ls-files", "--others", "--exclude-standard", "-z")
    for chemin in filter(None, sortie.split("\0")):
        # `--no-index` sort en 1 quand les fichiers diffèrent : c’est le cas attendu.
        nouveau = subprocess.run(
            [*racine, "diff", "--binary", "--no-index", "--", "/dev/null", chemin],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        if nouveau.returncode not in (0, 1):
            raise RunnerErreur(f"git diff a échoué : {nouveau.stderr.strip()}")
        diff += nouveau.stdout
    return diff


def _git(dossier: Path | None, sous_commande: str, *args: str) -> str:
    """`git -C <dossier> <sous_commande> …` (`dossier` absent : le dossier courant) ; l’étape
    d’une erreur nomme la sous-commande."""
    racine = ["git"] if dossier is None else ["git", "-C", str(dossier)]
    return _executer([*racine, sous_commande, *args], f"git {sous_commande}")


def _executer(commande: list[str], etape: str, dossier: Path | None = None) -> str:
    try:
        return subprocess.run(
            commande, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=dossier
        ).stdout
    except FileNotFoundError as erreur:
        raise RunnerErreur(f"{etape} : {erreur}") from erreur
    except subprocess.CalledProcessError as erreur:
        detail = (erreur.stderr or "").strip().splitlines()
        raise RunnerErreur(f"{etape} a échoué" + (f" : {detail[-1]}" if detail else "")) from erreur


class ClientRunner:
    """Côté `runtime` : l’API interne du runner (`WAP_RUNNER`), sur le réseau Compose."""

    def __init__(self, http):
        self._http = http

    def _poster(self, chemin: str, **options):
        import httpx

        try:
            return self._http.post(chemin, **options)
        except httpx.HTTPError as erreur:
            raise RunnerErreur(f"runner injoignable ({erreur})") from erreur

    def lancer(
        self, repo: str, ticket: int, agent: str, branche: str, identite: Identite, choix: Choix | None = None
    ) -> dict:
        """Mêmes erreurs que `Runner.lancer` ; `RunnerErreur` aussi si le runner est injoignable."""
        demande = {"repo": repo, "ticket": ticket, "agent": agent, "branche": branche,
                   "login": identite.login, "email": identite.email}
        if choix is not None:
            demande["choix"] = choix
        # Le premier clone d’un gros repo peut être long.
        reponse = self._poster("/sessions", json=demande, timeout=300)
        if reponse.status_code == 409:
            corps = reponse.json()
            if "clone" in corps:
                raise CloneSale(corps["clone"]["fichiers"], corps["clone"]["diff"])
            raise SessionOuverte(corps["session"])
        if not reponse.is_success:
            try:
                detail = reponse.json()["detail"]
            except (ValueError, KeyError, TypeError):
                detail = f"le runner a répondu {reponse.status_code}"
            raise RunnerErreur(str(detail))
        return reponse.json()

    def terminer(self, id_: str) -> dict:
        """`RunnerErreur` si le runner est injoignable ou ne connaît pas la session."""
        if not ID_SESSION.fullmatch(id_):
            raise RunnerErreur(f"session {id_} inconnue")
        reponse = self._poster(f"/sessions/{quote(id_, safe='')}/terminer", timeout=60)
        if not reponse.is_success:
            raise RunnerErreur(f"le runner a répondu {reponse.status_code}")
        return reponse.json()

    def url_terminal(self, id_: str) -> str:
        """Websocket du terminal de la session, sur le réseau Compose."""
        if not ID_SESSION.fullmatch(id_):
            raise RunnerErreur(f"session {id_} inconnue")
        base = str(self._http.base_url).rstrip("/")
        return f"ws{base.removeprefix('http')}/sessions/{quote(id_, safe='')}/terminal"


def creer_app_runner(runner: Runner):
    """`POST /sessions` : 201 et la session, 409 et la session ouverte ou le clone sale (fichiers et
    diff), 422 et le message.

    `POST /sessions/{id}/terminer` : la session close ; websocket `/sessions/{id}/terminal` : le
    terminal en direct d’une session ouverte (`wap_runtime.terminal`).
    """
    from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    from wap_runtime import __version__
    from wap_runtime.terminal import Ecrivains, relayer

    class Lancement(BaseModel):
        repo: str
        ticket: int
        agent: str
        branche: str
        login: str
        email: str
        choix: Choix | None = None

    class Suivante(BaseModel):
        ticket: int
        jeton: str

    app = FastAPI(title="wap-runner", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    # `def` : FastAPI l’exécute hors de la boucle, le clone peut prendre du temps.
    @app.post("/sessions", status_code=201)
    def lancer(demande: Lancement):
        identite = Identite(demande.login, demande.email)
        try:
            return runner.lancer(
                demande.repo, demande.ticket, demande.agent, demande.branche, identite, demande.choix
            )
        except SessionOuverte as refus:
            return JSONResponse({"detail": str(refus), "session": refus.session}, status_code=409)
        except CloneSale as refus:
            return JSONResponse(refus.corps(), status_code=409)
        except RunnerErreur as erreur:
            return JSONResponse({"detail": str(erreur)}, status_code=422)

    @app.post("/sessions/{id_}/terminer")
    def terminer(id_: str) -> dict:
        if not ID_SESSION.fullmatch(id_) or (session := runner.terminer(id_)) is None:
            raise HTTPException(404, f"session {id_} inconnue")
        return session

    @app.post("/sessions/{id_}/suivante", status_code=202)
    def suivante(id_: str, demande: Suivante, taches: BackgroundTasks):
        """Depuis la session (`wap-runtime enchainer`) : 202, puis l’enchaînement une fois la
        réponse partie ; 403 (jeton) ou 422 et la raison du refus."""
        try:
            ouvrir = runner.enchainer(id_, demande.ticket, demande.jeton)
        except JetonRefuse as refus:
            return JSONResponse({"detail": str(refus)}, status_code=403)
        except RunnerErreur as erreur:
            return JSONResponse({"detail": str(erreur)}, status_code=422)

        def ouvrir_apres_la_reponse() -> None:
            # Échouée, la suivante est close ; l’agent qui demandait n’est plus là pour le lire.
            with suppress(RunnerErreur):
                ouvrir()

        taches.add_task(ouvrir_apres_la_reponse)
        return {"detail": f"session suivante : /implement #{demande.ticket}"}

    ecrivains = Ecrivains()

    @app.websocket("/sessions/{id_}/terminal")
    async def terminal(websocket: WebSocket, id_: str) -> None:
        session = runner.session(id_) if ID_SESSION.fullmatch(id_) else None
        if session is None or session["etat"] != OUVERTE:
            # Avant `accept` : la poignée de main est refusée.
            await websocket.close()
            return
        await websocket.accept()
        with ecrivains.connexion(id_) as main:
            await relayer(websocket, nom_tmux(session["id"]), main)

    return app


def servir_runner(hote: str, port: int) -> None:
    import uvicorn

    from wap_runtime.github import ClientGitHub

    # `GH_TOKEN` de `secrets.env` (`env_file`) : une nouvelle connexion recrée le service.
    jeton = os.environ.get("GH_TOKEN")
    runner = Runner(
        Path(os.environ.get("WAP_CLONES", "/clones")),
        Path(os.environ.get("WAP_JOBS", "/jobs")),
        github=ClientGitHub(jeton) if jeton else None,
    )
    uvicorn.run(creer_app_runner(runner), host=hote, port=port, log_level="warning")
