"""Connexion GitHub de l’instance (ADR 0003).

L’identité de l’instance est celle du `gh` de l’utilisateur d’instance sur l’hôte ;
son token est copié dans `secrets.env` sous `GH_TOKEN`, lu par le service `runtime`.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import IO, Mapping

from wap_runtime.fichiers import remplacer

ETAPE_LOGIN = "gh auth login"
ETAPE_TOKEN = "gh auth token"
ETAPE_COMPTE = "gh api user"
ETAPE_SECRETS = "secrets.env"
ETAPE_REDEMARRAGE = "redémarrage du service runtime"
# Assez large pour les tokens classiques (`gho_…`, `ghp_…`) et fine-grained
# (`github_pat_…`), assez étroit pour ne rien glisser d’autre dans `secrets.env`.
_JETON = re.compile(r"[A-Za-z0-9_]+")
# Vus par `gh`, ils remplacent sa connexion : `auth login` refuse alors de stocker
# le token et `auth token` rend celui de l’environnement.
_VARIABLES_GH = ("GH_TOKEN", "GITHUB_TOKEN")


class AuthErreur(Exception):
    def __init__(self, etape: str, detail: str):
        super().__init__(f"l’étape « {etape} » a échoué ({detail})")


def connecter(
    instance: Path,
    jeton: str | None = None,
    utilisateur: str | None = None,
    env: Mapping[str, str] = os.environ,
    entree: IO | None = None,
) -> str:
    """Connecte `gh` (device flow, ou `jeton` s’il est fourni), copie le token dans
    `secrets.env` et redémarre `runtime` ; rend le compte GitHub.

    `utilisateur` : celui sous lequel lancer `gh` (root → utilisateur d’instance).
    `entree` : stdin du device flow, quand ce n’est pas celui du processus.
    """
    home = instance.parent
    if jeton is None:
        _gh(["auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"],
            ETAPE_LOGIN, home, utilisateur, env, stdin=entree)
    else:
        _gh(["auth", "login", "--hostname", "github.com", "--with-token"],
            ETAPE_LOGIN, home, utilisateur, env, entree_texte=jeton + "\n")
    jeton = _gh(["auth", "token"], ETAPE_TOKEN, home, utilisateur, env).strip()
    if not _JETON.fullmatch(jeton):
        raise AuthErreur(ETAPE_TOKEN, "token vide ou inattendu")
    compte = _compte(home, jeton, utilisateur, env)
    try:
        ecrire_jeton(instance / "secrets.env", jeton)
    except OSError as erreur:
        raise AuthErreur(ETAPE_SECRETS, str(erreur)) from erreur
    try:
        # `restart` relancerait le conteneur sans relire `env_file`.
        subprocess.run(
            ["docker", "compose", "-f", str(instance / "compose.yaml"),
             "up", "-d", "--force-recreate", "runtime"],
            check=True,
            stdin=subprocess.DEVNULL,
            env=dict(env),
        )
    except (OSError, subprocess.CalledProcessError) as erreur:
        raise AuthErreur(ETAPE_REDEMARRAGE, str(erreur)) from erreur
    return compte


def lancer_auth(
    instance: Path,
    jeton: str | None = None,
    utilisateur: str | None = None,
    env: Mapping[str, str] = os.environ,
    entree: IO | None = None,
) -> int:
    """`connecter`, avec sa ligne OK / KO ; rend le code de sortie."""
    try:
        compte = connecter(instance, jeton, utilisateur, env, entree)
    except AuthErreur as erreur:
        print(f"KO — {erreur}", flush=True)
        return 1
    print(f"OK — instance connectée à GitHub en tant que {compte} ; service runtime redémarré",
          flush=True)
    return 0


def statut(
    instance: Path, utilisateur: str | None = None, env: Mapping[str, str] = os.environ
) -> tuple[bool, str]:
    """(connectée, compte ou raison) : le `GH_TOKEN` de `secrets.env`, validé par GitHub."""
    jeton = lire_jeton(instance / "secrets.env")
    if not jeton:
        return False, "aucun GH_TOKEN dans secrets.env"
    try:
        return True, _compte(instance.parent, jeton, utilisateur, env)
    except AuthErreur as erreur:
        return False, f"token refusé : {erreur}"


def lire_jeton(secrets: Path) -> str | None:
    try:
        lignes = secrets.read_text().splitlines()
    except FileNotFoundError:
        return None
    valeurs = [l.partition("=")[2].strip() for l in lignes if _est_jeton(l)]
    return valeurs[-1] if valeurs and valeurs[-1] else None


def ecrire_jeton(secrets: Path, jeton: str) -> None:
    """Remplace `GH_TOKEN` en gardant les autres lignes ; fichier remplacé d’un coup, `0600`."""
    lignes = secrets.read_text().splitlines() if secrets.exists() else []
    contenu = "".join(f"{l}\n" for l in lignes if not _est_jeton(l)) + f"GH_TOKEN={jeton}\n"
    remplacer(secrets, contenu, 0o600)


def _est_jeton(ligne: str) -> bool:
    return ligne.strip().startswith("GH_TOKEN=")


def _compte(home: Path, jeton: str, utilisateur: str | None, env: Mapping[str, str]) -> str:
    compte = _gh(["api", "user", "--jq", ".login"], ETAPE_COMPTE, home, utilisateur, env,
                 jeton=jeton).strip()
    if not compte:
        raise AuthErreur(ETAPE_COMPTE, "compte vide")
    return compte


def _gh(
    args: list[str],
    etape: str,
    home: Path,
    utilisateur: str | None,
    env: Mapping[str, str],
    jeton: str | None = None,
    stdin: IO | None = None,
    entree_texte: str | None = None,
) -> str:
    """Lance `gh` dans le HOME de l’instance ; rend stdout, sauf en device flow où
    `gh` parle directement au terminal."""
    commande = ["gh", *args]
    if utilisateur:
        commande = ["runuser", "-u", utilisateur, "--", *commande]
    env_gh = {k: v for k, v in env.items() if k not in _VARIABLES_GH}
    env_gh["HOME"] = str(home)
    if jeton is not None:
        env_gh["GH_TOKEN"] = jeton
    interactif = args[:2] == ["auth", "login"] and entree_texte is None
    if interactif:
        options = {"stdin": stdin}
    elif entree_texte is not None:
        options = {"input": entree_texte, "capture_output": True}
    else:
        options = {"stdin": subprocess.DEVNULL, "capture_output": True}
    try:
        resultat = subprocess.run(commande, env=env_gh, text=True, **options)
    except OSError as erreur:
        raise AuthErreur(etape, str(erreur)) from erreur
    if resultat.returncode != 0:
        detail = (resultat.stderr or "").strip().splitlines()
        raise AuthErreur(etape, detail[-1] if detail else f"code {resultat.returncode}")
    return resultat.stdout or ""
