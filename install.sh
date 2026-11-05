#!/usr/bin/env bash
# NETDECK//OS installer.
#
#   ./install.sh                  install the `netdeck` command + app-menu launcher (no sudo)
#   ./install.sh --session        ...and add NETDECK//OS to the login screen: the deck IS the session,
#                                 no desktop loads behind it. Adds `netdeck-switch` to jump between
#                                 the deck and Ubuntu without retyping your password (needs sudo once)
#   ./install.sh --login          ...or open the deck fullscreen on top of your normal desktop at login
#   ./install.sh --every-terminal ...and open the deck in every new terminal window
#   ./install.sh --uninstall      remove everything this script added
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/netdeck"
SESSION_BIN="$BIN_DIR/netdeck-session"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APP_DIR/netdeck.desktop"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
AUTOSTART="$AUTOSTART_DIR/netdeck.desktop"
SESSION_FILE=/usr/share/wayland-sessions/netdeck.desktop
KIOSK_BIN=/usr/local/bin/netdeck-kiosk
SWITCH_ROOT=/usr/local/sbin/netdeck-switch-root
SUDOERS=/etc/sudoers.d/netdeck
SWITCH_BIN="$BIN_DIR/netdeck-switch"
JACK_LAUNCHER="$APP_DIR/netdeck-jack-in.desktop"
RESTORE_AUTOSTART="$AUTOSTART_DIR/netdeck-restore.desktop"
RC="$HOME/.bashrc"
MARK_BEGIN="# >>> netdeck autostart >>>"
MARK_END="# <<< netdeck autostart <<<"

red=$'\e[38;5;203m'; cyan=$'\e[38;5;87m'; yel=$'\e[38;5;227m'; dim=$'\e[38;5;95m'; rst=$'\e[0m'
say() { printf '%s◢%s %s\n' "$red" "$rst" "$*"; }

SESSION=0; LOGIN=0; TERMINAL=0; UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --session|--kiosk)             SESSION=1 ;;
    --login|--boot)                LOGIN=1 ;;
    --every-terminal|--autostart)  TERMINAL=1 ;;
    --uninstall)                   UNINSTALL=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
  rm -f "$BIN" "$SESSION_BIN" "$SWITCH_BIN" "$DESKTOP" "$JACK_LAUNCHER" "$RESTORE_AUTOSTART"
  if [[ -f "$AUTOSTART" ]]; then rm -f "$AUTOSTART"; say "login autostart removed"; fi
  if [[ -e "$SESSION_FILE" || -e "$KIOSK_BIN" || -e "$SWITCH_ROOT" || -e "$SUDOERS" ]]; then
    say "removing the NETDECK//OS login session and session switcher (sudo)"
    [[ -x "$SWITCH_ROOT" ]] && sudo "$SWITCH_ROOT" --restore || true
    sudo rm -f "$SESSION_FILE" "$KIOSK_BIN" "$SWITCH_ROOT" "$SUDOERS"
  fi
  remove_terminal_autostart
  say "netdeck uninstalled. config kept in ~/.config/netdeck, shards in ~/.local/share/netdeck"
  exit 0
fi

command -v python3 >/dev/null || { say "python3 is required (sudo apt install python3)"; exit 1; }
python3 -c 'import curses' 2>/dev/null || { say "python3 curses module missing"; exit 1; }

mkdir -p "$BIN_DIR" "$APP_DIR"
install -m 0755 "$HERE/netdeck.py" "$BIN"
install -m 0755 "$HERE/netdeck-session.sh" "$SESSION_BIN"
install -m 0755 "$HERE/netdeck-switch.sh" "$SWITCH_BIN"
say "installed ${cyan}$BIN${rst}"

if (( ! SESSION )); then
  cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK//OS
GenericName=Cyberdeck Dashboard
Comment=Hijacked corp terminal for netrunners
Exec=$SESSION_BIN
Icon=utilities-terminal
Terminal=false
Categories=System;Monitor;
Keywords=cyberpunk;dashboard;terminal;monitor;
EOF
  say "app-menu launcher: ${cyan}NETDECK//OS${rst} ${dim}(opens fullscreen)${rst}"
fi

