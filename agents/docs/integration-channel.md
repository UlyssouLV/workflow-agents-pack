# Canal d’intégration

Fichier optionnel : **`agents/integration-channel.yml`**.

## Rôle

Sur `main`, le cycle de version ouvre une branche depuis `main`, PR vers `main`, release `vX.Y.Z`, squash dans `main`.

Pour un chantier long (ex. runtime orchestrateur) qui ne doit **pas** merger chaque version dans `main`, ce fichier déclare un **canal** :

| Clé | Exemple | Effet |
| --- | --- | --- |
| `base_branch` | `feat/runtime-orchestrator` | `/ob` part de `origin/<base>` ; `/opr` et `/mpr` ciblent cette base ; ne jamais supprimer cette branche |
| `release_tag_prefix` | `orchestrator-v` | Tag / Release GitHub = `{prefix}{X.Y.Z}` → `orchestrator-v0.1.0` |

Absent → base = `main`, tags = `vX.Y.Z`.

## Résolution (tous les skills git)

Au début de `/ob`, `/opr`, `/mpr`, `/crel`, `commit`, `ouvrir-la-version`, `finaliser-la-version` :

1. Si `agents/integration-channel.yml` existe dans le working tree : lire `base_branch` et `release_tag_prefix` (les deux requis). **base** = `base_branch`. **protected** = `main`, `master`, et `base`. **tag(X.Y.Z)** = `release_tag_prefix` + `X.Y.Z` (concaténation directe).
2. Sinon : **base** = `main`. **protected** = `main`, `master`. **tag(X.Y.Z)** = `v` + `X.Y.Z`.

Ne pas committer sur une branche **protected** (sauf `/init` sur `main` uniquement). Ne jamais `git push --force` vers **base** ni `main`.

Pour ouvrir une version du canal : être sur **base** (ou un descendant qui a déjà le fichier), puis « Ouvre la version X.Y.Z ».

## Suivi

La feuille de route du canal (ici le runtime) vit avec le chantier. Les releases du préfixe (`orchestrator-v*`) sont le suivi publié de l’orchestrateur ; les `v*` sur `main` restent le suivi du pack.
