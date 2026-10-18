"""Ligne de commande de l’agent : `--model` Cursor, jamais pour Auto ni Claude."""

import pytest

from wap_runtime.agents import CLAUDE, CURSOR, commande_agent, ligne_commande


@pytest.mark.parametrize("modele", [None, "", "Auto", "auto"])
def test_cursor_auto_ou_vide_n_ajoute_pas_model(modele):
    assert commande_agent(CURSOR, None, modele) == ["agent"]
    assert commande_agent(CURSOR, 30, modele) == ["agent", "/implement #30"]
    assert ligne_commande(commande_agent(CURSOR, 30, modele)) == 'agent "/implement #30"'


def test_cursor_passe_model_avant_le_ticket():
    assert commande_agent(CURSOR, None, "composer-2") == ["agent", "--model", "composer-2"]
    assert commande_agent(CURSOR, 31, "composer-2") == [
        "agent", "--model", "composer-2", "/implement #31",
    ]
    assert ligne_commande(commande_agent(CURSOR, 31, "composer-2")) == (
        'agent --model composer-2 "/implement #31"'
    )


def test_claude_ignore_le_modele():
    assert commande_agent(CLAUDE, None, "composer-2") == ["claude"]
    assert commande_agent(CLAUDE, 30, "composer-2") == ["claude", "/implement #30"]
