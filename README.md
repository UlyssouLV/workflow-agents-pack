<p align="center">
  <img src="https://img.shields.io/badge/HéphaïstOS-Pack_de_développement-c8102e?style=for-the-badge" alt="HéphaïstOS — Pack de développement" />
</p>

# Pack de développement HéphaïstOS

**HéphaïstOS** est le dépôt qui porte le pack d’agents partagé par les projets (ArgOS, BBASS Agents IA, et les suivants). Ce README décrit **uniquement le pack** : ce qu’il contient, comment l’adopter sur un projet, et comment le mettre à jour.

Ce n’est **pas** le README de la future branche `main` du dépôt (runtime, cockpit, déploiement). Ici on parle de la branche **`pack`** : skills, hooks, scripts d’adoption et de sync.

| | Aujourd’hui | Bientôt |
| --- | --- | --- |
| Nom du dépôt GitHub | `workflow-agents-pack` | **HéphaïstOS** |
| Branche de ce pack | `main` | **`pack`** |

Dans les commandes ci-dessous, remplace `REPO` et `BRANCH` si le dépôt ou la branche ont déjà basculé :

```bash
REPO="https://github.com/UlyssouLV/workflow-agents-pack.git"
BRANCH="main"   # après bascule : BRANCH="pack"
```

---

## À quoi sert le pack

Le pack installe dans un projet un **cycle de travail piloté par des skills** (Cursor et Claude Code) :

- ouvrir une version, créer des tickets, `/implement`, tests humains (`/th`), quality gate, finaliser ;
- conventions tracker GitHub, feuille de route, glossaire, hooks (ex. garde `/code-review`) ;
- scripts pour **adopter** le pack la première fois et le **synchroniser** ensuite.

Source canonique dans le projet après adoption : `agents/skills/`, `agents/hooks/`, `agents/scripts/`. Les adaptateurs `.cursor/skills/` et `.claude/skills/` sont des **copies** produites par `dispatch.py` — on ne les édite pas à la main pour un skill du pack.

Les skills **propres à un projet** (ex. Moduléo chez BBASS) restent dans ce projet : une mise à jour du pack ne les efface pas.

---

## Prérequis

Communs à tous les OS :

- **Git**
- **Python 3** (pour `dispatch.py` après adopt / update)
- **Cursor** et / ou **Claude Code** (pour `/init`, `/up`, et le reste des skills)
- Shell qui exécute les scripts **bash** du pack (`adopter-le-pack.sh`, `update-from-pack.sh`)

| OS | Shell recommandé | Notes |
| --- | --- | --- |
| **macOS** | Terminal (bash ou zsh) | `mktemp`, `rsync`, `bash` sont disponibles. |
| **Linux** | bash | Idem. Paquets usuels : `git`, `rsync`, `python3`. |
| **Windows** | **Git Bash** ou **WSL** (Ubuntu) | Les scripts sont en bash : PowerShell seul ne suffit pas. Avec Git for Windows, ouvrir *Git Bash* à la racine du projet. Sous WSL, travailler dans le filesystem Linux du clone. |

`gh` (GitHub CLI) n’est pas requis pour adopter ou mettre à jour le pack ; il l’est pour beaucoup de skills une fois le pack en place (`/cub`, `/ct`, PRs, etc.).

---

## Comment ça s’articule

```text
Dépôt HéphaïstOS (branche pack)
        │
        │  adopter-le-pack.sh   →  première fois (pas encore agents/skills/)
        │  update-from-pack.sh  →  sync mécanique (skills / hooks / scripts)
        │  skill /up            →  inventaire + migrations + sync (recommandé)
        ▼
Projet (ArgOS, BBASS, …)
   agents/skills/   agents/hooks/   agents/scripts/
        │
        │  dispatch.py
        ▼
   .cursor/skills/   .claude/skills/
```

- **`/init`** : uniquement pour un **nouveau** dépôt vide (le skill écrit le README produit). Ne pas l’utiliser pour coller le pack sur un projet déjà nommé.
- **`adopter-le-pack.sh`** : première installation sur un projet qui a déjà du code / un README.
- **`/up`** : mise à jour intelligente (propose, attend **oui**, puis applique).
- **`update-from-pack.sh`** : sync brut sans migrations de chemins / rôles / cycle.

---

## Adopter le pack

Toujours depuis la **racine du projet cible** (pas depuis le clone du pack).

### Cas A — Nouveau dépôt GitHub (encore sans README produit)

Objectif : poser le pack, puis laisser **`/init`** créer le squelette et le README du projet.

1. Créer et cloner le dépôt projet.
2. À la racine du projet, **sans** `README.md` encore (sinon `/init` s’arrête) :

**macOS / Linux / Git Bash / WSL :**

```bash
REPO="https://github.com/UlyssouLV/workflow-agents-pack.git"
BRANCH="main"   # après bascule : pack

git clone --depth 1 --branch "$BRANCH" "$REPO" /tmp/hephaistos-pack
rsync -a --exclude README.md --exclude .git --exclude .DS_Store /tmp/hephaistos-pack/ .
rm -rf /tmp/hephaistos-pack
```

Le `rsync` **exclut** le README du pack : le projet ne doit pas hériter de ce fichier.

3. Ouvrir le projet dans Cursor ou Claude Code.
4. Lancer **`/init`** et suivre les questions (Sonar, suivi HTML, docs-site, etc.).

### Cas B — Projet déjà commencé (README et code déjà là)

Objectif : installer `agents/` **sans** écraser le README ni lancer `/init`.

