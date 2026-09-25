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

## Mettre à jour un repo déjà initialisé

À la racine du projet (celui qui a déjà `agents/skills/`, ex. `aduna_crea-website`) :

```bash
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/UlyssouLV/workflow-agents-pack.git "$TMP"
bash "$TMP/agents/scripts/update-from-pack.sh"
rm -rf "$TMP"
```

Ça met à jour les skills et hooks **déjà présents** avec la version de ce pack, et **ajoute** ceux qui n’existent que dans le pack. Ça n’efface pas un skill ou un hook créé seulement dans le projet. `AGENTS.md`, `agents/roles.yml`, le README du projet, `.env` et les settings des adaptateurs ne sont pas touchés.

Ensuite `dispatch.py` recopie vers `.claude/skills/` et `.cursor/skills/` (sans supprimer un skill qui n’existe que dans un adaptateur).
