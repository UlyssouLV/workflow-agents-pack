#!/bin/sh
# Recopie les skills de l’image dans le `HOME` persistant (`runner-home/`), monté
# par-dessus celui du build. Les skills ajoutés à la main dans ce `HOME` restent.
set -eu

for dossier in .agents/skills .claude/skills .cursor/skills; do
    if [ -d "$WAP_RUNNER_SQUELETTE/$dossier" ]; then
        mkdir -p "$HOME/$dossier"
        cp -Rf "$WAP_RUNNER_SQUELETTE/$dossier/." "$HOME/$dossier/"
    fi
done

exec "$@"
