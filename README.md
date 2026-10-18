# workflow-agents-pack — orchestrateur (`feat/runtime-orchestrator`)

Cette branche développe l’**orchestrateur** self-hosted : un runtime installé sur la machine de l’utilisateur (Linux, pas un VPS imposé) et un cockpit local qui suit puis pilote les repos métier ayant adopté le pack de skills. Produit public et générique : aucune instance perso dans ce dépôt. Vocabulaire : [`docs/glossaire.md`](docs/glossaire.md).

## Trajectoire

| Version | Objectif |
| --- | --- |
| 0.1.0 | Frontière pack / runtime : le pack est un outil installé, `orchestrator/` est la zone de code |
| 0.2.0 | Provisionning de la machine hôte (Linux + CLIs, Docker Compose, healthcheck) |
| 0.3.0 | Registry des repos métier + cockpit en lecture seule |
| 0.4.0 | Runner distant borné : lancer `/implement` depuis le cockpit dans un terminal, sessions enregistrées et rejouables |
| 0.4.1 | Correctifs du runner distant (tests humains 0.4.0) |
| 0.4.2 | Session libre et réponse attendue |
| 0.5.0 | Pilote : démarrer et surveiller la chaîne Implement (stops + notifs), sans remplacer l’enchaînement du pack |
| 0.6.0 | Instances multiples isolées sur un même serveur |
| 0.7.0 | Accès web authentifié |

Détail, hors périmètre et suite : [feuille de route](docs/dev/feuille-de-route/feuille-de-route-dev.md).

## Installer l’orchestrateur sur une machine hôte

Sur un serveur **Debian 12+ ou Ubuntu 22.04+**, une seule commande, sans interaction hormis la connexion GitHub quand un terminal est disponible (ADR 0003) :

```bash
curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash
```

Elle installe `python3`, `pipx` et `git`, crée l’utilisateur système `orchestrator`, installe pour lui le paquet `wap-runtime`, puis lance `wap-runtime setup` : socle manquant (Docker + Compose, `gh`, `claude`, `agent`, sans authentification), instance `/home/orchestrator/.wap-runtime/`, `docker compose up -d --build`, attente de `GET /health`, puis connexion GitHub de l’instance si elle n’est pas faite (voir **Connexion GitHub**). La relancer répare ou met à niveau sans réinstaller ce qui est présent ni toucher à `secrets.env` ou aux valeurs éditées de `config.toml`. Le service repart seul après un redémarrage (`restart: unless-stopped`) et n’écoute que sur `127.0.0.1`.

L’instance a deux services Compose : `runtime` (API et cockpit, instance montée en écriture pour persister le toggle **Pilote** dans `repos.toml`) et `runner` (sessions des agents, ADR 0004). L’image `runner` contient `git`, `gh`, `claude` (version épinglée), `agent` (version épinglée, archive vérifiée par empreinte SHA-256), Python 3 + venv, Node, `tmux` et les skills de Matt Pocock à un commit épinglé (`orchestrator/runner/Dockerfile`) ; aucun script téléchargé n’y est exécuté sans vérification et les scripts d’installation npm des dépendances ne tournent pas. Il tourne avec l’UID d’`orchestrator`, sans socket Docker ni port publié, et n’écrit que dans `clones/`, `jobs/` et `runner-home/` (son `HOME`), créés par `setup` et supprimés par `uninstall --purge`. Relancer `setup` reconstruit l’image (épinglages changés).

Options, par variables d’environnement passées à `sudo` :

| Variable | Défaut | Effet |
| --- | --- | --- |
| `WAP_REF` | `feat/runtime-orchestrator` | Branche, tag ou commit d’où s’installe le paquet `wap-runtime` ; les images `runtime` et `runner` se construisent au même commit |
| `WAP_PORT` | `8787` | Port publié sur `127.0.0.1` (à la création de `config.toml`) |
| `WAP_PACK_REF` | `main` | Branche ou tag du pack cloné dans l’instance (à la création de `config.toml`) |
| `WAP_DEBUG` | — | `1` : trace bash (`set -x`) et journal verbeux |
| `GH_TOKEN` | — | Token GitHub utilisé pour connecter l’instance, sans interaction |
| `WAP_SKIP_AUTH` | — | `1` : ne lance pas le device flow GitHub, même dans un terminal |

