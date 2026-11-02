#!/usr/bin/env python3
"""Câble les hooks du pack dans un projet (Claude Code + Cursor).

Usage : cabler-hooks.py <pack> <projet>

1. Copie les wrappers adapter de chaque hook du pack (agents/hooks/<nom>/) :
   .claude/hooks/<nom>.py et .cursor/hooks/<nom>.sh.
2. Fusionne les entrées du pack dans .claude/settings.json (clé hooks) et
   .cursor/hooks.json. Une entrée du projet qui lance le même hook du pack
   est **remplacée** (pas doublée) : une ancienne commande (`py -3`,
   `python3 agents/hooks/…`) laisse la place à la commande portable.
   Les hooks propres au projet et le reste des réglages ne bougent pas.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _lire(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    texte = chemin.read_text(encoding="utf-8").strip()
    return json.loads(texte) if texte else {}


def _hooks_lances(entree: dict, noms: list[str]) -> set[str]:
    texte = json.dumps(entree, ensure_ascii=False)
    return {nom for nom in noms if nom in texte}


def fusionner(existant: dict, entrant: dict, noms: list[str]) -> dict:
    sortie = dict(existant)
    for evenement, entrees in entrant.items():
        liste = list(sortie.get(evenement) or [])
        for entree in entrees:
            lances = _hooks_lances(entree, noms)
            memes = [i for i, e in enumerate(liste) if lances & _hooks_lances(e, noms)]
            if memes:
                # Remplacée à sa place ; un doublon éventuel disparaît.
                liste[memes[0]] = entree
                liste = [e for i, e in enumerate(liste) if i not in memes[1:]]
            else:
                liste.append(entree)
        sortie[evenement] = liste
    return sortie


def _copier(source: Path, cible: Path, executable: bool = False) -> None:
    if not source.exists() or source.resolve() == cible.resolve():
        return
    cible.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, cible)
    if executable:
        cible.chmod(cible.stat().st_mode | 0o111)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    pack, projet = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    noms = sorted(p.name for p in (pack / "agents" / "hooks").iterdir() if p.is_dir())

    for nom in noms:
        _copier(pack / ".claude" / "hooks" / f"{nom}.py", projet / ".claude" / "hooks" / f"{nom}.py")
        _copier(pack / ".cursor" / "hooks" / f"{nom}.sh", projet / ".cursor" / "hooks" / f"{nom}.sh", executable=True)

    refs = pack / "agents" / "skills" / "process" / "initialise-le-repo" / "references"
    claude_src = _lire(refs / "settings-hooks.json")
    claude_path = projet / ".claude" / "settings.json"
    claude = _lire(claude_path)
    claude["hooks"] = fusionner(claude.get("hooks") or {}, claude_src.get("hooks") or {}, noms)
    claude_path.parent.mkdir(parents=True, exist_ok=True)
    claude_path.write_text(json.dumps(claude, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cursor_src = _lire(pack / ".cursor" / "hooks.json")
    cursor_path = projet / ".cursor" / "hooks.json"
    cursor = _lire(cursor_path)
    cursor.setdefault("version", cursor_src.get("version", 1))
    cursor["hooks"] = fusionner(cursor.get("hooks") or {}, cursor_src.get("hooks") or {}, noms)
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(cursor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"câblé  hooks du pack ({', '.join(noms)}) — Claude + Cursor, hooks du projet conservés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
