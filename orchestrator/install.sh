#!/usr/bin/env bash
# Provisionnement en une commande (ADR 0002) :
#   curl -fsSL https://raw.githubusercontent.com/UlyssouLV/workflow-agents-pack/feat/runtime-orchestrator/orchestrator/install.sh | sudo bash
# Options sans interaction : WAP_PORT, WAP_PACK_REF, WAP_DEBUG=1 (passées par
# l’environnement, ex. `| sudo WAP_PORT=9000 bash`) et transmises à `wap-runtime setup`.
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
PAQUET="git+https://github.com/UlyssouLV/workflow-agents-pack@feat/runtime-orchestrator#subdirectory=orchestrator"
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
OS_ID=$(. /etc/os-release 2>/dev/null && echo "${ID:-}") || OS_ID=
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
  apt-get install -y python3 pipx git
}

creer_utilisateur() {
  if ! id "$UTILISATEUR" > /dev/null 2>&1; then
    useradd --system --create-home --shell /bin/bash "$UTILISATEUR"
  fi
}

installer_wap_runtime() {
  # --force : réinstalle depuis la branche de base, donc met à niveau un paquet existant.
  runuser -u "$UTILISATEUR" -- env HOME="$HOME_UTILISATEUR" pipx install --force "$PAQUET"
}

etape "python3, pipx, git" paquets_de_base
etape "utilisateur $UTILISATEUR" creer_utilisateur
etape "paquet wap-runtime" installer_wap_runtime

# `setup` hérite de WAP_PORT, WAP_PACK_REF et WAP_DEBUG ; il nomme lui-même l’étape en échec.
exec "$HOME_UTILISATEUR/.local/bin/wap-runtime" setup