```bash
curl -fsSL …/orchestrator/install.sh | sudo WAP_PORT=9000 WAP_DEBUG=1 bash
```

**Tester une branche de version** avant sa fusion (ADR 0005) : `WAP_REF` choisit le ref du paquet, et `setup` construit les images au commit du paquet installé (lu dans `direct_url.json`), donc paquet et images ne se désalignent pas. `WAP_PACK_REF` reste indépendant.

```bash
curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/<ref>/orchestrator/install.sh | sudo WAP_REF=<ref> bash
```

Revenir à la base : relancer `install.sh` sans `WAP_REF`. Un paquet installé sans origine git (local ou éditable) construit les images depuis `feat/runtime-orchestrator`.

**Log et debug** : chaque étape est journalisée dans `/var/log/wap-runtime/install.log`. Un échec nomme l’étape, renvoie à ce log et sort en code `≠ 0` ; relancer avec `WAP_DEBUG=1` pour une trace détaillée.

**Commande `wap-runtime`** : `setup` crée le lien `/usr/local/bin/wap-runtime → ~orchestrator/.local/bin/wap-runtime`, dans le `secure_path` de sudo : `sudo wap-runtime …` se lance tel quel. Relancer `setup` le recrée s’il manque (instance 0.4.0) et n’y touche pas s’il est déjà là ; un autre fichier à cet emplacement fait échouer `setup` (`KO`) sans être écrasé.

**Santé** : `sudo wap-runtime health` dit en une ligne si le runtime répond (code `0` si OK), sur le port de `config.toml` (`--port N` pour un autre).

**Connexion GitHub** (ADR 0003) : `sudo wap-runtime auth` lance `gh auth login` (device flow : un code et une URL à valider dans le navigateur) en utilisateur `orchestrator`, copie son token dans `secrets.env` (`0600`) sous `GH_TOKEN`, puis recrée le service `runtime` pour qu’il le lise. `… | sudo wap-runtime auth --with-token` lit un token (fine-grained par exemple) sur stdin. Relancer `auth` reconnecte l’instance ou change de compte. `auth status` affiche une ligne par connexion — GitHub (compte connecté, ou « non connecté »), Claude Code, Cursor — et sort en code `0` si GitHub est connecté, `≠ 0` sinon (les agents sont au choix). En fin de `setup`, si l’instance n’est pas connectée : `GH_TOKEN` présent → utilisé ; sinon terminal disponible et pas `WAP_SKIP_AUTH=1` → `auth` ; sinon le setup réussit en affichant la prochaine étape.

**Connexion des agents** (ADR 0004) : `sudo wap-runtime auth claude` lance `claude setup-token` en utilisateur `orchestrator` sur l’hôte (une URL à ouvrir dans le navigateur, un code à recoller dans le terminal), relève le token affiché et l’écrit dans `secrets.env` (`0600`) sous `CLAUDE_CODE_OAUTH_TOKEN`. `… | sudo wap-runtime auth claude --with-token` lit le token sur stdin à la place ; une clé API Anthropic (`sk-ant-api…`) y est acceptée et s’écrit sous `ANTHROPIC_API_KEY` (une seule identité Claude à la fois : l’autre clé est retirée). Cursor se connecte par clé API (`agent login` exige un navigateur sur la machine) : `… | sudo wap-runtime auth agent --with-token` l’écrit sous `CURSOR_API_KEY`. Chaque écriture remplace l’ancien token sans toucher aux autres lignes, puis recrée tous les services de l’instance pour qu’ils relisent `secrets.env` ; relancer la commande reconnecte l’agent après une révocation. Le runner étant recréé lui aussi, une session ouverte passe `interrompue` : connecter un agent pendant une session l’arrête. « Connecté » veut dire token présent, sans appel de vérification : un token refusé se voit dans le terminal de l’agent. `setup` ne lance pas ces connexions ; il affiche celles qui manquent comme prochaine étape.

