#!/bin/bash
# Scaffold or refresh the generic Docusaurus docs-site in a target repo.
# Usage (from pack or via PATH):
#   scaffold-docs-site.sh <TARGET_REPO_ROOT> [--force-owned]
# --force-owned : when docs-site already exists, overwrite PACK_OWNED.txt paths only
# Without existing docs-site: full copy + stubs + workflow + roles.yml role.
# --force-owned also repairs known defects left by older templates (see
# repair_known_defects).
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

TARGET="${1:-}"
MODE_FORCE_OWNED=0
shift || true
for arg in "$@"; do
  case "$arg" in
    --force-owned) MODE_FORCE_OWNED=1 ;;
    *)
      echo "Option inconnue : $arg" >&2
      exit 1
      ;;
  esac
done

if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "Usage: $0 <TARGET_REPO_ROOT> [--force-owned]" >&2
  exit 1
fi

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TMPL="$PACK/agents/templates/docs-site"
STUBS="$PACK/agents/templates/docs-stubs"
WF_DIR="$PACK/agents/templates/github/workflows"
# First line of a pack-managed workflow; a project removes it to keep its own.
WF_MARQUEUR="# Géré par workflow-agents-pack"

if [ ! -d "$TMPL" ] || [ ! -f "$TMPL/package.json" ]; then
  echo "Template introuvable : $TMPL" >&2
  echo "Lance ce script depuis un clone du pack (bash <pack>/agents/scripts/scaffold-docs-site.sh <cible>)." >&2
  exit 1
fi

