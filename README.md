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
