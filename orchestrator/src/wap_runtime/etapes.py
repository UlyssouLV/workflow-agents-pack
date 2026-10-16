"""Étape d’une version ouverte, déduite du tracker (spec 0.3.0, « Étapes affichées »).

Le cockpit lit les labels, il ne les pose pas.
"""

from dataclasses import asdict, dataclass

# État agrégé des checks et statuts du commit de tête de la PR de version.
CI_ECHEC, CI_EN_COURS, CI_OK, CI_AUCUNE = "echec", "en_cours", "ok", "aucune"
_CONCLUSIONS_ECHEC = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}


@dataclass(frozen=True)
class Etape:
    numero: int | None
    libelle: str
    humain: bool

    def en_json(self) -> dict:
        return asdict(self)


QUESTION = Etape(1, "Question en attente", True)
ETAPE_CI_ECHEC = Etape(2, "CI en échec", True)
TESTS_HUMAINS_EN_COURS = Etape(3, "Tests humains en cours", True)
TESTS_HUMAINS_A_FAIRE = Etape(4, "Tests humains à faire", True)
TESTS_AGENT_EN_COURS = Etape(5, "Tests agent en cours", False)
ETAPE_CI_EN_COURS = Etape(6, "CI en cours", False)
IMPLEMENT = Etape(7, "Implement", False)
FINALISE = Etape(8, "Code review / Finalise à faire", True)
PAS_DE_VERSION = Etape(9, "Pas de version ouverte", False)
# Aucune règle ne s’applique (ex. enfants fermés sans PR de version).
INDETERMINEE = Etape(None, "Étape indéterminée", False)


def etat_ci(check_runs: list[dict], statuts: list[dict]) -> str:
    """Échec l’emporte sur en cours, qui l’emporte sur ok ; rien → aucune."""
    etats = {etat_check(c) for c in check_runs} | {etat_statut(s) for s in statuts}
    if not etats:
        return CI_AUCUNE
    return next((e for e in (CI_ECHEC, CI_EN_COURS) if e in etats), CI_OK)


def etat_check(check_run: dict) -> str:
    if check_run["status"] != "completed":
        return CI_EN_COURS
    return CI_ECHEC if check_run["conclusion"] in _CONCLUSIONS_ECHEC else CI_OK


def etat_statut(statut: dict) -> str:
    if statut["state"] in ("failure", "error"):
        return CI_ECHEC
    return CI_EN_COURS if statut["state"] == "pending" else CI_OK


def signaux(enfants: list[dict], ci: str | None) -> list[Etape]:
    """Toutes les règles qui s’appliquent, dans l’ordre de priorité.

    `enfants` : sub-issues du parent (`state`, `labels`) ; `ci` : `None` sans PR de version.
    """
    ouverts = [set(noms_labels(e)) for e in enfants if e["state"] == "open"]
    regles = [
        (QUESTION, any("needs-info" in l for l in ouverts)),
        (ETAPE_CI_ECHEC, ci == CI_ECHEC),
        (TESTS_HUMAINS_EN_COURS, any("in-human-test" in l for l in ouverts)),
        (TESTS_HUMAINS_A_FAIRE, bool(ouverts) and all("ready-for-human" in l for l in ouverts)),
        (TESTS_AGENT_EN_COURS, any("in-agent-test" in l for l in ouverts)),
        (ETAPE_CI_EN_COURS, ci == CI_EN_COURS),
        (IMPLEMENT, any("ready-for-agent" in l for l in ouverts)),
        (FINALISE, not ouverts and ci is not None),
    ]
    return [etape for etape, applicable in regles if applicable]


def etape_de_version(applicables: list[Etape]) -> Etape:
    """La première des `signaux` d’une version, sinon indéterminée."""
    return applicables[0] if applicables else INDETERMINEE


def etape_du_repo(etapes: list[Etape]) -> Etape:
    """Étape d’un repo parmi celles de ses versions : celles qui attendent quelqu’un d’abord
    (le badge suit l’étape affichée), puis par priorité ; sans version, pas de version."""
    numerotees = [e for e in etapes if e.numero is not None]
    if numerotees:
        return min(numerotees, key=lambda e: (not e.humain, e.numero))
    return etapes[0] if etapes else PAS_DE_VERSION


def noms_labels(issue: dict) -> list[str]:
    return [label["name"] for label in issue.get("labels", [])]
