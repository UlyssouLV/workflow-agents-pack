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

## Installer l’orchestrateur sur une machine hôte

Sur un serveur **Debian 12+ ou Ubuntu 22.04+**, une seule commande, sans interaction hormis la connexion GitHub quand un terminal est disponible (ADR 0003) :

```bash
curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash
```

Elle installe `python3`, `pipx` et `git`, crée l’utilisateur système `orchestrator`, installe pour lui le paquet `wap-runtime`, puis lance `wap-runtime setup` : socle manquant (Docker + Compose, `gh`, `claude`, `agent`, sans authentification), instance `/home/orchestrator/.wap-runtime/`, `docker compose up -d --build`, attente de `GET /health`, puis connexion GitHub de l’instance si elle n’est pas faite (voir **Connexion GitHub**). La relancer répare ou met à niveau sans réinstaller ce qui est présent ni toucher à `secrets.env` ou aux valeurs éditées de `config.toml`. Le service repart seul après un redémarrage (`restart: unless-stopped`) et n’écoute que sur `127.0.0.1`.

Options, par variables d’environnement passées à `sudo` :

| Variable | Défaut | Effet |
| --- | --- | --- |
| `WAP_PORT` | `8787` | Port publié sur `127.0.0.1` (à la création de `config.toml`) |
| `WAP_PACK_REF` | `main` | Branche ou tag du pack cloné dans l’instance (à la création de `config.toml`) |
| `WAP_DEBUG` | — | `1` : trace bash (`set -x`) et journal verbeux |
| `GH_TOKEN` | — | Token GitHub utilisé pour connecter l’instance, sans interaction |
| `WAP_SKIP_AUTH` | — | `1` : ne lance pas le device flow GitHub, même dans un terminal |

```bash
curl -fsSL …/orchestrator/install.sh | sudo WAP_PORT=9000 WAP_DEBUG=1 bash
```

**Log et debug** : chaque étape est journalisée dans `/var/log/wap-runtime/install.log`. Un échec nomme l’étape, renvoie à ce log et sort en code `≠ 0` ; relancer avec `WAP_DEBUG=1` pour une trace détaillée.

**Santé** : `sudo -u orchestrator ~orchestrator/.local/bin/wap-runtime health` dit en une ligne si le runtime répond (code `0` si OK), sur le port de `config.toml` (`--port N` pour un autre).

**Connexion GitHub** (ADR 0003) : `sudo ~orchestrator/.local/bin/wap-runtime auth` lance `gh auth login` (device flow : un code et une URL à valider dans le navigateur) en utilisateur `orchestrator`, copie son token dans `secrets.env` (`0600`) sous `GH_TOKEN`, puis recrée le service `runtime` pour qu’il le lise. `… | sudo wap-runtime auth --with-token` lit un token (fine-grained par exemple) sur stdin. Relancer `auth` reconnecte l’instance ou change de compte. `auth status` affiche une ligne par connexion — GitHub (compte connecté, ou « non connecté »), Claude Code, Cursor — et sort en code `0` si GitHub est connecté, `≠ 0` sinon (les agents sont au choix). En fin de `setup`, si l’instance n’est pas connectée : `GH_TOKEN` présent → utilisé ; sinon terminal disponible et pas `WAP_SKIP_AUTH=1` → `auth` ; sinon le setup réussit en affichant la prochaine étape.

**Connexion des agents** (ADR 0004) : `sudo ~orchestrator/.local/bin/wap-runtime auth claude` lance `claude setup-token` en utilisateur `orchestrator` sur l’hôte (une URL à ouvrir dans le navigateur, un code à recoller dans le terminal), relève le token affiché et l’écrit dans `secrets.env` (`0600`) sous `CLAUDE_CODE_OAUTH_TOKEN`. `… | sudo wap-runtime auth claude --with-token` lit le token sur stdin à la place ; une clé API Anthropic (`sk-ant-api…`) y est acceptée et s’écrit sous `ANTHROPIC_API_KEY` (une seule identité Claude à la fois : l’autre clé est retirée). Cursor se connecte par clé API (`agent login` exige un navigateur sur la machine) : `… | sudo wap-runtime auth agent --with-token` l’écrit sous `CURSOR_API_KEY`. Chaque écriture remplace l’ancien token sans toucher aux autres lignes, puis recrée tous les services de l’instance pour qu’ils relisent `secrets.env` ; relancer la commande reconnecte l’agent après une révocation. « Connecté » veut dire token présent, sans appel de vérification : un token refusé se voit dans le terminal de l’agent. `setup` ne lance pas ces connexions ; il affiche celles qui manquent comme prochaine étape.

