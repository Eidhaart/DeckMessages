#!/usr/bin/env bash
# NETDECK//OS installer - user-level, no root needed.
#
#   ./install.sh               install `netdeck` command + app-menu launcher
#   ./install.sh --autostart   ...and launch the deck whenever you open a terminal
#   ./install.sh --uninstall   remove everything this script added
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/netdeck.py"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/netdeck"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APP_DIR/netdeck.desktop"
RC="$HOME/.bashrc"
MARK_BEGIN="# >>> netdeck autostart >>>"
MARK_END="# <<< netdeck autostart <<<"

red=$'\e[38;5;203m'; cyan=$'\e[38;5;87m'; yel=$'\e[38;5;227m'; dim=$'\e[38;5;95m'; rst=$'\e[0m'
say() { printf '%s◢%s %s\n' "$red" "$rst" "$*"; }

remove_autostart() {
  if [[ -f "$RC" ]] && grep -qF "$MARK_BEGIN" "$RC"; then
    sed -i "/$MARK_BEGIN/,/$MARK_END/d" "$RC"
    say "autostart removed from $RC"
  fi
}

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "$BIN" "$DESKTOP"
  remove_autostart
  say "netdeck uninstalled. config kept in ~/.config/netdeck, shards in ~/.local/share/netdeck"
  exit 0
fi

command -v python3 >/dev/null || { say "python3 is required (sudo apt install python3)"; exit 1; }
python3 -c 'import curses' 2>/dev/null || { say "python3 curses module missing"; exit 1; }

mkdir -p "$BIN_DIR" "$APP_DIR"
install -m 0755 "$SRC" "$BIN"
say "installed ${cyan}$BIN${rst}"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK//OS
GenericName=Cyberdeck Dashboard
Comment=Hijacked corp terminal for netrunners
Exec=$BIN
Icon=utilities-terminal
Terminal=true
Categories=System;Monitor;
Keywords=cyberpunk;dashboard;terminal;monitor;
EOF
say "app-menu launcher: ${cyan}$DESKTOP${rst}"

if [[ "${1:-}" == "--autostart" ]]; then
  remove_autostart
  cat >> "$RC" <<EOF
$MARK_BEGIN
# Open NETDECK//OS in every new interactive terminal (not inside the deck's own shell, tmux, or ssh).
if [[ \$- == *i* && -z "\${NETDECK:-}" && -z "\${TMUX:-}" && -z "\${SSH_CONNECTION:-}" && -t 1 ]]; then
  "$BIN"
fi
$MARK_END
EOF
  say "autostart enabled in ${cyan}$RC${rst} ${dim}(undo: ./install.sh --uninstall)${rst}"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "${yel}note:${rst} $BIN_DIR is not on your PATH - log out and back in, or add it to ~/.profile" ;;
esac

printf '\n%s   jack in with:%s netdeck%s\n\n' "$dim" "$yel" "$rst"
