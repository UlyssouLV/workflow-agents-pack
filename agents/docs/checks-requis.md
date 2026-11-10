# Checks requis sur la base

## Sans ruleset : les skills portent la règle (opt-in)

Sur un dépôt privé en plan free, GitHub n’offre ni ruleset ni protection de branche. La règle « une PR rouge ne se fusionne pas » est alors portée par les skills, **seulement si `agents/checks-requis.yml` existe** (absent → les skills sautent l’étape ; un ruleset garde la base) :

- **`agents/checks-requis.yml`** liste les noms **exacts** des checks exigés, tels que l’onglet *Checks* d’une PR les affiche. Format lu sans PyYAML, un nom par ligne :

  ```yaml
  checks:
    - build-docs
    - Tests
  ```

- **`agents/scripts/checks-requis.py [<pr>]`** lit cette liste et `gh pr checks --json name,bucket`. Un check exigé **rouge** (`fail`, `cancel`), **en attente** ou **absent** → sortie `1`, chaque check fautif nommé ; tous verts → `0` ; liste ou sortie de `gh` illisible → `2`. Un job sauté par `if:` (`skipping`) compte comme vert. Le nom doit être exact : par exemple `SonarCloud Code Analysis` (publié par l’app SonarCloud) n’est pas le nom du job d’analyse de la CI.
- **`fusionner-pr`** (`/mpr`) le lance avant `gh pr merge --squash` ; **`finaliser-la-version`** avant `/crel` (pas de tag sur une PR rouge), puis `/mpr` le relance. Seulement en attente → `gh pr checks --watch`, puis une seconde lecture.
- Conseillé : un test du projet qui vérifie que chaque nom de la liste est produit par un seul job d’un workflow déclenché sur `pull_request` sans `paths:`.

**Limite** : le bouton « Merge » de GitHub reste cliquable, et `gh pr merge` lancé à la main n’est pas filtré. La règle tient pour les agents, pas contre un clic humain.

Ajouter une CI dont le check doit être exigé : ajouter son nom à `agents/checks-requis.yml` dans la même version. Passer un jour à un ruleset : y reporter la même liste, puis supprimer `agents/checks-requis.yml`.

### Dependabot (opt-in)

Avec `.github/dependabot.yml`, `finaliser-la-version` s’arrête tant qu’une PR Dependabot vers la base reste ouverte (étape 1 bis). Pour la même règle hors agent, copier le modèle `agents/templates/github/workflows/dependances-a-jour.yml` dans `.github/workflows/` et exiger son check **`Dépendances à jour`** (ruleset ou `agents/checks-requis.yml`). Il est rouge tant qu’une PR Dependabot vers la base de la PR reste ouverte (résolue = fusionnée ou fermée), sauté sur les PR Dependabot elles-mêmes, et rejoué sur les PR ouvertes dès qu’une PR Dependabot s’ouvre ou se ferme (`pull_request_target`, jeton `actions: write`, aucun code de PR récupéré).

## Avec un ruleset

Protéger la branche d’intégration (`main`, ou `base_branch` du [canal d’intégration](integration-channel.md)) est un geste **humain** d’admin du dépôt (pas d’API dans le cycle) : **Settings** → **Rules** → **Rulesets** → **New branch ruleset** (ou celui qui cible la base).

1. **Enforcement status** : Active. **Target branches** : la base.
2. **Restrict deletions** et **Block force pushes** : activés.
3. **Require a pull request before merging** : activé, méthode de merge **Squash** seulement (`fusionner-pr` squash-merge ; le tag de Release est posé sur le SHA de la branche, voir `creer-release`).
4. **Require status checks to pass** : ajouter **exactement** les noms affichés sur une PR (onglet *Checks*), un par compartiment de CI — par exemple `build-docs` (workflow `build-docs.yml` du pack), le job de Sonar, les tests.

## Écrire une CI dont les checks peuvent être requis

- **Filtre de chemins au niveau du job**, jamais `paths:` sur `on:` : un workflow non déclenché laisse un check requis en attente pour toujours, alors qu’un job sauté par `if:` compte comme réussi. Modèle : `.github/workflows/build-docs.yml` (job `changes` avec `dorny/paths-filter`, puis `if:` sur le job suivant).
- **Un job agrégateur** quand une suite se découpe en jobs parallèles (un job par test-root) : seul l’agrégateur est requis ; ajouter une racine ne touche pas le ruleset.
- **Aucun commit de bot sur la base** : ce qu’un workflow génère (aperçus README, compteurs) est soit publié avec le site (`static/`), soit produit sur la branche de version et entre dans le squash (`finaliser-la-version`).
- Toute CI ajoutée plus tard : ajouter son check à la liste du ruleset dans la même version, et le dire dans ses notes de Release (**Hors périmètre** si le geste reste à faire).

Tant qu’un check requis est rouge, la PR ne se fusionne pas (ruleset, ou à défaut `agents/checks-requis.yml`).
