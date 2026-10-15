"""Sonde `GET /health` du runtime publié sur `127.0.0.1`."""

import json
import urllib.request


def sonder(port: int, timeout: float = 5) -> tuple[bool, str]:
    """Interroge `/health` ; rend (OK ?, message d’une ligne)."""
    adresse = f"127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"http://{adresse}/health", timeout=timeout) as rep:
            corps = json.loads(rep.read())
    except (OSError, ValueError) as erreur:
        return False, f"le runtime ne répond pas sur {adresse} ({erreur})"
    if not isinstance(corps, dict) or corps.get("status") != "ok":
        return False, f"réponse inattendue de {adresse} : {corps}"
    return True, f"wap-runtime {corps.get('version')} répond sur {adresse}"
