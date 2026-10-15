# workflow-agents-pack — orchestrateur (`feat/runtime-orchestrator`)

Cette branche développe l’**orchestrateur** self-hosted : un runtime installé sur la machine de l’utilisateur (Linux, pas un VPS imposé) et un cockpit local qui suit puis pilote les repos métier ayant adopté le pack de skills. Produit public et générique : aucune instance perso dans ce dépôt. Vocabulaire : [`docs/glossaire.md`](docs/glossaire.md).

## Trajectoire

| Version | Objectif |
| --- | --- |
| 0.1.0 | Frontière pack / runtime : le pack est un outil installé, `orchestrator/` est la zone de code |
| 0.2.0 | Provisionning de la machine hôte (Linux + CLIs, Docker Compose, healthcheck) |
| 0.3.0 | Registry des repos métier + cockpit en lecture seule |
| 0.4.0 | Runner distant borné : lancer une action agent depuis le cockpit |
| 0.5.0 | FSM et blocages humains (`running` / `needs-human` / `failed` / `done`) |
| 0.6.0 | Autopilot borné : enchaîner les enfants `ready-for-agent` tant que rien ne bloque |

Détail, hors périmètre et suite : [feuille de route](docs/dev/feuille-de-route/feuille-de-route-dev.md).

## Le pack vit sur `main`

Le pack de skills se maintient sur `main` ; cette branche n’y est jamais fusionnée. Ici, le pack est un outil installé : `agents/skills/`, `agents/hooks/`, `agents/scripts/`, `agents/templates/`, `.claude/skills/` et `.cursor/skills/` sont ignorés par git. Un skill à corriger se corrige sur `main`, puis se réinstalle ici. Voir l’[ADR 0001](docs/adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md).

Les versions de cette branche partent de `feat/runtime-orchestrator` et y reviennent (tags `orchestrator-v*`) : [`agents/integration-channel.yml`](agents/integration-channel.yml).

## Installer les skills

Cloner la branche :

```bash
git clone -b feat/runtime-orchestrator https://github.com/UlyssouLV/workflow-agents-pack.git
cd workflow-agents-pack
```

Puis, à la racine du dépôt :

```bash
mkdir -p agents/skills
TMP=$(mktemp -d)
git clone --depth 1 -b main https://github.com/UlyssouLV/workflow-agents-pack.git "$TMP"
bash "$TMP/agents/scripts/update-from-pack.sh"
rm -rf "$TMP"
```

Le script copie skills, hooks et scripts du pack puis lance `dispatch.py` (skills visibles dans Claude Code et Cursor).

**Mettre à jour** quand les skills évoluent sur `main` : relancer ce second bloc, sans le `mkdir`, à la racine du dépôt (pas le clone). `git status` reste propre.

## Préparer l’environnement de dev

Le code vit sous `orchestrator/` (paquet Python `wap-runtime`), les tests sous `orchestrator/tests/`. Python 3.12 pour le dev (le paquet accepte ≥ 3.10) :

```bash
python3.12 -m venv orchestrator/.venv
orchestrator/.venv/bin/pip install -e 'orchestrator[dev]'
```

L’installation éditable fournit la commande `orchestrator/.venv/bin/wap-runtime` (`serve`, `health [--port N]`).

Lancer les tests : **`/t`** dans Claude Code ou Cursor, ou directement :

```bash
cd orchestrator && .venv/bin/pytest
```

## Repères

- Règles pour les agents : [`AGENTS.md`](AGENTS.md).
- Specs de version : [`docs/specs/`](docs/specs/). Décisions : [`docs/adr/`](docs/adr/).
- Cycle Ouvre / Implement / Finalise, tracker, labels : [`agents/issue-tracker.md`](agents/issue-tracker.md), [`agents/docs/integration-channel.md`](agents/docs/integration-channel.md).
