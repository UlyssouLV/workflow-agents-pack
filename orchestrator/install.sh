#!/usr/bin/env bash
# Provisionnement en une commande (ADR 0002) :
#   curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash
# Options sans interaction : WAP_REF, WAP_PORT, WAP_PACK_REF, WAP_DEBUG=1, GH_TOKEN, WAP_SKIP_AUTH=1
# (passées par l’environnement, ex. `| sudo WAP_PORT=9000 bash`) et transmises à
# `wap-runtime setup`. Seule la connexion GitHub peut interagir, sur /dev/tty (ADR 0003).
set -euo pipefail

if [ "${WAP_DEBUG:-}" = 1 ]; then
  set -x
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "KO — l’installation doit tourner en root : curl -fsSL …/orchestrator/install.sh | sudo bash" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
UTILISATEUR=orchestrator
HOME_UTILISATEUR="/home/$UTILISATEUR"
DEPOT=UlyssouLV/workflow-agents-pack
JOURNAL=/var/log/wap-runtime/install.log

mkdir -p "$(dirname "$JOURNAL")"
cd /

journaliser() {
  echo "[$(date -Iseconds)] $*" >> "$JOURNAL"
}

etape() {
  local nom=$1
  shift
  echo "→ $nom"
  journaliser "étape « $nom » : début"
  local code=0
  "$@" >> "$JOURNAL" 2>&1 || code=$?
  if [ "$code" -ne 0 ]; then
    journaliser "étape « $nom » : échec (code $code)"
    echo "KO — l’étape « $nom » a échoué (code $code) ; voir $JOURNAL" >&2
    exit 1
  fi
  journaliser "étape « $nom » : OK"
}

# Avant tout apt : hors Debian 12+ / Ubuntu 22.04+, Python < 3.10 ferait échouer pipx sans message clair.
# /etc/os-release n’existe que sur la machine cible.
# shellcheck source=/dev/null
OS_ID=$(. /etc/os-release 2>/dev/null && echo "${ID:-}") || OS_ID=
# shellcheck source=/dev/null
OS_VERSION=$(. /etc/os-release 2>/dev/null && echo "${VERSION_ID:-}") || OS_VERSION=
case "$OS_ID:$OS_VERSION" in
  debian:1[2-9]* | debian:[2-9][0-9]*) ;;
  ubuntu:2[2-9].* | ubuntu:[3-9][0-9].*) ;;
  *)
    echo "KO — plateforme non supportée : ${OS_ID:-inconnue} ${OS_VERSION:-(sans VERSION_ID)} ; plateformes supportées : Debian 12+ / Ubuntu 22.04+" >&2
    exit 2
    ;;
esac

paquets_de_base() {
  apt-get update
  apt-get install -y python3 pipx git curl
}

# Lit la liste de l’API des Releases sur stdin ; écrit le tag `orchestrator-vX.Y.Z`
# publié (ni brouillon ni prerelease) le plus haut, ou échoue s’il n’y en a pas.
derniere_release() {
  python3 -c '
import json, re, sys
tags = [
    (tuple(map(int, m.groups())), r["tag_name"])
    for r in json.load(sys.stdin)
    if not r.get("prerelease") and not r.get("draft")
    and (m := re.fullmatch(r"orchestrator-v(\d+)\.(\d+)\.(\d+)", r.get("tag_name") or ""))
]
if not tags:
    sys.exit(1)
print(max(tags)[1])
'
}

resoudre_wap_ref() {
  # API publique : aucun jeton (ADR 0013).
  local releases
  releases=$(curl -fsSL "https://api.github.com/repos/$DEPOT/releases?per_page=100") || {
    echo "KO — impossible de lister les Releases de $DEPOT ; passer WAP_REF=<ref>" >&2
    exit 1
  }
  WAP_REF=$(printf '%s' "$releases" | derniere_release) || {
    echo "KO — aucune Release orchestrator-vX.Y.Z publiée sur $DEPOT ; passer WAP_REF=<ref>" >&2
    exit 1
  }
  journaliser "dernière Release : $WAP_REF"
}

creer_utilisateur() {
  if ! id "$UTILISATEUR" > /dev/null 2>&1; then
    useradd --system --create-home --shell /bin/bash "$UTILISATEUR"
  fi
}

installer_wap_runtime() {
  local paquet="git+https://github.com/$DEPOT@$WAP_REF#subdirectory=orchestrator"
  # --force : réinstalle depuis WAP_REF, donc met à niveau ou change de ref un paquet existant.
  runuser -u "$UTILISATEUR" -- env HOME="$HOME_UTILISATEUR" pipx install --force "$paquet"
}

etape "python3, pipx, git, curl" paquets_de_base
# Ref du paquet (branche, tag ou commit), par défaut la dernière Release ; `setup` tire
# les images de ghcr à ce ref, ou les construit au même commit (ADR 0005, 0013).
if [ -z "${WAP_REF:-}" ]; then
  echo "→ dernière Release"
  resoudre_wap_ref
fi
echo "  ref du paquet : $WAP_REF"
etape "utilisateur $UTILISATEUR" creer_utilisateur
etape "paquet wap-runtime" installer_wap_runtime

# `setup` hérite de WAP_PORT, WAP_PACK_REF et WAP_DEBUG ; il nomme lui-même l’étape en échec.
exec "$HOME_UTILISATEUR/.local/bin/wap-runtime" setup
