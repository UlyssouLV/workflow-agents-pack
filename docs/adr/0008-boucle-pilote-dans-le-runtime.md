# 0008 — Boucle pilote dans le service runtime

- Statut : accepté
- Date : 2026-10-18
- Version : 0.5.0 (#73)

## Contexte

La 0.4.1 permet déjà à une session d’ouvrir la suivante via le pack (`encadrer-implement` → `wap-runtime enchainer`, ADR 0006). La 0.4.2 expose l’activité des sessions (ADR 0007). Il manque le démarrage du premier ticket et la reprise après un stop, sans humain devant le cockpit. On pourrait croire que l’« autopilot » doit aussi décider quel ticket vient ensuite, ou vivre dans le navigateur / un 3ᵉ service.

## Décision

1. Le **Pilote** est une boucle de surveillance dans le service `runtime` : opt-in par repo lié (`repos.toml`), agent préféré, lancement du premier `/implement #n` éligible (session libre + premier message), stops et notifications, reprise automatique tant que le toggle est ON.
2. L’**enchaînement** reste exclusivement le pack + ADR 0006. Le runtime ne choisit pas le prochain ticket et n’appelle pas `enchainer` : s’il y a déjà une session ouverte sur le repo, il observe seulement.
3. Pas de conteneur / process `pilot` séparé ; pas de boucle qui dépend d’un onglet cockpit ouvert (les notifications navigateur sont un canal d’alerte, pas le moteur).

## Conséquences

- « Sans humain » tient au reboot du service et cockpit fermé, tant que l’instance tourne.
- Un futur lecteur qui cherche une file de tickets côté orchestrateur ne la trouvera pas : c’est volontaire.
- Les règles « une session par repo » et « une session qui travaille » (ADR 0007) s’appliquent aussi aux lancements du pilote.
