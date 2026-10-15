"""Point d’entrée console `wap-runtime`."""

import argparse
import os
import subprocess
from pathlib import Path

from wap_runtime.instance import desinstaller
from wap_runtime.provisionnement import demarrer_instance, setup
from wap_runtime.sante import sonder
from wap_runtime.server import creer_serveur

PORT_PAR_DEFAUT = 8787


def _health(port: int) -> int:
    ok, message = sonder(port)
    print(f"{'OK' if ok else 'KO'} — {message}")
    return 0 if ok else 1


def _serve(hote: str, port: int) -> int:
    serveur = creer_serveur(hote, port)
    print(f"wap-runtime écoute sur {hote}:{port}", flush=True)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
    return 0


def _uninstall(purge: bool) -> int:
    try:
        instance = desinstaller(Path.home(), purge)
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
    health.add_argument("--port", type=int, default=PORT_PAR_DEFAUT)
    serve = sous.add_parser("serve", help="lance le service HTTP du runtime")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=PORT_PAR_DEFAUT)
    uninstall = sous.add_parser(
        "uninstall", help="arrête et retire le Compose de l’instance"
    )
    uninstall.add_argument(
        "--purge", action="store_true", help="supprime aussi ~/.wap-runtime/"
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
    if args.commande == "serve":
        return _serve(args.host, args.port)
    if args.commande == "uninstall":
        return _uninstall(args.purge)
    return _health(args.port)
