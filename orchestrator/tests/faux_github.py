"""Faux GitHub REST, branché sur le client par un transport `httpx` injecté."""

import re
from dataclasses import dataclass, field

import httpx

JETON = "jeton-de-test"


@dataclass
class FauxRepo:
    issues: list[dict] = field(default_factory=list)
    sous_issues: dict[int, list[dict]] = field(default_factory=dict)
    pulls: list[dict] = field(default_factory=list)
    check_runs: dict[str, list[dict]] = field(default_factory=dict)
    statuts: dict[str, list[dict]] = field(default_factory=dict)
    # Réponse forcée pour toute route du repo : (code HTTP, en-têtes, message).
    panne: tuple[int, dict, str] | None = None

    def version(self, numero: int, enfants: list[tuple[int, str, list[str]]], titre=None, bloques=()):
        """Parent ouvert et ses enfants `(numéro, "open" | "closed", labels)` ; `bloques` : numéros
        des enfants qu’un bloqueur ouvert retient."""
        self.sous_issues[numero] = [
            _issue(n, f"Enfant {n}", etat, labels, bloque=n in bloques) for n, etat, labels in enfants
        ]
        parent = _issue(numero, titre or f"V0.{numero}.0", "open", [])
        parent["sub_issues_summary"] = {
            "total": len(enfants),
            "completed": sum(etat == "closed" for _, etat, _ in enfants),
            "percent_completed": 0,
        }
        self.issues.append(parent)
        return parent

    def bug(self, numero: int, titre: str, labels=("bug",)):
        self.issues.append(_issue(numero, titre, "open", list(labels)))

    def pr(
        self, numero: int, corps: str, sha: str, checks=(), statuts=(), brouillon=False, branche=None
    ):
        """PR ouverte ; `checks` en `(status, conclusion)`, `statuts` en états de commit."""
        self.pulls.append(
            {
                "number": numero,
                "title": f"PR {numero}",
                "body": corps,
                "draft": brouillon,
                "html_url": f"https://github.com/o/r/pull/{numero}",
                "head": {"sha": sha, "ref": branche or f"branche-{numero}"},
            }
        )
        self.issues.append({**_issue(numero, f"PR {numero}", "open", []), "pull_request": {}})
        self.check_runs[sha] = [
            {
                "name": f"check {i}",
                "status": s,
                "conclusion": c,
                "html_url": f"https://github.com/o/r/runs/{i}",
            }
            for i, (s, c) in enumerate(checks)
        ]
        self.statuts[sha] = [
            {"context": f"statut {i}", "state": e, "target_url": f"https://ci.example/{i}"}
            for i, e in enumerate(statuts)
        ]


def _issue(numero: int, titre: str, etat: str, labels: list[str], bloque=False) -> dict:
    return {
        "number": numero,
        "title": titre,
        "state": etat,
        "html_url": f"https://github.com/o/r/issues/{numero}",
        "labels": [{"name": nom} for nom in labels],
        "sub_issues_summary": {"total": 0, "completed": 0, "percent_completed": 0},
        # `blocked_by` : bloqueurs encore ouverts ; `total_blocked_by` compte aussi les fermés.
        "issue_dependencies_summary": {
            "blocked_by": int(bloque),
            "total_blocked_by": 1,
            "blocking": 0,
            "total_blocking": 0,
        },
    }


class FauxGitHub:
    def __init__(self):
        self.repos: dict[str, FauxRepo] = {}
        self.appels: list[str] = []
        self.compte = "octocat"

    def repo(self, slug: str) -> FauxRepo:
        return self.repos.setdefault(slug, FauxRepo())

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._repondre)

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        self.appels.append(chemin)
        if requete.headers.get("Authorization") != f"Bearer {JETON}":
            return httpx.Response(401, json={"message": "Bad credentials"})
        if chemin == "/user":
            return httpx.Response(200, json={"login": self.compte, "id": 583231})
        m = re.fullmatch(r"/repos/([^/]+/[^/]+)(/.*)", chemin)
        if not m or m[1] not in self.repos:
            return httpx.Response(404, json={"message": "Not Found"})
        repo, route = self.repos[m[1]], m[2]
        if repo.panne:
            code, entetes, message = repo.panne
            return httpx.Response(code, headers=entetes, json={"message": message})
        if route == "/issues":
            assert requete.url.params.get("state") == "open"
            return httpx.Response(200, json=repo.issues)
        if route == "/pulls":
            assert requete.url.params.get("state") == "open"
            return httpx.Response(200, json=repo.pulls)
        if m2 := re.fullmatch(r"/issues/(\d+)/sub_issues", route):
            return httpx.Response(200, json=repo.sous_issues.get(int(m2[1]), []))
        if m2 := re.fullmatch(r"/commits/(\w+)/check-runs", route):
            runs = repo.check_runs.get(m2[1], [])
            return httpx.Response(200, json={"total_count": len(runs), "check_runs": runs})
        if m2 := re.fullmatch(r"/commits/(\w+)/status", route):
            statuts = repo.statuts.get(m2[1], [])
            return httpx.Response(200, json={"state": "pending", "statuses": statuts})
        return httpx.Response(404, json={"message": "Not Found"})
