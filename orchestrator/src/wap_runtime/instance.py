"""Instance `~/.wap-runtime/` : config, secrets, Compose et clone du pack."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from wap_runtime import __version__

NOM_INSTANCE = ".wap-runtime"
DEPOT_PACK = "https://github.com/UlyssouLV/workflow-agents-pack"
# Contexte de build du service `runtime` : `orchestrator/` de la branche de base,
# celle d’où `install.sh` installe le paquet (ADR 0002).
CONTEXTE_RUNTIME = (
    "https://github.com/UlyssouLV/workflow-agents-pack.git"
    "#feat/runtime-orchestrator:orchestrator"
)
PORT_CONTENEUR = 8787


def chemin_instance(home: Path) -> Path:
    return home / NOM_INSTANCE


def preparer_instance(
    home: Path, env: Mapping[str, str] = os.environ, depot_pack: str = DEPOT_PACK
) -> Path:
    """Une passe : crée ou complète l’instance, régénère Compose, aligne le pack."""
    instance = chemin_instance(home)
    instance.mkdir(parents=True, exist_ok=True)
    config = _completer_config(instance / "config.toml", _config_par_defaut(instance, env))
    _creer_secrets(instance / "secrets.env")
    (instance / "compose.yaml").write_text(_compose(config["port"]))
    _aligner_pack(depot_pack, Path(config["pack_path"]), config["pack_ref"])
    return instance


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


def _compose(port: int) -> str:
    return f"""\
# Généré par wap-runtime depuis config.toml : réécrit à chaque passe, ne pas éditer.
name: wap-runtime
services:
  runtime:
    build:
      context: {CONTEXTE_RUNTIME}
      dockerfile: Dockerfile
    image: wap-runtime:local
    env_file:
      - secrets.env
    ports:
      - "127.0.0.1:{port}:{PORT_CONTENEUR}"
    restart: unless-stopped
"""


def _aligner_pack(depot: str, pack: Path, ref: str) -> None:
    if not (pack / ".git").exists():
        _git("clone", "--quiet", "--no-checkout", depot, str(pack))
    _git("-C", str(pack), "fetch", "--quiet", "--tags", "--force", "origin", ref)
    _git("-C", str(pack), "checkout", "--quiet", "--force", "--detach", "FETCH_HEAD")


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)