**Repos liés** : `sudo wap-runtime repo add owner/name [--nom <affichage>]`, `repo remove owner/name` et `repo list` gèrent le registry `~orchestrator/.wap-runtime/repos.toml` (en root, l’instance visée est celle d’`orchestrator`). `owner/name` invalide ou en double est refusé. Le fichier s’édite aussi à la main (`pilote`, `agent` = `claude` ou `cursor`) ; `setup` n’y touche pas, et le service `runtime` le relit et l’écrit (toggle **Pilote** du cockpit).

**Cockpit** : le service `runtime` sert le cockpit sur `http://127.0.0.1:<port>/` (port de `config.toml`, `8787` par défaut). La vue liste montre une ligne par repo lié — version ouverte, progression X/Y, étape, badge **Intervention humaine requise**, badge **Pilote** si le toggle est ON (et la raison du stop — réponse attendue, intervention humaine, etc. — s’il est en pause), heure de lecture — les repos qui attendent quelqu’un en tête, et se relit toutes les 60 s (la lecture GitHub de la liste est gardée 60 s). Un repo inaccessible n’affiche que sa ligne en erreur ; un bandeau demande `sudo wap-runtime auth` si l’instance n’est pas connectée ou si son token est refusé ; l’encart **Agents** dit si Claude Code et Cursor sont connectés, avec la commande à lancer sur l’hôte pour ceux qui ne le sont pas. L’en-tête mène à la page **Sessions** (`/sessions`) : toutes les sessions de l’instance (repo, agent, branche, titre, état, activité et skill des sessions ouvertes), de la plus récente à la plus ancienne, et affiche « N réponse(s) attendue(s) » (lien vers Sessions) ; le titre de l’onglet devient `(N) Cockpit wap-runtime` quand N > 0. La vue `/repos/<owner>/<name>` relit le repo en direct : parent, enfants (état, labels, bloqué), PR de version et ses checks, bugs ouverts, toggle **Pilote** et agent préféré (persistés dans `repos.toml`), et les sessions du repo. Les liens ouvrent GitHub. L’API JSON est sous `/api/` (`/api/repos`, `/api/repos/<owner>/<name>` aussi en `PATCH` pour le pilote, `/api/repos/<owner>/<name>/sessions`, `/api/sessions`, `/api/sessions/<id>`, `/api/sessions/<id>/terminal.cast`, `/api/auth`, `/api/agents`) ; les requêtes d’action (`POST`, `PATCH`, websocket) ne sont acceptées que depuis une page servie par le cockpit (en-tête `Origin`).

**Pilote** : sur la vue détail d’un repo lié, activez le toggle **Pilote** et choisissez l’agent (Claude Code ou Cursor). Tant qu’il est ON, le service `runtime` lance le premier enfant Implement éligible (`/implement #n`) et reprend après un stop dès qu’un enfant redevient éligible — sans onglet cockpit ouvert. La liste marque ces repos **Pilote**, et affiche la raison du stop (réponse attendue, intervention humaine, session échouée ou interrompue, aucun ticket éligible, échec de lancement). Après une session échouée ou interrompue, un nouvel enregistrement des préférences Pilote (détail) acquitte le stop et permet la reprise. Avec le cockpit ouvert, le navigateur demande une fois la permission de notification ; chaque stop envoie ensuite une notification, y compris si un autre onglet est au premier plan. Le pilote ne lance que l’Implement sous surveillance : pas « Ouvre la version », `/th`, `/code-review`, « Finalise la version » ni `/cqg`.

