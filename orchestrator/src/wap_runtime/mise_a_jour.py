"""`sudo wap-runtime update` : applique la Release `orchestrator-vX.Y.Z` la plus haute (ADR 0013).

En root : lit `version` dans `config.toml`, choisit la Release, vérifie que ses images
sont sur ghcr et qu’aucune session n’est ouverte, puis réinstalle le paquet au tag
pour l’utilisateur d’instance. Le reste tourne dans le **nouveau** paquet, relancé en
utilisateur d’instance comme `setup --instance-seule` : Compose régénéré, pull,
recreate, `version`, anciennes images `wap-*`. Codes : 0 mise à jour faite, 2 rien à
faire, 1 échec (journalisé, pas de rollback).
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

from wap_runtime.instance import (
    DEPOT_PACK,
    REGISTRE,
    chemin_instance,
    ecrire_version,
    image_publiee,
    lire_config,
    regenerer_compose,
)
from wap_runtime.sessions import OUVERTE, Sessions
from wap_runtime.socle import HOME_UTILISATEUR, JOURNAL, UTILISATEUR, journaliser

JOURNAL_MISE_A_JOUR = JOURNAL.parent / "update.log"
API_RELEASES = "https://api.github.com/repos/UlyssouLV/workflow-agents-pack/releases?per_page=100"
PREFIXE_TAG = "orchestrator-v"
_RE_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Seules images que la mise à jour supprime : jamais de `prune` global (hôte partagé).
PREFIXE_IMAGES = f"{REGISTRE}/wap-"
SERVICES_REQUIS = ("runtime", "runner")
FAIT, RIEN_A_FAIRE, ECHEC = 0, 2, 1


def lister_releases() -> list[dict]:
    """Releases du dépôt, par l’API publique (aucun jeton, ADR 0013)."""
    requete = urllib.request.Request(API_RELEASES, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return json.loads(reponse.read())


def release_cible(releases: list[dict], locale: str) -> str | None:
    """`X.Y.Z` de la Release publiée (ni brouillon ni prerelease) la plus haute,
    strictement supérieure à `locale` ; `None` sinon."""
    plancher = _semver(locale)
    candidates = [
        version
        for r in releases
        if not r.get("prerelease") and not r.get("draft")
        and (tag := str(r.get("tag_name") or "")).startswith(PREFIXE_TAG)
        and (version := _semver(tag.removeprefix(PREFIXE_TAG)))
        and version > plancher
    ]
    return ".".join(map(str, max(candidates))) if candidates else None


def mettre_a_jour(
    home: Path = HOME_UTILISATEUR,
    force: bool = False,
    env: Mapping[str, str] = os.environ,
    releases: Callable[[], list[dict]] = lister_releases,
    image_existe: Callable[[str], bool] = image_publiee,
    journal: Path = JOURNAL_MISE_A_JOUR,
) -> int:
    """Partie root : garde-fous, paquet au tag, puis `appliquer` dans le nouveau paquet."""
    instance = chemin_instance(home)
    try:
        locale = str(lire_config(instance).get("version") or "")
    except (OSError, ValueError) as erreur:
        print(f"KO — config de l’instance illisible ({erreur})")
        return ECHEC
    if not _semver(locale):
        print(f"Version « {locale} » : pas une version de production : rien à faire")
        return RIEN_A_FAIRE
    try:
        cible = release_cible(releases(), locale)
    except (OSError, ValueError) as erreur:
        print(f"KO — impossible de lister les Releases ({erreur})")
        return ECHEC
    if cible is None:
        print(f"OK — version {locale} à jour : rien à faire")
        return RIEN_A_FAIRE
    manquantes = [i for i in _images(cible) if not image_existe(i)]
    if manquantes:
        print(f"Release {cible} : images pas encore sur ghcr ({', '.join(manquantes)}) : rien à faire")
        return RIEN_A_FAIRE
    ouvertes = [s for s in Sessions(instance / "jobs").toutes() if s["etat"] == OUVERTE]
    if ouvertes and not force:
        print(f"KO — {len(ouvertes)} session(s) ouverte(s) : le recreate du runner les interromprait")
        for s in ouvertes:
            ticket = f" #{s['ticket']}" if s.get("ticket") else ""
            print(f"  {s['id']} — {s['repo']}{ticket} ({s['agent']})")
        print("Relancer quand elles sont closes, ou `sudo wap-runtime update --force`.")
        return ECHEC

    print(f"→ mise à jour {locale} → {cible}", flush=True)
    journal.parent.mkdir(parents=True, exist_ok=True)
    env_instance = {**env, "HOME": str(home)}
    with journal.open("a") as log:
        journaliser(log, f"mise à jour {locale} → {cible}")
        paquet = f"git+{DEPOT_PACK}@{PREFIXE_TAG}{cible}#subdirectory=orchestrator"
        code = _en_utilisateur(["pipx", "install", "--force", paquet], env_instance, log)
        if code != 0:
            journaliser(log, f"paquet : échec (code {code})")
            print(f"KO — `pipx install` du paquet {cible} a échoué (code {code}) ; voir {journal}")
            return ECHEC
        # pipx recrée le venv au même chemin : `sys.executable` est désormais le nouveau paquet.
        code = _en_utilisateur(
            [sys.executable, "-m", "wap_runtime", "update", "--instance-seule", cible],
            env_instance,
            log,
            relayer=True,
        )
        journaliser(log, f"mise à jour : {'OK' if code == 0 else f'échec (code {code})'}")
    if code != 0:
        print(f"Journal : {journal}")
        return ECHEC
    return FAIT


def appliquer(home: Path, version: str) -> int:
    """Partie utilisateur d’instance, dans le paquet `version` : Compose, pull, recreate,
    `version`, anciennes images. Rend 0 ou 1."""
    if not (semver := _semver(version)):
        return _echec("version", f"« {version} » n’est pas X.Y.Z")
    # Reconstruite des entiers lus : seule une version X.Y.Z atteint Compose et la config.
    version = ".".join(map(str, semver))
    instance = chemin_instance(home)
    compose = instance / "compose.yaml"
    print("→ compose", flush=True)
    try:
        # Images déjà vérifiées sur ghcr par la partie root.
        regenerer_compose(
            instance,
            direct_url={"vcs_info": {"requested_revision": f"{PREFIXE_TAG}{version}"}},
            image_existe=lambda image: True,
        )
    except (OSError, ValueError, KeyError) as erreur:
        return _echec("compose", erreur)
    print("→ docker compose pull", flush=True)
    if (code := _docker("compose", "-f", str(compose), "pull")) != 0:
        return _echec("docker compose pull", f"code {code}")
    print("→ docker compose up", flush=True)
    if _docker("compose", "-f", str(compose), "up", "-d", "--wait", "--force-recreate") != 0:
        en_marche = _services_en_marche(compose)
        absents = [s for s in SERVICES_REQUIS if s not in en_marche]
        if absents:
            return _echec("docker compose up", f"{', '.join(absents)} ne tourne pas")
        print("Attention — Caddy n’a pas démarré (80/443 occupés ?) : `wap-runtime diagnostic`", flush=True)
    ecrire_version(instance, version)
    _supprimer_anciennes_images(version)
    print(f"OK — instance en version {version}", flush=True)
    return FAIT


def _images(version: str) -> tuple[str, str]:
    return (f"{REGISTRE}/wap-runtime:{version}", f"{REGISTRE}/wap-runner:{version}")


def _semver(texte: str) -> tuple[int, int, int] | None:
    trouve = _RE_SEMVER.fullmatch(texte)
    return tuple(map(int, trouve.groups())) if trouve else None


def _en_utilisateur(commande: list[str], env: Mapping[str, str], log, relayer: bool = False) -> int:
    """Lance `commande` en utilisateur d’instance, sortie dans le journal ; `relayer`
    recopie aussi les lignes d’étape et de résultat à l’écran."""
    log.flush()
    enfant = subprocess.Popen(
        ["runuser", "-u", UTILISATEUR, "--", *commande],
        env=dict(env),
        cwd="/",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for ligne in enfant.stdout:
        log.write(ligne)
        log.flush()
        if relayer and ligne.startswith(("→ ", "OK", "KO", "Attention")):
            print(ligne, end="", flush=True)
    return enfant.wait()


def _docker(*args: str) -> int:
    try:
        return subprocess.run(["docker", *args], stdin=subprocess.DEVNULL).returncode
    except OSError:
        return 127


def _services_en_marche(compose: Path) -> set[str]:
    try:
        sortie = subprocess.run(
            ["docker", "compose", "-f", str(compose), "ps", "--status", "running", "--services"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        ).stdout
    except OSError:
        return set()
    return set(sortie.split())


def _supprimer_anciennes_images(version: str) -> None:
    """Images `ghcr.io/ulyssoulv/wap-*` d’une autre étiquette (orphelines comprises)."""
    try:
        sortie = subprocess.run(
            ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        ).stdout
    except OSError:
        return
    gardees = set(_images(version))
    for ligne in sortie.splitlines():
        reference, _, ident = ligne.partition(" ")
        if not reference.startswith(PREFIXE_IMAGES) or reference in gardees:
            continue
        cible = ident if reference.endswith(":<none>") else reference
        if _docker("image", "rm", cible) != 0:
            print(f"Attention — image {reference} non supprimée", flush=True)


def _echec(etape: str, erreur) -> int:
    print(f"KO — l’étape « {etape} » a échoué ({erreur}) ; pas de rollback", flush=True)
    return ECHEC
