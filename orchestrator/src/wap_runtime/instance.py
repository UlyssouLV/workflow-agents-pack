"""Instance `~/.wap-runtime/` : config, secrets, Compose et clone du pack."""

import json
import os
import re
import shutil
import subprocess
from importlib.metadata import distribution
from pathlib import Path
from typing import Callable, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from wap_runtime.runner import PORT_RUNNER

NOM_INSTANCE = ".wap-runtime"
FICHIER_CONFIG = "config.toml"
DEPOT_PACK = "https://github.com/UlyssouLV/workflow-agents-pack"
# Ref des images quand le paquet n’a pas d’origine VCS (installation locale ou
# éditable) : la base du canal d’intégration, défaut de `WAP_REF` (ADR 0005).
REF_PAR_DEFAUT = "feat/runtime-orchestrator"
# Images publiées par la CI (ADR 0013) : paquets publics, tirés sans jeton.
REGISTRE = "ghcr.io/ulyssoulv"
_RE_TAG_RELEASE = re.compile(r"^orchestrator-v(\d+\.\d+\.\d+)$")
# `direct_url.json` du paquet installé, lu quand l’appelant n’en passe pas.
_PAQUET_INSTALLE = object()
PORT_CONTENEUR = 8787
# L’instance montée dans `runtime`, pour y lire et écrire `repos.toml` (toggle Pilote).
INSTANCE_CONTENEUR = "/instance"
# Seuls dossiers de l’instance montés en écriture dans `runner` (ADR 0004).
DOSSIERS_RUNNER = ("clones", "jobs", "runner-home")
HOME_RUNNER = "/home/runner"
# Hôte DNS pour TLS : labels alphanumériques / tirets, pas de chemin ni `..`.
_RE_DOMAINE = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)


def chemin_instance(home: Path) -> Path:
    return home / NOM_INSTANCE


def preparer_instance(
    home: Path,
    env: Mapping[str, str] = os.environ,
    depot_pack: str = DEPOT_PACK,
    direct_url: Mapping | None = _PAQUET_INSTALLE,
    image_existe: Callable[[str], bool] | None = None,
) -> Path:
    """Une passe : crée ou complète l’instance, régénère Compose, aligne le pack.

    `version` reprend le paquet installé à chaque passe ; les images se tirent de
    ghcr ou se construisent au ref lu dans `direct_url` (`regenerer_compose`).
    """
    if direct_url is _PAQUET_INSTALLE:
        direct_url = _direct_url_du_paquet()
    instance = chemin_instance(home)
    instance.mkdir(parents=True, exist_ok=True)
    config = _completer_config(_chemin_config(instance), _config_par_defaut(instance, env))
    _ecrire_cle_config(instance, "version", version_installee(direct_url))
    _creer_secrets(instance / "secrets.env")
    for nom in DOSSIERS_RUNNER:
        (instance / nom).mkdir(exist_ok=True)
    # Cette passe tourne en utilisateur d’instance : le runner reprend son UID.
    regenerer_compose(instance, direct_url=direct_url, image_existe=image_existe)
    _aligner_pack(depot_pack, Path(config["pack_path"]), config["pack_ref"])
    return instance


def regenerer_compose(
    instance: Path,
    direct_url: Mapping | None = _PAQUET_INSTALLE,
    image_existe: Callable[[str], bool] | None = None,
) -> None:
    """Réécrit `compose.yaml` et le Caddyfile depuis `config.toml` (sans toucher au pack).

    Images ghcr à l’étiquette du paquet (`etiquette_des_images`) quand les deux
    existent ; sinon build au commit du paquet (ADR 0005, secours).
    """
    if direct_url is _PAQUET_INSTALLE:
        direct_url = _direct_url_du_paquet()
    image_existe = image_existe or image_publiee
    config = lire_config(instance)
    exposition = bool(config.get("exposition", False))
    domaine = str(config.get("domaine") or "").strip()
    etiquette = etiquette_des_images(direct_url)
    images = None
    if etiquette:
        images = (f"{REGISTRE}/wap-runtime:{etiquette}", f"{REGISTRE}/wap-runner:{etiquette}")
        if not all(image_existe(image) for image in images):
            images = None
    contexte = f"{DEPOT_PACK}.git#{ref_des_images(direct_url)}:orchestrator"
    (instance / "compose.yaml").write_text(
        _compose(
            contexte,
            images,
            config["port"],
            os.getuid(),
            os.getgid(),
            exposition,
            domaine=domaine,
        )
    )
    _ecrire_caddyfile(instance, exposition, domaine)


