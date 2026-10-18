# 0011 — Exposition web opt-in via Caddy borné au cockpit

- Statut : accepté
- Date : 2026-10-18
- Version : 0.6.0 (#89)

## Contexte

L’objectif 0.6.0 est de joindre le cockpit depuis Internet sans exposer les services runtime en clair ni ouvrir le reste du réseau privé. Alternatives : laisser l’opérateur apporter seul nginx/Caddy ; livrer un tunnel type Cloudflare/Tailscale ; ou livrer un reverse proxy dans Compose. L’opérateur ne configure pas Caddy sur sa box : la box ne fait au mieux que le NAT.

## Décision

1. **Caddy dans Compose**, livré avec le produit : reverse proxy qui, quand l’**exposition web** est activée, publie **uniquement** 80/443 et relaie **seulement** vers le cockpit de cette instance.
2. **Opt-in / désactivable** : sans exposition, usage local ou tunnel SSH (toujours documenté) ; `runtime` et `runner` ne sont pas publiés sur Internet.
3. **TLS** : Let’s Encrypt via Caddy lorsqu’un nom de domaine pointe vers la machine ; pas de mode officiel « HTTP public ». DNS et NAT restent côté opérateur ; documenter les limites (ex. CGNAT sur box 4G).
4. **Tests** : vérifier que la surface proxifiée ne permet pas d’échapper vers d’autres hôtes ou services du LAN.

## Conséquences

- Le produit maîtrise la config proxy (bornage) plutôt que de dépendre d’un proxy externe mal réglé.
- Sans domaine, 0.6.0 reste utilisable (auth + expo off + SSH) ; le HTTPS public s’active quand le DNS/NAT le permettent.
- Pas de config automatique de la box ; une CLI de diagnostic sépare ce que l’instance a fait du reste à faire côté réseau.
