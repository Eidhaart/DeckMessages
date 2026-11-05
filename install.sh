#!/usr/bin/env bash
# NETDECK//OS installer - user-level, no root needed.
#
#   ./install.sh                  install the `netdeck` command + app-menu launcher
#   ./install.sh --login          ...and open the deck fullscreen every time you log in   (recommended)
#   ./install.sh --every-terminal ...and open the deck in every new terminal window
#   ./install.sh --login --every-terminal   both
#   ./install.sh --uninstall      remove everything this script added
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/netdeck"
SESSION="$BIN_DIR/netdeck-session"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APP_DIR/netdeck.desktop"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
AUTOSTART="$AUTOSTART_DIR/netdeck.desktop"
RC="$HOME/.bashrc"
MARK_BEGIN="# >>> netdeck autostart >>>"
MARK_END="# <<< netdeck autostart <<<"

red=$'\e[38;5;203m'; cyan=$'\e[38;5;87m'; yel=$'\e[38;5;227m'; dim=$'\e[38;5;95m'; rst=$'\e[0m'
say() { printf '%s◢%s %s\n' "$red" "$rst" "$*"; }

LOGIN=0; TERMINAL=0; UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --login|--boot)                LOGIN=1 ;;
    --every-terminal|--autostart)  TERMINAL=1 ;;
    --uninstall)                   UNINSTALL=1 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) say "unknown option: $arg (try --help)"; exit 1 ;;
  esac
done

remove_terminal_autostart() {
  if [[ -f "$RC" ]] && grep -qF "$MARK_BEGIN" "$RC"; then
    sed -i "/$MARK_BEGIN/,/$MARK_END/d" "$RC"
    say "terminal autostart removed from $RC"
  fi
}

if (( UNINSTALL )); then
  rm -f "$BIN" "$SESSION" "$DESKTOP"
  [[ -f "$AUTOSTART" ]] && rm -f "$AUTOSTART" && say "login autostart removed"
  remove_terminal_autostart
  say "netdeck uninstalled. config kept in ~/.config/netdeck, shards in ~/.local/share/netdeck"
  exit 0
fi

command -v python3 >/dev/null || { say "python3 is required (sudo apt install python3)"; exit 1; }
python3 -c 'import curses' 2>/dev/null || { say "python3 curses module missing"; exit 1; }

mkdir -p "$BIN_DIR" "$APP_DIR"
install -m 0755 "$HERE/netdeck.py" "$BIN"
install -m 0755 "$HERE/netdeck-session.sh" "$SESSION"
say "installed ${cyan}$BIN${rst}"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK//OS
GenericName=Cyberdeck Dashboard
Comment=Hijacked corp terminal for netrunners
Exec=$SESSION
Icon=utilities-terminal
Terminal=false
Categories=System;Monitor;
Keywords=cyberpunk;dashboard;terminal;monitor;
EOF
say "app-menu launcher: ${cyan}NETDECK//OS${rst} ${dim}(opens fullscreen)${rst}"

if (( LOGIN )); then
  mkdir -p "$AUTOSTART_DIR"
  cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK//OS
Comment=Boot into the cyberdeck on login
Exec=$SESSION
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=2
EOF
  say "login autostart: ${cyan}$AUTOSTART${rst}"
  say "the deck now boots fullscreen every time you log in"
fi

if (( TERMINAL )); then
  remove_terminal_autostart
  cat >> "$RC" <<EOF
$MARK_BEGIN
# Open NETDECK//OS in every new interactive terminal (not inside the deck's own shell, tmux, or ssh).
if [[ \$- == *i* && -z "\${NETDECK:-}" && -z "\${TMUX:-}" && -z "\${SSH_CONNECTION:-}" && -t 1 ]]; then
  "$BIN"
fi
$MARK_END
EOF
  say "terminal autostart enabled in ${cyan}$RC${rst}"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "${yel}note:${rst} $BIN_DIR is not on your PATH yet - log out and back in (Ubuntu adds it automatically)" ;;
esac

if (( LOGIN )); then
  printf '\n%s   try it now:%s netdeck-session%s   %s(or just log out and back in)%s\n\n' "$dim" "$yel" "$rst" "$dim" "$rst"
else
  printf '\n%s   jack in with:%s netdeck%s   %s(add --login to boot into it at every login)%s\n\n' "$dim" "$yel" "$rst" "$dim" "$rst"
fi
