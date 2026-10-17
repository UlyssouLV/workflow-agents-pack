"""Connexion des agents de l’instance : Claude Code et Cursor (ADR 0004).

Leurs tokens vivent dans `secrets.env`, lu par les services par `env_file` : chaque écriture
recrée les services. « Connecté » veut dire token présent, sans appel de vérification.
"""

import fcntl
import os
import re
import select
import struct
import subprocess
import sys
import termios
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from wap_runtime.auth import AuthErreur, ecrire_secret
from wap_runtime.pseudo_terminal import brut, controler, restaurer

ETAPE_SETUP_TOKEN = "claude setup-token"
ETAPE_SECRETS = "secrets.env"
ETAPE_REDEMARRAGE = "redémarrage des services"
# Pas d’espace, de `=` ni de retour à la ligne : rien d’autre ne glisse dans `secrets.env`.
_JETON = re.compile(r"[A-Za-z0-9_.-]+")
# Token OAuth (`sk-ant-oat01-…`) ou clé API (`sk-ant-api03-…`) d’Anthropic.
_JETON_CLAUDE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-_]")
# Assez large pour que `claude` n’enroule pas le token sur deux lignes.
_COLONNES = 1000


@dataclass(frozen=True)
class Agent:
    id: str
    nom: str
    # La première est celle qu’écrit `auth` ; n’importe laquelle suffit à « connecté ».
    cles: tuple[str, ...]
    commande: str
    # Lancé en mode interactif sur `/implement #n` ; aussi la cible de `wap-runtime auth`.
    programme: str
    # Racine de ses transcriptions sous `HOME`, et motif des fichiers à copier.
    transcriptions: tuple[str, str]


CLAUDE = Agent(
    "claude", "Claude Code", ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"),
    "sudo wap-runtime auth claude", "claude", (".claude/projects", "**/*.jsonl"),
)
CURSOR = Agent(
    "cursor", "Cursor", ("CURSOR_API_KEY",), "… | sudo wap-runtime auth agent --with-token",
    "agent", (".cursor/projects", "*/agent-transcripts/**/*.jsonl"),
)
AGENTS = (CLAUDE, CURSOR)


def agent_par_id(id_: str) -> Agent | None:
    return next((a for a in AGENTS if a.id == id_), None)


def commande_agent(agent: Agent, ticket: int) -> list[str]:
    return [agent.programme, f"/implement #{ticket}"]


def connecte(agent: Agent, valeurs: Mapping[str, str]) -> bool:
    return any((valeurs.get(cle) or "").strip() for cle in agent.cles)


def etat_agents(valeurs: Mapping[str, str]) -> list[dict]:
    """L’encart Agents du cockpit, depuis `valeurs` (`secrets.env` ou l’environnement du service)."""
    return [
        {"id": a.id, "nom": a.nom, "connecte": connecte(a, valeurs), "commande": a.commande}
        for a in AGENTS
    ]


def connecter_claude(
    instance: Path,
    jeton: str | None = None,
    utilisateur: str | None = None,
    env: Mapping[str, str] = os.environ,
) -> str:
    """`claude setup-token` sur l’hôte (ou `jeton`), écrit dans `secrets.env`, services recréés ;
    rend la clé écrite.

    Une clé API (`sk-ant-api…`) s’écrit sous `ANTHROPIC_API_KEY` ; une seule identité Claude
    à la fois, l’autre clé est retirée.
    """
    if jeton is None:
        jeton = _setup_token(instance.parent, utilisateur, env)
    elif not _JETON.fullmatch(jeton):
        raise AuthErreur("stdin", "token vide ou inattendu")
    cle = "ANTHROPIC_API_KEY" if jeton.startswith("sk-ant-api") else "CLAUDE_CODE_OAUTH_TOKEN"
    _ecrire(instance, cle, jeton, retirer=tuple(c for c in CLAUDE.cles if c != cle), env=env)
    return cle


def connecter_cursor(instance: Path, jeton: str, env: Mapping[str, str] = os.environ) -> str:
    """Clé API Cursor écrite sous `CURSOR_API_KEY`, services recréés ; rend la clé écrite."""
    if not _JETON.fullmatch(jeton):
        raise AuthErreur("stdin", "clé vide ou inattendue")
    _ecrire(instance, "CURSOR_API_KEY", jeton, env=env)
    return "CURSOR_API_KEY"


