# Guide des skills

À coller (ou dire) à Cursor ou Claude Code. Une ligne de **commande**, des **options** si besoin, puis éventuellement un **corps** (le reste du message).

`/` = commande (un skill). `-` = option de cette commande (`/c -a -p`, pas `/c /a /p`).

`meta/` = fonctions primaires. `process/` = recettes qui s’appellent entre elles.

Ce guide appartient au pack (`/up` l’écrase). Les skills propres à un projet sont dans `agents/docs/guide-projet.md`.

---

## Meta

### Créer un skill

**Commande :** `/cs`

**Options :** aucune.

**Corps :** ce que le skill doit faire, quand il se déclenche, `meta` ou `process` si tu le sais déjà.

Écrit un `SKILL.md` sous `agents/skills/` **après confirmation** (même sans grill), le copie vers `.claude/skills/` et `.cursor/skills/`, et ajoute l’entrée dans `agents/docs/guide-skills.md`. Équivalent : « crée un skill ».

**Exemple :**

```
/cs
Un skill qui propose un message de lint après un pytest rouge.
Trigger : « explique l'échec des tests ». Meta.
```

### Créer un hook

**Commande :** `/ch`

**Options :** aucune.

**Corps :** quand le hook doit tirer, ce qu’il bloque ou laisse passer.

Grill si besoin, **décrit le hook et attend un oui**, puis écrit `agents/hooks/<nom>/`, câble Claude **et** Cursor, et ajoute l’entrée dans `agents/docs/guide-hooks.md`. Équivalent : « crée un hook ».

**Exemple :**

```
/ch
Bloquer /code-review sauf si l’utilisateur l’a demandé, ou Finalise la version.
```

### Message de commit

**Commande :** `/mc`

**Options :** `-d` — ajoute un corps (description) au message.

**Corps :** inutile ; le skill lit le diff `HEAD` ↔ working tree.

Propose un **titre** de commit (français, le pourquoi). Ne commit pas. Avec `-d` : trois blocs copiables (titre ; description ; titre + ligne vide + description). Équivalent : « trouve un message de commit ».

**Exemple :**

```
/mc
```

```
/mc -d
```



### Lister les skills

**Commande :** `/sl`

**Options :** aucune.

**Corps :** inutile ; le skill scanne `agents/skills/`, `.claude/skills/` et `.cursor/skills/`.

Tableau : chaque skill, bucket `meta`/`process` s’il est sous `agents/`, présence Claude / Cursor. Liste les écarts (adaptateur seul, source sans copie). Équivalent : « récapitule les skills ».

**Exemple :**

```
/sl
```

### Lancer les tests

**Commande :** `/t`

**Options :** `-a` — tous les `test-roots`, suites complètes (ignore le scoping).

**Corps :** inutile.

Rôle **`test-roots`**. Sans `-a` : périmètre **hybride** — working tree s’il est sale, sinon `origin/main...HEAD` ; pour pytest, seulement les fichiers de tests liés aux `*.py` touchés (repli = suite du root si aucun match). `npm test` reste la suite du package. Détecte le runner par racine (pytest + venv, sinon `npm test`, sinon `cargo test --workspace`). Inconnu → stop. Extra Tests : rôle **`agent-adapter`**. Échec → stop. Équivalent : « lance les tests ».

**Exemple :**

```
/t
```

```
/t -a
```

### Quality gate

**Commande :** `/qg`

**Options :** `-w` — attend que `project_pull_requests/list` ou `project_branches/list` montre le SHA `HEAD` (15 s × 60, soit 15 min). Credentials absents → stop tout de suite, pas de poll.

**Corps :** inutile ; le skill lit le Quality Gate du **commit courant** via sa PR ou sa branche Sonar (`project_status?pullRequest=` / `?branch=`). Jamais le gate de `main` par défaut, jamais `project_analyses/search` comme source de vérité.

Lecture seule (`SONAR_HOST_URL`, `SONAR_TOKEN`, `SONAR_PROJECT_KEY` dans `.env`). Credentials manquants ou vides → stop immédiat (même avec `-w`). Pas d’entrée de liste pour ce HEAD → stop (avec `-w` : après le poll). Gate pas `OK` (`ERROR`, `WARN`, …) → stop. Ne corrige pas. Équivalent : « vérifie le quality gate ».

**Exemple :**

```
/qg
```

```
/qg -w
```

### Débloquer la feuille de route

