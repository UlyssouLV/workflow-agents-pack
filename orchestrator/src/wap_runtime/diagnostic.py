"""Diagnostic d’exposition web : côté instance vs reste opérateur (DNS / NAT / CGNAT)."""

from __future__ import annotations

import re
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wap_runtime.identifiants_cockpit import est_configure
from wap_runtime.instance import lire_config

PORTS_PROXY = (80, 443)
PROC_NET = Path("/proc/net")
# État `LISTEN` dans `/proc/net/tcp` (hexadécimal, `include/net/tcp_states.h`).
ETAT_LISTEN = "0A"


@dataclass(frozen=True)
class EtatDiagnostic:
    """Observations déjà collectées — la mise en forme ne relance rien."""

    exposition: bool
    domaine: str
    auth_cockpit: bool
    caddy_up: bool | None
    ports_ok: bool | None
    # Ports du proxy tenus par un autre processus que le Caddy de l’instance.
    ports_occupes: tuple[int, ...] = ()


def observer(instance: Path) -> EtatDiagnostic:
    """Lit config / Compose / docker pour un rapport diagnostic."""
    config = lire_config(instance)
    exposition = bool(config.get("exposition", False))
    domaine = str(config.get("domaine") or "").strip()
    auth = est_configure(instance)
    if not exposition:
        return EtatDiagnostic(
            exposition=False,
            domaine=domaine,
            auth_cockpit=auth,
            caddy_up=None,
            ports_ok=None,
        )
    compose = (instance / "compose.yaml").read_text(encoding="utf-8")
    ports_ok = _ports_proxy_publies(compose)
    caddy_up = _caddy_tourne(instance)
    # Caddy up tient lui-même 80/443 ; sinon un port qui écoute est à un autre service.
    occupes = () if caddy_up else tuple(p for p in PORTS_PROXY if _port_ecoute(p))
    return EtatDiagnostic(
        exposition=True,
        domaine=domaine,
        auth_cockpit=auth,
        caddy_up=caddy_up,
        ports_ok=ports_ok,
        ports_occupes=occupes,
    )


def formater(etat: EtatDiagnostic) -> tuple[list[str], int]:
    """Rend les lignes à afficher et le code de sortie (1 si KO côté instance)."""
    lignes: list[str] = ["=== Côté instance ==="]
    ko = False

    if etat.auth_cockpit:
        lignes.append("OK — identifiants cockpit configurés")
    else:
        ko = True
        lignes.append(
            "KO — identifiants cockpit non configurés : "
            "`wap-runtime cockpit-auth --login <login>`"
        )

    if not etat.exposition:
        lignes.append("OK — exposition web désactivée (accès local / SSH)")
        lignes.extend(_bloc_operateur(etat, expo_off=True))
        return lignes, (1 if ko else 0)

    lignes.append("OK — exposition web activée")

    if etat.ports_ok:
        if etat.domaine:
            lignes.append("OK — ports 80/443 publiés comme attendu")
        else:
            lignes.append(
                "OK — ports 80/443 sur 127.0.0.1 (pas de HTTP public sans domaine)"
            )
    else:
        ko = True
        lignes.append("KO — ports 80/443 absents ou incomplets dans Compose")

    if etat.caddy_up:
        lignes.append("OK — Caddy est up")
    elif etat.caddy_up is False:
        ko = True
        lignes.append("KO — Caddy n’est pas up")
    else:
        ko = True
        lignes.append("KO — impossible de sonder Caddy (`docker compose ps`)")

    for port in etat.ports_occupes:
        lignes.append(
            f"KO — port {port} occupé par un autre processus que le Caddy de l’instance : "
            f"Caddy ne peut pas démarrer — voir qui l’écoute (`sudo ss -ltnp 'sport = :{port}'`), "
            "libérer le port ou garder l’exposition off (README, « Hôte partagé »)"
        )

    if etat.domaine:
        lignes.append(f"OK — domaine configuré : {etat.domaine} (chemin HTTPS / Let’s Encrypt)")
    else:
        ko = True
        lignes.append(
            "KO — aucun domaine configuré : HTTPS Let’s Encrypt indisponible ; "
            "HTTP public non supporté — `wap-runtime domaine <hote>`"
        )

    lignes.extend(_bloc_operateur(etat, expo_off=False))
    return lignes, (1 if ko else 0)


def _bloc_operateur(etat: EtatDiagnostic, *, expo_off: bool) -> list[str]:
    lignes = ["", "=== Côté opérateur (reste à faire) ==="]
    if expo_off:
        lignes.append(
            "→ rien de public attendu ; pour l’accès distant sans ouvrir la box : tunnel SSH"
        )
        return lignes
    if etat.domaine:
        lignes.append(
            f"→ DNS : « {etat.domaine} » doit pointer vers l’adresse publique de cette machine"
        )
    else:
        lignes.append(
            "→ DNS : définir un nom qui pointe ici, puis `wap-runtime domaine <hote>`"
        )
    lignes.append(
        "→ NAT : sur la box, rediriger les ports 80 et 443 vers cette machine "
        "(Caddy tourne sur l’hôte, pas sur la box)"
    )
    lignes.append(
        "→ CGNAT : certaines box 4G n’offrent pas de NAT public utilisable — "
        "dans ce cas garder SSH ou un autre accès ; le produit ne configure pas la box"
    )
    return lignes


def _ports_proxy_publies(compose: str) -> bool:
    """Vrai si Caddy publie 80/443 (public ou loopback lab sans domaine)."""
    if "caddy:" not in compose:
        return False
    a80 = '"80:80"' in compose or '"127.0.0.1:80:80"' in compose
    a443 = '"443:443"' in compose or '"127.0.0.1:443:443"' in compose
    return a80 and a443


def _port_ecoute(port: int, proc_net: Path = PROC_NET) -> bool:
    """Vrai si un processus écoute ce port TCP de l’hôte, sur n’importe quelle adresse.

    Lit les sockets `LISTEN` de `/proc/net/tcp{,6}` (IP publique comprise, sans root) ;
    hors Linux, se rabat sur une connexion à `127.0.0.1`.
    """
    tables = []
    for nom in ("tcp", "tcp6"):
        try:
            tables.append((proc_net / nom).read_text())
        except OSError:
            continue
    if not tables:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False
    for table in tables:
        for ligne in table.splitlines()[1:]:
            champs = ligne.split()
            if len(champs) < 4 or champs[3] != ETAT_LISTEN:
                continue
            if int(champs[1].rsplit(":", 1)[1], 16) == port:
                return True
    return False


def _caddy_tourne(instance: Path) -> bool | None:
    compose = instance / "compose.yaml"
    if not compose.is_file():
        return False
    try:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose),
                "ps",
                "--status",
                "running",
                "caddy",
            ],
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    # Une ligne de service « running » (hors en-tête éventuel).
    corps = proc.stdout or ""
    if re.search(r"\bcaddy\b", corps, re.IGNORECASE) and re.search(
        r"\brunning\b", corps, re.IGNORECASE
    ):
        return True
    # Format table Docker Compose v2 : parfois le nom du projet préfixe le service.
    lignes = [l for l in corps.splitlines() if l.strip() and not l.lower().startswith("name")]
    return any("caddy" in l.lower() for l in lignes)