def lancer_auth_agent(
    instance: Path,
    agent: Agent,
    jeton: str | None = None,
    utilisateur: str | None = None,
    env: Mapping[str, str] = os.environ,
) -> int:
    """`connecter_claude` / `connecter_cursor`, avec sa ligne OK / KO ; rend le code de sortie."""
    try:
        if agent is CLAUDE:
            cle = connecter_claude(instance, jeton, utilisateur, env)
        else:
            cle = connecter_cursor(instance, jeton or "", env)
    except AuthErreur as erreur:
        print(f"KO — {erreur}", flush=True)
        return 1
    print(f"OK — {agent.nom} connecté ({cle} dans secrets.env) ; services redémarrés", flush=True)
    return 0


def _ecrire(
    instance: Path, cle: str, jeton: str, env: Mapping[str, str], retirer: tuple[str, ...] = ()
) -> None:
    try:
        ecrire_secret(instance / "secrets.env", cle, jeton, retirer)
    except OSError as erreur:
        raise AuthErreur(ETAPE_SECRETS, str(erreur)) from erreur
    try:
        # Tous les services lisent `secrets.env` ; `restart` ne relirait pas `env_file`.
        subprocess.run(
            ["docker", "compose", "-f", str(instance / "compose.yaml"), "up", "-d", "--force-recreate"],
            check=True,
            stdin=subprocess.DEVNULL,
            env=dict(env),
        )
    except (OSError, subprocess.CalledProcessError) as erreur:
        raise AuthErreur(ETAPE_REDEMARRAGE, str(erreur)) from erreur


def _setup_token(home: Path, utilisateur: str | None, env: Mapping[str, str]) -> str:
    """Lance `claude setup-token` dans un pseudo-terminal relié à celui de l’utilisateur :
    il y voit l’URL et y colle le code ; le token est relevé dans la sortie."""
    commande = ["claude", "setup-token"]
    if utilisateur:
        commande = ["runuser", "-u", utilisateur, "--", *commande]
    # Une identité Claude dans l’environnement court-circuiterait la connexion.
    env_claude = {k: v for k, v in env.items() if k not in CLAUDE.cles}
    env_claude["HOME"] = str(home)
    maitre, esclave = os.openpty()
    fcntl.ioctl(esclave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, _COLONNES, 0, 0))
    try:
        processus = subprocess.Popen(
            commande, stdin=esclave, stdout=esclave, stderr=esclave, env=env_claude,
            preexec_fn=controler,
        )
    except OSError as erreur:
        os.close(maitre)
        raise AuthErreur(ETAPE_SETUP_TOKEN, str(erreur)) from erreur
    finally:
        os.close(esclave)
    try:
        sortie = _relayer(maitre)
    finally:
        os.close(maitre)
    code = processus.wait()
    if code != 0:
        raise AuthErreur(ETAPE_SETUP_TOKEN, f"code {code}")
    jetons = _JETON_CLAUDE.findall(_ANSI.sub("", sortie.decode(errors="replace")))
    if not jetons:
        raise AuthErreur(
            ETAPE_SETUP_TOKEN,
            "aucun token dans sa sortie : copie-le et `… | sudo wap-runtime auth claude --with-token`",
        )
    return jetons[-1]


def _relayer(maitre: int) -> bytes:
    """Recopie la sortie du pseudo-terminal sur stdout et le clavier vers lui ; rend la sortie."""
    sortie = bytearray()
    entree = sys.stdin.fileno() if sys.stdin.isatty() else None
    sys.stdout.flush()
    # Le terminal de l’utilisateur en mode brut le temps du relais : `claude` gère l’écho.
    clavier, avant = entree, brut(entree) if entree is not None else None
    try:
        while True:
            lus, _, _ = select.select([maitre] + ([entree] if entree is not None else []), [], [])
            if maitre in lus:
                try:
                    morceau = os.read(maitre, 4096)
                except OSError:  # Linux : EIO quand l’enfant a fermé le terminal.
                    morceau = b""
                if not morceau:
                    return bytes(sortie)
                sortie += morceau
                sys.stdout.buffer.write(morceau)
                sys.stdout.buffer.flush()
            if entree is not None and entree in lus:
                frappe = os.read(entree, 1024)
                if frappe:
                    os.write(maitre, frappe)
                else:
                    entree = None
    finally:
        if clavier is not None:
            restaurer(clavier, avant)
