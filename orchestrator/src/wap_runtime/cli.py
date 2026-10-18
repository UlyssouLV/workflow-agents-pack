"""Point d’entrée console `wap-runtime`."""

import argparse
import json
import os
import select
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from wap_runtime.agents import AGENTS, CURSOR, connecte, lancer_auth_agent
from wap_runtime.auth import lancer_auth, lire_secrets, statut
from wap_runtime.identifiants_cockpit import definir as definir_identifiants_cockpit
from wap_runtime.instance import (
    chemin_instance,
    definir_exposition,
    desinstaller,
    lire_config,
    regenerer_compose,
)
from wap_runtime.provisionnement import demarrer_instance, setup
from wap_runtime.registry import (
    RegistryErreur,
    ajouter,
    chemin_registry,
    lire_registry,
    retirer,
)
from wap_runtime.runner import PORT_RUNNER
from wap_runtime.sante import sonder
from wap_runtime.socle import (
    HOME_UTILISATEUR,
    LIEN_COMMANDE,
    UTILISATEUR,
    cible_commande,
    retirer_lien_commande,
)

PORT_PAR_DEFAUT = 8787


def _home_instance() -> Path:
    """En root (`sudo wap-runtime …`), l’instance est celle de l’utilisateur d’instance."""
    return HOME_UTILISATEUR if os.geteuid() == 0 else Path.home()


def _instance_existante() -> Path | None:
    """L’instance visée, ou `None` (avec la ligne KO) si `setup` n’est pas passé."""
    instance = chemin_instance(_home_instance())
    if not instance.is_dir():
        print(f"KO — aucune instance dans {instance} : lance d’abord `sudo wap-runtime setup`")
        return None
    return instance


def _port_configure() -> int:
    try:
        config = lire_config(chemin_instance(_home_instance()))
        # Expo on : le runtime n’a plus de port hôte ; `/health` passe par Caddy :80.
        if config.get("exposition"):
            return 80
        return int(config["port"])
    except (OSError, ValueError, KeyError):
        return PORT_PAR_DEFAUT


def _exposition(action: str) -> int:
    """Active ou désactive l’exposition web (Caddy) et réapplique Compose."""
    instance = _instance_existante()
    if instance is None:
        return 1
    actif = action == "on"
    try:
        definir_exposition(instance, actif)
        regenerer_compose(instance)
    except (OSError, ValueError, KeyError) as erreur:
        print(f"KO — impossible de {'activer' if actif else 'désactiver'} l’exposition ({erreur})")
        return 1
    compose = instance / "compose.yaml"
    try:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose),
                "up",
                "-d",
                "--remove-orphans",
            ],
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as erreur:
        print(f"KO — `docker compose up` a échoué ({erreur})")
        return 1
    print(f"OK — exposition web {'activée' if actif else 'désactivée'}")
    return 0


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


def _runner(hote: str, port: int) -> int:
    try:
        import uvicorn  # noqa: F401

        from wap_runtime.runner import servir_runner
    except ImportError as erreur:
        print(f"KO — service runner indisponible ({erreur}) : `pip install 'wap-runtime[serve]'`")
        return 1
    print(f"wap-runtime runner écoute sur {hote}:{port}", flush=True)
    servir_runner(hote, port)
    return 0


def _lire_stdin() -> str:
    """JSON déjà pipé par un hook ; ne bloque pas si stdin est un TTY ou vide."""
    try:
        if sys.stdin.isatty():
            return ""
        pret, _, _ = select.select([sys.stdin], [], [], 0)
        if not pret:
            return ""
        return sys.stdin.read()
    except (AttributeError, OSError, ValueError, TypeError):
        try:
            return sys.stdin.read()
        except (OSError, ValueError):
            return ""


def _depuis_hook(texte: str) -> tuple[str | None, str | None]:
    """JSON des hooks : `prompt` (titre) et nom du skill si l’outil `Skill` a tourné."""
    try:
        data = json.loads(texte)
    except ValueError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    prompt = data.get("prompt")
    prompt = prompt.strip() if isinstance(prompt, str) and prompt.strip() else None
    skill = None
    if str(data.get("tool_name") or "") == "Skill":
        entree = data.get("tool_input")
        if isinstance(entree, dict):
            for cle in ("skill", "name"):
                valeur = entree.get(cle)
                if isinstance(valeur, str) and valeur.strip():
                    skill = valeur.strip()
                    break
    return prompt, skill


