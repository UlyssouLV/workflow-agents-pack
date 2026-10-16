"""`wap-runtime setup` : socle → instance → `docker compose up -d --build` → `/health`
→ connexion GitHub.

`setup` tourne en root (lancé par `install.sh`) : il installe le socle, puis relance
`wap-runtime setup --instance-seule` en utilisateur d’instance `orchestrator` pour
le reste (ADR 0002) et recopie sa sortie dans le journal. Il finit par la connexion
GitHub de l’instance, seule étape qui peut interagir (ADR 0003).
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping

from wap_runtime.auth import lancer_auth, statut
from wap_runtime.instance import chemin_instance, lire_config, preparer_instance
from wap_runtime.sante import sonder
from wap_runtime.socle import (
    HOME_UTILISATEUR,
    JOURNAL,
    OS_RELEASE,
    UTILISATEUR,
    installer_socle,
    journaliser,
    mode_debug,
)

DELAI_HEALTH = 60
ETAPE_INSTANCE = "instance"
ETAPE_COMPOSE = "docker compose up -d --build"
ETAPE_HEALTH = "attente /health"
TERMINAL = Path("/dev/tty")


def setup(
    os_release: Path = OS_RELEASE,
    journal: Path = JOURNAL,
    env: Mapping[str, str] = os.environ,
    home_orchestrator: Path = HOME_UTILISATEUR,
    terminal: Path = TERMINAL,
) -> int:
    """Une passe complète, idempotente ; rend le code de sortie."""
    code = installer_socle(os_release, journal, env, home_orchestrator)
    if code != 0:
        return code
    commande = [
        "runuser", "-u", UTILISATEUR, "--",
        sys.executable, "-m", "wap_runtime", "setup", "--instance-seule",
    ]
    debug = mode_debug(env)
    with journal.open("a") as log:
        journaliser(log, f"instance : passe en utilisateur {UTILISATEUR}")
        enfant = subprocess.Popen(
            commande,
            env={**env, "HOME": str(home_orchestrator)},
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for ligne in enfant.stdout:
            log.write(ligne)
            log.flush()
            if debug or ligne.startswith(("→ ", "OK", "KO")):
                print(ligne, end="", flush=True)
        code = enfant.wait()
        journaliser(log, f"instance : {'OK' if code == 0 else f'échec (code {code})'}")
    if code != 0:
        print(f"Journal : {journal}")
        return code
    return _connecter_github(chemin_instance(home_orchestrator), env, terminal)


def _connecter_github(instance: Path, env: Mapping[str, str], terminal: Path) -> int:
    """`GH_TOKEN` fourni → sans interaction ; terminal et pas `WAP_SKIP_AUTH=1` →
    device flow ; sinon la prochaine étape, sans échec."""
    connectee, compte = statut(instance, UTILISATEUR, env)
    if connectee:
        print(f"OK — instance déjà connectée à GitHub en tant que {compte}", flush=True)
        return 0
    if env.get("GH_TOKEN"):
        return lancer_auth(instance, env["GH_TOKEN"].strip(), UTILISATEUR, env)
    tty = None
    if env.get("WAP_SKIP_AUTH") != "1":
        try:
            # `curl … | sudo bash` : stdin est le script, le terminal reste joignable ici.
            tty = terminal.open()
        except OSError:
            pass
    if tty is not None:
        with tty:
            return lancer_auth(instance, None, UTILISATEUR, env, entree=tty)
    print("Instance non connectée à GitHub — prochaine étape : `sudo wap-runtime auth`", flush=True)
    return 0


def demarrer_instance(
    home: Path, env: Mapping[str, str] = os.environ, delai: float = DELAI_HEALTH
) -> int:
    """Partie utilisateur d’instance : instance, Compose, attente de `/health`."""
    print(f"→ {ETAPE_INSTANCE}", flush=True)
    try:
        instance = preparer_instance(home, env)
        port = lire_config(instance)["port"]
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as erreur:
        return _echec(ETAPE_INSTANCE, erreur)

    print(f"→ {ETAPE_COMPOSE}", flush=True)
    compose = instance / "compose.yaml"
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "up", "-d", "--build"],
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as erreur:
        return _echec(ETAPE_COMPOSE, erreur)

    print(f"→ {ETAPE_HEALTH}", flush=True)
    echeance = time.monotonic() + delai
    while True:
        ok, message = sonder(port, timeout=2)
        if ok:
            print(f"OK — {message}", flush=True)
            return 0
        if time.monotonic() >= echeance:
            return _echec(ETAPE_HEALTH, f"pas de réponse OK en {delai:g} s : {message}")
        time.sleep(0.5)


def _echec(etape: str, erreur) -> int:
    print(f"KO — l’étape « {etape} » a échoué ({erreur})", flush=True)
    return 1
