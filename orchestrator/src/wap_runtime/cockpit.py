"""API du cockpit : l’état des repos liés, lu sur GitHub.

Le registry est relu à chaque appel. La liste garde la lecture GitHub de chaque repo (et
l’état d’auth) `CACHE_SECONDES` ; le détail d’un repo est lu en direct. Rien n’est persisté.
"""

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from wap_runtime import etapes
from wap_runtime.github import TOKEN_REFUSE, ClientGitHub, GitHubErreur
from wap_runtime.registry import RegistryErreur, RepoLie, lire_registry

CACHE_SECONDES = 60
SANS_TOKEN = "GitHub non connecté : `sudo wap-runtime auth`"


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

    def detail(self, slug: str) -> dict | None:
        """Le repo lié `slug`, lu en direct (sans cache) ; `None` s’il n’est pas dans le registry.

        Lève `RegistryErreur` si le registry est illisible.
        """
        repo = next((r for r in lire_registry(self._registry) if r.designe(slug)), None)
        if repo is None:
            return None
        lu_a = self._horloge()
        if self._client is None:
            return {**_en_erreur(repo, lu_a, SANS_TOKEN), "bugs": [], "branches": _sans_branches()}
        try:
            issues = self._client.issues_ouvertes(repo.slug)
            versions = lire_versions(self._client, repo.slug, issues)
            branches = branches_de_session(self._client, repo.slug, versions)
        except GitHubErreur as erreur:
            return {**_en_erreur(repo, lu_a, str(erreur)), "bugs": [], "branches": _sans_branches()}
        return {
            **_etat(repo, lu_a, versions),
            "bugs": [_bug(i) for i in issues if "bug" in etapes.noms_labels(i)],
            "branches": branches,
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
            versions = lire_versions(self._client, repo.slug, self._client.issues_ouvertes(repo.slug))
        except GitHubErreur as erreur:
            return _en_erreur(repo, lu_a, str(erreur))
        etat = _etat(repo, lu_a, versions)
        return {**etat, "versions": [_resume(v) for v in etat["versions"]]}


def branches_de_session(client: ClientGitHub, slug: str, versions: list[dict]) -> dict:
    """Base d’intégration + branches des PR de version ; défaut = PR de version, sinon la base."""
    base = base_d_integration(client, slug)
    proposees = [base]
    prs = []
    for version in versions:
        if version["pr"] and (branche := version["pr"]["branche"]) not in proposees:
            proposees.append(branche)
        if version["pr"]:
            prs.append(version["pr"]["branche"])
    return {"proposees": proposees, "defaut": prs[0] if prs else base}


def base_d_integration(client: ClientGitHub, slug: str) -> str:
    """`base_branch` de `agents/integration-channel.yml`, sinon la branche par défaut du repo."""
    if texte := client.fichier(slug, "agents/integration-channel.yml"):
        for ligne in texte.splitlines():
            if (m := re.match(r"^base_branch:\s*[\"']?([^\"'#\s]+)", ligne)):
                return m.group(1)
    return client.depot(slug)["default_branch"]


def _sans_branches() -> dict:
    return {"proposees": [], "defaut": ""}


def lire_versions(client: ClientGitHub, slug: str, issues: list[dict]) -> list[dict]:
    """Versions ouvertes du repo (parmi `issues`, celles ayant des sub-issues), avec enfants,
    PR de version et ses checks, signaux et étape retenue (`Etape`)."""
    parents = [i for i in issues if (i.get("sub_issues_summary") or {}).get("total")]
    if not parents:
        return []
    prs = client.prs_ouvertes(slug)
    versions = []
    for parent in parents:
        enfants = client.sous_issues(slug, parent["number"])
        pr = pr_de_version(prs, parent["number"])
        checks = ci = None
        if pr is not None:
            sha = pr["head"]["sha"]
            runs, statuts = client.check_runs(slug, sha), client.statuts(slug, sha)
            ci, checks = etapes.etat_ci(runs, statuts), _checks(runs, statuts)
        resume = parent["sub_issues_summary"]
        signaux = etapes.signaux(enfants, ci)
        versions.append(
            {
                "numero": parent["number"],
                "titre": parent["title"],
                "url": parent["html_url"],
                "progression": {"completed": resume["completed"], "total": resume["total"]},
                "enfants": [_enfant(e) for e in enfants],
                "pr": None
                if pr is None
                else {
                    "numero": pr["number"],
                    "titre": pr["title"],
                    "url": pr["html_url"],
                    "brouillon": pr.get("draft", False),
                    # Branche où le runner lance les sessions.
                    "branche": pr["head"]["ref"],
                    "ci": ci,
                    "checks": checks,
                },
                "signaux": signaux,
                "etape": etapes.etape_de_version(signaux),
            }
        )
    return versions


def _checks(runs: list[dict], statuts: list[dict]) -> list[dict]:
    """Checks et statuts du commit de tête, un par un."""
    return [
        {"nom": c["name"], "etat": etapes.etat_check(c), "url": c.get("html_url")} for c in runs
    ] + [
        {"nom": s["context"], "etat": etapes.etat_statut(s), "url": s.get("target_url")}
        for s in statuts
    ]


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


def _etat(repo: RepoLie, lu_a: datetime, versions: list[dict]) -> dict:
    """Le repo et ses versions en JSON ; le badge suit l’étape retenue pour le repo."""
    etape = etapes.etape_du_repo([v["etape"] for v in versions])
    return {
        **_identite(repo, lu_a),
        "erreur": None,
        "etape": etape.en_json(),
        "humain_requis": etape.humain,
        "versions": [
            {**v, "etape": v["etape"].en_json(), "signaux": [e.en_json() for e in v["signaux"]]}
            for v in versions
        ],
    }


def _resume(version: dict) -> dict:
    """Ce que la liste garde d’une version : ni enfants, ni signaux, ni checks."""
    pr = version["pr"]
    return {
        **{k: version[k] for k in ("numero", "titre", "url", "progression", "etape")},
        "pr": None if pr is None else {k: pr[k] for k in ("numero", "url", "brouillon", "ci")},
    }


def _enfant(issue: dict) -> dict:
    dependances = issue.get("issue_dependencies_summary") or {}
    return {
        "numero": issue["number"],
        "titre": issue["title"],
        "url": issue["html_url"],
        "ouvert": issue["state"] == "open",
        "labels": etapes.noms_labels(issue),
        # `blocked_by` ne compte que les bloqueurs encore ouverts.
        "bloque": dependances.get("blocked_by", 0) > 0,
    }


def _bug(issue: dict) -> dict:
    return {
        "numero": issue["number"],
        "titre": issue["title"],
        "url": issue["html_url"],
        "labels": etapes.noms_labels(issue),
    }


def _en_erreur(repo: RepoLie, lu_a: datetime, message: str) -> dict:
    return {
        **_identite(repo, lu_a),
        "erreur": message,
        "etape": None,
        "humain_requis": False,
        "versions": [],
    }
