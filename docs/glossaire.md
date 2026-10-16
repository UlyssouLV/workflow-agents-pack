# Glossaire

**Pack** — l’ensemble des skills, hooks et scripts de `workflow-agents-pack`, maintenu sur `main` et installé dans les repos métier (et sur la branche orchestrateur) par les commandes d’adoption / de mise à jour.

**Runtime** — la partie de l’orchestrateur qui tourne sur la machine hôte (services, runners, configuration d’instance). Code sous `orchestrator/`.

**Orchestrateur** — le produit développé sur `feat/runtime-orchestrator` : runtime + cockpit.

**Cockpit** — l’interface locale de l’orchestrateur qui montre l’état des repos métier et, plus tard, déclenche des actions agent.

**Machine hôte** — la machine de l’utilisateur (Linux) qui fait tourner le runtime. Pas un VPS imposé.

**Instance** — une installation du runtime sur une machine hôte, avec sa configuration et ses secrets hors git (`~/.wap-runtime/`).

**Repo métier** — un dépôt de l’utilisateur qui a adopté le pack et que l’orchestrateur suit ou pilote.

**Socle** — les outils système dont le runtime a besoin sur la machine hôte : `git`, Docker Engine + Compose, `gh`, et les CLIs agents `claude` / `agent`. Le provisionnement n’installe que ce qui manque, sans authentification.

**Provisionnement** — la préparation d’une machine hôte par la commande d’installation : socle (Docker, `git`, `gh`, CLIs agents), utilisateur d’instance, instance et services runtime démarrés.

**Utilisateur d’instance** — l’utilisateur système `orchestrator` créé par le provisionnement : il possède l’instance et les CLIs agents, et exécute le runtime (jamais root).

**Repo lié** — un repo métier que l’instance suit, déclaré par son `owner/name` GitHub, sans clone.

**Registry** — la liste des repos liés d’une instance (`~/.wap-runtime/repos.toml`), gérée par `wap-runtime repo add|remove|list`.

**Étape** — ce que le cockpit affiche pour une version ouverte d’un repo lié, déduite du tracker (labels, sub-issues, checks de la PR) : une seule par version, choisie par priorité. L’étape d’un repo est celle de ses versions qui attend quelqu’un, sinon la plus prioritaire.

**Intervention humaine** — une étape qui attend quelqu’un (question en attente, CI en échec, tests humains, code review / Finalise) ; le cockpit la signale par un badge.