**Repos liés** : `sudo ~orchestrator/.local/bin/wap-runtime repo add owner/name [--nom <affichage>]`, `repo remove owner/name` et `repo list` gèrent le registry `~orchestrator/.wap-runtime/repos.toml` (en root, l’instance visée est celle d’`orchestrator`). `owner/name` invalide ou en double est refusé. Le fichier s’édite aussi à la main ; `setup` n’y touche pas, et le service `runtime` le voit en lecture seule (l’instance est montée sur `/instance:ro`).

**Cockpit** : le service `runtime` sert un cockpit en lecture seule sur `http://127.0.0.1:<port>/` (port de `config.toml`, `8787` par défaut). La vue liste montre une ligne par repo lié — version ouverte, progression X/Y, étape, badge **Intervention humaine requise**, heure de lecture — les repos qui attendent quelqu’un en tête, et se relit toutes les 60 s (la lecture GitHub de la liste est gardée 60 s). Un repo inaccessible n’affiche que sa ligne en erreur ; un bandeau demande `sudo wap-runtime auth` si l’instance n’est pas connectée ou si son token est refusé ; l’encart **Agents** dit si Claude Code et Cursor sont connectés, avec la commande à lancer sur l’hôte pour ceux qui ne le sont pas. La vue `/repos/<owner>/<name>` relit le repo en direct : parent, enfants (état, labels, bloqué), PR de version et ses checks, bugs ouverts. Les liens ouvrent GitHub ; aucune action n’est lancée depuis le cockpit. L’API JSON est sous `/api/` (`/api/repos`, `/api/repos/<owner>/<name>`, `/api/auth`, `/api/agents`).

Le port n’écoute que sur `127.0.0.1` de l’hôte (ADR 0002) : depuis votre poste, ouvrez un tunnel SSH puis le navigateur.

```bash
ssh -L 8787:127.0.0.1:8787 mon-serveur      # puis http://127.0.0.1:8787/
```

**Désinstallation** : `sudo ~orchestrator/.local/bin/wap-runtime uninstall` (en root, l’instance visée est celle d’`orchestrator`) arrête et retire le Compose ; `--purge` supprime aussi l’instance. Docker, `gh` et les CLIs agents restent installés.

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

L’installation éditable fournit la commande `orchestrator/.venv/bin/wap-runtime` (`serve`, `health [--port N]`, `auth [status|claude|agent] [--with-token]`, `repo add|remove|list`, `setup`, `uninstall [--purge]`).

Le front du cockpit vit sous `orchestrator/cockpit/` (React + TypeScript + Vite, Node 24) ; l’image le construit dans une étape Node, l’hôte n’a pas besoin de Node :

```bash
cd orchestrator/cockpit && npm ci
npm run dev        # front sur http://127.0.0.1:5173/, API relayée vers un `wap-runtime serve` local (8787)
npm run build      # typecheck + build dans dist/ ; `WAP_COCKPIT=dist wap-runtime serve` le sert sur /
```

Lancer les tests : **`/t`** dans Claude Code ou Cursor (deux test-roots : pytest sous `orchestrator/`, Vitest sous `orchestrator/cockpit/`), ou directement :

```bash
cd orchestrator && .venv/bin/pytest
cd orchestrator/cockpit && npm test
```

## Repères

- Règles pour les agents : [`AGENTS.md`](AGENTS.md).
- Specs de version : [`docs/specs/`](docs/specs/). Décisions : [`docs/adr/`](docs/adr/).
- Cycle Ouvre / Implement / Finalise, tracker, labels : [`agents/issue-tracker.md`](agents/issue-tracker.md), [`agents/docs/integration-channel.md`](agents/docs/integration-channel.md).
