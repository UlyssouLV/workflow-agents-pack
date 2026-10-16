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
    if not check_runs and not statuts:
        return CI_AUCUNE
    if any(c["status"] == "completed" and c["conclusion"] in _CONCLUSIONS_ECHEC for c in check_runs) or any(
        s["state"] in ("failure", "error") for s in statuts
    ):
        return CI_ECHEC
    if any(c["status"] != "completed" for c in check_runs) or any(s["state"] == "pending" for s in statuts):
        return CI_EN_COURS
    return CI_OK


def signaux(enfants: list[dict], ci: str | None) -> list[Etape]:
    """Toutes les règles qui s’appliquent, dans l’ordre de priorité.

    `enfants` : sub-issues du parent (`state`, `labels`) ; `ci` : `None` sans PR de version.
    """
    ouverts = [_labels(e) for e in enfants if e["state"] == "open"]
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


def choisir(signaux_: list[Etape]) -> Etape:
    return signaux_[0] if signaux_ else INDETERMINEE


def la_plus_prioritaire(etapes: list[Etape]) -> Etape:
    """Étape d’un repo : celle de ses versions qui passe en premier, sinon pas de version."""
    numerotees = [e for e in etapes if e.numero is not None]
    if numerotees:
        return min(numerotees, key=lambda e: e.numero)
    return etapes[0] if etapes else PAS_DE_VERSION


def _labels(issue: dict) -> set[str]:
    return {label["name"] for label in issue.get("labels", [])}
