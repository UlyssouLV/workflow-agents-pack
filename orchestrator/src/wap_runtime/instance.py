"""Instance `~/.wap-runtime/` : config, secrets, Compose et clone du pack."""

import json
import os
import re
import shutil
import subprocess
from importlib.metadata import distribution
from pathlib import Path
from typing import Mapping

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from wap_runtime import __version__
from wap_runtime.runner import PORT_RUNNER

NOM_INSTANCE = ".wap-runtime"
DEPOT_PACK = "https://github.com/UlyssouLV/workflow-agents-pack"
# Ref des images quand le paquet n’a pas d’origine VCS (installation locale ou
# éditable) : la base du canal d’intégration, défaut de `WAP_REF` (ADR 0005).
REF_PAR_DEFAUT = "feat/runtime-orchestrator"
# `direct_url.json` du paquet installé, lu quand l’appelant n’en passe pas.
_PAQUET_INSTALLE = object()
PORT_CONTENEUR = 8787
# L’instance montée en lecture seule dans `runtime`, pour y lire `repos.toml`.
INSTANCE_CONTENEUR = "/instance"
# Seuls dossiers de l’instance montés en écriture dans `runner` (ADR 0004).
DOSSIERS_RUNNER = ("clones", "jobs", "runner-home")
HOME_RUNNER = "/home/runner"


def chemin_instance(home: Path) -> Path:
    return home / NOM_INSTANCE


def preparer_instance(
    home: Path,
    env: Mapping[str, str] = os.environ,
    depot_pack: str = DEPOT_PACK,
    direct_url: Mapping | None = _PAQUET_INSTALLE,
) -> Path:
    """Une passe : crée ou complète l’instance, régénère Compose, aligne le pack.

    Les images se construisent au ref lu dans `direct_url` (`ref_des_images`).
    """
    if direct_url is _PAQUET_INSTALLE:
        direct_url = _direct_url_du_paquet()
    instance = chemin_instance(home)
    instance.mkdir(parents=True, exist_ok=True)
    config = _completer_config(instance / "config.toml", _config_par_defaut(instance, env))
    _creer_secrets(instance / "secrets.env")
    for nom in DOSSIERS_RUNNER:
        (instance / nom).mkdir(exist_ok=True)
    # Cette passe tourne en utilisateur d’instance : le runner reprend son UID.
    contexte = f"{DEPOT_PACK}.git#{ref_des_images(direct_url)}:orchestrator"
    compose = _compose(contexte, config["port"], os.getuid(), os.getgid())
    (instance / "compose.yaml").write_text(compose)
    _aligner_pack(depot_pack, Path(config["pack_path"]), config["pack_ref"])
    return instance


def ref_des_images(direct_url: Mapping | None) -> str:
    """Ref git des images : le commit du paquet installé (PEP 610), à défaut le ref
    demandé à l’installation ; sans origine VCS, `REF_PAR_DEFAUT` (ADR 0005)."""
    vcs = (direct_url or {}).get("vcs_info", {})
    return vcs.get("commit_id") or vcs.get("requested_revision") or REF_PAR_DEFAUT


def lire_config(instance: Path) -> dict:
    return tomllib.loads((instance / "config.toml").read_text())


def desinstaller(home: Path, purge: bool) -> Path | None:
    """`docker compose down` sur l’instance ; `purge` supprime aussi l’instance.

    Rend l’instance traitée, ou `None` s’il n’y en a pas.
    """
    instance = chemin_instance(home)
    if not instance.exists():
        return None
    compose = instance / "compose.yaml"
    if compose.exists():
        subprocess.run(["docker", "compose", "-f", str(compose), "down"], check=True)
    if purge:
        shutil.rmtree(instance)
    return instance


def _config_par_defaut(instance: Path, env: Mapping[str, str]) -> dict:
    port = env.get("WAP_PORT", str(PORT_CONTENEUR))
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(f"WAP_PORT invalide : {port!r} (attendu : un port 1–65535)")
    return {
        "port": int(port),
        "pack_ref": env.get("WAP_PACK_REF", "main"),
        "pack_path": str(instance / "pack"),
        "version": __version__,
    }


def _completer_config(chemin: Path, defauts: dict) -> dict:
    """Ajoute les clés manquantes sans toucher au reste du fichier ; rend la config lue."""
    texte = chemin.read_text() if chemin.exists() else ""
    existantes = tomllib.loads(texte)
    manquantes = [
        f"{cle} = {json.dumps(valeur)}\n"
        for cle, valeur in defauts.items()
        if cle not in existantes
    ]
    if manquantes:
        # Avant la première table : sinon les clés atterriraient dans cette table.
        table = re.search(r"^\s*\[", texte, re.MULTILINE)
        debut = texte[: table.start()] if table else texte
        fin = texte[table.start() :] if table else ""
        if debut and not debut.endswith("\n"):
            debut += "\n"
        chemin.write_text(debut + "".join(manquantes) + ("\n" + fin if fin else ""))
    return {**existantes, **{c: v for c, v in defauts.items() if c not in existantes}}


def _creer_secrets(chemin: Path) -> None:
    if chemin.exists():
        return
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descripteur)
    chemin.chmod(0o600)


def _direct_url_du_paquet() -> dict | None:
    texte = distribution("wap-runtime").read_text("direct_url.json")
    return json.loads(texte) if texte else None


def _compose(contexte: str, port: int, uid: int, gid: int) -> str:
    return f"""\
# Généré par wap-runtime depuis config.toml : réécrit à chaque passe, ne pas éditer.
name: wap-runtime
services:
  runtime:
    build:
      context: {contexte}
      dockerfile: Dockerfile
    image: wap-runtime:local
    env_file:
      - secrets.env
    environment:
      WAP_INSTANCE: {INSTANCE_CONTENEUR}
      WAP_RUNNER: http://runner:{PORT_RUNNER}
    # Le dossier et non `repos.toml` seul : absent, ce fichier deviendrait un dossier
    # sur l’hôte ; remplacé, il ne serait plus vu par le conteneur.
    volumes:
      - ".:{INSTANCE_CONTENEUR}:ro"
    ports:
      - "127.0.0.1:{port}:{PORT_CONTENEUR}"
    restart: unless-stopped
  # Sessions des agents : pas de socket Docker, aucun port publié ; le `runtime` lui
  # parle sur le réseau Compose.
  runner:
    build:
      context: {contexte}
      dockerfile: runner/Dockerfile
    image: wap-runner:local
    command: ["wap-runtime", "runner", "--host", "0.0.0.0", "--port", "{PORT_RUNNER}"]
    user: "{uid}:{gid}"
    init: true
    env_file:
      - secrets.env
    environment:
      HOME: {HOME_RUNNER}
      WAP_CLONES: /clones
      WAP_JOBS: /jobs
    volumes:
      - "./clones:/clones"
      - "./jobs:/jobs"
      - "./runner-home:{HOME_RUNNER}"
    restart: unless-stopped
"""


def _aligner_pack(depot: str, pack: Path, ref: str) -> None:
    if not (pack / ".git").exists():
        _git("clone", "--quiet", "--no-checkout", depot, str(pack))
    _git("-C", str(pack), "fetch", "--quiet", "--tags", "--force", "origin", ref)
    _git("-C", str(pack), "checkout", "--quiet", "--force", "--detach", "FETCH_HEAD")


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)
