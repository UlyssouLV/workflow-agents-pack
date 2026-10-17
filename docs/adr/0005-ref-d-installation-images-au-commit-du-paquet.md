# 0005 — Ref d’installation choisi, images au commit du paquet

- Statut : accepté
- Date : 2026-10-17
- Version : 0.4.1 (#45)

## Contexte

L’ADR 0002 installe le paquet `wap-runtime` et construit les images de l’instance depuis la tête de la branche de base (`feat/runtime-orchestrator`), écrite en dur dans `install.sh` et `instance.py`. Une branche de version ne peut donc pas être testée sur un serveur avant sa fusion : les tests humains de la 0.4.0 (#34) ont dû modifier le paquet installé à la main (#42). Le paquet et les images, lus à des moments différents, peuvent aussi se désaligner.

## Décision

1. `install.sh` installe le paquet depuis `WAP_REF` (branche, tag ou commit), par défaut la branche de base du canal d’intégration.
2. `setup` construit les images (`runtime`, `runner`) depuis **le commit du paquet installé**, lu dans ses métadonnées d’installation (`direct_url.json`, PEP 610 : `commit_id`, à défaut `requested_revision`). Sans origine VCS (installation locale ou éditable), il prend la branche de base.
3. L’URL et le comportement par défaut de l’ADR 0002 restent : sans `WAP_REF`, on installe la dernière version livrée.

## Conséquences

- Paquet et images ne peuvent plus se désaligner : relancer `setup` reconstruit au commit du paquet.
- Tester une branche de version = `curl …/<ref>/orchestrator/install.sh | sudo WAP_REF=<ref> bash`.
- Revenir à la version livrée = relancer `install.sh` sans `WAP_REF`.
- `WAP_PACK_REF` (pack cloné dans l’instance) reste indépendant.
