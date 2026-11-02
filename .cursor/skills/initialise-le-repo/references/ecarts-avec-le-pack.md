# Écarts avec le pack

Modifications faites dans ce dépôt sur des fichiers qui viennent de `workflow-agents-pack` (skills, hooks, scripts, `agents/docs/`, modèles docs-site). Un `/up` (`update-from-pack.sh`) **écrase** ces fichiers : tant qu’une ligne est **à reporter**, le hook `bloque-up-ecarts-pack` refuse `/up`. Reporter d’abord dans le pack (skill **`remonter-au-pack`**, `/rap`), puis passer le statut à **reporté** (ou **abandonné** si la modification ne doit pas survivre).

Ce qui est propre au projet (skill ou hook absent du pack, valeurs de `agents/roles.yml`, `AGENTS.md`) n’a pas sa place ici : `/up` ne l’écrase pas.

| Date | Sujet | Fichiers du dépôt | Où dans le pack | Statut |
| --- | --- | --- | --- | --- |
