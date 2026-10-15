# Feuille de route de dev

Runtime self-hosted (monorepo) : pack syncé vers les repos métier ; orchestrateur installé sur la machine de l’utilisateur. Produit public et générique — aucune instance perso dans ce dépôt.

## Déjà livré

*(aucune version encore)*

## Prochaine : 0.1.0 — Frontière pack / runtime

Objectif. Le monorepo sépare clairement le pack (`agents/`) du runtime (`orchestrator/`). Les commandes d’init et de mise à jour ne déploient que la partie pack ; le runtime est exclu de la sync. La doc expose les deux surfaces : adopter le pack sur un projet vs installer le cockpit sur sa machine.

Hors périmètre : installer le runtime, UI, runners, credentials d’instance.

## Ensuite : 0.2.0 — Provisionning self-hosted (Linux + CLIs)

Objectif. Une commande dédiée prépare une machine hôte (Linux chez l’utilisateur, pas un VPS imposé) : vérifie ou guide l’install du socle (Docker Compose, `git`, `gh`, CLI agents Cursor `agent` et/ou Claude `claude`), crée la config d’instance hors git (`~/.wap-runtime/` : secrets, emplacements), démarre les services runtime via Compose, et expose un healthcheck local. Tout le runtime repose sur du CLI / headless — pas d’IDE graphique sur la box.

Hors périmètre : dashboard multi-repo, lancer des actions métier (`/implement`, etc.), mapping skills → prompts headless, tunnel Internet, autopilot.

## Ensuite : 0.3.0 — Registry + cockpit lecture seule

Objectif. L’utilisateur configure des repos liés de façon générique et suit leur état (labels / cycle du pack) depuis un cockpit local en lecture seule.

Hors périmètre : déclencher `/implement` ou toute autre action agent depuis l’UI.

## Ensuite : 0.4.0 — Runner distant borné

Objectif. Depuis le cockpit, lancer une action agent sur un clone local géré par la machine hôte, avec logs visibles.

Hors périmètre : enchaînement autopilot, parallélisme multi-jobs avancé.

## Ensuite : 0.5.0 — FSM et blocages humains

Objectif. Une machine d’états (`running` / `needs-human` / `failed` / `done`) dérivée du tracker rend visibles les blocages (tests humains, erreur, coupure) et le progrès (enfants X/Y, étape).

Hors périmètre : enchaînement automatique des tickets sans validation humaine aux points de blocage.

## Ensuite : 0.6.0 — Autopilot borné

Objectif. Enchaîner les enfants `ready-for-agent` tant que rien ne bloque ; s’arrêter net sur besoin humain ou erreur.

Hors périmètre : SaaS multi-tenant, marketplace, orchestration hors machine utilisateur.

## Plus tard (pas encore numéroté)

### Accès distant optionnel à la machine hôte

Tunnel (Tailscale, Cloudflare Tunnel, etc.) pour joindre le cockpit hors LAN — sans imposer de VPS.

### Workers parallèles multi-repos

Plusieurs jobs agents en parallèle sur la même machine hôte, avec isolation et quotas.