**Commande :** `/dfr` ou `Débloque la feuille de route` / `Analyse les blocages` / `Quelles versions sont ouvrables`

**Options :** aucune.

**Corps :** rien.

Opt-in : seulement quand le projet a `scripts/deblocages-feuille-de-route.mjs` (rubriques **Bloquée par.** de la feuille de route, README *Blocages*). Recalcule l’**État.** de chaque version et la **Prochaine** (première version ouvrable), puis rapporte ce qui est ouvrable, en cours (branches et PR ouvertes), débloqué, encore bloqué et à découper. Seul, il lit la feuille de la base sans toucher la branche ; `finaliser-la-version` l’appelle sur la branche de version. Ne modifie ni objectifs ni bloqueurs (`/afr`), ne commite pas. Skill `debloquer-la-feuille-de-route`.

**Exemple :**

```
/dfr
```

### Ouvrir une branche

**Commande :** `/ob`

**Options :** aucune.

**Corps :** le nom de la branche. S’il manque, le skill demande et attend.

Crée et checkout la branche depuis la **base** d’intégration (`origin/main` par défaut ; si `agents/integration-channel.yml` est présent, `origin/<base_branch>` — voir [integration-channel.md](integration-channel.md)), en emportant le working tree. Pas de commit, pas de push. Stop si le nom existe. Équivalent : « ouvre une branche ».

**Exemple :**

```
/ob v1.3.0-carte
```



### Ouvrir une pull request

**Commande :** `/opr`

**Options :** `-draft` — ouvre un brouillon.

**Corps :** titre + summary / `Fixes` si tu les as ; sinon titre = dernier commit.

Push la branche courante (pas de force) et ouvre un PR vers la **base** (`main` par défaut, ou `base_branch` du [canal d’intégration](integration-channel.md)). Refuse de créer depuis une branche protected. Équivalent : « ouvre une PR ».

**Exemple :**

```
/opr
```

```
/opr -draft
VX.Y.Z — un job
Fixes #12
Fixes #13
```

### Créer un ticket

**Commande :** `/ct`

**Options :** aucune.

**Corps :** titre + ce que le ticket livre (critères d’acceptation) ; `#parent` si besoin ; éventuellement `Blocked by #n` **avec** `vraie dépendance : <ce qui casse>` ou `ordre de confort : …` (`agents/issue-tracker.md`). Sans cette phrase : l’agent demande, il n’invente pas.

Crée **un** enfant GitHub (`Part of`, sub-issue, parent bloqué par l’enfant). Corps au format Matt `/to-tickets` : `## What to build` / `## Acceptance criteria` / `## Blocked by` (`agents/issue-tracker.md`). Avant : le ticket tient dans `docs/specs/vX.Y.Z-*.md`. Après : le corps de l’issue parente GitHub = ce fichier ; si une PR ouverte cite déjà le parent, ajoute les `Fixes #n` manquants. Pas de nouvelle PR. Équivalent : « crée un ticket ». Skill `creer-ticket`.

**Exemple :**

```
/ct #12
Titre : garde-fou chiffres manquants après reverse
Le reverse d’un message avec chiffres doit rejouer le garde-fou avant envoi.
Blocked by #40 — vraie dépendance : sans #40 le reverse n’a pas de garde-fou à rejouer
```

### Créer un bug

**Commande :** `/cub`

**Options :** aucune.

**Corps :** titre court + constat, reproductibilité, impact, cause probable, à corriger ; métadonnées (version trouvée, contexte, date, priorité). Hors périmètre optionnel. Captures d’écran optionnelles (images du chat ou chemins).

Crée **une** issue GitHub (`Bug — …`, label `bug`, corps à titres fixes) et l’entrée sous **Plus tard** de la feuille de route (`docs/dev/feuille-de-route/`). Si captures : fichiers sous `docs/img/bugs/` + `gh --attach` (pièces jointes réelles sur le ticket). Standards : `docs/dev/feuille-de-route/README.md` (jeton `Informations manquantes` si une case manque → bug **incomplet**). Pas de commit (sauf si tu veux versionner `docs/img/bugs/` via `/c`). Pas de promo en Prochaine/Ensuite (`/afr`). Équivalents : « crée un bug », « ajoute un bug », « documente un bug ». Skill `creer-un-bug`.

**Exemple :**

