"""Hooks d’activité en portée utilisateur dans le HOME du runner.

Fusionnés à chaque démarrage avec les réglages existants ; aucun fichier du clone.
Cursor (CLI épinglée) : `beforeSubmitPrompt`, `stop`, `postToolUse` — pas de `Notification`.
"""

from __future__ import annotations

import os
from pathlib import Path

from wap_runtime.permissions_enchainer import _ecrire_json, _lire_json, _sous_racine

ETAT_TRAVAILLE = "wap-runtime etat travaille"
ETAT_ATTEND = "wap-runtime etat attend"

# (événement, commande, matcher ou None)
CLAUDE_HOOKS = (
    ("UserPromptSubmit", ETAT_TRAVAILLE, None),
    ("Stop", ETAT_ATTEND, None),
    ("Notification", ETAT_ATTEND, None),
    ("PostToolUse", ETAT_TRAVAILLE, "Skill"),
)
CURSOR_HOOKS = (
    ("beforeSubmitPrompt", ETAT_TRAVAILLE, None),
    ("stop", ETAT_ATTEND, None),
    ("postToolUse", ETAT_TRAVAILLE, "Skill"),
)

_CLAUDE_RELATIF = (".claude", "settings.json")
_CURSOR_RELATIF = (".cursor", "hooks.json")


def assurer(home: Path) -> None:
    """Ajoute les hooks d’activité sous `home` s’ils manquent."""
    racine = os.path.realpath(home.expanduser())
    _fusionner_claude(_sous_racine(racine, *_CLAUDE_RELATIF))
    _fusionner_cursor(_sous_racine(racine, *_CURSOR_RELATIF))


def _fusionner_claude(chemin: Path) -> None:
    data = _lire_json(chemin)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{chemin} : hooks doit être un objet")
    for event, commande, matcher in CLAUDE_HOOKS:
        liste = hooks.setdefault(event, [])
        if not isinstance(liste, list):
            raise ValueError(f"{chemin} : hooks.{event} doit être une liste")
        if _claude_deja(liste, commande, matcher):
            continue
        bloc: dict = {"hooks": [{"type": "command", "command": commande}]}
        if matcher:
            bloc["matcher"] = matcher
        liste.append(bloc)
    _ecrire_json(chemin, data)


def _claude_deja(liste: list, commande: str, matcher: str | None) -> bool:
    for bloc in liste:
        if not isinstance(bloc, dict):
            continue
        if matcher is not None and bloc.get("matcher") != matcher:
            continue
        for hook in bloc.get("hooks") or []:
            if isinstance(hook, dict) and hook.get("command") == commande:
                return True
    return False


def _fusionner_cursor(chemin: Path) -> None:
    data = _lire_json(chemin)
    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{chemin} : hooks doit être un objet")
    for event, commande, matcher in CURSOR_HOOKS:
        liste = hooks.setdefault(event, [])
        if not isinstance(liste, list):
            raise ValueError(f"{chemin} : hooks.{event} doit être une liste")
        if any(
            isinstance(h, dict)
            and h.get("command") == commande
            and (matcher is None or h.get("matcher") == matcher)
            for h in liste
        ):
            continue
        entree: dict = {"command": commande}
        if matcher:
            entree["matcher"] = matcher
        liste.append(entree)
    _ecrire_json(chemin, data)


def main() -> int:
    assurer(Path.home())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