# Resolve owner/repo from git remote
OWNER="OWNER"
REPO="REPO"
TITLE="Documentation"
TAGLINE="Documentation du projet — produit, features et décisions"
if git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  remote="$(git -C "$TARGET" remote get-url origin 2>/dev/null || true)"
  if [[ "$remote" =~ github.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    OWNER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
  fi
  # Prefer README H1 or package name later — default to repo name
  TITLE="$REPO"
fi

apply_placeholders() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return
  fi
  OWNER="$OWNER" REPO="$REPO" TITLE="$TITLE" TAGLINE="$TAGLINE" python3 - "$file" <<'PY'
import os, sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
for key in ("OWNER", "REPO", "TITLE", "TAGLINE"):
    text = text.replace(f"__{key}__", os.environ[key])
path.write_text(text)
PY
}

add_docs_site_role() {
  local roles="$TARGET/agents/roles.yml"
  if [ ! -f "$roles" ]; then
    echo "avertissement : agents/roles.yml absent — rôle docs-site non ajouté" >&2
    return
  fi
  if grep -q 'docs-site:' "$roles"; then
    return
  fi
  python3 - "$roles" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
block = """  docs-site:
    paths:
      - docs-site/
"""
if "docs-site:" in text:
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
  echo "ajouté rôle docs-site dans agents/roles.yml"
}

# Vrai si la page existe en .md ou en .mdx (chemin sans extension) :
# Docusaurus refuse deux docs au même id (index.md à côté d'index.mdx).
page_existe() {
  [ -f "$1.md" ] || [ -f "$1.mdx" ]
}

# Vrai si le dossier a déjà une page d'index de catégorie : index, README ou
# <nom du dossier>, en .md ou .mdx. Elles ont toutes la même URL.
index_existe() {
  local dossier="$1" nom
  for nom in index README "$(basename "$dossier")"; do
    page_existe "$dossier/$nom" && return 0
  done
  return 1
}

copy_stubs() {
  mkdir -p "$TARGET/docs/changelog" "$TARGET/docs/bugs" "$TARGET/docs/feuille-de-route" "$TARGET/docs/features" "$TARGET/docs/adr"
  for pair in \
    "changelog/README.md:docs/changelog/README.md" \
    "bugs/README.md:docs/bugs/README.md" \
    "feuille-de-route/README.md:docs/feuille-de-route/README.md" \
    "features/index.md:docs/features/index.md"
  do
    src="${pair%%:*}"
    dest="${pair##*:}"
    if ! index_existe "$TARGET/$(dirname "$dest")" && [ -f "$STUBS/$src" ]; then
      mkdir -p "$(dirname "$TARGET/$dest")"
      copier "$STUBS/$src" "$TARGET/$dest"
      echo "créé   $dest"
    fi
  done
  # An empty docs/adr/ leaves adrSidebar with nothing to link to: build fails.
  if [ -z "$(find "$TARGET/docs/adr" -maxdepth 1 \( -name '*.md' -o -name '*.mdx' \) -print -quit)" ]; then
    copier "$STUBS/adr/index.md" "$TARGET/docs/adr/index.md"
    echo "créé   docs/adr/index.md"
  fi
  if ! page_existe "$TARGET/docs/glossaire"; then
    printf '%s\n' '# Glossary' > "$TARGET/docs/glossaire.md"
    echo "créé   docs/glossaire.md"
  fi
}

copy_workflow() {
  mkdir -p "$TARGET/.github/workflows"
  local deploy="$TARGET/.github/workflows/deploy-docs.yml"
  local build="$TARGET/.github/workflows/build-docs.yml"
  local deploy_gere=0
  if [ ! -f "$deploy" ]; then
    copier "$WF_DIR/deploy-docs.yml" "$deploy"
    echo "créé   .github/workflows/deploy-docs.yml"
    deploy_gere=1
  elif head -n 1 "$deploy" | grep -q "^$WF_MARQUEUR"; then
    copier "$WF_DIR/deploy-docs.yml" "$deploy"
    echo "MAJ    .github/workflows/deploy-docs.yml"
    deploy_gere=1
  else
    echo "gardé  .github/workflows/deploy-docs.yml (personnalisé : pas de ligne « $WF_MARQUEUR »)"
  fi
  # build-docs.yml is called by the pack's deploy-docs.yml.
  if [ ! -f "$build" ]; then
    if [ "$deploy_gere" -eq 1 ]; then
      copier "$WF_DIR/build-docs.yml" "$build"
      echo "créé   .github/workflows/build-docs.yml"
    fi
  elif head -n 1 "$build" | grep -q "^$WF_MARQUEUR"; then
    copier "$WF_DIR/build-docs.yml" "$build"
    echo "MAJ    .github/workflows/build-docs.yml"
  else
    echo "gardé  .github/workflows/build-docs.yml (personnalisé)"
  fi
}

# package.json: pack dependencies added or bumped, pack scripts added,
# project scripts and extra dependencies kept (a project may chain its own
# steps in prebuild). Then: npm install in docs-site/.
merge_package_json() {
  python3 - "$TMPL/package.json" "$TARGET/docs-site/package.json" <<'PY2'
import json
import sys
from pathlib import Path

pack = json.loads(Path(sys.argv[1]).read_text())
cible_path = Path(sys.argv[2])
projet = json.loads(cible_path.read_text())
for cle in ("dependencies", "devDependencies"):
    fusion = dict(projet.get(cle) or {})
    fusion.update(pack.get(cle) or {})
    projet[cle] = dict(sorted(fusion.items()))
scripts = dict(projet.get("scripts") or {})
for nom, commande in (pack.get("scripts") or {}).items():
    scripts.setdefault(nom, commande)
projet["scripts"] = scripts
cible_path.write_text(json.dumps(projet, indent=2, ensure_ascii=False) + "\n")
PY2
  echo "fusion docs-site/package.json (scripts du projet gardés)"
}

sync_owned_only() {
  local owned="$TMPL/PACK_OWNED.txt"
  if [ ! -f "$owned" ]; then
    echo "PACK_OWNED.txt introuvable" >&2
    exit 1
  fi
  while IFS= read -r rel || [ -n "$rel" ]; do
    # Checkout Windows (core.autocrlf) : PACK_OWNED.txt arrive en CRLF ; sans
    # retirer le \r, aucun chemin n'existe et rien n'est rafraîchi, en silence.
    rel="${rel%$'\r'}"
    [[ -z "$rel" || "$rel" =~ ^# ]] && continue
    if [ "$rel" = "package.json" ] && [ -f "$TARGET/docs-site/package.json" ]; then
      merge_package_json
    elif [ -e "$TMPL/$rel" ]; then
      mkdir -p "$(dirname "$TARGET/docs-site/$rel")"
      copier "$TMPL/$rel" "$TARGET/docs-site/$rel"
      echo "MAJ    docs-site/$rel"
    fi
  done < "$owned"
  copy_workflow
}

# Known defects left by older templates in a project's docs-site/ (files
# outside PACK_OWNED): tsconfig pointing outside docs-site or not extending
# @docusaurus/tsconfig, data stubs with the wrong JSON shape, @font-face
# reading a file outside docs-site, static/ without any file. Valid project
# content is left alone.
repair_known_defects() {
  python3 - "$TARGET/docs-site" "$TMPL" <<'PY'
import json, re, shutil, sys
from pathlib import Path
site, tmpl = Path(sys.argv[1]), Path(sys.argv[2])

def report(rel):
    print(f"réparé docs-site/{rel}")

# A path that leaves docs-site/ is a defect only when it leads nowhere: old
# templates carried BBASS's ../poste/… paths into projects without poste/.
# A project that points at its own sources on purpose (they exist) is kept.
def chemin_absent(base, relatif):
    propre = relatif.split("*")[0].split("?")[0].split("#")[0]
    return not (base / propre).exists()

rel = "tsconfig.json"
cfg = site / rel
try:
    tsconfig = json.loads(cfg.read_text())
    externes = [
        cible
        for cibles in ((tsconfig.get("compilerOptions") or {}).get("paths") or {}).values()
        for cible in cibles
        if cible.startswith("../")
    ]
    if isinstance(tsconfig.get("extends"), str) and tsconfig["extends"].startswith("../"):
        externes.append(tsconfig["extends"])
    casse = any(chemin_absent(site, cible) for cible in externes)
except (OSError, ValueError, AttributeError, TypeError):
    casse = True
if casse:
    shutil.copyfile(tmpl / rel, cfg)
    report(rel)

shapes = {
    "src/data/bugs.json": lambda d: isinstance(d, dict) and isinstance(d.get("bugs"), list),
    "src/data/changelog.json": lambda d: isinstance(d, list),
    "src/data/feuille-de-route.json": lambda d: isinstance(d, dict)
        and isinstance(d.get("versions"), list) and isinstance(d.get("plusTard"), list),
}
for rel, valid in shapes.items():
    data = site / rel
    try:
        ok = valid(json.loads(data.read_text()))
    except (OSError, ValueError):
        ok = False
    if not ok:
        data.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmpl / rel, data)
        report(rel)

# Docusaurus fails the build on a static/ without any file (git drops
# empty dirs, so older scaffolds from a pack clone had none).
static = site / "static"
if not static.is_dir() or not any(p.is_file() for p in static.rglob("*")):
    static.mkdir(exist_ok=True)
    (static / ".nojekyll").touch()
    report("static/.nojekyll")

rel = "src/css/custom.css"
css = site / rel
if css.exists():
    text = css.read_text()
    def sans_police_absente(bloc):
        url = re.search(r"url\(\s*[\"']?([^\"')]+)", bloc.group(0))
        if url and url.group(1).startswith("../") and chemin_absent(css.parent, url.group(1)):
            return ""
        return bloc.group(0)

    cleaned = re.sub(r"@font-face\s*\{[^}]*\}\s*", sans_police_absente, text)
    if cleaned != text:
        css.write_text(cleaned)
        report(rel)
PY
}

print_next_steps() {
  echo "Étapes suivantes :"
  echo "  cd docs-site && npm install && npm run typecheck"
  echo "  GitHub → Settings → Pages → Source : GitHub Actions (après le premier push)"
}

if [ -d "$TARGET/docs-site" ] && [ -f "$TARGET/docs-site/package.json" ]; then
  if [ "$MODE_FORCE_OWNED" -eq 1 ]; then
    echo "docs-site présent — sync chemins PACK_OWNED uniquement"
    sync_owned_only
    repair_known_defects
    add_docs_site_role
    copy_stubs
    print_next_steps
  else
    echo "docs-site déjà présent — rien (passe --force-owned pour rafraîchir les fichiers pack)"
  fi
  exit 0
fi

echo "Scaffold docs-site → $TARGET (owner=$OWNER repo=$REPO)"
mkdir -p "$TARGET/docs-site"
copier --exclude .DS_Store --exclude node_modules --exclude build --exclude .docusaurus \
  "$TMPL" "$TARGET/docs-site"
apply_placeholders "$TARGET/docs-site/docusaurus.config.ts"
copy_stubs
copy_workflow
add_docs_site_role
echo "docs-site prêt."
print_next_steps
