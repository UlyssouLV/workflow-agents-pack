# Checks requis sur la base

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

Tant qu’un check requis est rouge, la PR ne se fusionne pas.
