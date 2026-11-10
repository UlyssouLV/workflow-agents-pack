#!/bin/bash
# From a project root that already has agents/skills/: refresh pack-owned
# skills and hooks from this checkout. Adds names that exist only in the
# pack. Never deletes a skill or hook that exists only in the project.
# Does not touch AGENTS.md, README or .env. In adapter settings, only the
# entries of the pack hooks are (re)written (cabler-hooks.py).
#
# Usage: update-from-pack.sh [--with-docs] [--with-suivi]
#   --with-docs   scaffold docs-site if missing; else refresh PACK_OWNED paths
#                 and repair known defects left by older templates
#   --with-suivi  scaffold suivi-avancement if missing (role + README + template)
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

WITH_DOCS=0
WITH_SUIVI=0
for arg in "$@"; do
  case "$arg" in
    --with-docs) WITH_DOCS=1 ;;
    --with-suivi) WITH_SUIVI=1 ;;
    -h|--help)
      echo "Usage: $0 [--with-docs] [--with-suivi]" >&2
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg (attendu : --with-docs | --with-suivi)" >&2
      exit 1
      ;;
  esac
done

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$(pwd)"
REFS="$PACK/agents/skills/process/initialise-le-repo/references"

if [ ! -d "$TARGET/agents/skills" ]; then
  echo "À lancer à la racine d’un repo déjà initialisé (agents/skills/ introuvable)." >&2
  exit 1
fi
if [ ! -d "$PACK/agents/skills" ]; then
  echo "Pack incomplet : $PACK/agents/skills introuvable." >&2
  exit 1
fi

echo "Cible : $TARGET"
if git -C "$PACK" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Pack  : $(git -C "$PACK" rev-parse --short HEAD) — $(git -C "$PACK" log -1 --format='%s')"
else
  echo "Pack  : $PACK"
fi

updated=0
added=0

sync_skill() {
  local src="$1"
  local name bucket dest
  name="$(basename "$src")"
  bucket="$(basename "$(dirname "$src")")"
  dest=""
  if [ -d "$TARGET/agents/skills/meta/$name" ]; then
    dest="$TARGET/agents/skills/meta/$name"
  elif [ -d "$TARGET/agents/skills/process/$name" ]; then
    dest="$TARGET/agents/skills/process/$name"
  fi
  if [ -n "$dest" ]; then
    copier --delete --exclude .DS_Store --exclude __pycache__ "$src" "$dest"
    echo "skill  MAJ   $name"
    updated=$((updated + 1))
  else
    mkdir -p "$TARGET/agents/skills/$bucket"
    copier --exclude .DS_Store --exclude __pycache__ "$src" "$TARGET/agents/skills/$bucket/$name"
    echo "skill  AJOUT $name → agents/skills/$bucket/$name"
    added=$((added + 1))
  fi
}

sync_hook() {
  local src="$1"
  local name dest
  name="$(basename "$src")"
  dest="$TARGET/agents/hooks/$name"
  if [ -d "$dest" ]; then
    copier --delete --exclude .DS_Store --exclude __pycache__ "$src" "$dest"
    echo "hook   MAJ   $name"
    updated=$((updated + 1))
  else
    mkdir -p "$TARGET/agents/hooks"
    copier --exclude .DS_Store --exclude __pycache__ "$src" "$dest"
    echo "hook   AJOUT $name"
    added=$((added + 1))
  fi
}

for bucket in meta process; do
  pack_bucket="$PACK/agents/skills/$bucket"
  [ -d "$pack_bucket" ] || continue
  for skill in "$pack_bucket"/*/; do
    [ -d "$skill" ] || continue
    [ -f "${skill}SKILL.md" ] || continue
    sync_skill "$skill"
  done
done

if [ -d "$PACK/agents/hooks" ]; then
  for hook in "$PACK/agents/hooks"/*/; do
    [ -d "$hook" ] || continue
    sync_hook "$hook"
  done
fi

mkdir -p "$TARGET/agents/scripts"
# Tous les scripts du pack, pas une liste : un script ajouté au pack (ex.
# checks-requis.py, appelé par fusionner-pr et finaliser-la-version) ne peut
# plus être oublié. Les scripts propres au projet ne sont pas touchés.
for chemin in "$PACK"/agents/scripts/*.sh "$PACK"/agents/scripts/*.py; do
  [ -f "$chemin" ] || continue
  f="$(basename "$chemin")"
  copier "$chemin" "$TARGET/agents/scripts/$f"
  chmod +x "$TARGET/agents/scripts/$f" 2>/dev/null || true
done

# Adapter copies + settings entries of the pack hooks (same as adopter-le-pack.sh).
# An entry that runs the same pack hook is replaced, never doubled.
python3 "$PACK/agents/scripts/cabler-hooks.py" "$PACK" "$TARGET"

# Pack-owned process docs: skills point to them, so a project must not lag.
mkdir -p "$TARGET/agents/docs"
for f in integration-channel.md migrations-pack.md checks-requis.md; do
  copier "$PACK/agents/docs/$f" "$TARGET/agents/docs/$f"
done
copier "$PACK/agents/README.md" "$TARGET/agents/README.md"
# domain.md : conventions communes (les chemins du projet sont dans roles.yml).
copier "$PACK/agents/domain.md" "$TARGET/agents/domain.md"
# Guides: pack sections only. Project skills / hooks live in guide-projet.md;
# until /up has moved them there, keep the project's guides untouched.
if [ -f "$TARGET/agents/docs/guide-projet.md" ]; then
  for f in guide-skills.md guide-hooks.md; do
    copier "$PACK/agents/docs/$f" "$TARGET/agents/docs/$f"
  done
else
  echo "guides NON mis à jour : agents/docs/guide-projet.md absent (migration guides-projet de /up)"
fi
if [ ! -f "$TARGET/agents/docs/ecarts-avec-le-pack.md" ]; then
  copier "$REFS/ecarts-avec-le-pack.md" "$TARGET/agents/docs/ecarts-avec-le-pack.md"
  echo "créé   agents/docs/ecarts-avec-le-pack.md"
fi

# Templates stay in the pack: scaffold-docs-site.sh reads them from $PACK.
# Drop a copy left by an older update (duplicates docs-site/ for Sonar).
if [ "$TARGET" != "$PACK" ] && [ -d "$TARGET/agents/templates" ]; then
  rm -rf "$TARGET/agents/templates"
  echo "retiré agents/templates/ (lu depuis le pack, plus copié)"
fi

# --- docs-site ---
if [ "$WITH_DOCS" -eq 1 ]; then
  if [ -d "$TARGET/docs-site" ] && [ -f "$TARGET/docs-site/package.json" ]; then
    bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET" --force-owned
  else
    bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET"
  fi
else
  if [ ! -d "$TARGET/docs-site" ]; then
    echo "Astuce : pour ajouter Docusaurus + GitHub Pages → $0 --with-docs"
  fi
fi

# --- suivi ---
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
if "suivi-avancement:" in text:
    raise SystemExit(0)
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
PY
    echo "ajouté rôle suivi-avancement dans agents/roles.yml"
  fi
fi

(
  cd "$TARGET"
  python3 agents/scripts/dispatch.py
  python3 agents/scripts/dispatch.py --check
)

echo "Pack à jour : $updated mis à jour, $added ajouté(s). Rien de local n’a été effacé (hors agents/templates/ et chemins docs PACK_OWNED si --with-docs)."
