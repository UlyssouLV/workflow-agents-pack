"""Boucle Pilote (ADR 0008) : un tour lance le premier `/implement #n` éligible.

Le runtime n’appelle pas `enchainer` : session libre, puis le premier message dans le terminal.
"""

from pathlib import Path

from wap_runtime.cockpit import Cockpit
from wap_runtime.eligibilite import lancements
from wap_runtime.github import ClientGitHub, GitHubErreur
from wap_runtime.registry import RepoLie, lire_registry
from wap_runtime.runner import (
    ClientRunner,
    CloneSale,
    Identite,
    RunnerErreur,
    SessionOuverte,
    SessionQuiTravaille,
    email_noreply,
)
from wap_runtime.sessions import ATTEND, ECHOUEE, INTERROMPUE, Sessions

# Stops exposés sur liste/détail (`pilote_stop`) tant que la condition dure.
ATTENDRE, HUMAIN, AUCUN = "attend", "humain_requis", "aucun_eligible"
ECHEC = "echec_lancement"
_STOPS_SESSION = {ECHOUEE: "echouee", INTERROMPUE: "interrompue"}


def stop_du_pilote(
    repo: RepoLie,
    detail: dict | None,
    ouverte: dict | None,
    derniere: dict | None,
    agents: list[dict],
    echec: bool = False,
) -> str | None:
    """Raison de pause/stop, ou `None` si le pilote peut lancer ou seulement surveiller."""
    if not repo.pilote:
        return None
    if ouverte is not None and ouverte.get("activite") == ATTEND:
        return ATTENDRE
    if ouverte is None and derniere is not None and derniere["etat"] in _STOPS_SESSION:
        return _STOPS_SESSION[derniere["etat"]]
    if detail is None or detail.get("erreur"):
        return ECHEC
    if detail.get("humain_requis"):
        return HUMAIN
    agent = next((a for a in agents if a["id"] == repo.agent), None)
    if agent is None or not agent["connecte"]:
        return ECHEC
    if any("enfants" in v for v in detail.get("versions", [])) and not _candidats(
        detail, agents, repo.agent
    ):
        return AUCUN
    return ECHEC if echec else None


def tourner(
    registry: Path,
    cockpit: Cockpit,
    sessions: Sessions,
    runner: ClientRunner,
    agents: list[dict],
    github: ClientGitHub | None,
    echecs: dict[str, bool] | None = None,
) -> dict | None:
    """Un tour : au plus une session libre + `/implement #n` (plus petit éligible). `None` sinon."""
    if github is None:
        return None
    echecs = {} if echecs is None else echecs
    for repo in lire_registry(registry):
        ouverte = sessions.ouverte(repo.slug)
        derniere = next(iter(sessions.du_repo(repo.slug)), None)
        detail = None if not repo.pilote else cockpit.detail(repo.slug)
        cle = repo.slug.lower()
        if stop_du_pilote(repo, detail, ouverte, derniere, agents, echecs.get(cle, False)):
            continue
        if not repo.pilote or ouverte is not None:
            continue
        if detail is None or detail["erreur"]:
            continue
        candidats = _candidats(detail, agents, repo.agent)
        if not candidats:
            continue
        numero, branche = min(candidats, key=lambda c: c[0])
        try:
            compte = github.utilisateur()
            identite = Identite(compte["login"], email_noreply(compte["login"], compte["id"]))
            session = runner.lancer(repo.slug, None, repo.agent, branche, identite)
        except (GitHubErreur, CloneSale, SessionOuverte, SessionQuiTravaille, RunnerErreur):
            echecs[cle] = True
            return None
        echecs.pop(cle, None)
        runner.saisir(session["id"], f"/implement #{numero}\r")
        return session
    return None


def _candidats(detail: dict, agents: list[dict], agent: str) -> list[tuple[int, str]]:
    detail = lancements(detail, None, agents)
    return [
        (enfant["numero"], version["pr"]["branche"])
        for version in detail["versions"]
        for enfant in version["enfants"]
        if enfant["lancement"].get(agent) is None
    ]
