#!/bin/bash
# Ouvre une conversation Claude Code vierge sur /implement #<n> (nouvelle fenêtre
# de terminal), ou délègue à $WAP_ENCHAINER quand il est défini (session du
# runner de l’orchestrateur, ADR 0006). Ne ferme / clear pas la session courante.
# Usage : bash agents/scripts/enchainer-implement.sh <n>
# Ne remplace pas /implement dans Cursor Agent chat.
set -euo pipefail

N="${1:-}"
if ! [[ "$N" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 <numéro-issue-enfant>" >&2
  exit 1
fi

REPO="$(pwd)"
if [ ! -d "$REPO/agents/skills" ]; then
  echo "À lancer à la racine d’un repo agents (agents/skills/ introuvable)." >&2
  exit 1
fi

# Point d’extension (runner) : avant tout backend local / test d’OS.
if [ -n "${WAP_ENCHAINER:-}" ]; then
  # Word-splitting voulu : WAP_ENCHAINER = commande + args (ex. "wap-runtime enchainer").
  # shellcheck disable=SC2086
  $WAP_ENCHAINER "$N"
  exit $?
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "claude introuvable dans le PATH." >&2
  exit 1
fi

PROMPT="/implement #${N}"
# shellcheck disable=SC2016
INNER=$(printf 'cd %q && exec claude %q' "$REPO" "$PROMPT")

ouvrir_macos() {
  osascript \
    -e 'on run argv' \
    -e 'set repo to item 1 of argv' \
    -e 'set n to item 2 of argv' \
    -e 'set cmd to "cd " & quoted form of repo & " && exec claude \"/implement #" & n & "\""' \
    -e 'tell application "Terminal"' \
    -e '  activate' \
    -e '  do script cmd' \
    -e 'end tell' \
    -e 'end run' \
    -- "$REPO" "$N"
}

ouvrir_linux() {
  if [ -n "${TERMINAL:-}" ] && command -v "$TERMINAL" >/dev/null 2>&1; then
    case "$TERMINAL" in
      gnome-terminal|gnome-terminal.real)
        "$TERMINAL" -- bash -lc "$INNER" &
        return 0
        ;;
      *)
        "$TERMINAL" -e bash -lc "$INNER" &
        return 0
        ;;
    esac
  fi
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "$INNER" &
    return 0
  fi
  if command -v konsole >/dev/null 2>&1; then
    konsole -e bash -lc "$INNER" &
    return 0
  fi
  if command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal -e "bash -lc $(printf %q "$INNER")" &
    return 0
  fi
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -lc "$INNER" &
    return 0
  fi
  if command -v xterm >/dev/null 2>&1; then
    xterm -e bash -lc "$INNER" &
    return 0
  fi
  echo "Enchaînement auto : aucun terminal graphique trouvé (TERMINAL, gnome-terminal, konsole, xfce4-terminal, x-terminal-emulator, xterm)." >&2
  return 1
}

# Windows (Git Bash / MSYS / Cygwin) : la fenêtre s'ouvre dans le clone et y
# lance claude sous PowerShell, pour que la session se retrouve dans
# `claude --resume` depuis le clone. Jamais `bash` : wt.exe / cmd.exe le
# cherchent dans le PATH Windows et tombent sur celui de WSL.
ouvrir_windows() {
  local dossier ps commande q
  dossier="$(cygpath -w "$REPO" 2>/dev/null || true)"
  if [ -z "$dossier" ] || [ ! -d "$(cygpath -u "$dossier" 2>/dev/null || true)" ]; then
    echo "Enchaînement auto : dossier du clone introuvable côté Windows (${dossier:-$REPO})." >&2
    return 1
  fi
  ps="$(command -v pwsh || command -v pwsh.exe || command -v powershell.exe || command -v powershell || true)"
  if [ -z "$ps" ]; then
    echo "Enchaînement auto : PowerShell introuvable (ni pwsh ni powershell)." >&2
    return 1
  fi
  ps="$(cygpath -w "$ps")"
  # Prompt entre apostrophes PowerShell (une apostrophe se double).
  local q="'"
  commande="& claude '${PROMPT//$q/$q$q}'"
  # MSYS réécrit les args qui commencent par / (/c, /D) : conversion coupée.
  if command -v wt.exe >/dev/null 2>&1; then
    MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1       wt.exe new-tab -d "$dossier" "$ps" -NoLogo -Command "$commande"
    return $?
  fi
  if command -v cmd.exe >/dev/null 2>&1; then
    MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1       cmd.exe /c start "" /D "$dossier" "$ps" -NoLogo -Command "$commande"
    return $?
  fi
  echo "Enchaînement auto : ni wt.exe ni cmd.exe pour ouvrir une nouvelle fenêtre." >&2
  return 1
}

OS="$(uname -s)"
case "$OS" in
  Darwin)
    ouvrir_macos
    ;;
  Linux)
    ouvrir_linux
    ;;
  MINGW*|MSYS*|CYGWIN*)
    ouvrir_windows
    ;;
  *)
    echo "Enchaînement auto : OS non supporté ($OS). Définis WAP_ENCHAINER, ou ouvre une session Claude et lance /implement #${N}." >&2
    exit 1
    ;;
esac

echo "Session Claude ouverte : /implement #$N"