Condition : le projet **n’a pas encore** `agents/skills/`. S’il l’a déjà → section [Mettre à jour](#mettre-à-jour-le-pack).

**macOS / Linux / Git Bash / WSL :**

```bash
REPO="https://github.com/UlyssouLV/workflow-agents-pack.git"
BRANCH="main"   # après bascule : pack

TMP=$(mktemp -d)
git clone --depth 1 --branch "$BRANCH" "$REPO" "$TMP"
bash "$TMP/agents/scripts/adopter-le-pack.sh"
# options : --with-docs   --with-suivi
rm -rf "$TMP"
```

Avec un clone local du pack déjà à jour :

```bash
bash "/chemin/absolu/vers/hephaistos-ou-workflow-agents-pack/agents/scripts/adopter-le-pack.sh"
```

Ce que fait l’adoption (résumé) :

- crée `agents/` (skills, hooks, scripts, docs du pack) ;
- ajoute le squelette manquant (`docs/dev/`, glossaire / modèles s’ils n’existent pas) ;
- câble les hooks Claude / Cursor **sans** écraser des settings déjà présents ;
- lance `dispatch.py` ;
- **ne** réécrit **pas** le README du projet ;
- Sonar reste désactivé tant que tu n’ajoutes pas les credentials (`SONAR_*` dans `.env`).

Options :

| Option | Effet |
| --- | --- |
| `--with-docs` | Scaffold Docusaurus + workflow Pages (`docs-site/`) |
| `--with-suivi` | Scaffold `docs/suivi-avancement/` + rôle dans `agents/roles.yml` |

Ensuite : ouvrir le projet dans l’IDE et utiliser les skills (`/ob`, `/opr`, `/implement`, …). Pas de `/init`.

---

## Mettre à jour le pack

Prérequis : le projet a déjà `agents/skills/`.

### Méthode recommandée — skill `/up`

1. Ouvrir le **projet** (pas le dépôt pack) dans Cursor ou Claude Code.
2. À la racine, taper **`/up`** (ou « mets à jour le pack »).
3. Optionnel : indiquer un checkout local du pack dans le même message, pour ne pas recloner GitHub :

   ```text
   /up /chemin/absolu/vers/workflow-agents-pack
   ```

4. Lire le plan (migrations + sync). Répondre **`oui`** (mot entier), ou une sous-liste du type « seulement skills-sync, agents-tracker ».
5. Vérifier le diff, puis versionner : **`/c -a -p`** (le `/up` ne commit pas).

Le skill lit le catalogue **`agents/docs/migrations-pack.md` depuis la source pack** (pas seulement la copie locale, qui peut être vieille). Il peut proposer, entre autres :

- chemins glossaire / feuille de route ;
- clés manquantes dans `agents/roles.yml` ;
- alignement `issue-tracker.md` / `triage-labels.md` ;
- sections Cycle / Tests dans `AGENTS.md` et `.claude/CLAUDE.md` ;
- sync skills / hooks / scripts (`skills-sync`, toujours) ;
- activation docs-site ou suivi (questions **o/n**).

À la fin il écrit `agents/.pack-sha` (SHA du pack appliqué).

### Méthode sync brut — `update-from-pack.sh`

Sans inventaire ni migrations de chemins. Utile pour un refresh mécanique des skills seulement.

**macOS / Linux / Git Bash / WSL :**

```bash
REPO="https://github.com/UlyssouLV/workflow-agents-pack.git"
BRANCH="main"   # après bascule : pack

TMP=$(mktemp -d)
git clone --depth 1 --branch "$BRANCH" "$REPO" "$TMP"
bash "$TMP/agents/scripts/update-from-pack.sh"
# options : --with-docs   --with-suivi
rm -rf "$TMP"
```

Clone local :

```bash
bash "/chemin/absolu/vers/le-pack/agents/scripts/update-from-pack.sh"
```

#### Ce que fait le script

| Fait | Ne fait pas |
| --- | --- |
| Met à jour ou ajoute chaque skill / hook présent dans le pack | Supprimer un skill ou hook **local-only** |
| Rafraîchit les scripts pack sous `agents/scripts/` | Déplacer glossaire / feuille / `CONTEXT.md` (→ `/up`) |
| Rafraîchit `.claude/hooks/gate-code-review.py` et `.cursor/hooks/gate-code-review.sh` | Réécrire le README produit, `.env`, ou les settings adapter en général |
| Retire une ancienne copie `agents/templates/` (templates lus depuis le pack) | Réécrire le corps métier de la feuille de route |
| Lance `dispatch.py` (+ `--check`) | Commit / push |

Flags (identiques à l’adoption) : `--with-docs`, `--with-suivi` — ils **ajoutent** ou rafraîchissent docs-site / suivi ; ils ne « recentrent » pas le reste du projet.

---

## Après une mise à jour

- Si docs-site a été touché : `cd docs-site && npm install && npm run typecheck` (évite les faux « Cannot find module » dans l’IDE).
- Si docs-site vient d’être créé : GitHub → Settings → Pages → Source **GitHub Actions** après le premier push.
- Feuille encore hors format Prochaine / Ensuite : skill **`/afr`** (`/up` ne réécrit pas le contenu métier).

Catalogue détaillé des migrations : [`agents/docs/migrations-pack.md`](agents/docs/migrations-pack.md). Inventaire des commandes : [`agents/docs/guide-skills.md`](agents/docs/guide-skills.md).

---

## En une phrase

**Adopter** = première pose du pack sur un projet (`adopter-le-pack.sh` ou copie + `/init`). **Mettre à jour** = `/up` (recommandé) ou `update-from-pack.sh` (sync seul), toujours depuis la racine du **projet**, en puisant la branche **`pack`** du dépôt **HéphaïstOS** (aujourd’hui encore `main` de `workflow-agents-pack` tant que la bascule n’est pas faite).
