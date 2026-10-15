# Glossaire

**Pack** — l’ensemble des skills, hooks et scripts de `workflow-agents-pack`, maintenu sur `main` et installé dans les repos métier (et sur la branche orchestrateur) par les commandes d’adoption / de mise à jour.

**Runtime** — la partie de l’orchestrateur qui tourne sur la machine hôte (services, runners, configuration d’instance). Code sous `orchestrator/`.

**Orchestrateur** — le produit développé sur `feat/runtime-orchestrator` : runtime + cockpit.

**Cockpit** — l’interface locale de l’orchestrateur qui montre l’état des repos métier et, plus tard, déclenche des actions agent.

**Machine hôte** — la machine de l’utilisateur (Linux) qui fait tourner le runtime. Pas un VPS imposé.

**Instance** — une installation du runtime sur une machine hôte, avec sa configuration et ses secrets hors git (`~/.wap-runtime/`).

**Repo métier** — un dépôt de l’utilisateur qui a adopté le pack et que l’orchestrateur suit ou pilote.
