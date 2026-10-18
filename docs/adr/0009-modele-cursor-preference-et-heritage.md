# 0009 — Modèle Cursor : préférence repo et héritage de chaîne

- Statut : accepté
- Date : 2026-10-18
- Version : 0.5.1 (#82)

## Contexte

La CLI Cursor accepte `--model`. Le cockpit lance déjà Cursor pour une session libre, un enchaînement pack (`precedente` / `suivante`) et le Pilote. Si chaque lancement **écrivait** le modèle choisi dans le défaut du repo, une session libre écraserait le réglage utilisé par le Pilote et l’enchaînement. Si l’on ne gardait qu’un défaut repo sans mémoire de session, une chaîne Implement pourrait changer de modèle d’un ticket à l’autre.

## Décision

1. **Préférence repo** (`repos.toml`) : défaut éditable sur le détail (Cursor seulement). Elle préremplit **Nouvelle session**, sert de fallback hors chaîne, et est utilisée par le Pilote quand il n’y a pas de `precedente`. Elle n’est **jamais** écrite automatiquement au lancement d’une session.
2. **Héritage** : une session ouverte via `precedente` (pack `enchainer` ou suite de chaîne) reprend le modèle enregistré sur la session précédente (`session.json`). Une Nouvelle session libre repart de la préférence repo (override ponctuel possible pour *cette* session seulement).
3. **Auto / vide** : pas de `--model` passé à la CLI ; affichage cockpit **« Auto »**. Liste des modèles = sortie de la CLI Cursor ; pas de catalogue produit. Lancement refusé si Cursor connecté mais liste indisponible, ou si l’ID mémorisé n’y figure plus.

## Conséquences

- Continuité d’implémentation sans confliter avec les sessions libres.
- Un lecteur qui cherche « le modèle du repo » le trouve dans `repos.toml` ; le modèle *de cette session* est dans `session.json`.
- Claude Code reste hors sujet (pas de sélecteur).
