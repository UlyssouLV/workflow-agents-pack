"""Vue liste du cockpit : l’état de chaque repo lié, lu sur GitHub derrière un cache mémoire.

Le registry est relu à chaque appel ; seule la lecture GitHub de chaque repo (et l’état
d’auth) est gardée `CACHE_SECONDES`. Rien n’est persisté.
"""

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from wap_runtime import etapes
from wap_runtime.github import ClientGitHub, GitHubErreur
from wap_runtime.registry import RegistryErreur, RepoLie, lire_registry

CACHE_SECONDES = 60
SANS_TOKEN = "GitHub non connecté : `sudo wap-runtime auth`"
TOKEN_REFUSE = "token refusé par GitHub : `sudo wap-runtime auth`"


class Cockpit:
    def __init__(
        self,
        registry: Path,
        client: ClientGitHub | None,
        horloge: Callable[[], datetime],
    ):
        self._registry = registry
        self._client = client
        self._horloge = horloge
        self._cache: dict[str, tuple[datetime, dict]] = {}
        self._verrou = threading.Lock()

    def auth(self, cache: bool = False) -> dict:
        """`connecte` (avec le compte), `sans_token`, `token_refuse` ou `injoignable`."""
        if self._client is None:
            return {"etat": "sans_token", "compte": None}
        return self._memoiser("/user", self._lire_auth) if cache else self._lire_auth()

    def liste(self) -> dict:
        auth = self.auth(cache=True)
        try:
            repos = lire_registry(self._registry)
        except RegistryErreur as erreur:
            return {"auth": auth, "erreur": str(erreur), "repos": []}
        return {
            "auth": auth,
            "erreur": None,
            "repos": [self._entree(repo, auth["etat"]) for repo in repos],
        }

    def _entree(self, repo: RepoLie, auth: str) -> dict:
        if auth == "sans_token":
            return _en_erreur(repo, self._horloge(), SANS_TOKEN)
        if auth == "token_refuse":
            # Inutile d’appeler GitHub : chaque lecture serait refusée.
            return _en_erreur(repo, self._horloge(), TOKEN_REFUSE)
        return self._memoiser(repo.slug.lower(), lambda: self._lire_repo(repo))

    def _memoiser(self, cle: str, lire: Callable[[], dict]) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            garde = self._cache.get(cle)
        if garde and (maintenant - garde[0]).total_seconds() < CACHE_SECONDES:
            return garde[1]
        valeur = lire()
        with self._verrou:
            self._cache[cle] = (maintenant, valeur)
        return valeur

    def _lire_auth(self) -> dict:
        try:
            return {"etat": "connecte", "compte": self._client.compte()}
        except GitHubErreur as erreur:
            etat = "token_refuse" if erreur.statut == 401 else "injoignable"
            return {"etat": etat, "compte": None}

    def _lire_repo(self, repo: RepoLie) -> dict:
        lu_a = self._horloge()
        try:
            versions = lire_versions(self._client, repo.slug)
        except GitHubErreur as erreur:
            return _en_erreur(repo, lu_a, str(erreur))
        etape = etapes.la_plus_prioritaire([v["etape"] for v in versions])
        return {
            **_identite(repo, lu_a),
            "erreur": None,
            "etape": etape.en_json(),
            "humain_requis": any(v["etape"].humain for v in versions),
            "versions": [{**v, "etape": v["etape"].en_json()} for v in versions],
        }


def lire_versions(client: ClientGitHub, slug: str) -> list[dict]:
    """Versions ouvertes du repo (issues ouvertes ayant des sub-issues), étape comprise."""
    parents = [
        i for i in client.issues_ouvertes(slug) if (i.get("sub_issues_summary") or {}).get("total")
    ]
    if not parents:
        return []
    prs = client.prs_ouvertes(slug)
    versions = []
    for parent in parents:
        enfants = client.sous_issues(slug, parent["number"])
        pr = pr_de_version(prs, parent["number"])
        ci = None
        if pr is not None:
            sha = pr["head"]["sha"]
            ci = etapes.etat_ci(client.check_runs(slug, sha), client.statuts(slug, sha))
        resume = parent["sub_issues_summary"]
        versions.append(
            {
                "numero": parent["number"],
                "titre": parent["title"],
                "url": parent["html_url"],
                "progression": {"completed": resume["completed"], "total": resume["total"]},
                "pr": None
                if pr is None
                else {
                    "numero": pr["number"],
                    "url": pr["html_url"],
                    "brouillon": pr.get("draft", False),
                    "ci": ci,
                },
                "etape": etapes.choisir(etapes.signaux(enfants, ci)),
            }
        )
    return versions


def pr_de_version(prs: list[dict], parent: int) -> dict | None:
    """PR ouverte dont le corps contient `Fixes #<parent>`."""
    motif = re.compile(rf"\bfixes\s+#{parent}\b", re.IGNORECASE)
    return next((pr for pr in prs if motif.search(pr.get("body") or "")), None)


def _identite(repo: RepoLie, lu_a: datetime) -> dict:
    return {
        "slug": repo.slug,
        "nom": repo.nom,
        "url": f"https://github.com/{repo.slug}",
        "lu_a": lu_a.isoformat(),
    }


def _en_erreur(repo: RepoLie, lu_a: datetime, message: str) -> dict:
    return {
        **_identite(repo, lu_a),
        "erreur": message,
        "etape": None,
        "humain_requis": False,
        "versions": [],
    }