```
/cub
Titre : bascule de conversation pendant qu’une réponse est en cours
Constat : le fil affiché ne suit pas la sidebar…
Reproductibilité : envoyer un message, cliquer une autre conversation
Impact : mauvais fil affiché
Cause probable : état React non synchronisé avec la sélection
À corriger : synchroniser le fil même si une requête est en vol
Trouvé dans : 1.4.3
Contexte : test humain
Priorité : avant déploiement
```

### Créer une release

**Commande :** `/crel`

**Options :** aucune.

**Corps :** `vX.Y.Z` (ou `X.Y.Z`), éventuellement le purpose.

Crée la GitHub Release **sur le SHA de la branche courante**, pas la base. Tag = `vX.Y.Z` ou `{release_tag_prefix}X.Y.Z` si [canal d’intégration](integration-channel.md) (ex. `orchestrator-v0.1.0`). Titre humain `VX.Y.Z — …` au **numéro produit** (le tag passé par Finalise prime sur la branche ; le numéro de développement va dans les notes, ligne `Développement : D (#parent)`). Notes : Pourquoi / Ce qu’on peut faire / Historique (PR + Fixes) / Hors périmètre (ADR sur le tag) — **même format** ; l’historique de commits ne sert qu’à **combler les manques** (feature ou bug absents de la spec/PR), jamais en dump de subjects. Ne retaggue pas. Pas de merge. Équivalent : « crée une release ».

**Exemple :**

```
/crel v1.3.0
```

### Fusionner le PR

**Commande :** `/mpr`

**Options :** aucune.

**Corps :** inutile.

Squash-merge du PR de la branche courante dans la **base** (`main` ou canal), suppression de la branche **feature** seulement (jamais la base). Si `agents/checks-requis.yml` existe, refuse tant qu’un check de cette liste n’est pas vert (`agents/docs/checks-requis.md`). Ne déplace pas le tag de release. Équivalent : « fusionne le PR ».

**Exemple :**

```
/mpr
```

---



## Process

### Mettre à jour le pack

**Commande :** `/up` ou `Mets à jour le pack` / `Update le pack`

**Options :** aucune sur `/up` ; docs / suivi se choisissent dans le plan (o/n).

**Corps :** optionnel — chemin local vers un checkout `workflow-agents-pack` ; sinon clone temporaire depuis GitHub.

Inventorie le projet vs le pack (`agents/docs/migrations-pack.md`), propose migrations + sync skills, **attend un oui**, puis applique et dispatch. Refusé (hook `bloque-up-ecarts-pack`) tant qu’une ligne de `agents/docs/ecarts-avec-le-pack.md` est « à reporter » → **`/rap`** d’abord. N’efface pas les skills locaux. Ne commit pas. Skill `mettre-a-jour-le-pack`. Sync brut sans grill : `update-from-pack.sh`.

**Exemple :**

```
/up
```

```
/up
Pack local : /Users/moi/Desktop/workflow-agents-pack
```

### Remonter au pack

**Commande :** `/rap` ou `Remonte au pack` / `Reporte dans le pack`

**Options :** aucune.

**Corps :** chemin d’un checkout local de `workflow-agents-pack` (obligatoire : les modifications y sont écrites).

Depuis un projet : compare les fichiers venus du pack à leur version au `agents/.pack-sha`, classe chaque écart (bug du pack, amélioration générique, variante optionnelle, spécifique au projet, retard du projet), **attend un oui**, porte les éléments choisis dans le pack (branche `remontee-<projet>-<date>`, généralisés, opt-in si besoin) et passe leurs lignes à « reporté » dans `agents/docs/ecarts-avec-le-pack.md`. Ne commit pas. Ensuite : `/c` dans le pack, puis `/up` dans le projet. Skill `remonter-au-pack`.

**Exemple :**

```
/rap
Pack local : /Users/moi/Desktop/workflow-agents-pack
```

### Initialise le repo

**Commande :** `/init` ou `Initialise le repo`

**Options :** aucune.

**Corps :** inutile ; le skill grille à quoi sert le repo.

Crée le squelette (`docs/dev/feuille-de-route/`, recherches, specs, ADR, `docs/glossaire.md`), dispatch, grill, README + modèles, demande Sonar **o/n** (`.env` + `gh secret set` si oui), demande suivi d’avancement HTML **o/n**, demande documentation Docusaurus + GitHub Pages **o/n** (`scaffold-docs-site.sh` si oui), commit `/c -a -p` (y compris sur `main`). Stop si un README existe déjà. Skill `initialise-le-repo`. Sur un repo déjà initialisé sans site : `agents/scripts/update-from-pack.sh --with-docs`.

