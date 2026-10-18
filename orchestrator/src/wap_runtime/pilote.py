"""Boucle Pilote (ADR 0008) : un tour lance le premier `/implement #n` éligible.

Le runtime n’appelle pas `enchainer` : session libre, puis le premier message dans le terminal.
"""

from pathlib import Path

from wap_runtime.cockpit import Cockpit
from wap_runtime.eligibilite import lancements
from wap_runtime.github import ClientGitHub, GitHubErreur
from wap_runtime.registry import lire_registry
from wap_runtime.runner import (
    ClientRunner,
    CloneSale,
    Identite,
    RunnerErreur,
    SessionOuverte,
    SessionQuiTravaille,
    email_noreply,
)
from wap_runtime.sessions import Sessions


def tourner(
    registry: Path,
    cockpit: Cockpit,
    sessions: Sessions,
    runner: ClientRunner,
    agents: list[dict],
    github: ClientGitHub | None,
) -> dict | None:
    """Un tour : au plus une session libre + `/implement #n` (plus petit éligible). `None` sinon."""
    if github is None:
        return None
    for repo in lire_registry(registry):
        if not repo.pilote:
            continue
        ouverte = sessions.ouverte(repo.slug)
        if ouverte is not None:
            continue
        detail = cockpit.detail(repo.slug)
        if detail is None or detail["erreur"]:
            continue
        detail = lancements(detail, None, agents)
        agent = next((a for a in agents if a["id"] == repo.agent), None)
        if agent is None or not agent["connecte"]:
            continue
        candidats = [
            (enfant["numero"], version["pr"]["branche"])
            for version in detail["versions"]
            for enfant in version["enfants"]
            if enfant["lancement"].get(repo.agent) is None
        ]
        if not candidats:
            continue
        numero, branche = min(candidats, key=lambda c: c[0])
        try:
            compte = github.utilisateur()
            identite = Identite(compte["login"], email_noreply(compte["login"], compte["id"]))
            session = runner.lancer(repo.slug, None, repo.agent, branche, identite)
        except (GitHubErreur, CloneSale, SessionOuverte, SessionQuiTravaille, RunnerErreur):
            return None
        runner.saisir(session["id"], f"/implement #{numero}\r")
        return session
    return None
