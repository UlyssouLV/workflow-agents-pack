"""Socle de la machine hôte : plateforme, plan d’installation, exécution journalisée.

Le plan ne contient que ce qui manque, installé par les méthodes officielles et
sans authentification. Les étapes système tournent en root ; `claude` et
`agent` s’installent pour l’utilisateur d’instance `orchestrator` (ADR 0002).
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

OS_RELEASE = Path("/etc/os-release")
JOURNAL = Path("/var/log/wap-runtime/install.log")
UTILISATEUR = "orchestrator"
HOME_UTILISATEUR = Path("/home") / UTILISATEUR
VERSIONS_MINIMALES = {"debian": (12,), "ubuntu": (22, 4)}
PLATEFORMES = "Debian 12+ / Ubuntu 22.04+"


class PlateformeNonSupportee(Exception):
    pass


@dataclass(frozen=True)
class Plateforme:
    id: str
    version: str
    codename: str


@dataclass(frozen=True)
class Etape:
    nom: str
    commandes: tuple[str, ...]
    utilisateur: str | None = None  # None : root


def lire_plateforme(os_release: Path = OS_RELEASE) -> Plateforme:
    try:
        texte = os_release.read_text()
    except OSError as erreur:
        raise PlateformeNonSupportee(
            f"{os_release} illisible ({erreur}) ; plateformes supportées : {PLATEFORMES}"
        ) from None
    champs = {}
    for ligne in texte.splitlines():
        cle, egal, valeur = ligne.partition("=")
        if egal:
            champs[cle.strip()] = valeur.strip().strip("\"'")
    ident, version = champs.get("ID", "?"), champs.get("VERSION_ID", "")
    minimum = VERSIONS_MINIMALES.get(ident)
    try:
        supportee = minimum is not None and _version(version) >= minimum
    except ValueError:
        supportee = False
    if not supportee or not champs.get("VERSION_CODENAME"):
        raise PlateformeNonSupportee(
            f"Plateforme non supportée : {ident} {version or '(sans VERSION_ID)'} ; "
            f"plateformes supportées : {PLATEFORMES}"
        )
    return Plateforme(ident, version, champs["VERSION_CODENAME"])


def planifier(
    os_release: Path = OS_RELEASE,
    env: Mapping[str, str] = os.environ,
    home_orchestrator: Path = HOME_UTILISATEUR,
) -> list[Etape]:
    """Étapes à exécuter, dans l’ordre, pour ce qui manque seulement."""
    return _plan(lire_plateforme(os_release), _detecter(env, home_orchestrator))


def installer_socle(
    os_release: Path = OS_RELEASE,
    journal: Path = JOURNAL,
    env: Mapping[str, str] = os.environ,
    home_orchestrator: Path = HOME_UTILISATEUR,
) -> int:
    """Détecte, planifie et exécute ; rend le code de sortie."""
    try:
        plateforme = lire_plateforme(os_release)
    except PlateformeNonSupportee as erreur:
        print(f"KO — {erreur}")
        return 2
    debug = mode_debug(env)
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a") as log:
        journaliser(log, f"socle : {plateforme.id} {plateforme.version} ({plateforme.codename})")
        detection = _detecter(env, home_orchestrator)
        if debug:
            for element, present in detection.items():
                journaliser(log, f"détecté {element} : {'oui' if present else 'non'}")
        plan = _plan(plateforme, detection)
        if not plan:
            journaliser(log, "socle complet, rien à installer")
            print("OK — socle déjà installé.")
            return 0
        for etape in plan:
            print(f"→ {etape.nom}", flush=True)
            journaliser(log, f"étape « {etape.nom} » : début")
            code = _executer(etape, env, log, debug)
            if code != 0:
                journaliser(log, f"étape « {etape.nom} » : échec (code {code})")
                print(f"KO — l’étape « {etape.nom} » a échoué (code {code}) ; voir {journal}")
                return 1
            journaliser(log, f"étape « {etape.nom} » : OK")
    print(f"OK — socle installé ({len(plan)} étape(s)) ; journal : {journal}")
    return 0


def mode_debug(env: Mapping[str, str]) -> bool:
    return env.get("WAP_DEBUG") == "1"


def _version(texte: str) -> tuple[int, ...]:
    return tuple(int(partie) for partie in texte.split("."))


def _detecter(env: Mapping[str, str], home_orchestrator: Path) -> dict[str, bool]:
    path = env.get("PATH", "")
    chez_orchestrator = os.pathsep.join([path, str(home_orchestrator / ".local" / "bin")])
    groupes = _sortie(["id", "-nG", UTILISATEUR], path)
    return {
        "git": _present("git", path),
        "docker": _present("docker", path),
        "docker compose": _reussit(["docker", "compose", "version"], path),
        "docker activé": _reussit(["systemctl", "is-enabled", "docker"], path),
        "gh": _present("gh", path),
        "curl": _present("curl", path),
        "claude": _present("claude", chez_orchestrator),
        "agent": _present("agent", chez_orchestrator),
        "utilisateur": groupes is not None,
        "groupe docker": groupes is not None and "docker" in groupes.split(),
    }


def _present(binaire: str, path: str) -> bool:
    return shutil.which(binaire, path=path) is not None


def _sortie(commande: list[str], path: str) -> str | None:
    executable = shutil.which(commande[0], path=path)
    if executable is None:
        return None
    resultat = subprocess.run(
        [executable, *commande[1:]], capture_output=True, text=True, env={"PATH": path}
    )
    return resultat.stdout if resultat.returncode == 0 else None


def _reussit(commande: list[str], path: str) -> bool:
    return _sortie(commande, path) is not None


def _plan(plateforme: Plateforme, present: Mapping[str, bool]) -> list[Etape]:
    plan = []
    if not present["git"]:
        plan.append(Etape("git", ("apt-get update", "apt-get install -y git")))
    if not present["docker"]:
        plan.append(_etape_docker(plateforme, plugin_seul=False))
    else:
        if not present["docker compose"]:
            plan.append(_etape_docker(plateforme, plugin_seul=True))
        # Sans service activé, Compose ne repart pas après un redémarrage.
        if not present["docker activé"]:
            plan.append(Etape("service docker", ("systemctl enable --now docker",)))
    if not present["gh"]:
        plan.append(_etape_gh())
    if not present["utilisateur"]:
        plan.append(
            Etape(
                f"utilisateur {UTILISATEUR}",
                (f"useradd --system --create-home --shell /bin/bash {UTILISATEUR}",),
            )
        )
    if not present["groupe docker"]:
        plan.append(Etape("groupe docker", (f"usermod -aG docker {UTILISATEUR}",)))
    installeurs = [
        Etape(nom, (f"curl -fsSL {url} | bash",), UTILISATEUR)
        for nom, url in (
            ("claude", "https://claude.ai/install.sh"),
            ("agent", "https://cursor.com/install"),
        )
        if not present[nom]
    ]
    if installeurs and not present["curl"]:
        plan.append(Etape("curl", ("apt-get update", "apt-get install -y ca-certificates curl")))
    return plan + installeurs


def _depot_apt(cle_url: str, cle: str, liste: str, depot: str) -> tuple[str, ...]:
    """Dépôt apt signé, selon la procédure officielle de l’éditeur."""
    return (
        "apt-get update",
        "apt-get install -y ca-certificates curl",
        "install -m 0755 -d /etc/apt/keyrings",
        f"curl -fsSL {cle_url} -o {cle}",
        f"chmod a+r {cle}",
        f'echo "deb [arch=$(dpkg --print-architecture) signed-by={cle}] {depot}"'
        f" > /etc/apt/sources.list.d/{liste}",
        "apt-get update",
    )


def _etape_docker(plateforme: Plateforme, plugin_seul: bool) -> Etape:
    base = f"https://download.docker.com/linux/{plateforme.id}"
    depot = _depot_apt(
        f"{base}/gpg",
        "/etc/apt/keyrings/docker.asc",
        "docker.list",
        f"{base} {plateforme.codename} stable",
    )
    if plugin_seul:
        return Etape("plugin docker compose", (*depot, "apt-get install -y docker-compose-plugin"))
    return Etape(
        "docker",
        (
            *depot,
            "apt-get install -y docker-ce docker-ce-cli containerd.io"
            " docker-buildx-plugin docker-compose-plugin",
            "systemctl enable --now docker",
        ),
    )


def _etape_gh() -> Etape:
    depot = _depot_apt(
        "https://cli.github.com/packages/githubcli-archive-keyring.gpg",
        "/etc/apt/keyrings/githubcli-archive-keyring.gpg",
        "github-cli.list",
        "https://cli.github.com/packages stable main",
    )
    return Etape("gh", (*depot, "apt-get install -y gh"))


def _executer(etape: Etape, env: Mapping[str, str], log, debug: bool) -> int:
    script = "\n".join(["set -euo pipefail" + (" -x" if debug else ""), *etape.commandes])
    commande = ["/bin/bash", "-c", script]
    if etape.utilisateur:
        commande = ["runuser", "-u", etape.utilisateur, "--", *commande]
    log.flush()
    resultat = subprocess.run(
        commande,
        env={**env, "DEBIAN_FRONTEND": "noninteractive"},
        cwd="/",
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return resultat.returncode


def journaliser(log, message: str) -> None:
    log.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    log.flush()
