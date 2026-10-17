# 0007 — Une session ouverte par repo, activité par les hooks des agents

- Statut : accepté
- Date : 2026-10-17
- Version : 0.4.2 (#62)

## Contexte

En 0.4.0, une seule session est ouverte sur l’instance et le runner ne sait que si elle est ouverte ou fermée (ADR 0004, point 4). La 0.4.2 remplace le bouton `/implement #n` par une session libre et veut qu’on puisse lancer une session pendant qu’une autre attend une réponse (grilling, question). Chaque repo n’a qu’un clone géré : deux sessions sur le même clone se marcheraient dessus (branche, arbre, commits). L’ADR 0004 renvoyait les états « travaille » / « réponse attendue » aux hooks des agents.

## Décision

1. **Au plus une session ouverte par repo** ; plusieurs repos peuvent avoir chacun la leur. Remplace le point 4 de l’ADR 0004.
2. **Un lancement est refusé tant qu’une session d’un autre repo travaille.** La règle porte sur le lancement seulement : le terminal d’une session n’est jamais bloqué par l’activité d’une autre, et une activité *inconnue* ne bloque rien. L’enchaînement (ADR 0006) n’y est pas soumis.
3. **L’activité vient des hooks des agents, en portée utilisateur** dans le `HOME` du runner (`runner-home`) : aucun fichier suivi du clone n’est modifié et les hooks du repo métier restent actifs. Les hooks appellent `wap-runtime etat …` avec le jeton de la session, qui écrit l’activité via l’API interne du runner. Un hook en échec rend 0 : il ne bloque jamais l’agent.
4. Un agent dont la CLI épinglée n’expose pas de hooks utilisables garde l’activité *inconnue*.

## Conséquences

- On lance une session sur un repo pendant qu’une autre attend une réponse ; deux sessions qui travaillent en même temps restent possibles (réponse tapée pendant qu’une autre travaille), sur des clones distincts.
- L’activité est indicative : un hook manqué ou un agent planté peut laisser *travaille* ; **Terminer** reste toujours disponible.
- Un agent peut déclarer une fausse activité sur sa propre session ; elle n’ouvre aucun droit.
- Plusieurs sessions sur le même repo demanderaient un clone (ou un worktree) par session : hors 0.4.2.
