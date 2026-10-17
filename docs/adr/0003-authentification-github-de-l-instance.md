# 0003 — Authentification GitHub de l’instance, interactive seulement quand un terminal existe

- Statut : accepté ; point 1 remplacé par l’ADR 0004 (le runner utilise le `gh` de son image avec `GH_TOKEN`)
- Date : 2026-10-17
- Version : 0.3.0 (#17)

## Contexte

La 0.3.0 lit l’état des repos liés sur l’API GitHub, souvent privés : l’orchestrateur a besoin d’une identité GitHub. La 0.2.0 installe `gh` sans authentification et l’installation n’interagit jamais (ADR 0002). Le runner (0.4.0) appellera `gh` sur l’hôte, sous l’utilisateur d’instance, via les CLIs agents et les skills du pack. Une connexion peut expirer ou être révoquée : il faut pouvoir la refaire sans réinstaller.

## Décision

1. **Une identité GitHub par instance** : celle du `gh` de l’utilisateur d’instance sur l’hôte. Son token est copié dans `secrets.env` (`0600`) sous `GH_TOKEN`, lu par le service `runtime` ; le conteneur n’embarque pas `gh`.
2. **`wap-runtime auth`** connecte l’instance : `gh auth login` (device flow) en tant qu’utilisateur d’instance, copie du token, redémarrage du service. `--with-token` lit un token sur stdin ; `auth status` affiche l’état. La commande est idempotente et sert aussi à se reconnecter.
3. **Le setup enchaîne sur l’auth** s’il n’est pas connecté : `GH_TOKEN` dans l’environnement → utilisé sans interaction ; sinon terminal disponible (`/dev/tty`) et pas `WAP_SKIP_AUTH=1` → `wap-runtime auth` ; sinon il affiche la prochaine étape et termine. C’est la **seule** interaction possible de l’installation : le point 2 de l’ADR 0002 est assoupli pour elle seule.

## Conséquences

- `curl … | sudo bash` lancé à la main peut attendre la validation du code dans le navigateur ; une installation automatisée ne bloque jamais.
- Le cockpit et le runner partagent une seule connexion : une révocation les coupe tous les deux, une seule commande les répare.
- Changer de compte = relancer `wap-runtime auth`.
- Avec plusieurs instances sur un même hôte (0.7.0), chacune aura son utilisateur, donc son `gh` et son token.
