# workflow-agents-pack — orchestrateur (`feat/runtime-orchestrator`)

Cette branche développe l’**orchestrateur** self-hosted : un runtime installé sur la machine de l’utilisateur (Linux, pas un VPS imposé) et un cockpit web qui suit puis pilote les repos métier ayant adopté le pack de skills. Produit public et générique : aucune instance perso dans ce dépôt.

**Ce n’est pas le pack.** Le pack de skills (skills, hooks, scripts, templates) se maintient sur **`main`**. Cette branche n’y est jamais fusionnée. Ici, le pack est un **outil installé** depuis `main` : `agents/skills/`, `agents/hooks/`, `agents/scripts/`, `agents/templates/`, `.claude/skills/` et `.cursor/skills/` sont ignorés par git. Un skill à corriger se corrige sur `main`, puis se réinstalle ici (voir [Installer les skills](#installer-les-skills) et l’[ADR 0001](docs/adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md)).

Les versions de cette branche partent de `feat/runtime-orchestrator` et y reviennent (tags `orchestrator-v*`) : [`agents/integration-channel.yml`](agents/integration-channel.yml). Vocabulaire : [`docs/glossaire.md`](docs/glossaire.md).

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
| 0.5.1 | Modèle Cursor par session : choix au lancement, visible dans le cockpit, repris sur la chaîne |
| 0.6.0 | Accès web authentifié |
| 0.7.0 | CI |
| 0.7.1 | CD |
| 0.8.0 | Enregistrement d’orchestrateur par compte GitHub |
| 0.8.1 | Refonte graphique du cockpit |
| 0.9.0 | Main d’aiguillage et feuilles de route multi-branches |

Détail, hors périmètre et suite : [feuille de route](docs/dev/feuille-de-route/feuille-de-route-dev.md).

## Installer l’orchestrateur sur une machine hôte

Sur un serveur **Debian 12+ ou Ubuntu 22.04+**, une seule commande, sans interaction hormis la connexion GitHub quand un terminal est disponible (ADR 0003) :

```bash
curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash
```

Elle installe `python3`, `pipx`, `git` et `curl`, résout la **dernière Release** `orchestrator-vX.Y.Z` publiée (ni brouillon ni prerelease, API GitHub publique), crée l’utilisateur système `orchestrator`, installe pour lui le paquet `wap-runtime` à ce tag, puis lance `wap-runtime setup` : socle manquant (Docker + Compose, `gh`, `claude`, `agent`, sans authentification), instance `/home/orchestrator/.wap-runtime/` (`version = "X.Y.Z"` dans `config.toml`), `docker compose up -d --build` avec les images `ghcr.io/ulyssoulv/wap-runtime:X.Y.Z` et `wap-runner:X.Y.Z` tirées de ghcr sans jeton (ADR 0013), attente de `GET /health`, puis connexion GitHub de l’instance si elle n’est pas faite (voir **Connexion GitHub**). La relancer répare ou met à niveau sans réinstaller ce qui est présent ni toucher à `secrets.env` ou aux valeurs éditées de `config.toml`. **Démarrage du serveur** : `setup` écrit et active l’unité systemd `/etc/systemd/system/wap-runtime.service` (sans la démarrer : Compose tourne déjà). À chaque boot, après Docker et le réseau, elle lance `wap-runtime update` en root — un échec ou « rien à faire » n’empêche pas le démarrage — puis `docker compose up -d --wait runtime runner` dans l’instance, en utilisateur `orchestrator`, et enfin Caddy s’il est configuré, sans bloquer (80/443 pris par un autre service ne met pas l’unité en échec) ; en cas d’échec de `runtime` ou `runner`, systemd relance au plus 5 fois en 10 minutes. L’instance démarre donc à la dernière Release. `restart: unless-stopped` reste dans le Compose pour les redémarrages de Docker. Relancer `setup` réécrit la même unité ; `update` la régénère depuis la nouvelle Release.

Par défaut l’exposition web est **désactivée** : le service `runtime` n’écoute que sur `127.0.0.1`. Après l’install, créez les **identifiants cockpit** (obligatoires pour ouvrir le cockpit, y compris en local — ADR 0010) :

```bash
sudo wap-runtime cockpit-auth --login <votre-login>
```

L’instance a deux services Compose de base : `runtime` (API et cockpit, instance montée en écriture pour persister le toggle **Pilote** dans `repos.toml`) et `runner` (sessions des agents, ADR 0004). Quand l’exposition web est activée, un troisième service **Caddy** publie uniquement les ports 80/443 et relaie vers le cockpit (ADR 0011). L’image `runner` contient `git`, `gh`, `claude` (version épinglée), `agent` (version épinglée, archive vérifiée par empreinte SHA-256), Python 3 + venv, Node, `tmux` et les skills de Matt Pocock à un commit épinglé (`orchestrator/runner/Dockerfile`) ; aucun script téléchargé n’y est exécuté sans vérification et les scripts d’installation npm des dépendances ne tournent pas. Il tourne avec l’UID d’`orchestrator`, sans socket Docker ni port publié, et n’écrit que dans `clones/`, `jobs/` et `runner-home/` (son `HOME`), créés par `setup` et supprimés par `uninstall --purge`. Quand les images viennent de ghcr, elles ont été construites et testées sur la PR de la version ; en secours seulement (ci-dessous), relancer `setup` les reconstruit sur l’hôte.

Options, par variables d’environnement passées à `sudo` :

| Variable | Défaut | Effet |
| --- | --- | --- |
| `WAP_REF` | dernière Release `orchestrator-vX.Y.Z` | Branche, tag ou commit d’où s’installe le paquet `wap-runtime` (prioritaire sur la dernière Release) ; les images `runtime` et `runner` sont tirées de ghcr à ce ref, ou construites au même commit |
| `WAP_PORT` | `8787` | Port publié sur `127.0.0.1` (à la création de `config.toml`) ; ignoré côté hôte quand l’exposition web est on |
| `WAP_PACK_REF` | `main` | Branche ou tag du pack cloné dans l’instance (à la création de `config.toml`) |
| `WAP_DEBUG` | — | `1` : trace bash (`set -x`) et journal verbeux |
| `GH_TOKEN` | — | Token GitHub utilisé pour connecter l’instance, sans interaction |
| `WAP_SKIP_AUTH` | — | `1` : ne lance pas le device flow GitHub, même dans un terminal |

```bash
curl -fsSL …/orchestrator/install.sh | sudo WAP_PORT=9000 WAP_DEBUG=1 bash
```

**Tester une branche de version** avant sa fusion (ADR 0005, 0013) : `WAP_REF` choisit le ref du paquet, et `setup` tire les images `:sha-<commit>` du commit du paquet installé (lu dans `direct_url.json`), publiées par le job `images` quand la CI de la PR est verte ; `config.toml` garde le ref (`version = "<ref>"`). Paquet et images ne se désalignent pas. `WAP_PACK_REF` reste indépendant.

```bash
curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/<ref>/orchestrator/install.sh | sudo WAP_REF=<ref> bash
```

Revenir à la version livrée : relancer `install.sh` sans `WAP_REF`.

**Build en secours** : si l’une des deux images n’existe pas sur ghcr (fork, commit jamais passé en CI, Release pas encore promue), `setup` les construit sur l’hôte au commit du paquet, comme avant la 0.7.1 (ADR 0005). Un paquet installé sans origine git (local ou éditable) construit les images depuis `feat/runtime-orchestrator`, sans interroger ghcr.

**Mise à jour** : `sudo wap-runtime update` applique la Release `orchestrator-vX.Y.Z` la plus haute (ni brouillon ni prerelease) si elle est strictement supérieure à `version` de `config.toml`. Elle réinstalle le paquet à ce tag pour `orchestrator` (`pipx install --force`), puis, dans le nouveau paquet, régénère `compose.yaml`, lance `docker compose pull` et `up -d --wait --force-recreate`, écrit `version` et supprime les anciennes images `ghcr.io/ulyssoulv/wap-*` seulement (jamais de `prune`). Enfin, toujours dans le nouveau paquet mais en root, elle réécrit et réactive l’unité `wap-runtime.service`. Elle ne touche ni à `secrets.env`, ni à `repos.toml`, `jobs/` ou `clones/`, ni aux autres clés de `config.toml`. Journal : `/var/log/wap-runtime/update.log`.

| Code | Cas |
| --- | --- |
| `0` | Mise à jour faite (Caddy qui ne démarre pas, `runtime` et `runner` sains : avertissement, pas d’échec) |
| `2` | Rien à faire : déjà à la dernière Release, version locale non semver (« pas une version de production » : instance installée avec `WAP_REF`), ou images `X.Y.Z` pas encore promues sur ghcr (rien n’est touché) |
| `1` | Échec : Releases injoignables, session ouverte (liste affichée ; `--force` passe outre, au prix de l’interrompre), `pipx`, `pull`, recreate ou unité en échec — journalisé, **sans rollback** : corriger puis relancer |

**Depuis une instance 0.7.0** : elle n’a ni `update` ni `version` ; relancer une fois `install.sh` (sans `WAP_REF`) pour passer à la dernière Release, puis `sudo wap-runtime update` suffit.

**Log et debug** : chaque étape est journalisée dans `/var/log/wap-runtime/install.log`. Un échec nomme l’étape, renvoie à ce log et sort en code `≠ 0` ; relancer avec `WAP_DEBUG=1` pour une trace détaillée.

**Commande `wap-runtime`** : `setup` crée le lien `/usr/local/bin/wap-runtime → ~orchestrator/.local/bin/wap-runtime`, dans le `secure_path` de sudo : `sudo wap-runtime …` se lance tel quel. Relancer `setup` le recrée s’il manque (instance 0.4.0) et n’y touche pas s’il est déjà là ; un autre fichier à cet emplacement fait échouer `setup` (`KO`) sans être écrasé.

**Santé** : `sudo wap-runtime health` dit en une ligne si le runtime répond (code `0` si OK), sur le port de `config.toml` (`--port N` pour un autre). Avec l’exposition activée, sondez plutôt le proxy (port 80 / 443) ou utilisez `sudo wap-runtime diagnostic`.

**Désinstallation** : `sudo wap-runtime uninstall` (en root, l’instance visée est celle d’`orchestrator`) désactive et supprime l’unité `wap-runtime.service`, arrête et retire le Compose, et retire le lien `/usr/local/bin/wap-runtime` s’il pointe vers le binaire d’`orchestrator` ; `--purge` supprime aussi l’instance. Docker, `gh` et les CLIs agents restent installés.

## Configuration

L’instance vit sous `/home/orchestrator/.wap-runtime/` (ou `~/.wap-runtime/` de l’utilisateur d’instance). Fichiers utiles :

| Fichier | Rôle |
| --- | --- |
| `config.toml` | Port local, ref du pack, `version` installée (réécrite par `setup` et `update`), `exposition` (bool), `domaine` (hôte TLS) — `setup` / les CLI d’expo et de domaine réécrivent les clés qu’ils gèrent ; le reste des valeurs éditées est conservé |
| `secrets.env` (`0600`) | Tokens GitHub / agents — jamais les identifiants cockpit |
| `repos.toml` | Registry des repos liés (+ préférences Pilote / agent / modèle) |
| `compose.yaml`, `Caddyfile` | Générés depuis `config.toml` — ne pas éditer à la main ; relancer `setup` ou les CLI d’expo / domaine |

### Identifiants cockpit (accès web)

Distincts de `wap-runtime auth` (GitHub / agents). Un seul login + mot de passe par instance ; le hash est stocké dans l’instance. **Toute** page et API du cockpit exige une session (sauf surface de login et `GET /health` sans secrets), y compris sur `127.0.0.1` (ADR 0010).

```bash
sudo wap-runtime cockpit-auth --login operateur          # crée ou change (prompt)
echo 'mon-mot-de-passe' | sudo wap-runtime cockpit-auth --login operateur --with-password
```

Changer le mot de passe **invalide** les sessions ouvertes (~7 jours sinon, sauf déconnexion). Les tentatives de login échouées sont limitées.

### Exposition web et domaine

Opt-in (ADR 0011) : sans exposition, accès local ou tunnel SSH uniquement. Avec exposition **on**, seuls **80/443** du reverse proxy Caddy sont publiés sur l’hôte ; `runtime` et `runner` ne sont pas joignables depuis Internet. Le proxy ne relaie que vers le cockpit de cette instance.

```bash
sudo wap-runtime exposition on     # publie 80/443 via Caddy
sudo wap-runtime exposition off    # revient à l’écoute 127.0.0.1:<port>
sudo wap-runtime domaine cockpit.exemple.test   # HTTPS Let’s Encrypt dès que DNS/NAT le permettent
```

Il n’y a **pas** de mode officiel « HTTP public » : sans domaine, Caddy n’ouvre pas 80/443 sur Internet (loopback seulement) ; gardez local / SSH, ou configurez un domaine puis rouvrez l’exposition / la box.

## Accéder au cockpit

Dans tous les cas : page de login avec les **identifiants cockpit**, puis session navigateur (cookie httpOnly). Déconnexion explicite depuis le cockpit.

### Local (exposition off)

Sur la machine hôte, après `cockpit-auth` :

```text
http://127.0.0.1:8787/     # port de config.toml (8787 par défaut)
```

### Tunnel SSH (exposition off)

Depuis votre poste, sans ouvrir la box :

```bash
ssh -L 8787:127.0.0.1:8787 mon-serveur
# puis http://127.0.0.1:8787/
```

Adaptez le port à celui de `config.toml`. Ce chemin reste le moyen recommandé tant que vous n’avez pas de domaine + NAT fiables.

### Exposition off (rappel)

`sudo wap-runtime exposition off` (défaut après install) : pas de ports 80/443 publics ; `runtime` écoute seulement `127.0.0.1:<port>`. Accès = local ou SSH ci-dessus.

### Exposition on, sans domaine

`sudo wap-runtime exposition on` sans `domaine` : Caddy est démarré, mais les ports **80/443 restent sur `127.0.0.1`** (pas de HTTP public). HTTPS Let’s Encrypt n’est pas disponible tant qu’un domaine n’est pas configuré. Usage prévu : lab local ; pour un accès distant sûr sans domaine, gardez l’exposition **off** et le tunnel SSH.

### Exposition on, avec domaine + DNS + NAT

1. Choisissez un nom d’hôte (ex. `cockpit.exemple.test`) et faites-le pointer (DNS A/AAAA) vers l’**adresse publique de la machine hôte** (pas vers la box elle-même si celle-ci n’est que le routeur).
2. Sur la box / le routeur : redirigez (NAT) les ports **80** et **443** vers cette machine. Caddy tourne sur l’**hôte**, pas sur la box.
3. Sur l’hôte :

```bash
sudo wap-runtime cockpit-auth --login <login>   # si pas déjà fait
sudo wap-runtime domaine cockpit.exemple.test
sudo wap-runtime exposition on
sudo wap-runtime diagnostic
```

4. Ouvrez `https://cockpit.exemple.test/` — Caddy obtient et renouvelle le certificat Let’s Encrypt lorsque DNS et NAT sont corrects.

Checklist opérateur (ce que le produit ne fait pas) :

- [ ] L’enregistrement DNS pointe vers la bonne IP publique
- [ ] NAT 80 → hôte:80 et 443 → hôte:443
- [ ] Aucun autre service ne monopolise 80/443 sur l’hôte
- [ ] Le pare-feu de l’hôte laisse passer 80/443 si besoin

### CGNAT (ex. box 4G)

Certaines box (notamment 4G) sont derrière du **CGNAT** : pas d’IP publique dédiée, le NAT entrant ne marche pas. Le produit **ne configure pas** la box. Dans ce cas : garder l’exposition **off** et le **tunnel SSH**, ou un autre accès hors produit (VPN perso, etc.). `wap-runtime diagnostic` le rappelle côté opérateur.

### Diagnostic

Sépare ce que l’instance a fait (identifiants cockpit, expo, ports 80/443, Caddy up, domaine) du reste à faire (DNS, NAT, limites CGNAT) :

```bash
sudo wap-runtime diagnostic
```

Code de sortie `≠ 0` s’il manque quelque chose **côté instance** (auth cockpit, ports, Caddy, domaine si expo on). Les lignes « Côté opérateur » sont informatives : à traiter sur votre DNS / box.

Expo on et Caddy pas up : si 80 ou 443 répond quand même sur l’hôte, `diagnostic` dit que le port est **occupé par un autre processus** que le Caddy de l’instance (une ligne `KO` par port, avec la commande `ss` pour trouver qui l’écoute). Expo off : aucune alerte 80/443.

### Hôte partagé

L’orchestrateur peut tourner sur le même serveur qu’un autre service (ArgOS par exemple). Ce qui est propre à l’instance ne se partage pas :

| Élément | Instance |
| --- | --- |
| Unité systemd | `wap-runtime.service` |
| Utilisateur | `orchestrator` |
| Dossier | `/home/orchestrator/.wap-runtime/` |
| Projet Compose | `wap-runtime` (`name:` de `compose.yaml`) |
| Images | `ghcr.io/ulyssoulv/wap-runtime`, `wap-runner` ; `update` ne supprime que les anciennes `wap-*` |
| Port par défaut | `127.0.0.1:8787` (`WAP_PORT`) |

**Conflit 80/443, non résolu en 0.7.1** : avec l’exposition on, le Caddy de l’instance veut 80/443 ; si un autre service les tient déjà, Caddy ne démarre pas. `runtime` et `runner` démarrent et se mettent à jour quand même (`update` avertit sans échouer ; au boot, l’unité `wap-runtime.service` finit en échec après ses relances, mais les deux services tournent), et `sudo wap-runtime diagnostic` nomme le port occupé. En attendant, gardez l’exposition **off** (local / tunnel SSH) sur un hôte partagé ; une **VM par service** supprime le conflit. Pas de reverse proxy partagé ni de ports Caddy configurables dans cette version.

## Connexion GitHub

`sudo wap-runtime auth` lance `gh auth login` (device flow : un code et une URL à valider dans le navigateur) en utilisateur `orchestrator`, copie son token dans `secrets.env` (`0600`) sous `GH_TOKEN`, puis recrée le service `runtime` pour qu’il le lise (ADR 0003). `… | sudo wap-runtime auth --with-token` lit un token (fine-grained par exemple) sur stdin. Relancer `auth` reconnecte l’instance ou change de compte. `auth status` affiche une ligne par connexion — GitHub (compte connecté, ou « non connecté »), Claude Code, Cursor — et sort en code `0` si GitHub est connecté, `≠ 0` sinon (les agents sont au choix). En fin de `setup`, si l’instance n’est pas connectée : `GH_TOKEN` présent → utilisé ; sinon terminal disponible et pas `WAP_SKIP_AUTH=1` → `auth` ; sinon le setup réussit en affichant la prochaine étape.

## Connexion des agents

`sudo wap-runtime auth claude` lance `claude setup-token` en utilisateur `orchestrator` sur l’hôte (une URL à ouvrir dans le navigateur, un code à recoller dans le terminal), relève le token affiché et l’écrit dans `secrets.env` (`0600`) sous `CLAUDE_CODE_OAUTH_TOKEN` (ADR 0004). `… | sudo wap-runtime auth claude --with-token` lit le token sur stdin à la place ; une clé API Anthropic (`sk-ant-api…`) y est acceptée et s’écrit sous `ANTHROPIC_API_KEY` (une seule identité Claude à la fois : l’autre clé est retirée). Cursor se connecte par clé API (`agent login` exige un navigateur sur la machine) : `… | sudo wap-runtime auth agent --with-token` l’écrit sous `CURSOR_API_KEY`. Chaque écriture remplace l’ancien token sans toucher aux autres lignes, puis recrée tous les services de l’instance pour qu’ils relisent `secrets.env` ; relancer la commande reconnecte l’agent après une révocation. Le runner étant recréé lui aussi, une session ouverte passe `interrompue` : connecter un agent pendant une session l’arrête. « Connecté » veut dire token présent, sans appel de vérification : un token refusé se voit dans le terminal de l’agent. `setup` ne lance pas ces connexions ; il affiche celles qui manquent comme prochaine étape.

## Repos liés

`sudo wap-runtime repo add owner/name [--nom <affichage>]`, `repo remove owner/name` et `repo list` gèrent le registry `~orchestrator/.wap-runtime/repos.toml` (en root, l’instance visée est celle d’`orchestrator`). `owner/name` invalide ou en double est refusé. Le fichier s’édite aussi à la main (`pilote`, `agent` = `claude` ou `cursor`, et pour Cursor un modèle préféré) ; `setup` n’y touche pas, et le service `runtime` le relit et l’écrit (toggle **Pilote** / préférences du cockpit).

## Cockpit

Le service `runtime` sert le cockpit (port de `config.toml` en local, ou via Caddy si exposition on). La vue liste montre une ligne par repo lié — version ouverte, progression X/Y, étape, badge **Intervention humaine requise**, badge **Pilote** si le toggle est ON (et la raison du stop — réponse attendue, intervention humaine, etc. — s’il est en pause), heure de lecture — les repos qui attendent quelqu’un en tête, et se relit toutes les 60 s (la lecture GitHub de la liste est gardée 60 s). Un repo inaccessible n’affiche que sa ligne en erreur ; un bandeau demande `sudo wap-runtime auth` si l’instance n’est pas connectée ou si son token est refusé ; l’encart **Agents** dit si Claude Code et Cursor sont connectés, avec la commande à lancer sur l’hôte pour ceux qui ne le sont pas. L’en-tête mène à la page **Sessions** (`/sessions`) : toutes les sessions de l’instance (repo, agent, modèle Cursor s’il s’applique, branche, titre, état, activité et skill des sessions ouvertes), de la plus récente à la plus ancienne, et affiche « N réponse(s) attendue(s) » (lien vers Sessions) ; le titre de l’onglet devient `(N) Cockpit wap-runtime` quand N > 0. La vue `/repos/<owner>/<name>` relit le repo en direct : parent, enfants (état, labels, bloqué), PR de version et ses checks, bugs ouverts, toggle **Pilote** et agent préféré (persistés dans `repos.toml`), et les sessions du repo. Les liens ouvrent GitHub. L’API JSON est sous `/api/` (`/api/repos`, `/api/repos/<owner>/<name>` aussi en `PATCH` pour le pilote, `/api/repos/<owner>/<name>/sessions`, `/api/sessions`, `/api/sessions/<id>`, `/api/sessions/<id>/terminal.cast`, `/api/auth`, `/api/agents`, `/api/modeles` — liste Cursor via le runner en Compose) ; les requêtes d’action (`POST`, `PATCH`, websocket) ne sont acceptées que depuis une page servie par le cockpit (en-tête `Origin`), et toute route (sauf login / health) exige une session cockpit.

**Pilote** : sur la vue détail d’un repo lié, activez le toggle **Pilote** et choisissez l’agent (Claude Code ou Cursor). Si l’agent est Cursor, choisissez aussi le **modèle** (liste fournie par la CLI, avec Auto) : le Pilote l’utilise quand il démarre sans session précédente dans la chaîne. Tant qu’il est ON, le service `runtime` lance le premier enfant Implement éligible (`/implement #n`) et reprend après un stop dès qu’un enfant redevient éligible — sans onglet cockpit ouvert. La liste marque ces repos **Pilote**, et affiche la raison du stop (réponse attendue, intervention humaine, session échouée ou interrompue, aucun ticket éligible, échec de lancement). Après une session échouée ou interrompue, un nouvel enregistrement des préférences Pilote (détail) acquitte le stop et permet la reprise. Avec le cockpit ouvert, le navigateur demande une fois la permission de notification ; chaque stop envoie ensuite une notification, y compris si un autre onglet est au premier plan. Le pilote ne lance que l’Implement sous surveillance : pas « Ouvre la version », `/th`, `/code-review`, « Finalise la version » ni `/cqg`.

**Nouvelle session** (ADR 0007, session libre 0.4.2 ; modèle Cursor ADR 0009) : sur la vue détail, choisir l’agent (Claude Code ou Cursor) et la branche (base d’intégration — `base_branch` de `agents/integration-channel.yml` lu sur GitHub, sinon la branche par défaut du repo — et les branches des PR de version ouvertes ; par défaut la PR de version s’il y en a une, sinon la base), puis **Nouvelle session**. Avec Cursor connecté, un select de **modèle** (liste `agent models`, Auto inclus) est prérempli avec la préférence du repo ; un override ne modifie que cette session. Auto (ou vide) lance `agent` sans `--model` ; un autre ID passe `--model <id>`. L’agent démarre vide (`claude` / `agent`) dans le clone géré : on y tape `/implement #n`, « Ouvre la version », `/th`… comme en local. Le select modèle n’apparaît pas si Cursor n’est pas connecté ; si la liste échoue ou qu’un ID mémorisé n’y est plus, le lancement Cursor est refusé. Le bouton est grisé, avec la raison, si l’agent n’est pas connecté, si une session est déjà ouverte sur ce repo (lien vers cette session), ou si une session d’un autre repo a l’activité *travaille* (« une session travaille sur owner/name », lien) ; *attend* et *inconnue* ne bloquent pas. Le terminal d’une session n’est jamais bloqué par l’activité d’une autre. Les tickets restent affichés, sans bouton `/implement #n`. Une session sur la base n’exige pas de PR de version ; le runner refuse toute autre branche. Le runner met à jour le clone `clones/<owner>/<name>/` (créé au premier lancement) sur la branche choisie, avec l’identité git du compte de `GH_TOKEN`. Si le clone suit `agents/skills/` et `agents/scripts/dispatch.py`, le runner lance `python3 agents/scripts/dispatch.py` dans le clone : l’agent a les skills du pack à la version de la branche sous `.claude/skills/` et `.cursor/skills/` ; un dispatch en échec, ou qui modifie un fichier suivi, ne lance pas l’agent. Sinon le clone reste tel quel (pas d’initialisation du pack). Si le clone a des changements non commités, rien n’est lancé : le cockpit montre la branche actuelle du clone et propose **Reprendre** (session sur cette branche, arbre tel quel) ou **Jeter** (diff gardé dans `jobs/<id>/abandon.patch`, `reset --hard` et `clean -fd`, puis la branche choisie). Au plus une session ouverte par repo (clone géré unique) ; plusieurs repos peuvent chacun en avoir une. La vue liste marque chaque repo concerné d’un badge **Travaille**, **Réponse attendue** ou **Session en cours** (activité inconnue). Un deuxième lancement sur le même repo est refusé (`409` et le lien de la session ouverte). Un lancement est aussi refusé (`409` et le lien) tant qu’une session d’un autre repo *travaille*.

**Sessions** : la page `/sessions/<id>` montre le titre (premier message tapé, sinon le nom de l’agent), l’agent, le **modèle** Cursor s’il s’applique (libellé **Auto** sans `--model`), l’activité (`travaille`, `attend` avec le dernier skill s’il est connu, `inconnue` au départ), l’état (`ouverte`, `terminée`, `échouée` avec le code de sortie, `interrompue`, `enchaînée`) et la durée. Une session enchaînée reprend le modèle de sa `precedente` (ADR 0009). Tant que la session est ouverte, elle affiche le terminal de l’agent en direct : on y tape le workflow des skills comme en local (`/clear`, `/implement #suivant`…). Fermer l’onglet ne l’arrête pas ; un seul onglet a la *main* (peut taper) : les autres affichent « Lecture seule : un autre onglet a la main. » et un bouton **Prendre la main**, qui la lui donne et met l’ancien en lecture seule. Quitter la page (vers la liste ou la vue détail, même sans fermer l’onglet) libère la main ; quand l’onglet qui l’a part, le plus ancien des autres la prend. **Terminer** arrête l’agent. Chaque session est enregistrée sous `~orchestrator/.wap-runtime/jobs/<id>/` : `session.json` (repo, `branche`, `ticket` — `null` pour une session libre —, agent, modèle Cursor le cas échéant, commande, début, fin, état, code de sortie, `precedente` / `suivante` d’une chaîne, `activite`, `skill`, `titre`), `terminal.cast` (le terminal, au format asciinema v2, écrit pendant la session) et `transcription/` (la transcription native de l’agent — `~/.claude/projects/` ou `~/.cursor/projects/*/agent-transcripts/` du `HOME` du runner — copiée à la fin). Si le runner redémarre pendant des sessions ouvertes, toutes passent `interrompue` à son démarrage et de nouvelles sessions peuvent être lancées. La vue détail liste les sessions du repo (date, agent, modèle Cursor s’il s’applique, commande, état, liens vers la précédente et la suivante d’une chaîne), de la plus récente à la plus ancienne ; la page d’une session finie **rejoue** son `terminal.cast`, sans saisie (Pause, Aller à la fin, Rejouer ; les longues attentes sont ramenées à une seconde). `asciinema play terminal.cast` le rejoue aussi hors du cockpit. Rien n’est supprimé automatiquement : `jobs/` se vide à la main.

**Activité** : l’entrypoint du runner installe des hooks **en portée utilisateur** dans `runner-home/` (fusionnés avec les réglages existants, sans toucher au clone) qui appellent `wap-runtime etat <travaille|attend> [--skill <nom>]`. La commande parle à l’API interne du runner avec `WAP_SESSION` et `WAP_SESSION_JETON` (le jeton de la session ouverte, réutilisable pour l’activité, distinct de l’usage unique de l’enchaînement). Un hook en échec rend 0 : l’agent n’est jamais bloqué. Claude Code : soumission d’un message → `travaille` (le premier message devient le titre) ; `Stop` et `Notification` → `attend` ; outil `Skill` → le skill est retenu. Cursor : mêmes événements si la CLI les expose (`beforeSubmitPrompt`, `stop`, `postToolUse`) ; pas de hook `Notification`, donc une attente de permission reste `travaille` jusqu’au `stop`. Sans hooks, l’activité reste `inconnue`. `activite`, `skill` et `titre` sont dans `session.json` et dans les réponses de l’API.

**Enchaînement** (ADR 0006) : le runner lance chaque agent avec `WAP_ENCHAINER=wap-runtime enchainer`, `WAP_SESSION=<id>` et `WAP_SESSION_JETON` (aléatoire, propre à la session, gardé en mémoire par le runner et absent de `session.json`). L’entrypoint du runner fusionne dans `runner-home/` des règles de permission étroites (Claude `permissions.allow`, Cursor `terminalAllowlist`) pour `bash agents/scripts/enchainer-implement.sh` et `wap-runtime enchainer`, afin que le mode auto n’exige pas un humain pour ce seul chemin. Quand `encadrer-implement` enchaîne sur le ticket suivant, le pack lance `$WAP_ENCHAINER <n>` : la commande demande au runner (`POST /sessions/<id>/suivante`, API interne, même conteneur) d’ouvrir `/implement #n`. Cela marche aussi depuis une session libre lancée sur la branche d’une PR de version, et n’est pas soumis à la règle « une autre session travaille ». Le runner refuse — la commande sort en `≠ 0` avec la raison, rien n’est lancé ni fermé — si le jeton n’est pas celui de la session ouverte ou a déjà servi, si `#n` n’est pas un enfant éligible (mêmes règles qu’en 0.4.1, lues sur GitHub) de la version de la même branche du même repo, ou si le clone a des changements non commités. Acceptée, la commande répond `OK`, puis la session courante passe `enchaînée` (tmux arrêté) et la suivante démarre sur `/implement #n` : même repo, même branche, même agent, nouveau processus sans reprise de conversation. Les deux `session.json` se lient par `precedente` / `suivante`, exposés par `/api/sessions/<id>` et `/api/repos/<owner>/<name>/sessions`. Aucune autre commande, aucun autre repo ni agent n’est possible par ce chemin. Côté cockpit, la page d’une session ouverte qui passe `enchaînée` bascule vers la suivante avec le bandeau « Session enchaînée : /implement #n » ; l’onglet qui avait la main la reprend dans la nouvelle session (le terminal se reconnecte tant que son tmux démarre). Ouverte plus tard, la page d’une session enchaînée rejoue son terminal et donne le lien vers la suivante. Sans pack à jour sur `main`, le skill retombe sur son fallback.

## Installer les skills

Sur cette branche, pour développer l’orchestrateur avec les skills du pack :

```bash
git clone -b feat/runtime-orchestrator https://github.com/UlyssouLV/workflow-agents-pack.git
cd workflow-agents-pack
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

L’installation éditable fournit la commande `orchestrator/.venv/bin/wap-runtime` (`serve`, `health [--port N]`, `auth [status|claude|agent] [--with-token]`, `cockpit-auth`, `exposition`, `domaine`, `diagnostic`, `repo add|remove|list`, `setup`, `uninstall [--purge]`).

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

## CI

Workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (ADR [0012](docs/adr/0012-ci-actions-sonar-sur-pr-base.md)) : il tourne sur **chaque PR vers `feat/runtime-orchestrator`**, à l’ouverture puis à chaque push sur la branche de la PR, sans filtre de chemins. Un nouveau push annule le run en cours de la même PR. Pas de CI sur `main` ni sur un push hors PR.

| Check | Ce qu’il vérifie |
| --- | --- |
| `pytest` | Suite `orchestrator/tests/` (Python 3.12, dépendances verrouillées par hash) avec couverture |
| `vitest` | Suite `orchestrator/cockpit/tests/` (Node 24, `npm run test:coverage`) avec couverture |
| `sonar` | Après `pytest` et `vitest` : scan Sonar de `orchestrator/` ([`sonar-project.properties`](sonar-project.properties)) avec les deux couvertures ; **échoue si le quality gate n’est pas `OK`** |
| `images` | Après les trois autres : construit et pousse les images de l’instance sur ghcr (staging, ci-dessous) ; ignoré pour une PR de fork |

Les quatre doivent être verts pour merger. Le check `SonarCloud Code Analysis` que Sonar ajoute sur la PR n’est pas requis : `sonar` porte déjà le verdict du gate. Les suites gardent le faux `docker` des tests, pas de Docker Engine dans Actions. Une CI en échec se corrige jusqu’au vert : tests en local avec `/t`, gate avec `/cqg`.

### Images sur ghcr (staging)

Le job `images` (ADR [0013](docs/adr/0013-images-ghcr-promotion-et-mise-a-jour-de-l-instance.md)) appelle [`orchestrator/scripts/publier-images-staging.sh`](orchestrator/scripts/publier-images-staging.sh) : buildx + QEMU, manifestes `linux/amd64` + `linux/arm64`, construits au **SHA de tête de la PR** (pas au merge-ref) et poussés vers `ghcr.io/ulyssoulv/wap-runtime` et `ghcr.io/ulyssoulv/wap-runner` en `:sha-<sha>` (SHA complet) et `:staging` (dernière PR verte). Le jeton du workflow suffit (`packages: write`), aucun secret à ajouter. Une PR de fork ne publie rien.

Hors Actions, le même script tourne depuis un clone au commit voulu : `bash orchestrator/scripts/publier-images-staging.sh [<sha>]` (défaut : `HEAD`), après `docker login ghcr.io` avec un jeton `write:packages` et un buildx capable d’`arm64` (QEMU).

**Visibilité publique (geste manuel unique)** : ghcr crée les paquets en privé au premier push et l’API GitHub ne change pas cette visibilité. Après le premier run vert du job `images`, pour `wap-runtime` puis `wap-runner` : profil GitHub → **Packages** → le paquet → **Package settings** → **Danger Zone → Change visibility → Public**. Vérifier sans jeton : `docker logout ghcr.io && docker buildx imagetools inspect ghcr.io/ulyssoulv/wap-runtime:staging` liste `linux/amd64` et `linux/arm64`.

### Promotion à la Release

Le workflow [`.github/workflows/promotion.yml`](.github/workflows/promotion.yml) tourne quand une Release est **publiée** ; seuls les tags `orchestrator-v*` le déclenchent (les Releases du pack n’ont aucun effet). Il résout le commit du tag et appelle [`orchestrator/scripts/promouvoir-images-release.sh`](orchestrator/scripts/promouvoir-images-release.sh), qui retaggue `:sha-<sha>` vers `:X.Y.Z` et `:latest` avec `docker buildx imagetools create`, pour les deux images, sans rebuild : même digest que l’image testée sur la PR. Le script refuse un tag hors `orchestrator-vX.Y.Z` ; si `:sha-<sha>` manque pour l’une des images, il échoue avant de créer le moindre tag. Une Release créée par le `GITHUB_TOKEN` d’un autre workflow ne déclenche pas la promotion (règle GitHub) : Finalise la crée avec le jeton de `gh`.

Hors Actions : `bash orchestrator/scripts/promouvoir-images-release.sh orchestrator-vX.Y.Z [<sha>]` (défaut : commit du tag), après `docker login ghcr.io` avec un jeton `write:packages`. Vérifier : `docker buildx imagetools inspect ghcr.io/ulyssoulv/wap-runtime:X.Y.Z` et `…:sha-<sha>` donnent le même `Digest`.

### Secrets Sonar

Dans **Settings → Secrets and variables → Actions → Repository secrets**, les trois mêmes valeurs que le `.env` local de `/qg` (même projet Sonar) :

| Secret | Valeur |
| --- | --- |
| `SONAR_HOST_URL` | URL de l’hôte Sonar, sans `/` final (ex. `https://sonarcloud.io`) |
| `SONAR_TOKEN` | Jeton Sonar autorisé à analyser le projet |
| `SONAR_PROJECT_KEY` | Clé du projet Sonar |

L’organisation SonarCloud est dans `sonar-project.properties`. Sans ces secrets (ou sur une PR venant d’un fork, qui ne les reçoit pas), le job `sonar` échoue. Pas de rotation automatique : un jeton changé se remet à la main ici et dans `.env`.

### Ruleset sur `feat/runtime-orchestrator`

La protection est un réglage admin GitHub, posé et vérifié à la main (aucun script dans le dépôt). Formulaire direct : [`settings/rules/new?target=branch`](https://github.com/UlyssouLV/workflow-agents-pack/settings/rules/new?target=branch). Sinon : onglet **Settings du dépôt** (pas celui du profil), colonne de gauche **Code and automation → Rules → Rulesets → New ruleset → New branch ruleset**.

1. **Ruleset name** : `feat/runtime-orchestrator` ; **Enforcement status** : `Active` ; **Bypass list** vide (sinon un admin peut merger une CI en échec).
2. **Target branches → Add target → Include by pattern** : `feat/runtime-orchestrator`.
3. Cocher **Require a pull request before merging**, avec **Required approvals : `0`** (on ne peut pas approuver sa propre PR : à 1, un mainteneur seul ne merge plus) ; dans **Allowed merge methods**, garder **Squash** (Finalise squashe).
4. Cocher **Require status checks to pass**, puis **Add checks** : `pytest`, `vitest`, `sonar`, `images` (source GitHub Actions), pas `SonarCloud Code Analysis`. Laisser **Require branches to be up to date** décoché. Les noms n’apparaissent qu’après un premier run du workflow sur une PR.
5. Laisser **Restrict deletions** et **Block force pushes** cochés, ne rien cocher d’autre (**Restrict updates** bloquerait tout push), puis **Create**.

Vérifier : `gh api repos/UlyssouLV/workflow-agents-pack/rules/branches/feat/runtime-orchestrator` doit lister une règle `required_status_checks` avec les contextes `pytest`, `vitest`, `sonar` et `images` (`images` ajouté en 0.7.1 : sur un ruleset existant, **Edit** → **Add checks** → `images` → **Save changes**). Sur une PR vers la base, le bouton de merge reste bloqué tant que l’un d’eux est rouge ou en attente.

## Repères

- Règles pour les agents : [`AGENTS.md`](AGENTS.md).
- Specs de version : [`docs/specs/`](docs/specs/). Décisions : [`docs/adr/`](docs/adr/) (dont [0010](docs/adr/0010-identifiants-cockpit-auth-obligatoire.md), [0011](docs/adr/0011-caddy-exposition-web-opt-in.md), [0012](docs/adr/0012-ci-actions-sonar-sur-pr-base.md), [0013](docs/adr/0013-images-ghcr-promotion-et-mise-a-jour-de-l-instance.md)).
- Cycle Ouvre / Implement / Finalise, tracker, labels : [`agents/issue-tracker.md`](agents/issue-tracker.md), [`agents/docs/integration-channel.md`](agents/docs/integration-channel.md).