**Nouvelle session** (ADR 0007, session libre 0.4.2) : sur la vue détail, choisir l’agent (Claude Code ou Cursor) et la branche (base d’intégration — `base_branch` de `agents/integration-channel.yml` lu sur GitHub, sinon la branche par défaut du repo — et les branches des PR de version ouvertes ; par défaut la PR de version s’il y en a une, sinon la base), puis **Nouvelle session**. L’agent démarre vide (`claude` / `agent`) dans le clone géré : on y tape `/implement #n`, « Ouvre la version », `/th`… comme en local. Le bouton est grisé, avec la raison, si l’agent n’est pas connecté, si une session est déjà ouverte sur ce repo (lien vers cette session), ou si une session d’un autre repo a l’activité *travaille* (« une session travaille sur owner/name », lien) ; *attend* et *inconnue* ne bloquent pas. Le terminal d’une session n’est jamais bloqué par l’activité d’une autre. Les tickets restent affichés, sans bouton `/implement #n`. Une session sur la base n’exige pas de PR de version ; le runner refuse toute autre branche. Le runner met à jour le clone `clones/<owner>/<name>/` (créé au premier lancement) sur la branche choisie, avec l’identité git du compte de `GH_TOKEN`. Si le clone suit `agents/skills/` et `agents/scripts/dispatch.py`, le runner lance `python3 agents/scripts/dispatch.py` dans le clone : l’agent a les skills du pack à la version de la branche sous `.claude/skills/` et `.cursor/skills/` ; un dispatch en échec, ou qui modifie un fichier suivi, ne lance pas l’agent. Sinon le clone reste tel quel (pas d’initialisation du pack). Si le clone a des changements non commités, rien n’est lancé : le cockpit montre la branche actuelle du clone et propose **Reprendre** (session sur cette branche, arbre tel quel) ou **Jeter** (diff gardé dans `jobs/<id>/abandon.patch`, `reset --hard` et `clean -fd`, puis la branche choisie). Au plus une session ouverte par repo (clone géré unique) ; plusieurs repos peuvent chacun en avoir une. La vue liste marque chaque repo concerné d’un badge **Travaille**, **Réponse attendue** ou **Session en cours** (activité inconnue). Un deuxième lancement sur le même repo est refusé (`409` et le lien de la session ouverte). Un lancement est aussi refusé (`409` et le lien) tant qu’une session d’un autre repo *travaille*.

**Sessions** : la page `/sessions/<id>` montre le titre (premier message tapé, sinon le nom de l’agent), l’activité (`travaille`, `attend` avec le dernier skill s’il est connu, `inconnue` au départ), l’état (`ouverte`, `terminée`, `échouée` avec le code de sortie, `interrompue`, `enchaînée`) et la durée. Tant que la session est ouverte, elle affiche le terminal de l’agent en direct : on y tape le workflow des skills comme en local (`/clear`, `/implement #suivant`…). Fermer l’onglet ne l’arrête pas ; un seul onglet a la *main* (peut taper) : les autres affichent « Lecture seule : un autre onglet a la main. » et un bouton **Prendre la main**, qui la lui donne et met l’ancien en lecture seule. Quitter la page (vers la liste ou la vue détail, même sans fermer l’onglet) libère la main ; quand l’onglet qui l’a part, le plus ancien des autres la prend. **Terminer** arrête l’agent. Chaque session est enregistrée sous `~orchestrator/.wap-runtime/jobs/<id>/` : `session.json` (repo, `branche`, `ticket` — `null` pour une session libre —, agent, commande, début, fin, état, code de sortie, `precedente` / `suivante` d’une chaîne, `activite`, `skill`, `titre`), `terminal.cast` (le terminal, au format asciinema v2, écrit pendant la session) et `transcription/` (la transcription native de l’agent — `~/.claude/projects/` ou `~/.cursor/projects/*/agent-transcripts/` du `HOME` du runner — copiée à la fin). Si le runner redémarre pendant des sessions ouvertes, toutes passent `interrompue` à son démarrage et de nouvelles sessions peuvent être lancées. La vue détail liste les sessions du repo (date, agent, commande, état, liens vers la précédente et la suivante d’une chaîne), de la plus récente à la plus ancienne ; la page d’une session finie **rejoue** son `terminal.cast`, sans saisie (Pause, Aller à la fin, Rejouer ; les longues attentes sont ramenées à une seconde). `asciinema play terminal.cast` le rejoue aussi hors du cockpit. Rien n’est supprimé automatiquement : `jobs/` se vide à la main.

