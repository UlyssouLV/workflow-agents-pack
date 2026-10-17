"""Encart Agents du cockpit : l’état de Claude Code et Cursor selon `secrets.env`.

`secrets.env` arrive dans `runtime` par `env_file` (relu à chaque `auth claude` / `auth agent`,
qui recréent les services) : l’API lit donc l’environnement du service.
"""

import pytest
from fastapi.testclient import TestClient

from wap_runtime.server import creer_app


def agents(tmp_path, env: dict) -> list[dict]:
    app = creer_app(registry=tmp_path / "repos.toml", jeton="", env=env)
    return TestClient(app).get("/api/agents").json()["agents"]


def test_sans_token_les_deux_agents_sont_non_connectes_avec_leur_commande(tmp_path):
    assert agents(tmp_path, {}) == [
        {
            "id": "claude",
            "nom": "Claude Code",
            "connecte": False,
            "commande": "sudo wap-runtime auth claude",
        },
        {
            "id": "cursor",
            "nom": "Cursor",
            "connecte": False,
            "commande": "… | sudo wap-runtime auth agent --with-token",
        },
    ]


@pytest.mark.parametrize(
    "env, claude, cursor",
    [
        ({"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"}, True, False),
        ({"ANTHROPIC_API_KEY": "sk-ant-api03-x"}, True, False),
        ({"CURSOR_API_KEY": "key_x"}, False, True),
        ({"CLAUDE_CODE_OAUTH_TOKEN": "", "CURSOR_API_KEY": " "}, False, False),
    ],
)
def test_connecte_veut_dire_token_present(tmp_path, env, claude, cursor):
    etat = {a["id"]: a["connecte"] for a in agents(tmp_path, env)}

    assert etat == {"claude": claude, "cursor": cursor}


def test_la_liste_des_repos_porte_aussi_l_etat_des_agents(tmp_path):
    app = creer_app(registry=tmp_path / "repos.toml", jeton="", env={"CURSOR_API_KEY": "key_x"})

    liste = TestClient(app).get("/api/repos").json()

    assert [(a["id"], a["connecte"]) for a in liste["agents"]] == [("claude", False), ("cursor", True)]
