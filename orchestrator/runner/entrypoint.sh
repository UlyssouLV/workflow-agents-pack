#!/bin/sh
# Recopie les skills de l’image dans le `HOME` persistant (`runner-home/`), monté
# par-dessus celui du build. Les skills ajoutés à la main dans ce `HOME` restent.
# Fusionne aussi les règles étroites d’enchaînement (Claude + Cursor, bug #69).
set -eu

for dossier in .agents/skills .claude/skills .cursor/skills; do
    if [ -d "$WAP_RUNNER_SQUELETTE/$dossier" ]; then
        mkdir -p "$HOME/$dossier"
        cp -Rf "$WAP_RUNNER_SQUELETTE/$dossier/." "$HOME/$dossier/"
    fi
done

# `wap-runtime` est hors du PATH des agents ; l’entrypoint utilise le venv image.
/opt/wap-runtime/bin/python -m wap_runtime.permissions_enchainer

exec "$@"
