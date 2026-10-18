"""Diagnostic d’exposition web : côté instance vs reste opérateur (DNS / NAT / CGNAT)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wap_runtime.identifiants_cockpit import est_configure
from wap_runtime.instance import lire_config


@dataclass(frozen=True)
class EtatDiagnostic:
    """Observations déjà collectées — la mise en forme ne relance rien."""

    exposition: bool
    domaine: str
    auth_cockpit: bool
    caddy_up: bool | None
    ports_ok: bool | None


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
    return EtatDiagnostic(
        exposition=True,
        domaine=domaine,
        auth_cockpit=auth,
        caddy_up=caddy_up,
        ports_ok=ports_ok,
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
        lignes.append("OK — ports 80/443 publiés comme attendu")
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
    return '"80:80"' in compose and '"443:443"' in compose and "caddy:" in compose


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