def _etat(activite: str, skill: str | None) -> int:
    """Dans une session du runner : met à jour l’activité. Rend 0 même en cas de refus (hooks).

    `activite` `skill` : ne retient que le nom du skill (outil `Skill`), sans changer l’activité.
    """
    id_, jeton = os.environ.get("WAP_SESSION"), os.environ.get("WAP_SESSION_JETON")
    prompt, skill_hook = _depuis_hook(_lire_stdin())
    skill = skill or skill_hook
    if not (id_ and jeton):
        return 0
    base = os.environ.get("WAP_RUNNER", f"http://127.0.0.1:{PORT_RUNNER}").rstrip("/")
    # `skill` seul : pas d’`activite` dans le corps → le runner ne change pas travaille/attend.
    activite_corps = None if activite == "skill" else activite
    corps = {"jeton": jeton, "activite": activite_corps, "skill": skill, "prompt": prompt}
    requete = urllib.request.Request(
        f"{base}/sessions/{urllib.parse.quote(id_, safe='')}/etat",
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            reponse.read()
    except (urllib.error.HTTPError, OSError, ValueError):
        pass
    return 0


def _enchainer(ticket: int) -> int:
    """Dans une session du runner (ADR 0006) : demande `/implement #ticket` à sa suite."""
    id_, jeton = os.environ.get("WAP_SESSION"), os.environ.get("WAP_SESSION_JETON")
    if not (id_ and jeton):
        print("KO — hors d’une session du runner (WAP_SESSION ou WAP_SESSION_JETON absent)")
        return 1
    # Le runner et l’agent partagent le conteneur.
    base = os.environ.get("WAP_RUNNER", f"http://127.0.0.1:{PORT_RUNNER}").rstrip("/")
    requete = urllib.request.Request(
        f"{base}/sessions/{urllib.parse.quote(id_, safe='')}/suivante",
        data=json.dumps({"ticket": ticket, "jeton": jeton}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=120) as reponse:
            print(f"OK — {json.loads(reponse.read())['detail']}")
            return 0
    except urllib.error.HTTPError as refus:
        try:
            detail = json.loads(refus.read())["detail"]
        except (ValueError, KeyError, TypeError):
            detail = f"le runner a répondu {refus.code}"
        print(f"KO — {detail}")
    except (OSError, ValueError, KeyError) as erreur:
        print(f"KO — runner injoignable ({erreur})")
    return 1


def _uninstall(purge: bool) -> int:
    home = _home_instance()
    try:
        instance = desinstaller(home, purge)
    except (OSError, subprocess.CalledProcessError) as erreur:
        print(f"KO — `docker compose down` a échoué ({erreur}) ; instance conservée")
        return 1
    try:
        if retirer_lien_commande(LIEN_COMMANDE, cible_commande(home)):
            print(f"Lien {LIEN_COMMANDE} retiré.")
    except OSError as erreur:
        print(f"KO — lien {LIEN_COMMANDE} non retiré ({erreur})")
        return 1
    if instance is None:
        print("Aucune instance à désinstaller.")
    elif purge:
        print(f"Runtime arrêté, instance {instance} supprimée.")
    else:
        print(f"Runtime arrêté ; instance {instance} conservée (--purge pour la supprimer).")
    return 0


def _repo(action: str, slug: str | None, nom: str | None) -> int:
    instance = _instance_existante()
    if instance is None:
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


def _cockpit_auth(login: str, avec_password: bool) -> int:
    """Crée ou change les identifiants cockpit (distinct de `wap-runtime auth`)."""
    instance = _instance_existante()
    if instance is None:
        return 1
    login = (login or "").strip()
    if not login:
        print("KO — login requis : `wap-runtime cockpit-auth --login <login>`")
        return 1
    if avec_password:
        mot_de_passe = sys.stdin.read()
        if mot_de_passe.endswith("\n"):
            mot_de_passe = mot_de_passe[:-1]
        if mot_de_passe.endswith("\r"):
            mot_de_passe = mot_de_passe[:-1]
    else:
        import getpass

        mot_de_passe = getpass.getpass("Mot de passe cockpit : ")
    if not mot_de_passe:
        print("KO — mot de passe vide")
        return 1
    try:
        action = definir_identifiants_cockpit(instance, login, mot_de_passe)
    except ValueError as erreur:
        print(f"KO — {erreur}")
        return 1
    except OSError as erreur:
        print(f"KO — écriture des identifiants impossible ({erreur})")
        return 1
    if action == "cree":
        print(f"OK — identifiants cockpit créés (login « {login} »)")
    else:
        print(
            f"OK — mot de passe cockpit changé (login « {login} ») ; "
            "sessions invalidées"
        )
    return 0


def _auth(cible: str | None, avec_jeton: bool) -> int:
    """`cible` : `None` (GitHub), `status`, `claude` ou `agent` (Cursor)."""
    instance = _instance_existante()
    if instance is None:
        return 1
    # En root, `gh` et `claude` tournent en utilisateur d’instance : c’est sa connexion qui compte.
    utilisateur = UTILISATEUR if os.geteuid() == 0 else None
    if cible == "status":
        return _auth_status(instance, utilisateur)
    agent = next((a for a in AGENTS if a.programme == cible), None)
    if agent is CURSOR and not avec_jeton:
        # `agent login` exige un navigateur sur la machine même.
        print(f"KO — Cursor se connecte par clé API sur stdin : `{CURSOR.commande}`")
        return 1
    jeton = None
    if avec_jeton:
        jeton = sys.stdin.read().strip()
        if not jeton:
            commande = (agent.commande if agent else "sudo wap-runtime auth").removeprefix("… | ")
            print(f"KO — aucun token sur stdin : `… | {commande.removesuffix(' --with-token')} --with-token`")
            return 1
    if agent is None:
        return lancer_auth(instance, jeton, utilisateur)
    return lancer_auth_agent(instance, agent, jeton, utilisateur)


def _auth_status(instance: Path, utilisateur: str | None) -> int:
    """Une ligne par connexion ; le code de sortie est celui de GitHub, les agents étant au choix."""
    connectee, detail = statut(instance, utilisateur)
    if connectee:
        print(f"OK — instance connectée à GitHub en tant que {detail}")
    else:
        print(f"KO — instance non connectée à GitHub ({detail}) : `sudo wap-runtime auth`")
    secrets = lire_secrets(instance / "secrets.env")
    for agent in AGENTS:
        if connecte(agent, secrets):
            print(f"OK — {agent.nom} connecté")
        else:
            print(f"KO — {agent.nom} non connecté : `{agent.commande}`")
    return 0 if connectee else 1


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
    # Service `runner` de l’instance (dans son image) : API interne des sessions.
    runner = sous.add_parser("runner", help=argparse.SUPPRESS)
    runner.add_argument("--host", default="127.0.0.1")
    runner.add_argument("--port", type=int, default=PORT_RUNNER)
    # Lancé par l’agent d’une session du runner, via `WAP_ENCHAINER`.
    enchainer = sous.add_parser("enchainer", help="dans une session du runner : ouvre /implement #n à sa suite")
    enchainer.add_argument("ticket", type=int)
    etat = sous.add_parser(
        "etat",
        help="dans une session du runner : signale travaille, attend, ou retient un skill",
    )
    etat.add_argument(
        "activite",
        choices=["travaille", "attend", "skill"],
        help="`skill` : retient le nom du skill sans changer l’activité",
    )
    etat.add_argument("--skill", help="dernier skill chargé")
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
        "auth",
        help="connecte l’instance à GitHub (device flow), à Claude Code (`claude`) "
        "ou à Cursor (`agent`), ou affiche l’état des trois (`status`)",
    )
    auth.add_argument(
        "cible", nargs="?", choices=["status", *(a.programme for a in AGENTS)],
        help="sans argument : GitHub",
    )
    auth.add_argument(
        "--with-token", action="store_true", help="lit le token (ou la clé API) sur stdin"
    )
    cockpit_auth = sous.add_parser(
        "cockpit-auth",
        help="crée ou change les identifiants d’accès web au cockpit "
        "(distinct de `auth` GitHub / agents)",
    )
    cockpit_auth.add_argument("--login", required=True, help="login unique de l’instance")
    cockpit_auth.add_argument(
        "--with-password",
        action="store_true",
        help="lit le mot de passe sur stdin",
    )
    exposition = sous.add_parser(
        "exposition",
        help="active ou désactive l’exposition web (Caddy, ports 80/443)",
    )
    exposition.add_argument(
        "action",
        choices=["on", "off"],
        help="`on` : reverse proxy public ; `off` : accès local / SSH seulement",
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
        return _auth(args.cible, args.with_token)
    if args.commande == "cockpit-auth":
        return _cockpit_auth(args.login, args.with_password)
    if args.commande == "exposition":
        return _exposition(args.action)
    if args.commande == "repo":
        return _repo(args.action, getattr(args, "slug", None), getattr(args, "nom", None))
    if args.commande == "serve":
        return _serve(args.host, args.port)
    if args.commande == "runner":
        return _runner(args.host, args.port)
    if args.commande == "enchainer":
        return _enchainer(args.ticket)
    if args.commande == "etat":
        return _etat(args.activite, args.skill)
    if args.commande == "uninstall":
        return _uninstall(args.purge)
    return _health(args.port)