if (( SESSION )); then
  pkgs=()
  command -v cage >/dev/null || pkgs+=(cage)
  command -v wlr-randr >/dev/null || pkgs+=(wlr-randr)   # keeps the deck on the laptop screen only
  if ! command -v foot >/dev/null && ! command -v kitty >/dev/null && ! command -v alacritty >/dev/null; then
    pkgs+=(foot)
  fi
  if command -v fc-list >/dev/null && ! fc-list | grep -qi "JetBrains Mono"; then
    pkgs+=(fonts-jetbrains-mono)
  fi
  if command -v fc-list >/dev/null && ! fc-list | grep -qi "Noto Sans CJK"; then
    pkgs+=(fonts-noto-cjk)   # the Japanese labels
  fi
  if (( ${#pkgs[@]} )); then
    say "installing ${cyan}${pkgs[*]}${rst} (sudo)"
    sudo apt-get install -y "${pkgs[@]}"
  fi
  say "registering the NETDECK//OS login session (sudo)"
  sudo install -d /usr/share/wayland-sessions
  printf '%s\n' '#!/bin/sh' '# Entry point for the NETDECK//OS login session (see netdeck-session).' \
    'exec "$HOME/.local/bin/netdeck-session" --kiosk' | sudo tee "$KIOSK_BIN" >/dev/null
  sudo chmod 755 "$KIOSK_BIN"
  printf '%s\n' '[Desktop Entry]' 'Name=NETDECK//OS' 'Comment=Boot straight into the cyberdeck - no desktop' \
    "Exec=$KIOSK_BIN" "TryExec=$KIOSK_BIN" 'Type=Application' 'DesktopNames=NETDECK' \
    | sudo tee "$SESSION_FILE" >/dev/null
  say "login session installed: ${cyan}$SESSION_FILE${rst}"

  # session switcher: a root helper that only flips between the two sessions, runnable without a password
  sudo install -o root -g root -m 0755 "$HERE/netdeck-switch-root.py" "$SWITCH_ROOT"
  rule="$(mktemp)"
  printf '%s ALL=(root) NOPASSWD: %s\n' "${USER:-$(id -un)}" "$SWITCH_ROOT" > "$rule"
  if sudo visudo -cf "$rule" >/dev/null; then
    sudo install -o root -g root -m 0440 "$rule" "$SUDOERS"
    say "session switcher installed ${dim}(sudo rule: $SUDOERS, allows only $SWITCH_ROOT)${rst}"
  else
    say "${yel}note:${rst} couldn't add the sudo rule - switching will ask for your password"
  fi
  rm -f "$rule"

  # in Ubuntu: an app-menu launcher to jack into the deck, and a hidden cleanup that runs at login
  mkdir -p "$AUTOSTART_DIR"
  cat > "$JACK_LAUNCHER" <<EOF
[Desktop Entry]
Type=Application
Name=Jack into NETDECK
GenericName=Switch to the NETDECK//OS session
Comment=Log out of Ubuntu and straight into the cyberdeck
Exec=$SWITCH_BIN deck --gui
Icon=utilities-terminal
Terminal=false
Categories=System;
Keywords=cyberpunk;netdeck;deck;session;switch;
EOF
  cat > "$RESTORE_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK session switch cleanup
Comment=Turns off the one-time automatic login used when switching sessions
Exec=sh -c 'sudo -n $SWITCH_ROOT --restore >/dev/null 2>&1 || true'
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
  say "app menu: ${cyan}Jack into NETDECK${rst} ${dim}(pin it to the Ubuntu dock)${rst}"

  # the deck lives in its own session now - stop it popping up inside Ubuntu
  rm -f "$DESKTOP"
  if [[ -f "$AUTOSTART" ]]; then rm -f "$AUTOSTART"; say "removed the old desktop autostart (deck no longer opens inside Ubuntu)"; fi
  if (( ! TERMINAL )); then remove_terminal_autostart; fi
fi

if (( LOGIN )); then
  mkdir -p "$AUTOSTART_DIR"
  cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=NETDECK//OS
Comment=Open the cyberdeck on login
Exec=$SESSION_BIN
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Phase=Applications
EOF
  say "desktop login autostart: ${cyan}$AUTOSTART${rst}"
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

if (( SESSION )); then
  printf '\n%s   one-time setup at the login screen:%s\n' "$dim" "$rst"
  printf '     1. log out, then click your name\n'
  printf '     2. click the %sgear icon%s (bottom right) and pick %sNETDECK//OS%s\n' "$yel" "$rst" "$yel" "$rst"
  printf '     3. log in - the deck is the whole screen. Ubuntu remembers the choice.\n\n'
  printf '%s   switching:%s in the deck type %subuntu%s (or F10)  ·  in Ubuntu open %sJack into NETDECK%s\n' \
    "$dim" "$rst" "$yel" "$rst" "$yel" "$rst"
  printf '              or from any terminal: %snetdeck-switch deck%s / %snetdeck-switch ubuntu%s\n' \
    "$yel" "$rst" "$yel" "$rst"
  printf '%s   no password at boot:%s Settings → System → Users → Automatic Login\n\n' "$dim" "$rst"
elif (( LOGIN )); then
  printf '\n%s   try it now:%s netdeck-session%s   %s(or log out and back in)%s\n\n' "$dim" "$yel" "$rst" "$dim" "$rst"
else
  printf '\n%s   jack in with:%s netdeck%s   %s(add --session to make it your whole login session)%s\n\n' \
    "$dim" "$yel" "$rst" "$dim" "$rst"
fi
