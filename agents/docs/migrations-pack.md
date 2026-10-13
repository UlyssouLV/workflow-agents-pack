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
| `agents-tracker` | `agents/issue-tracker.md` ou `agents/triage-labels.md` diffère du pack (ou manque) | Remplacer par la copie pack (conventions partagées). |
| `adapter-cycle` | `AGENTS.md` ou `.claude/CLAUDE.md` : section Cycle / Tests sans tests humains (`/th`) ou sans gate à Finalise | Aligner les sections **Cycle** et **Tests** (et le § Fin d’`/implement` dans CLAUDE) sur `initialise-le-repo/references/AGENTS.md` et `CLAUDE.md`. Ne pas écraser le reste du fichier ni le README produit. |
| `skills-sync` | Toujours (chaque `/up`) | Exécuter `bash <pack>/agents/scripts/update-from-pack.sh` depuis la racine projet (flags docs/suivi selon opt-* validés). Sync skills/hooks/scripts + `dispatch.py`. Les templates (`docs-site`, workflow Pages) restent dans le pack et sont lus à la source ; une ancienne copie `agents/templates/` du projet est supprimée. Ne jamais supprimer un skill présent seulement dans le projet. |
| `opt-docs` | Pas de dossier `docs-site/` (ou pas de `docs-site/package.json`) | Demander o/n dans le plan. Si oui → `update-from-pack.sh --with-docs` (ou flag combiné). |
| `docs-site-sync` | `docs-site/package.json` présent | `update-from-pack.sh --with-docs` : rafraîchit les chemins `PACK_OWNED.txt` et répare les défauts connus des anciens templates, sans toucher au contenu projet valide : `tsconfig.json` qui sort de `docs-site/` ou n’étend pas `@docusaurus/tsconfig` ; `src/data/*.json` au mauvais shape (`bugs.json` = `{"bugs": []}`) ; `@font-face` qui lit un fichier hors `docs-site/` ; `static/` sans fichier ; `docs/adr/` sans page. |
| `opt-suivi` | Pas de rôle `suivi-avancement` **et** pas de `docs/suivi-avancement/` | Demander o/n. Si oui → `update-from-pack.sh --with-suivi`. |

## Après succès

Écrire `agents/.pack-sha` = SHA court (ou full) du commit pack appliqué.

## Rappels du résumé `/up`

Le résumé les liste **toujours** quand la condition est vraie, pour que « pack à jour » ne passe pas pour « projet à jour » :

- `opt-docs` ou `docs-site-sync` appliqué → `cd docs-site && npm install && npm run typecheck` (sans `node_modules`, l’IDE signale `Cannot find module '@docusaurus/…'`).
- `opt-docs` appliqué → GitHub → Settings → Pages → Source : **GitHub Actions** après le premier push.
- Feuille de route pas au format Prochaine / Ensuite → `/afr` (corps non réécrit par `/up`).

## Hors catalogue v1

- Reformater le contenu de la feuille (Prochaine / Ensuite) → `/afr`
- Remplacer un `docs-site` métier (ex. BBASS) par le template générique
- Effacer des skills locaux absents du pack
- Commit / push → skill `commit` (`/c`)
