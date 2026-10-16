"""Lecture de l’API REST GitHub avec le `GH_TOKEN` de l’instance (pas de `gh` dans l’image)."""

from datetime import datetime, timezone

import httpx

API_GITHUB = "https://api.github.com"
TOKEN_REFUSE = "token refusé par GitHub : `sudo wap-runtime auth`"


class GitHubErreur(Exception):
    """Lecture refusée ou impossible ; le message tient sur une ligne."""

    def __init__(self, message: str, statut: int | None = None):
        super().__init__(message)
        self.statut = statut


class ClientGitHub:
    """`transport` injectable : les tests y branchent un faux GitHub."""

    def __init__(
        self,
        jeton: str,
        api: str = API_GITHUB,
        transport: httpx.BaseTransport | None = None,
    ):
        self._http = httpx.Client(
            base_url=api,
            transport=transport,
            timeout=10,
            headers={
                "Authorization": f"Bearer {jeton}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def compte(self) -> str:
        return self._lire("/user")["login"]

    def issues_ouvertes(self, slug: str) -> list[dict]:
        """Issues ouvertes, sans les PR (que l’API des issues rend aussi)."""
        issues = self._paginer(f"/repos/{slug}/issues", state="open")
        return [i for i in issues if "pull_request" not in i]

    def sous_issues(self, slug: str, numero: int) -> list[dict]:
        return self._paginer(f"/repos/{slug}/issues/{numero}/sub_issues")

    def prs_ouvertes(self, slug: str) -> list[dict]:
        return self._paginer(f"/repos/{slug}/pulls", state="open")

    def check_runs(self, slug: str, sha: str) -> list[dict]:
        return self._lire(f"/repos/{slug}/commits/{sha}/check-runs", per_page=100)["check_runs"]

    def statuts(self, slug: str, sha: str) -> list[dict]:
        return self._lire(f"/repos/{slug}/commits/{sha}/status", per_page=100)["statuses"]

    def _paginer(self, chemin: str, **params) -> list[dict]:
        reponse = self._get(chemin, params={**params, "per_page": 100})
        elements = reponse.json()
        while suivante := reponse.links.get("next", {}).get("url"):
            reponse = self._get(suivante)
            elements += reponse.json()
        return elements

    def _lire(self, chemin: str, **params) -> dict:
        return self._get(chemin, params=params).json()

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        try:
            reponse = self._http.get(url, params=params)
        except httpx.HTTPError as erreur:
            raise GitHubErreur(f"GitHub injoignable ({erreur})") from erreur
        if reponse.is_success:
            return reponse
        raise GitHubErreur(_message(reponse), reponse.status_code)


def _message(reponse: httpx.Response) -> str:
    code = reponse.status_code
    try:
        detail = reponse.json().get("message", "")
    except ValueError:
        detail = ""
    if code == 429 or (
        code == 403
        and (reponse.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in detail.lower())
    ):
        return f"limite d’appels GitHub atteinte{_reprise(reponse)}"
    if code == 401:
        return TOKEN_REFUSE
    if code == 403:
        return "accès refusé : le token n’a pas de droit sur ce repo"
    if code == 404:
        return "introuvable : repo inexistant ou invisible pour le token"
    return f"GitHub a répondu {code}" + (f" ({detail})" if detail else "")


def _reprise(reponse: httpx.Response) -> str:
    if (attente := reponse.headers.get("retry-after", "")).isdigit():
        return f", réessaie dans {attente} s"
    if (reset := reponse.headers.get("x-ratelimit-reset", "")).isdigit():
        heure = datetime.fromtimestamp(int(reset), timezone.utc)
        return f", réessaie après {heure:%H:%M} UTC"
    return ""
