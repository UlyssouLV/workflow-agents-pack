# Migrations pack → projet (v1)

Catalogue lu par le skill **`mettre-a-jour-le-pack`** (`/up`).  
Ordre d’application recommandé = ordre du tableau.  
Le skill **propose** puis **attend un oui** avant d’écrire.

Source pack de référence : checkout temporaire ou path local du repo `workflow-agents-pack`.  
Cible : racine du projet déjà initialisé (`agents/skills/` présent).

## Catalogue

| Id | Détection (côté projet) | Action proposée |
| --- | --- | --- |
| `glossaire-path` | `CONTEXT.md` existe **ou** `roles.glossary.paths` ne contient pas `docs/glossaire.md` | Si `CONTEXT.md` et pas encore `docs/glossaire.md` : déplacer (ou copier puis laisser l’ancien si l’utilisateur refuse le delete). Mettre `glossary.paths` → `[docs/glossaire.md]`. Créer le fichier titre `# Glossary` s’il manque totalement. |
| `feuille-path` | Fichier `docs/dev/feuille-de-route-dev.md` **ou** `roles.roadmap.paths` pointe vers cet ancien path | Déplacer vers `docs/dev/feuille-de-route/feuille-de-route-dev.md`. Créer `docs/dev/recherches/` si absent. Copier le README standards depuis `agents/skills/process/initialise-le-repo/references/feuille-de-route/README.md` si `docs/dev/feuille-de-route/README.md` manque. Maj `roadmap.paths`. **Ne pas** réécrire le corps métier de la feuille (format Prochaine/Ensuite → rappel `/afr`). |
| `roles-required` | Dans `agents/roles.yml`, une des clés requises manque : `roadmap`, `glossary`, `spec`, `adr`, `readme`, `agent-adapter` | Ajouter **uniquement** les clés manquantes avec les paths du pack (`references/roles.yml`). Ne pas écraser un path custom déjà présent et valide. Ne **pas** inventer `test-roots`. Ne pas retirer `suivi-avancement` / `docs-site` s’ils existent. |
| `ecarts-a-reporter` | `agents/docs/ecarts-avec-le-pack.md` a une ligne au statut « à reporter » | **Stop avant tout le reste** (le hook `bloque-up-ecarts-pack` refuserait de toute façon `update-from-pack.sh`). Lister les sujets ; proposer **`/rap`** (`remonter-au-pack`) pour les reporter dans le pack, ou de passer le statut à « abandonné » si l’utilisateur accepte de perdre la modification. |
| `guides-projet` | `agents/docs/guide-projet.md` absent | Comparer `agents/docs/guide-skills.md` et `guide-hooks.md` du projet à ceux du pack : chaque section `###` qui documente un skill ou un hook **absent du pack** part dans `agents/docs/guide-projet.md` (`# Guide du projet`, `## Skills`, `## Hooks` ; même forme). Créer le fichier même vide. Ensuite `update-from-pack.sh` remplace les deux guides par ceux du pack (il ne le fait pas tant que `guide-projet.md` manque). |
| `agents-tracker` | `agents/issue-tracker.md` ou `agents/triage-labels.md` diffère du pack (ou manque) | Remplacer par la copie pack (conventions partagées). |
| `adapter-cycle` | `AGENTS.md` ou `.claude/CLAUDE.md` : section Cycle / Tests sans tests humains (`/th`), sans gate à Finalise, ou sans le paragraphe « Version numbers » | Aligner les sections **Cycle** et **Tests** (et le § Fin d’`/implement` dans CLAUDE) sur `initialise-le-repo/references/AGENTS.md` et `CLAUDE.md`. Ne pas écraser le reste du fichier ni le README produit. |
| `feuille-numerotation` | `docs/dev/feuille-de-route/README.md` sans section *Numéro de développement et numéro produit* | Insérer cette section (et la ligne « numéro de développement » de *Numérotation*) depuis `initialise-le-repo/references/feuille-de-route/README.md`, sans toucher au reste. Rappeler que le rôle `livrables` est optionnel et s’écrit à la main dans `agents/roles.yml` (chemins de ce qui atteint l’utilisateur final) ; sans lui, chaque version a sa Release. |
| `skills-sync` | Toujours (chaque `/up`) | Exécuter `bash <pack>/agents/scripts/update-from-pack.sh` depuis la racine projet (flags docs/suivi selon opt-* validés). Sync skills/hooks/scripts (dont `enchainer-implement.sh`, `cabler-hooks.py`) + `dispatch.py`. `cabler-hooks.py` copie les wrappers adapter de **chaque hook du pack** et réécrit leurs entrées dans `.claude/settings.json` / `.cursor/hooks.json` (une ancienne commande `py -3` ou `python3 agents/hooks/…` est remplacée, pas doublée ; les hooks du projet restent). Docs du pack rafraîchies : `agents/README.md`, `agents/docs/integration-channel.md`, `agents/docs/migrations-pack.md`, `agents/docs/checks-requis.md`, et les guides si `guides-projet` est fait. Crée `agents/docs/ecarts-avec-le-pack.md` s’il manque. Les templates (`docs-site`, workflows Pages) restent dans le pack et sont lus à la source ; une ancienne copie `agents/templates/` du projet est supprimée. Ne jamais supprimer un skill présent seulement dans le projet. |
| `opt-docs` | Pas de dossier `docs-site/` (ou pas de `docs-site/package.json`) | Demander o/n dans le plan. Si oui → `update-from-pack.sh --with-docs` (ou flag combiné). |
| `docs-site-sync` | `docs-site/package.json` présent | `update-from-pack.sh --with-docs` : rafraîchit les chemins `PACK_OWNED.txt` et répare les défauts connus des anciens templates, sans toucher au contenu projet valide : `tsconfig.json` qui sort de `docs-site/` ou n’étend pas `@docusaurus/tsconfig` ; `src/data/*.json` au mauvais shape (`bugs.json` = `{"bugs": []}`) ; `@font-face` qui lit un fichier hors `docs-site/` ; `static/` sans fichier ; `docs/adr/` sans page. `package.json` est **fusionné** (dépendances et scripts du pack ajoutés, scripts du projet gardés). `deploy-docs.yml` / `build-docs.yml` ne sont rafraîchis que s’ils commencent par la ligne « # Géré par workflow-agents-pack » (sinon gardés : personnalisés). Proposer aussi, si absent de `docs-site/docusaurus.config.ts` (fichier du projet), le plugin glossaire : `createRequire`, `const remarkGlossaire = require('./src/remark/glossaire.cjs')`, `beforeDefaultRemarkPlugins: [remarkGlossaire]` ; un ancien `src/data/glossaire.cjs` tenu à la main est désormais généré depuis `docs/glossaire.md` (`Formes : …` pour les pluriels composés, `Formes : aucune` pour ne pas lier). |
| `opt-suivi` | Pas de rôle `suivi-avancement` **et** pas de `docs/suivi-avancement/` | Demander o/n. Si oui → `update-from-pack.sh --with-suivi`. |

## Après succès

Écrire `agents/.pack-sha` = SHA court (ou full) du commit pack appliqué.

## Rappels du résumé `/up`

Le résumé les liste **toujours** quand la condition est vraie, pour que « pack à jour » ne passe pas pour « projet à jour » :

- `opt-docs` ou `docs-site-sync` appliqué → `cd docs-site && npm install && npm run typecheck` (sans `node_modules`, l’IDE signale `Cannot find module '@docusaurus/…'`).
- `docs-site-sync` appliqué et le README affiche des aperçus (`docs/img/apercu-…png`) → `cd docs-site && npx playwright install chromium` (sinon Finalise les saute en soft-skip).
- `opt-docs` appliqué → GitHub → Settings → Pages → Source : **GitHub Actions** après le premier push.
- Feuille de route pas au format Prochaine / Ensuite → `/afr` (corps non réécrit par `/up`).

## Hors catalogue v1

- Reformater le contenu de la feuille (Prochaine / Ensuite) → `/afr`
- Remplacer un `docs-site` métier (ex. BBASS) par le template générique
- Effacer des skills locaux absents du pack
- Commit / push → skill `commit` (`/c`)