def ref_des_images(direct_url: Mapping | None) -> str:
    """Ref git des images : le commit du paquet installé (PEP 610), à défaut le ref
    demandé à l’installation ; sans origine VCS, `REF_PAR_DEFAUT` (ADR 0005)."""
    vcs = (direct_url or {}).get("vcs_info", {})
    return vcs.get("commit_id") or vcs.get("requested_revision") or REF_PAR_DEFAUT


def version_installee(direct_url: Mapping | None) -> str:
    """`X.Y.Z` pour un paquet installé au tag de Release `orchestrator-vX.Y.Z`,
    sinon le ref demandé, le commit, ou `REF_PAR_DEFAUT` sans origine VCS."""
    vcs = (direct_url or {}).get("vcs_info", {})
    demande = vcs.get("requested_revision") or ""
    if release := _RE_TAG_RELEASE.fullmatch(demande):
        return release.group(1)
    return demande or vcs.get("commit_id") or REF_PAR_DEFAUT


def etiquette_des_images(direct_url: Mapping | None) -> str | None:
    """Étiquette ghcr des images du paquet : `X.Y.Z` (promotion de la Release),
    `sha-<commit>` (staging de la PR), ou `None` sans commit connu (ADR 0013)."""
    vcs = (direct_url or {}).get("vcs_info", {})
    if release := _RE_TAG_RELEASE.fullmatch(vcs.get("requested_revision") or ""):
        return release.group(1)
    commit = vcs.get("commit_id")
    return f"sha-{commit}" if commit else None


