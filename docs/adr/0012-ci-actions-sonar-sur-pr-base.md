# 0012 — CI via GitHub Actions sur les PR vers la base, avec Sonar dans le même pipeline

- Statut : accepté
- Date : 2026-10-19
- Version : 0.7.0 (#99)

## Contexte

Sur le canal orchestrateur, l’acceptation d’une version passe par une PR vers `feat/runtime-orchestrator`. Les suites existent en local (`/t`) et `/qg` sait lire un quality gate Sonar, mais sans workflow Actions rien ne vérifie automatiquement le HEAD de la PR, et rien n’alimente Sonar pour ce commit. Alternatives : garder uniquement les contrôles locaux ; faire tourner Sonar hors CI ; héberger la CI ailleurs que GitHub Actions ; séparer tests et Sonar en pipelines sans lien avec le merge.

## Décision

1. **GitHub Actions** est la CI du canal : déclenchée sur les **PR vers la base d’intégration** `feat/runtime-orchestrator` (sans filtre de chemins ; pas la CI pack sur `main` dans cette version).
2. **Contenu** : suites pytest et Vitest **avec couverture**, puis **scan Sonar** du code sous `orchestrator/` sur le même projet que `/qg` ; le job Sonar **échoue** si le quality gate n’est pas `OK`.
3. **Acceptation** : une CI rouge se corrige jusqu’au vert ; une **ruleset / protection de branche** (posée ou vérifiée à la main, documentée) exige les checks CI pour merger dans la base.

## Conséquences

- « Branche saine » a une vérité observable sur la PR (checks GitHub), alignée avec « CI en échec » côté cockpit.
- `/qg` et Finalise s’appuient sur une analyse produite pour le HEAD, plus seulement sur un scan manuel éventuel.
- Le pack sur `main` et le CD (publish / deploy) restent hors de cette décision (0.7.1 et chantiers pack).