**Activité** : l’entrypoint du runner installe des hooks **en portée utilisateur** dans `runner-home/` (fusionnés avec les réglages existants, sans toucher au clone) qui appellent `wap-runtime etat <travaille|attend> [--skill <nom>]`. La commande parle à l’API interne du runner avec `WAP_SESSION` et `WAP_SESSION_JETON` (le jeton de la session ouverte, réutilisable pour l’activité, distinct de l’usage unique de l’enchaînement). Un hook en échec rend 0 : l’agent n’est jamais bloqué. Claude Code : soumission d’un message → `travaille` (le premier message devient le titre) ; `Stop` et `Notification` → `attend` ; outil `Skill` → le skill est retenu. Cursor : mêmes événements si la CLI les expose (`beforeSubmitPrompt`, `stop`, `postToolUse`) ; pas de hook `Notification`, donc une attente de permission reste `travaille` jusqu’au `stop`. Sans hooks, l’activité reste `inconnue`. `activite`, `skill` et `titre` sont dans `session.json` et dans les réponses de l’API.

**Enchaînement** (ADR 0006) : le runner lance chaque agent avec `WAP_ENCHAINER=wap-runtime enchainer`, `WAP_SESSION=<id>` et `WAP_SESSION_JETON` (aléatoire, propre à la session, gardé en mémoire par le runner et absent de `session.json`). L’entrypoint du runner fusionne dans `runner-home/` des règles de permission étroites (Claude `permissions.allow`, Cursor `terminalAllowlist`) pour `bash agents/scripts/enchainer-implement.sh` et `wap-runtime enchainer`, afin que le mode auto n’exige pas un humain pour ce seul chemin. Quand `encadrer-implement` enchaîne sur le ticket suivant, le pack lance `$WAP_ENCHAINER <n>` : la commande demande au runner (`POST /sessions/<id>/suivante`, API interne, même conteneur) d’ouvrir `/implement #n`. Cela marche aussi depuis une session libre lancée sur la branche d’une PR de version, et n’est pas soumis à la règle « une autre session travaille ». Le runner refuse — la commande sort en `≠ 0` avec la raison, rien n’est lancé ni fermé — si le jeton n’est pas celui de la session ouverte ou a déjà servi, si `#n` n’est pas un enfant éligible (mêmes règles qu’en 0.4.1, lues sur GitHub) de la version de la même branche du même repo, ou si le clone a des changements non commités. Acceptée, la commande répond `OK`, puis la session courante passe `enchaînée` (tmux arrêté) et la suivante démarre sur `/implement #n` : même repo, même branche, même agent, nouveau processus sans reprise de conversation. Les deux `session.json` se lient par `precedente` / `suivante`, exposés par `/api/sessions/<id>` et `/api/repos/<owner>/<name>/sessions`. Aucune autre commande, aucun autre repo ni agent n’est possible par ce chemin. Côté cockpit, la page d’une session ouverte qui passe `enchaînée` bascule vers la suivante avec le bandeau « Session enchaînée : /implement #n » ; l’onglet qui avait la main la reprend dans la nouvelle session (le terminal se reconnecte tant que son tmux démarre). Ouverte plus tard, la page d’une session enchaînée rejoue son terminal et donne le lien vers la suivante. Sans pack à jour sur `main`, le skill retombe sur son fallback.

Le port n’écoute que sur `127.0.0.1` de l’hôte (ADR 0002) : depuis votre poste, ouvrez un tunnel SSH puis le navigateur.

```bash
ssh -L 8787:127.0.0.1:8787 mon-serveur      # puis http://127.0.0.1:8787/
```

**Désinstallation** : `sudo wap-runtime uninstall` (en root, l’instance visée est celle d’`orchestrator`) arrête et retire le Compose, et retire le lien `/usr/local/bin/wap-runtime` s’il pointe vers le binaire d’`orchestrator` ; `--purge` supprime aussi l’instance. Docker, `gh` et les CLIs agents restent installés.

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
