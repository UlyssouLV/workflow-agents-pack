# workflow-agents-pack

Première brique d’un projet : créer le repo GitHub, y coller ce pack, puis `/init`.

## Dans un nouveau repo

Repo GitHub créé et cloné. À la racine (sans `README.md` encore — `/init` l’écrira) :

```bash
git clone --depth 1 https://github.com/UlyssouLV/workflow-agents-pack.git /tmp/wap
rsync -a --exclude README.md --exclude .git --exclude .DS_Store /tmp/wap/ .
rm -rf /tmp/wap
```

Ouvrir ensuite le projet dans Cursor ou Claude Code et taper **`/init`**.

La commande ne copie pas le README de ce pack : `/init` s’arrête s’il en existe déjà un.

## Sur un projet déjà commencé

À la racine du projet (code déjà là, `README.md` déjà écrit, **pas** encore de `agents/skills/`) :

```bash
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/UlyssouLV/workflow-agents-pack.git "$TMP"
bash "$TMP/agents/scripts/adopter-le-pack.sh"
rm -rf "$TMP"
```

Pas de **`/init`** : le README, le code et un `AGENTS.md` déjà présent restent en place. Sonar est **désactivé** (pas de `SONAR_*` dans `.env`) ; `/qg` et la fin de `/implement` skippent tant que tu n’ajoutes pas les credentials. Le script pose `agents/`, le squelette manquant (`docs/dev/`, `CONTEXT.md`, modèles s’ils n’existent pas), câble les hooks sans écraser les settings, puis dispatch.

Si `agents/skills/` existe déjà, cette commande refuse : utilise la mise à jour ci-dessous.

## Mettre à jour un repo déjà initialisé

**Préférer le skill `/up`** (dans Cursor / Claude Code, à la racine du projet) : inventaire des écarts (chemins glossaire/feuille, rôles, tracker, cycle), proposition, **oui**, puis sync + migrations. Catalogue : `agents/docs/migrations-pack.md`.

Sync brut skills/hooks seulement (sans migration intelligente) :

```bash
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/UlyssouLV/workflow-agents-pack.git "$TMP"
bash "$TMP/agents/scripts/update-from-pack.sh"
# options : --with-docs  --with-suivi
rm -rf "$TMP"
```

Le script met à jour / ajoute les skills et hooks du pack, ne supprime pas un skill local-only, puis lance `dispatch.py`. Sans `/up`, il **n’aligne pas** tout seul `roles.yml`, `CONTEXT.md` → glossaire, ancienne feuille, etc.
