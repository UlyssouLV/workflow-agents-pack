# 0006 — Une session peut ouvrir la suivante

- Statut : accepté
- Date : 2026-10-17
- Version : 0.4.1 (#45)

## Contexte

En local, `encadrer-implement` enchaîne le ticket suivant en ouvrant une conversation Claude Code vierge (`enchainer-implement.sh`, Terminal.app sur macOS). Dans le runner (ADR 0004), ce script échoue : le workflow s’arrête au premier ticket et l’humain doit relancer `/implement #m` depuis le cockpit. Jusqu’ici, seul le cockpit pouvait ouvrir une session ; l’agent n’avait aucun accès au runner.

## Décision

1. Le runner lance chaque agent avec `WAP_ENCHAINER=wap-runtime enchainer` et un jeton propre à la session (`WAP_SESSION_JETON`). Le pack (sur `main`) exécute `$WAP_ENCHAINER <n>` quand la variable existe ; il ne connaît pas l’orchestrateur.
2. `wap-runtime enchainer <n>` demande au runner, par son API interne, d’ouvrir la session suivante. Le runner n’accepte que : le jeton de la session **ouverte**, **une seule fois** ; `/implement #n` sur un enfant **éligible du même repo** (règles du bouton du cockpit) ; un clone propre.
3. Accepté : la session courante se ferme à l’état `enchaînée`, la suivante démarre avec le même agent, sur la même branche, dans un **nouveau processus** sans reprise de conversation (contexte vierge). Le runner choisit tout sauf le numéro du ticket.

## Conséquences

- Une chaîne de tickets tourne sans intervention, jusqu’aux tests humains (la fin d’`encadrer-implement` demande un humain).
- Un agent ne peut ni lancer une autre commande, ni viser un autre repo, ni changer d’agent par ce chemin ; il ne peut pas ouvrir deux sessions.
- Sans pack à jour (ou hors runner), l’enchaînement retombe sur le fallback du skill.
- L’autopilot (0.5.0) reste distinct : ici, c’est le skill dans la session qui décide d’enchaîner.
