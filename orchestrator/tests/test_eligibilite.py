"""Éligibilité du bouton `/implement #n`, règle par règle (spec 0.4.0)."""

import pytest

from wap_runtime.eligibilite import raison_grisee

PR = {"numero": 18, "branche": "v0.4.0-runner"}


def enfant(**champs) -> dict:
    return {
        "numero": 30,
        "ouvert": True,
        "labels": ["ready-for-agent"],
        "bloque": False,
        **champs,
    }


def raison(e=None, pr=PR, session=None, connecte=True):
    return raison_grisee(e or enfant(), pr, session, connecte)


def test_enfant_eligible_sans_raison():
    assert raison() is None


@pytest.mark.parametrize(
    "e, attendue",
    [
        (enfant(ouvert=False), "enfant fermé"),
        (enfant(labels=[]), "pas `ready-for-agent`"),
        (enfant(bloque=True), "enfant bloqué"),
        (enfant(labels=["ready-for-agent", "in-agent-test"]), "déjà `in-agent-test`"),
    ],
)
def test_regles_de_l_enfant(e, attendue):
    assert raison(e) == attendue


def test_sans_pr_de_version():
    assert raison(pr=None) == "pas de PR de version"


def test_session_deja_ouverte_sur_l_instance():
    assert raison(session={"id": "s1", "repo": "x/y"}) == "session déjà ouverte"


def test_agent_non_connecte():
    assert raison(connecte=False) == "agent non connecté"


def test_la_premiere_regle_qui_echoue_donne_la_raison():
    assert raison(enfant(ouvert=False, bloque=True), pr=None, connecte=False) == "enfant fermé"
