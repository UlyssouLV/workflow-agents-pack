"""Point d’entrée console `wap-runtime`."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from wap_runtime.auth import lancer_auth, statut

from wap_runtime.instance import chemin_instance, desinstaller, lire_config
from wap_runtime.provisionnement import demarrer_instance, setup
from wap_runtime.registry import (
    RegistryErreur,
    ajouter,
    chemin_registry,
    lire_registry,
    retirer,
)
from wap_runtime.sante import sonder
from wap_runtime.socle import HOME_UTILISATEUR, UTILISATEUR

PORT_PAR_DEFAUT = 8787


def _home_instance() -> Path:
    """En root (`sudo wap-runtime …`), l’instance est celle de l’utilisateur d’instance."""
    return HOME_UTILISATEUR if os.geteuid() == 0 else Path.home()


def _port_configure() -> int:
    try:
        return int(lire_config(chemin_instance(_home_instance()))["port"])
    except (OSError, ValueError, KeyError):
        return PORT_PAR_DEFAUT


def _health(port: int | None) -> int:
    if port is None:
        port = _port_configure()
    ok, message = sonder(port)
    print(f"{'OK' if ok else 'KO'} — {message}")
    return 0 if ok else 1


def _serve(hote: str, port: int) -> int:
    try:
        # Dépendances de l’image seulement (extra `serve`) : la CLI de l’hôte s’en passe.
        from wap_runtime.server import servir
    except ImportError as erreur:
        print(f"KO — service HTTP indisponible ({erreur}) : `pip install 'wap-runtime[serve]'`")
        return 1
    print(f"wap-runtime écoute sur {hote}:{port}", flush=True)
    servir(hote, port)
    return 0


def _uninstall(purge: bool) -> int:
    try:
        instance = desinstaller(_home_instance(), purge)
    except (OSError, subprocess.CalledProcessError) as erreur:
        print(f"KO — `docker compose down` a échoué ({erreur}) ; instance conservée")
        return 1
    if instance is None:
        print("Aucune instance à désinstaller.")
    elif purge:
        print(f"Runtime arrêté, instance {instance} supprimée.")
    else:
        print(f"Runtime arrêté ; instance {instance} conservée (--purge pour la supprimer).")
    return 0


def _repo(action: str, slug: str | None, nom: str | None) -> int:
    instance = chemin_instance(_home_instance())
    if not instance.is_dir():
        print(f"KO — aucune instance dans {instance} : lance d’abord `sudo wap-runtime setup`")
        return 1
    registry = chemin_registry(instance)
    try:
        if action == "add":
            ajouter(registry, slug, nom)
            print(f"OK — {slug} ajouté au registry")
        elif action == "remove":
            retire = retirer(registry, slug)
            print(f"OK — {retire.slug} retiré du registry")
        else:
            repos = lire_registry(registry)
            if not repos:
                print("Aucun repo lié : `sudo wap-runtime repo add owner/name`.")
            for repo in repos:
                print(repo.slug + (f" — {repo.nom}" if repo.nom else ""))
    except RegistryErreur as erreur:
        print(f"KO — {erreur}")
        return 1
    except OSError as erreur:
        print(f"KO — écriture de {registry} impossible ({erreur})")
        return 1
    return 0


def _auth(status: bool, avec_jeton: bool) -> int:
    instance = chemin_instance(_home_instance())
    if not instance.is_dir():
        print(f"KO — aucune instance dans {instance} : lance d’abord `sudo wap-runtime setup`")
        return 1
    # En root, `gh` tourne en utilisateur d’instance : c’est sa connexion qui compte.
    utilisateur = UTILISATEUR if os.geteuid() == 0 else None
    if status:
        connectee, detail = statut(instance, utilisateur)
        if connectee:
            print(f"OK — instance connectée à GitHub en tant que {detail}")
            return 0
        print(f"KO — instance non connectée à GitHub ({detail}) : `sudo wap-runtime auth`")
        return 1
    jeton = None
    if avec_jeton:
        jeton = sys.stdin.read().strip()
        if not jeton:
            print("KO — aucun token sur stdin : `… | sudo wap-runtime auth --with-token`")
            return 1
    return lancer_auth(instance, jeton, utilisateur)


def _setup(instance_seule: bool) -> int:
    if instance_seule:
        return demarrer_instance(Path.home())
    if os.geteuid() != 0:
        print(
            "KO — `wap-runtime setup` doit tourner en root : "
            "`sudo wap-runtime setup`, ou `curl -fsSL …/install.sh | sudo bash`"
        )
        return 1
    return setup()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="wap-runtime")
    sous = parser.add_subparsers(dest="commande", required=True)
    health = sous.add_parser("health", help="interroge GET /health du runtime")
    health.add_argument(
        "--port", type=int, help="défaut : port de config.toml, sinon 8787"
    )
    serve = sous.add_parser("serve", help="lance le service HTTP du runtime")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=PORT_PAR_DEFAUT)
    uninstall = sous.add_parser(
        "uninstall", help="arrête et retire le Compose de l’instance"
    )
    uninstall.add_argument(
        "--purge", action="store_true", help="supprime aussi ~/.wap-runtime/"
    )
    repo = sous.add_parser("repo", help="gère le registry des repos liés")
    actions = repo.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="lie un repo GitHub owner/name")
    add.add_argument("slug", metavar="owner/name")
    add.add_argument("--nom", help="nom d’affichage dans le cockpit")
    remove = actions.add_parser("remove", help="retire un repo lié")
    remove.add_argument("slug", metavar="owner/name")
    actions.add_parser("list", help="liste les repos liés")
    auth = sous.add_parser(
        "auth", help="connecte l’instance à GitHub (device flow), ou affiche son état"
    )
    auth.add_argument("status", nargs="?", choices=["status"], help="affiche l’état")
    auth.add_argument(
        "--with-token", action="store_true", help="lit le token GitHub sur stdin"
    )
    setup_ = sous.add_parser(
        "setup",
        help="provisionne la machine : socle, instance, Compose, attente de /health",
    )
    # Relance interne de `setup` en utilisateur d’instance, après le socle.
    setup_.add_argument("--instance-seule", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.commande == "setup":
        return _setup(args.instance_seule)
    if args.commande == "auth":
        return _auth(args.status == "status", args.with_token)
    if args.commande == "repo":
        return _repo(args.action, getattr(args, "slug", None), getattr(args, "nom", None))
    if args.commande == "serve":
        return _serve(args.host, args.port)
    if args.commande == "uninstall":
        return _uninstall(args.purge)
    return _health(args.port)