**Exemple :**

```
/init
```

```
Initialise le repo
```

### Vérifie la fiabilité du code

**Commande :** `/vf` ou `Vérifie la fiabilité du code`

**Options :** aucune.

**Corps :** inutile.

Lance **`/t`** puis **`/qg`**. Premier échec → stop. Ne corrige pas le gate. Skill `verifier-la-fiabilite`.

**Exemple :**

```
/vf
```

```
Vérifie la fiabilité du code
```

### Corriger le quality gate

**Commande :** `/cqg` ou `Corriger le quality gate`

**Options :** aucune.

**Corps :** inutile.

Lit **`/qg`**, corrige ce que le gate exige. Ne relit pas le même SHA (même analyse). Appelé depuis **Finalise la version** quand le gate n’est pas `OK`. Le caller (ou toi) fait **`/c`** puis **`/qg`** / **`/qg -w`**. Skill `corriger-quality-gate`.

**Exemple :**

```
/cqg
```

### Commit

**Commande :** `/c`

**Options :** `-a` — tout le working tree, pas seulement l’index. `-p` — push après le commit. `-p -f` — `--force-with-lease` après confirmation **oui** au message suivant.

**Corps :** inutile ; le skill relit le diff via `/mc -d` (bloc 3 = message).

Commit sur la branche courante (HEAD ↔ working tree). Défaut = fichiers déjà stagés. Refuse `main` / `master`, **sauf** `/init`. Secrets exclus. Équivalent process : skill `commit`.

**Exemple :**

```
/c
```

```
/c -a -p
```

```
/c -p -f
```

### Fermer un ticket enfant

**Commande :** `/cci`

**Options :** `-t` — lance `/t` d’abord ; échec = pas de close.

**Corps :** `#n` de l’enfant. S’il manque, le skill demande et attend.

Retire `ready-for-agent` et ferme l’issue. Refuse s’il n’y a pas `Part of` / `## Parent` (probable spec). Refuse les tickets **tests humains** (`ready-for-human` → `/th`). Équivalent : « ferme le ticket enfant ».

**Exemple :**

```
/cci #42
```

```
/cci -t #42
```

### Augmenter la feuille de route de dev

**Commande :** `/afr` ou `Augmente la feuille de route de dev` / `Améliore la feuille de route de dev`

**Options :** aucune.

**Corps :** versions à ajouter ou à reformuler, si tu les as déjà ; sinon le skill lit la feuille de route de dev et propose.

Lit le rôle **`roadmap`** (`docs/dev/feuille-de-route/feuille-de-route-dev.md`), standards dans le README voisin. Liste Déjà livré / Prochaine / Ensuite / Plus tard (bugs), argumente, **attend**, puis écrit uniquement ce que tu as validé ; relance `scripts/avancement-feuille-de-route.mjs` s’il existe (bandeau d’avancement du README) ; avec les blocages (opt-in), écrit la rubrique **Bloquée par.** de chaque version et laisse le script calculer **État.** et la **Prochaine**. Pas de `/c` tout seul. Skill `augmenter-la-feuille-de-route-dev`.

**Exemple :**

```
/afr
```

```
Augmente la feuille de route de dev
1.0.0 — catalogue public et admin
```

### Ouvrir la version

**Commande :** `Ouvre la version`

**Options :** semver obligatoire `X.Y.Z` (ex. `1.3.0`).

**Corps :** seulement si la version n’est pas déjà dans le rôle **`roadmap`** — à quoi elle sert (un job).

Grill + spec, puis **`/ob`**, écriture de la spec, **`/c -a -p`**, tickets d’implémentation + **un enfant tests humains** (`ready-for-human` ; chaque enfant : `Part of`, **sub-issue** GitHub, `blocked_by` **avec** `vraie dépendance` / `ordre de confort`), **`/opr -draft`**, puis propose le premier `/implement` (pas le ticket tests humains). Skill `ouvrir-la-version`.

**Exemple :**

```
Ouvre la version 1.3.0
```



### Encadrer `/implement`

**Commande :** `/implement #<n>`

**Options :** le numéro d’issue enfant GitHub.

**Corps :** inutile en général (le ticket suffit).

