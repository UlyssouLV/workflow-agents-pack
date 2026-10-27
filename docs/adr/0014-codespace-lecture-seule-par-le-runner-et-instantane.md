# 0014 — Codespace exposé en lecture seule par le runner, instantané Git de fin de session

- Statut : accepté
- Date : 2026-10-26
- Version : 0.8.0 (#115)

## Contexte

Depuis la 0.4.0, une session ne se montre dans le cockpit que par son terminal (ADR 0004). On veut voir, depuis le navigateur, avec quel dépôt et quel arbre de fichiers l’agent travaille, dans une vue proche de VS Code, et pouvoir revoir cet arbre une fois la session fermée, alors que le clone géré passe à la session suivante (une ouverte par repo, ADR 0007). Le service `runtime` monte toute l’instance, clones compris ; le `runner` ne monte que `clones/`, `jobs/` et `runner-home/` et porte déjà tout ce qui touche aux sessions. Alternatives : un vrai VS Code serveur (openvscode-server, code-server) en service Compose ; le workbench VS Code en bibliothèque (monaco-vscode-api) ; lecture directe des clones par le `runtime` ; polling au lieu d’une surveillance du disque ; copie complète du dossier à la fermeture.

## Décision

1. **Vue en lecture seule dans le cockpit** : arborescence React et éditeur Monaco (édition désactivée), éditeur de diff Monaco pour un fichier modifié par rapport à HEAD. Pas de VS Code serveur : ni édition concurrente de l’agent, ni nouveau service exposé, ni seconde authentification.
2. **Le runner est le seul lecteur des clones** : il expose, par session, l’identité (repo, branche, HEAD), les entrées d’un dossier avec leur statut Git, le contenu d’un fichier (binaire ou > 1 Mo : non affiché), le diff d’un fichier et un websocket d’événements. Le `runtime` relaie derrière l’authentification du cockpit, comme pour le terminal. Tout chemin est résolu et doit rester sous le clone ; un symlink sortant n’est pas suivi.
3. **Tout le codespace est visible**, fichiers ignorés et `.git/` compris, chargés dossier par dossier.
4. **Surveillance poussée** : le runner surveille (inotify) les seuls dossiers dépliés et le fichier ouvert, plus la ref courante, et pousse des événements regroupés ; polling lent en secours.
5. **Instantané de fin de session** : à la transition vers terminée, arrêtée, échouée, interrompue ou enchaînée, le runner écrit l’arbre de travail (suivi et non suivi, hors ignorés) dans un commit dont le parent est HEAD, via un index temporaire, sous la ref privée `refs/wap/sessions/<id>` du clone ; il écrit `jobs/<id>/instantane.json` (SHA, HEAD, branche, date, entrées ignorées regroupées par dossier, fichiers et dossiers non suivis, ou erreur). Arbre, index, branche et distant ne changent pas ; la ref n’est jamais poussée. Un échec n’empêche pas la fermeture. Pas de purge.

## Conséquences

- Complète l’ADR 0004 : le runner reste le seul à toucher aux clones ; le cockpit ne lit jamais le disque de l’instance.
- Une session fermée se relit depuis son instantané, y compris le travail non commité ensuite « jeté » par la session suivante.
- Le contenu des fichiers ignorés (`node_modules/`, `.venv/`, `.env`) n’est pas conservé, seulement leurs noms.
- Les instantanés vivent dans le clone géré : supprimer ou recloner le clone les perd. Leur coût disque est celui des seuls contenus non commités.
- Les sessions antérieures à la 0.8.0 n’ont pas d’instantané.
- Le passage plus tard à un workbench VS Code complet ne changerait que le cockpit, pas l’API du runner.
