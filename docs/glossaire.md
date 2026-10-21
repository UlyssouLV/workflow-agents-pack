# Glossaire

**Pack** — l’ensemble des skills, hooks et scripts de `workflow-agents-pack`, maintenu sur `main` et installé dans les repos métier (et sur la branche orchestrateur) par les commandes d’adoption / de mise à jour.

**Runtime** — la partie de l’orchestrateur qui tourne sur la machine hôte (services, runners, configuration d’instance). Code sous `orchestrator/`.

**Orchestrateur** — le produit développé sur `feat/runtime-orchestrator` : runtime + cockpit.

**Cockpit** — l’interface web de l’orchestrateur qui montre l’état des repos métier et lance des sessions agents ; joignable en local, via tunnel SSH, ou (opt-in) derrière l’exposition web.

**Identifiants cockpit** — le login et le mot de passe propres à une instance pour ouvrir le cockpit ; distincts de l’authentification GitHub et des agents (`wap-runtime auth`).

**Exposition web** — mise à disposition du cockpit derrière le reverse proxy Caddy de l’instance (ports 80/443 sur la machine hôte), activable ou désactivable ; sans exposition, l’accès reste local ou par tunnel SSH.

**Domaine** — nom d’hôte configuré sur l’instance (`wap-runtime domaine`) pour que Caddy obtienne et renouvelle un certificat Let’s Encrypt ; sans domaine, pas de mode officiel « HTTP public ».

**Diagnostic** — commande CLI (`wap-runtime diagnostic`) qui sépare ce que l’instance a fait (Caddy, ports, auth cockpit, domaine) du reste côté opérateur (DNS, NAT, limites CGNAT).

**Machine hôte** — la machine de l’utilisateur (Linux) qui fait tourner le runtime. Pas un VPS imposé.

**Instance** — une installation du runtime sur une machine hôte, avec sa configuration et ses secrets hors git (`~/.wap-runtime/`).

**Repo métier** — un dépôt de l’utilisateur qui a adopté le pack et que l’orchestrateur suit ou pilote.

**Socle** — les outils système dont le runtime a besoin sur la machine hôte : `git`, Docker Engine + Compose, `gh`, et les CLIs agents `claude` / `agent`. Le provisionnement n’installe que ce qui manque, sans authentification.

**Provisionnement** — la préparation d’une machine hôte par la commande d’installation : socle (Docker, `git`, `gh`, CLIs agents), utilisateur d’instance, instance et services runtime démarrés.

**Utilisateur d’instance** — l’utilisateur système `orchestrator` créé par le provisionnement : il possède l’instance et les CLIs agents, et exécute le runtime (jamais root).

**Repo lié** — un repo métier que l’instance suit, déclaré par son `owner/name` GitHub ; le suivre ne le clone pas (le runner en tient un **clone géré** au premier lancement de session).

**Registry** — la liste des repos liés d’une instance (`~/.wap-runtime/repos.toml`), gérée par `wap-runtime repo add|remove|list`.

**Étape** — ce que le cockpit affiche pour une version ouverte d’un repo lié, déduite du tracker (labels, sub-issues, checks de la PR) : une seule par version, choisie par priorité. L’étape d’un repo est celle de ses versions qui attend quelqu’un, sinon la plus prioritaire.

**CI** — vérification automatique des changements proposés sur le canal orchestrateur : workflow GitHub Actions sur chaque PR vers la base d’intégration (`feat/runtime-orchestrator`), qui lance les suites (pytest, Vitest, avec couverture) puis un scan Sonar ; le job Sonar échoue si le quality gate n’est pas `OK`. Distinct des suites locales (`/t`) et de la seule lecture du gate (`/qg`).

**Intervention humaine** — une étape qui attend quelqu’un (question en attente, CI en échec, tests humains, code review / Finalise) ; le cockpit la signale par un badge.

**Runner** — le service de l’instance qui exécute les sessions agents sur les clones gérés, dans un conteneur sans accès à l’hôte (ADR 0004).

**Clone géré** — le clone d’un repo lié tenu par l’instance (`~/.wap-runtime/clones/<owner>/<name>/`), sur lequel travaillent les sessions du runner.

**Session** — un agent (Claude Code ou Cursor) lancé en mode interactif par le runner depuis le cockpit, dans un terminal affiché dans le navigateur, sur une branche du clone géré ; enregistrée sous `~/.wap-runtime/jobs/<id>/` et rejouable. Au plus une session ouverte par repo (ADR 0007). Une **session libre** démarre sans commande (`claude`, `agent`) : l’humain tape ce qu’il veut ; une session enchaînée lance `/implement #n`. Pour Cursor, chaque session a un **modèle** (ID CLI ou Auto) : défaut par repo lié, override possible à Nouvelle session, héritage via `precedente` pour l’enchaînement (ADR 0009).

**Session serveur** (aussi **session navigateur**) — l’authentification web au cockpit : cookie httpOnly + registre côté instance (~7 jours) ; distincte de la **session** agent ci-dessus. Créée au login, coupée à la déconnexion ou au changement du mot de passe cockpit (ADR 0010).

**Activité** — ce que fait une session ouverte, remonté par les hooks des agents : *travaille*, *attend* (réponse attendue, avec le dernier skill s’il est connu) ou *inconnue* (valeur de départ, ou agent sans hooks) (ADR 0007). Le titre de la session est le premier message tapé, sinon le nom de l’agent.

**Main** — le droit de taper dans le terminal d’une session ouverte : un seul onglet du cockpit l’a à la fois ; les autres sont en lecture seule et peuvent la **prendre**. Quitter la page de session la libère.

**Session enchaînée** — une session qui a demandé au runner d’ouvrir la suivante (`/implement #m` sur un enfant éligible du même repo, même agent, contexte vierge) et s’est fermée ; ses liens `precedente` / `suivante` forment la chaîne (ADR 0006).

**Pilote** — mode opt-in par repo lié : une boucle dans le service `runtime` démarre le premier enfant Implement éligible, surveille la chaîne (activité, intervention humaine, erreur) et notifie l’humain aux stops, puis reprend tant que le mode reste activé (ADR 0008). L’enchaînement ticket à ticket reste le pack (`encadrer-implement`), pas le runtime.