def image_publiee(image: str) -> bool:
    """L’image existe sur son registre (lecture anonyme des paquets publics)."""
    try:
        return (
            subprocess.run(
                ["docker", "manifest", "inspect", image],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
    except OSError:
        return False


def lire_config(instance: Path) -> dict:
    return tomllib.loads(_chemin_config(instance).read_text())


def definir_exposition(instance: Path, actif: bool) -> None:
    """Écrit `exposition` dans `config.toml` (la passe Compose lit cette clé)."""
    _ecrire_cle_config(instance, "exposition", bool(actif))


def definir_domaine(instance: Path, domaine: str) -> None:
    """Écrit `domaine` dans `config.toml` (hôte pour TLS Let’s Encrypt via Caddy)."""
    _ecrire_cle_config(instance, "domaine", normaliser_domaine(domaine))


def normaliser_domaine(domaine: str) -> str:
    """Valide un nom d’hôte DNS (rejette chemins, espaces, `..`)."""
    hote = str(domaine).strip().lower()
    if not hote or not _RE_DOMAINE.fullmatch(hote) or ".." in hote or "/" in hote:
        raise ValueError(f"domaine invalide : {domaine!r}")
    return hote


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
        "exposition": False,
        "domaine": "",
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


def _chemin_config(instance: Path) -> Path:
    """`config.toml` sous l’instance — jamais dérivé d’une entrée CLI."""
    racine = instance.resolve()
    chemin = (racine / FICHIER_CONFIG).resolve()
    if not chemin.is_relative_to(racine):
        raise ValueError("chemin config hors de l’instance")
    return chemin


def _ecrire_cle_config(instance: Path, cle: str, valeur) -> None:
    """Met à jour ou ajoute une clé scalaire de premier niveau dans `config.toml`."""
    chemin = _chemin_config(instance)
    texte = chemin.read_text() if chemin.exists() else ""
    ligne = f"{cle} = {json.dumps(valeur)}"
    if re.search(rf"^{re.escape(cle)} = ", texte, re.MULTILINE):
        chemin.write_text(
            re.sub(rf"^{re.escape(cle)} = .*$", ligne, texte, flags=re.MULTILINE)
        )
        return
    table = re.search(r"^\s*\[", texte, re.MULTILINE)
    debut = texte[: table.start()] if table else texte
    fin = texte[table.start() :] if table else ""
    if debut and not debut.endswith("\n"):
        debut += "\n"
    chemin.write_text(debut + ligne + "\n" + (("\n" + fin) if fin else ""))


def _ecrire_caddyfile(instance: Path, exposition: bool, domaine: str = "") -> None:
    chemin = instance / "Caddyfile"
    if not exposition:
        chemin.unlink(missing_ok=True)
        return
    # Relais borné au cockpit de cette instance (`runtime`) — ADR 0011.
    # Avec domaine : site nommé → HTTPS automatique Let’s Encrypt (pas de HTTP public).
    # Sans domaine : écoute :80 en lab local seulement (ports Compose bornés à 127.0.0.1).
    site = normaliser_domaine(domaine) if domaine.strip() else ":80"
    chemin.write_text(
        f"""{site} {{
	reverse_proxy runtime:{PORT_CONTENEUR}
}}
"""
    )


def _compose(
    contexte: str,
    images: tuple[str, str] | None,
    port: int,
    uid: int,
    gid: int,
    exposition: bool = False,
    *,
    domaine: str = "",
) -> str:
    # Expo on : seuls 80/443 du proxy ; runtime reste sur le réseau Compose.
    # Sans domaine : bind loopback seulement — pas de HTTP public (ADR 0011).
    ports_runtime = (
        ""
        if exposition
        else (
            "\n    ports:\n"
            f'      - "127.0.0.1:{port}:{PORT_CONTENEUR}"'
        )
    )
    caddy = ""
    if exposition:
        if domaine.strip():
            ports_caddy = '      - "80:80"\n      - "443:443"'
            commentaire = (
                "  # Entrée publique opt-in (domaine) : seuls 80/443 ; "
                "relaie uniquement vers `runtime` (cockpit)."
            )
        else:
            ports_caddy = '      - "127.0.0.1:80:80"\n      - "127.0.0.1:443:443"'
            commentaire = (
                "  # Expo sans domaine : Caddy sur loopback seulement "
                "(pas de HTTP public) ; `wap-runtime domaine` pour HTTPS."
            )
        caddy = f"""
{commentaire}
  caddy:
    image: caddy:2-alpine
    ports:
{ports_caddy}
    volumes:
      - "./Caddyfile:/etc/caddy/Caddyfile:ro"
      - "./caddy-data:/data"
      - "./caddy-config:/config"
    depends_on:
      - runtime
    restart: unless-stopped
"""
    if images:
        source_runtime = f"image: {images[0]}"
        source_runner = f"image: {images[1]}"
    else:
        source_runtime = f"""build:
      context: {contexte}
      dockerfile: Dockerfile
    image: wap-runtime:local"""
        source_runner = f"""build:
      context: {contexte}
      dockerfile: runner/Dockerfile
    image: wap-runner:local"""
    return f"""\
# Généré par wap-runtime depuis config.toml : réécrit à chaque passe, ne pas éditer.
name: wap-runtime
services:
  runtime:
    {source_runtime}
    user: "{uid}:{gid}"
    env_file:
      - secrets.env
    environment:
      WAP_INSTANCE: {INSTANCE_CONTENEUR}
      WAP_RUNNER: http://runner:{PORT_RUNNER}
    # Le dossier et non `repos.toml` seul : absent, ce fichier deviendrait un dossier
    # sur l’hôte ; remplacé, il ne serait plus vu par le conteneur. Sans `:ro` : le
    # cockpit persiste le toggle Pilote (remplacement atomique dans ce dossier).
    volumes:
      - ".:{INSTANCE_CONTENEUR}"{ports_runtime}
    restart: unless-stopped
  # Sessions des agents : pas de socket Docker, aucun port publié ; le `runtime` lui
  # parle sur le réseau Compose.
  runner:
    {source_runner}
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
{caddy}"""


def _aligner_pack(depot: str, pack: Path, ref: str) -> None:
    if not (pack / ".git").exists():
        _git("clone", "--quiet", "--no-checkout", depot, str(pack))
    _git("-C", str(pack), "fetch", "--quiet", "--tags", "--force", "origin", ref)
    _git("-C", str(pack), "checkout", "--quiet", "--force", "--detach", "FETCH_HEAD")


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)
