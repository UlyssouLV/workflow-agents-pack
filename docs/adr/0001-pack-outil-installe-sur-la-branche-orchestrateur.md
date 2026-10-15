# 0001 — Le pack est un outil installé sur la branche orchestrateur

- Statut : accepté
- Date : 2026-10-15
- Version : 0.1.0 (#4)

## Contexte

Le dépôt `workflow-agents-pack` porte deux choses : le pack de skills (maintenu sur `main`, synchronisé vers les repos métier) et l’orchestrateur self-hosted (développé sur `feat/runtime-orchestrator`, voir `agents/integration-channel.yml`). On utilise les skills du pack pour développer l’orchestrateur, mais la branche orchestrateur versionnait une copie complète du pack qui dérivait de `main`.

## Décision

1. Sur `feat/runtime-orchestrator`, le pack est un **outil installé** : ce que `update-from-pack.sh` et `dispatch.py` régénèrent (`agents/skills/`, `agents/hooks/`, `agents/scripts/`, `.claude/skills/`, `.cursor/skills/`) est ignoré par git, ainsi que `agents/templates/`, ancienne copie que la mise à jour supprime. Le développeur l’installe et le met à jour lui-même depuis `main`.
2. Le dépôt ne suit que la configuration propre au projet (`agents/roles.yml`, `agents/integration-channel.yml`, `agents/issue-tracker.md`, adaptateurs `.claude/` et `.cursor/` hors skills, etc.).
3. Les skills se modifient sur `main`, jamais ici. Les commandes d’adoption et de mise à jour du pack appartiennent à `main`.
4. `feat/runtime-orchestrator` n’est **jamais** fusionnée dans `main` : le retrait des skills de l’index les supprimerait de `main`.
5. Le code de l’orchestrateur vit sous `orchestrator/`.

## Conséquences

- Un clone neuf de la branche n’a pas de skills : le README documente l’installation (`mkdir -p agents/skills` puis `update-from-pack.sh`).
- La frontière est gardée par une suite pytest (`git check-ignore`), pas par une CI.
- Les correctifs d’outillage du pack découverts ici (ex. bug #3) se corrigent sur `main`.
- À terme, `main` deviendra une branche d’aiguillage dont le README décrit chaque branche dédiée ; ce n’est pas traité ici.