TDD du ticket (plugin `/implement`). La **fin** : **`/t`**, **`/c -p`**, **`/cci #<n>`**, puis auto-enchaînement du suivant `ready-for-agent` via `agents/scripts/enchainer-implement.sh` (`$WAP_ENCHAINER` si défini — session orchestrateur — sinon nouvelle fenêtre terminal + Claude Code vierge sur `/implement #<next>` sous macOS / Linux / Windows ; fallback : demander une nouvelle session). Pas de `/clear` de la conversation finie. Quand il n’en reste plus : remplit le **plan** sur le ticket tests humains et renvoie vers **`/th`** (pas `/code-review` tant que ce ticket est Open). Quand tout est Closed : **`/code-review`**, puis **Finalise la version**. Pas de quality gate ici. Skill `encadrer-implement`. Ne pas l’appeler à la place de `/implement`.

**Exemple :**

```
/implement #42
```



### Tests humains

**Commande :** `/th`

**Options :** `#<n>` (le ticket `Tests humains — VX.Y.Z`) ; sans numéro, celui de la branche courante.

**Corps :** vide au premier passage ; ensuite scénarios joués / non joués, résultats ; images de preuve optionnelles (commit sous `docs/img/changelog/vX.Y.Z/`).

Deux passages. **1)** `/th #<n>` seul : l’agent joue les scénarios qu’il peut faire sans vous (CLI, app locale, navigateur), commit les captures, écrit ses résultats sur le ticket et liste ce qui reste pour vous ; le ticket reste ouvert. **2)** `/th #<n>` avec vos résultats (ou « ok » s’il ne restait rien) : met à jour le ticket `ready-for-human`, commit vos captures si besoin, ferme l’issue, propose `/code-review` puis Finalise. Skill `tests-humains`. Pas `/implement`. Pas `/cci`.

**Exemple :**

```
/th #7
```

puis

```
/th #7
J’ai joué 3 et 5 (OK). 6 non joué (pas de compte admin sous la main).
```



### Ouvrir la semaine de travail

**Commande :** `/os`

**Options :** versions attendues en surcharge (`/os 1.5.0 1.6.0`) ; sinon Prochaine + Ensuite de la feuille de route (confirmation avant écriture).

**Corps :** inutile en général.

Nécessite le rôle **`suivi-avancement`** (opt-in à `/init` ou `adopter-le-pack.sh --with-suivi`). Crée le dossier `semaine-…` + HTML depuis `docs/suivi-avancement/template-semaine.html` (lun→ven). Convention : `docs/suivi-avancement/README.md`. Skill `ouvrir-semaine-de-travail`. Ne commit pas. Ne finalise pas.

**Exemple :**

```
/os
```



### Mettre à jour le suivi d’avancement

**Commande :** `/msa`

**Options :** semver `X.Y.Z` si pas déductible de la branche.

**Corps :** inutile.

Met à jour le HTML de la semaine courante pour la version livrée ; PDF si `generer-pdf.mjs` existe (sinon soft-skip). Soft-skip + rappel `/os` s’il n’y a pas de dossier. Soft-skip si le rôle suivi est absent. Appelé aussi par **Finalise la version**. Skill `mettre-a-jour-suivi-avancement`. Ne commit pas. Ne crée pas la semaine.

**Exemple :**

```
/msa 1.5.0
```



### Finaliser la version

**Commande :** `Finalise la version`

**Options :** aucune.

**Corps :** inutile.

Après une **`/code-review`** acceptée : branche à jour avec la base (sinon stop : merge de la base, `/t`, `/c -p`), calcul du **numéro produit** (`docs/dev/feuille-de-route/README.md` ; pas de Release si le rôle optionnel `livrables` existe et qu’aucun de ses chemins n’a bougé), tous les enfants Closed (y compris le ticket **tests humains** — sinon stop et **`/th`**), aucune PR Dependabot ouverte si `.github/dependabot.yml` existe (sinon stop : les fusionner ou les fermer) + docs à jour (`readme`, `roadmap` — et le bandeau d’avancement du README si `scripts/avancement-feuille-de-route.mjs` existe —, **`/msa`** si rôle suivi présent — `/c -a -p` si besoin), puis **`/qg -w`** (puis **`/cqg`** si le gate n’est pas `OK`), puis les checks exigés si `agents/checks-requis.yml` existe, puis **`/crel vP`**, puis les aperçus README si le README en affiche (opt-in, Playwright), puis les compteurs de commits du README si `scripts/stats-commits-readme.mjs` existe, puis **`/mpr`**. Skill `finaliser-la-version`. Ne relance pas `/code-review`.

**Exemple :**

```
Finalise la version
```

