"""Éligibilité du bouton `/implement #n` (spec 0.4.0) : la raison d’un bouton grisé, ou `None`."""


def raison_grisee(
    enfant: dict, pr: dict | None, session_ouverte: dict | None, agent_connecte: bool
) -> str | None:
    """`enfant` et `pr` à la forme de l’API du cockpit ; la première règle non tenue l’emporte."""
    labels = enfant["labels"]
    regles = [
        (enfant["ouvert"], "enfant fermé"),
        ("ready-for-agent" in labels, "pas `ready-for-agent`"),
        (not enfant["bloque"], "enfant bloqué"),
        ("in-agent-test" not in labels, "déjà `in-agent-test`"),
        (pr is not None, "pas de PR de version"),
        (session_ouverte is None, "session déjà ouverte"),
        (agent_connecte, "agent non connecté"),
    ]
    return next((raison for tenue, raison in regles if not tenue), None)


def enfant_de_version(versions: list[dict], ticket: int) -> tuple[dict, dict | None] | None:
    """L’enfant `#ticket` et la PR de sa version, parmi `versions` (API du cockpit) ; `None` s’il
    n’est l’enfant d’aucune."""
    return next(((e, v["pr"]) for v in versions for e in v["enfants"] if e["numero"] == ticket), None)


def lancements(detail: dict, session_ouverte: dict | None, agents: list[dict]) -> dict:
    """`detail` (API du cockpit) dont chaque enfant porte `lancement` : la raison par agent,
    `None` si `/implement #n` est possible."""
    versions = []
    for version in detail["versions"]:
        enfants = [
            {
                **enfant,
                "lancement": {
                    a["id"]: raison_grisee(enfant, version["pr"], session_ouverte, a["connecte"])
                    for a in agents
                },
            }
            for enfant in version["enfants"]
        ]
        versions.append({**version, "enfants": enfants})
    return {**detail, "versions": versions}
