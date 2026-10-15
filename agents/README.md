# Agents de développement

Sur cette branche, le pack de skills est un outil installé depuis `main` : `agents/skills/`, `agents/hooks/`, `agents/scripts/` et `agents/templates/` sont ignorés par git et se réinstallent avec le bloc « Installer les skills » du [README](../README.md). Ne pas créer ni corriger de skill ici : cela se fait sur `main`, puis se réinstalle ([ADR 0001](../docs/adr/0001-pack-outil-installe-sur-la-branche-orchestrateur.md)).

Ce dossier garde la configuration propre au projet : conventions de process (tracker, labels, lecture du domaine), chemins et règle d’arrêt si un rôle est irrésolu ([roles.yml](roles.yml)), canal d’intégration ([docs/integration-channel.md](docs/integration-channel.md), [integration-channel.yml](integration-channel.yml)). Comment lancer les skills : [docs/guide-skills.md](docs/guide-skills.md). Hooks : [docs/guide-hooks.md](docs/guide-hooks.md).
