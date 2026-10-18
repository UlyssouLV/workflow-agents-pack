"""Registry des repos liés : `~/.wap-runtime/repos.toml` de l’instance.

Fichier absent = registry vide. Éditable à la main ; `setup` n’y touche pas.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from wap_runtime.fichiers import remplacer

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

NOM_REGISTRY = "repos.toml"
# Règles GitHub : owner en alphanumériques et tirets isolés, ni en tête ni en fin,
# 39 caractères au plus ; name en alphanumériques, `.`, `_`, `-`, hors `.` et `..`.
_OWNER = r"(?=[A-Za-z0-9-]{1,39}/)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
_NAME = r"(?!\.\.?$)[A-Za-z0-9._-]{1,100}"
_SLUG = re.compile(rf"{_OWNER}/{_NAME}")
# Identifiants cockpit (`Agent.id`) : Claude Code ou Cursor. Absents du fichier → opt-out.
AGENTS = ("claude", "cursor")


class RegistryErreur(Exception):
    """Refus ou registry illisible ; le message tient sur une ligne."""


@dataclass(frozen=True)
class RepoLie:
    slug: str
    nom: str | None = None
    pilote: bool = False
    agent: str = "claude"
    # Préférence Cursor (`repos.toml`) ; `None` = Auto (pas de `--model`). Claude l’ignore.
    modele: str | None = None

    def designe(self, slug: str) -> bool:
        """GitHub ignore la casse d’`owner/name`."""
        return self.slug.lower() == slug.lower()


def chemin_registry(instance: Path) -> Path:
    return instance / NOM_REGISTRY


def lire_registry(chemin: Path) -> list[RepoLie]:
    """Les repos liés, dans l’ordre du fichier ; liste vide si le fichier est absent."""
    try:
        donnees = tomllib.loads(chemin.read_text())
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as erreur:
        raise RegistryErreur(f"{chemin} illisible ({erreur})") from erreur
    entrees = donnees.get("repos", [])
    if not isinstance(entrees, list) or not all(
        isinstance(e, dict) and isinstance(e.get("slug"), str) for e in entrees
    ):
        raise RegistryErreur(f"{chemin} : chaque [[repos]] doit avoir un `slug`")
    return [_repo(e) for e in entrees]


def enregistrer(
    chemin: Path, slug: str, pilote: bool, agent: str, modele: str | None = None
) -> RepoLie:
    """Persiste le toggle Pilote, l’agent préféré et le modèle Cursor du repo lié `slug`."""
    if agent not in AGENTS:
        raise RegistryErreur(f"agent inconnu : {agent!r} (attendu {' ou '.join(AGENTS)})")
    repos = lire_registry(chemin)
    if not any(r.designe(slug) for r in repos):
        raise RegistryErreur(f"{slug} absent du registry")
    modele = _modele(modele)
    maj = [
        RepoLie(r.slug, r.nom, pilote, agent, modele) if r.designe(slug) else r
        for r in repos
    ]
    _ecrire(chemin, maj)
    return next(r for r in maj if r.designe(slug))


def ajouter(chemin: Path, slug: str, nom: str | None = None) -> RepoLie:
    if not _SLUG.fullmatch(slug):
        raise RegistryErreur(f"{slug!r} invalide : attendu owner/name GitHub")
    repos = lire_registry(chemin)
    if any(r.designe(slug) for r in repos):
        raise RegistryErreur(f"{slug} est déjà dans le registry")
    nouveau = RepoLie(slug, nom)
    _ecrire(chemin, [*repos, nouveau])
    return nouveau


def retirer(chemin: Path, slug: str) -> RepoLie:
    repos = lire_registry(chemin)
    trouves = [r for r in repos if r.designe(slug)]
    if not trouves:
        raise RegistryErreur(f"{slug} absent du registry : rien à retirer")
    _ecrire(chemin, [r for r in repos if r not in trouves])
    return trouves[0]


def _chaine_toml(valeur: str) -> str:
    # Une chaîne JSON est une chaîne de base TOML, sauf DEL que TOML veut échappé.
    return json.dumps(valeur, ensure_ascii=False).replace("\x7f", "\\u007f")


def _ecrire(chemin: Path, repos: list[RepoLie]) -> None:
    """Remplace le fichier d’un coup : le runtime ne lit jamais un fichier à moitié écrit."""
    blocs = ["# Repos liés de l’instance : `wap-runtime repo add|remove|list`.\n"]
    for repo in repos:
        bloc = f"\n[[repos]]\nslug = {json.dumps(repo.slug)}\n"
        if repo.nom is not None:
            bloc += f"nom = {_chaine_toml(repo.nom)}\n"
        bloc += f"pilote = {'true' if repo.pilote else 'false'}\n"
        bloc += f"agent = {_chaine_toml(repo.agent)}\n"
        if repo.modele is not None:
            bloc += f"modele = {_chaine_toml(repo.modele)}\n"
        blocs.append(bloc)
    # Lisible par l’utilisateur du conteneur.
    remplacer(chemin, "".join(blocs), 0o644)


def _modele(valeur: object) -> str | None:
    """Auto / vide : pas de champ. Un ID CLI est une chaîne non vide."""
    from wap_runtime.agents import id_modele

    if valeur is None:
        return None
    if not isinstance(valeur, str):
        raise RegistryErreur("chaque [[repos]] : `modele` doit être une chaîne")
    return id_modele(valeur)


def _repo(entree: dict) -> RepoLie:
    pilote = entree.get("pilote", False)
    agent = entree.get("agent", "claude")
    if not isinstance(pilote, bool):
        raise RegistryErreur("chaque [[repos]] : `pilote` doit être un booléen")
    if agent not in AGENTS:
        raise RegistryErreur(f"chaque [[repos]] : `agent` attendu {' ou '.join(AGENTS)}")
    nom = entree.get("nom")
    if nom is not None and not isinstance(nom, str):
        raise RegistryErreur("chaque [[repos]] : `nom` doit être une chaîne")
    return RepoLie(entree["slug"], nom, pilote, agent, _modele(entree.get("modele")))
