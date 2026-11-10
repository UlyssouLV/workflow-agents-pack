#!/bin/bash
# Adopt the pack in a project that already has code. No /init, no README
# rewrite, no Sonar credentials. Creates missing skeleton/templates only.
# If agents/skills/ already exists, use update-from-pack.sh instead.
#
# Usage: adopter-le-pack.sh [--with-suivi] [--with-docs]
set -euo pipefail

# Copie : rsync s’il est installé, sinon Python (Git Bash sous Windows n’a
# pas rsync). Même fonction dans adopter-le-pack.sh, update-from-pack.sh et
# scaffold-docs-site.sh : la modifier dans les trois.
#   copier [--delete] [--exclude MOTIF]... SOURCE DESTINATION
# SOURCE dossier → son contenu va dans DESTINATION (rsync -a SOURCE/ DEST/).
# SOURCE fichier → copié vers DESTINATION.
# MOTIF : un nom ignoré à toute profondeur ; « /nom/ » : à la racine seulement.
# --delete : DESTINATION devient une copie exacte (sans Python, les fichiers
# exclus déjà présents dans DESTINATION sont aussi retirés).
PYTHON="$(command -v python3 || command -v python || true)"
copier() {
  local delete=0 exclusions=() motif
  while [ $# -gt 2 ]; do
    case "$1" in
      --delete) delete=1; shift ;;
      --exclude) exclusions+=("$2"); shift 2 ;;
      *) echo "copier : option inconnue $1" >&2; return 1 ;;
    esac
  done
  local src="${1%/}" dest="${2%/}"
  if command -v rsync >/dev/null 2>&1; then
    local args=(-a)
    [ "$delete" -eq 1 ] && args+=(--delete)
    for motif in ${exclusions[@]+"${exclusions[@]}"}; do
      args+=(--exclude "$motif")
    done
    if [ -d "$src" ]; then
      rsync "${args[@]}" "$src"/ "$dest"/
    else
      rsync "${args[@]}" "$src" "$dest"
    fi
    return
  fi
  if [ -z "$PYTHON" ]; then
    echo "copier : ni rsync ni python3/python introuvable" >&2
    return 1
  fi
  # « /nom/ » devient « ^nom » : Git Bash convertirait un argument qui
  # commence par « / » en chemin Windows avant de le passer à Python.
  local motifs=()
  for motif in ${exclusions[@]+"${exclusions[@]}"}; do
    case "$motif" in
      /*) motif="${motif#/}"; motifs+=("^${motif%/}") ;;
      *) motifs+=("${motif%/}") ;;
    esac
  done
  "$PYTHON" - "$src" "$dest" "$delete" ${motifs[@]+"${motifs[@]}"} <<'PY'
import os, shutil, stat, sys, time

src, dest, delete = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
racine = {m[1:] for m in sys.argv[4:] if m.startswith("^")}
partout = {m for m in sys.argv[4:] if not m.startswith("^")}

def rendre_inscriptible(fonction, chemin, _erreur):
    os.chmod(chemin, stat.S_IWRITE)
    fonction(chemin)

def supprimer(dossier):
    # Partage réseau Windows : un rmtree peut échouer (WinError 145) puis
    # passer quelques instants plus tard.
    for essai in range(1, 6):
        try:
            shutil.rmtree(dossier, onerror=rendre_inscriptible)
            return
        except OSError:
            if essai == 5:
                raise
            time.sleep(0.2 * essai)

if os.path.isfile(src):
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(src))
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    shutil.copy2(src, dest)
    sys.exit(0)

def ignorer(dossier, noms):
    ignores = {n for n in noms if n in partout}
    if dossier == src:
        ignores |= {n for n in noms if n in racine}
    return ignores

if delete and os.path.isdir(dest):
    supprimer(dest)
shutil.copytree(src, dest, symlinks=True, ignore=ignorer, dirs_exist_ok=True)
PY
}

WITH_SUIVI=0
WITH_DOCS=0
for arg in "$@"; do
  case "$arg" in
    --with-suivi) WITH_SUIVI=1 ;;
    --with-docs) WITH_DOCS=1 ;;
    -h|--help)
      echo "Usage: $0 [--with-suivi] [--with-docs]" >&2
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg (attendu : --with-suivi | --with-docs)" >&2
      exit 1
      ;;
  esac
done

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$(pwd)"
REFS="$PACK/agents/skills/process/initialise-le-repo/references"

if [ -d "$TARGET/agents/skills" ]; then
  echo "Le pack est déjà là (agents/skills/). Utilise update-from-pack.sh pour une mise à jour." >&2
  exit 1
fi
if [ ! -d "$PACK/agents/skills" ] || [ ! -f "$PACK/agents/scripts/dispatch.py" ]; then
  echo "Pack incomplet : $PACK/agents introuvable." >&2
  exit 1
fi
if [ ! -d "$REFS" ]; then
  echo "Pack incomplet : $REFS introuvable." >&2
  exit 1
fi

echo "Cible : $TARGET"
if git -C "$PACK" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Pack  : $(git -C "$PACK" rev-parse --short HEAD) — $(git -C "$PACK" log -1 --format='%s')"
else
  echo "Pack  : $PACK"
fi

mkdir -p "$TARGET/agents"
# templates/ stays in the pack: scaffold-docs-site.sh reads it from $PACK.
copier --exclude .DS_Store --exclude __pycache__ --exclude /templates/ \
  "$PACK/agents" "$TARGET/agents"
echo "copié  agents/ (sans templates/)"

if [ ! -f "$TARGET/docs/dev/feuille-de-route/feuille-de-route-dev.md" ]; then
  mkdir -p "$TARGET/docs/dev/feuille-de-route" "$TARGET/docs/dev/recherches"
  printf '%s\n' '# Feuille de route de dev' > "$TARGET/docs/dev/feuille-de-route/feuille-de-route-dev.md"
  echo "créé   docs/dev/feuille-de-route/feuille-de-route-dev.md"
fi
if [ ! -f "$TARGET/docs/dev/feuille-de-route/README.md" ] && [ -f "$REFS/feuille-de-route/README.md" ]; then
  mkdir -p "$TARGET/docs/dev/feuille-de-route"
  copier "$REFS/feuille-de-route/README.md" "$TARGET/docs/dev/feuille-de-route/README.md"
  echo "créé   docs/dev/feuille-de-route/README.md"
fi
mkdir -p "$TARGET/docs/specs" "$TARGET/docs/adr"
if [ ! -f "$TARGET/docs/glossaire.md" ]; then
  mkdir -p "$TARGET/docs"
  printf '%s\n' '# Glossary' > "$TARGET/docs/glossaire.md"
  echo "créé   docs/glossaire.md"
fi

if [ "$WITH_SUIVI" -eq 1 ]; then
  mkdir -p "$TARGET/docs/suivi-avancement"
  if [ ! -f "$TARGET/docs/suivi-avancement/README.md" ] && [ -f "$REFS/suivi-avancement/README.md" ]; then
    copier "$REFS/suivi-avancement/README.md" "$TARGET/docs/suivi-avancement/README.md"
    echo "créé   docs/suivi-avancement/README.md"
  fi
  if [ ! -f "$TARGET/docs/suivi-avancement/template-semaine.html" ] && [ -f "$REFS/suivi-avancement/template-semaine.html" ]; then
    copier "$REFS/suivi-avancement/template-semaine.html" "$TARGET/docs/suivi-avancement/template-semaine.html"
    echo "créé   docs/suivi-avancement/template-semaine.html"
  fi
  if [ -f "$TARGET/agents/roles.yml" ] && ! grep -q 'suivi-avancement:' "$TARGET/agents/roles.yml"; then
    python3 - "$TARGET/agents/roles.yml" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
block = """  suivi-avancement:
    paths:
      - docs/suivi-avancement/
"""
# Insert after roadmap block if present, else append under roles:
if "suivi-avancement:" in text:
    pass
elif "  roadmap:" in text:
    # after roadmap paths list — insert before next top-level role key under roles
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    inserted = False
    while i < len(lines):
        out.append(lines[i])
        if not inserted and lines[i].startswith("  roadmap:"):
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
                out.append(lines[i])
                i += 1
            out.append(block if block.endswith("\n") else block + "\n")
            inserted = True
            continue
        i += 1
    if not inserted:
        out.append(block if block.endswith("\n") else block + "\n")
    path.write_text("".join(out))
else:
    path.write_text(text.rstrip() + "\n" + block)
PY
    echo "ajouté rôle suivi-avancement dans agents/roles.yml"
  fi
fi

if [ ! -f "$TARGET/AGENTS.md" ]; then
  copier "$REFS/AGENTS.md" "$TARGET/AGENTS.md"
  echo "créé   AGENTS.md"
fi
if [ ! -f "$TARGET/.claude/CLAUDE.md" ]; then
  mkdir -p "$TARGET/.claude"
  copier "$REFS/CLAUDE.md" "$TARGET/.claude/CLAUDE.md"
  echo "créé   .claude/CLAUDE.md"
fi

python3 "$PACK/agents/scripts/cabler-hooks.py" "$PACK" "$TARGET"
if [ ! -f "$TARGET/agents/docs/ecarts-avec-le-pack.md" ]; then
  copier "$REFS/ecarts-avec-le-pack.md" "$TARGET/agents/docs/ecarts-avec-le-pack.md"
  echo "créé   agents/docs/ecarts-avec-le-pack.md"
fi

(
  cd "$TARGET"
  python3 agents/scripts/dispatch.py
  python3 agents/scripts/dispatch.py --check
)

if [ "$WITH_DOCS" -eq 1 ]; then
  bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET"
fi

echo "Sonar : désactivé (pas de credentials). /qg skippe tant que SONAR_* n’est pas dans .env."
if [ "$WITH_SUIVI" -eq 1 ]; then
  echo "Suivi : activé (docs/suivi-avancement/ + rôle)."
else
  echo "Suivi : non activé (passe --with-suivi pour le scaffold). Finalise soft-skip /msa."
fi
if [ "$WITH_DOCS" -eq 1 ]; then
  echo "Docs : activé (docs-site/ + workflow Pages). Active GitHub Pages → Actions après push."
else
  echo "Docs : non activé (passe --with-docs, ou plus tard update-from-pack.sh --with-docs)."
fi
echo "Ne lance pas /init : le README du projet est inchangé."
echo "Pack adopté."
