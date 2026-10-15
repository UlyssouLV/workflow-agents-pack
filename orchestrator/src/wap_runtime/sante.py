"""Sonde `GET /health` du runtime publié sur `127.0.0.1`."""

import http.client
import json

# Boucle locale uniquement : le runtime n’est publié que là, en HTTP clair.
HOTE = "127.0.0.1"


def sonder(port: int, timeout: float = 5) -> tuple[bool, str]:
    """Interroge `/health` ; rend (OK ?, message d’une ligne)."""
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536:
        return False, f"port invalide : {port!r}"
    adresse = f"{HOTE}:{port}"
    connexion = http.client.HTTPConnection(HOTE, port, timeout=timeout)
    try:
        connexion.request("GET", "/health")
        rep = connexion.getresponse()
        corps = json.loads(rep.read())
    except (OSError, http.client.HTTPException, ValueError) as erreur:
        return False, f"le runtime ne répond pas sur {adresse} ({erreur})"
    finally:
        connexion.close()
    if rep.status != 200 or not isinstance(corps, dict) or corps.get("status") != "ok":
        return False, f"réponse inattendue de {adresse} : {corps}"
    return True, f"wap-runtime {corps.get('version')} répond sur {adresse}"
