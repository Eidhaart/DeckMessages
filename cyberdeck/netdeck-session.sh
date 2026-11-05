#!/usr/bin/env bash
# NETDECK//OS session launcher: opens the deck in a fullscreen terminal window.
# install.sh --login runs this automatically when you log in to your desktop.
#
# When you jack out of the deck, the window stays open as a normal shell.
# To force a specific terminal, set NETDECK_TERMINAL in ~/.config/netdeck/session.conf, e.g.:
#   NETDECK_TERMINAL="kitty --start-as=fullscreen"
# The deck command is appended to whatever you put there.

DECK="${NETDECK_BIN:-$HOME/.local/bin/netdeck}"
[[ -x "$DECK" ]] || DECK="$(command -v netdeck || true)"
if [[ -z "$DECK" ]]; then
  notify-send "NETDECK//OS" "netdeck is not installed - run cyberdeck/install.sh" 2>/dev/null
  exit 1
fi

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/netdeck/session.conf"
# shellcheck disable=SC1090
[[ -f "$CONF" ]] && . "$CONF"

# Inside the window: run the deck, then fall back to the user's shell.
# NETDECK=1 stops the ~/.bashrc autostart from relaunching the deck in that shell.
INNER=(bash -c '"$0"; export NETDECK=1; exec "${SHELL:-/bin/bash}"' "$DECK")
INNER_STR="$(printf '%q ' "${INNER[@]}")"

have() { command -v "$1" >/dev/null 2>&1; }

if [[ -n "${NETDECK_TERMINAL:-}" ]]; then
  # shellcheck disable=SC2086
  exec $NETDECK_TERMINAL "${INNER[@]}"
fi

# Dedicated terminals first (if you installed one, you probably prefer it), then desktop defaults.
if   have kitty;          then exec kitty --start-as=fullscreen "${INNER[@]}"
elif have alacritty;      then exec alacritty -o window.startup_mode=Fullscreen -e "${INNER[@]}"
elif have wezterm;        then exec wezterm start -- "${INNER[@]}"
elif have gnome-terminal; then exec gnome-terminal --full-screen --hide-menubar -- "${INNER[@]}"
elif have ptyxis;         then exec ptyxis --new-window -x "$INNER_STR"
elif have kgx;            then exec kgx -- "${INNER[@]}"
elif have konsole;        then exec konsole --fullscreen -e "${INNER[@]}"
elif have xfce4-terminal; then exec xfce4-terminal --fullscreen -x "${INNER[@]}"
elif have tilix;          then exec tilix --full-screen -e "$INNER_STR"
elif have x-terminal-emulator; then exec x-terminal-emulator -e "${INNER[@]}"
elif have xterm;          then exec xterm -fullscreen -bg black -e "${INNER[@]}"
fi

notify-send "NETDECK//OS" "no terminal emulator found" 2>/dev/null
exit 1
