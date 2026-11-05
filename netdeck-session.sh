#!/usr/bin/env bash
# NETDECK//OS session launcher.
#
#   netdeck-session           open the deck in a fullscreen terminal window on your desktop
#   netdeck-session --kiosk   run the deck as the whole login session (no desktop at all).
#                             Used by the "NETDECK//OS" entry on the login screen (install.sh --session).
#
# The deck's font, size and background color come from ~/.config/netdeck/config.json (edit with F8).
# To force a specific terminal, set it in ~/.config/netdeck/session.conf, e.g.:
#   NETDECK_TERMINAL="kitty --start-as=fullscreen"
# (the deck command is appended to whatever you put there)

MODE=desktop
case "${1:-}" in
  --kiosk) MODE=kiosk ;;
  --kiosk-inner) MODE=kiosk-inner ;;
esac

DECK="${NETDECK_BIN:-$HOME/.local/bin/netdeck}"
[[ -x "$DECK" ]] || DECK="$(command -v netdeck || true)"
if [[ -z "$DECK" ]]; then
  notify-send "NETDECK//OS" "netdeck is not installed - run install.sh from the netdeck repo" 2>/dev/null
  echo "netdeck is not installed" >&2
  exit 1
fi

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/netdeck/session.conf"
# shellcheck disable=SC1090
[[ -f "$CONF" ]] && . "$CONF"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/netdeck"
mkdir -p "$CACHE"
FLAG="$CACHE/relaunch"
export NETDECK_SESSION=1

have() { command -v "$1" >/dev/null 2>&1; }

# ---- kiosk: become the display server's only client
if [[ $MODE == kiosk ]]; then
  if ! have cage; then
    echo "cage is not installed (sudo apt install cage)" >&2
    exit 1
  fi
  # -d: no window decorations   -s: allow Ctrl+Alt+F1..F7 to switch consoles
  exec cage -d -s -- "$(readlink -f "$0")" --kiosk-inner
fi
[[ $MODE == kiosk-inner ]] && export NETDECK_KIOSK=1

# ---- what runs inside the terminal window
#  exit 0  -> kiosk: end the session / desktop: leave a normal shell open
#  exit 75 -> relaunch the terminal (font change)
#  other   -> the deck crashed: show a raw shell, restart the deck when it closes
INNER_SCRIPT='deck="$0"
while :; do
  "$deck"; rc=$?
  [ "$rc" -eq 75 ] && exit 0
  if [ "$rc" -eq 0 ]; then
    [ -n "$NETDECK_KIOSK" ] && exit 0
    export NETDECK=1; exec "${SHELL:-/bin/bash}"
  fi
  printf "\n\033[38;5;197m◢ the deck crashed (exit %s). raw shell below - type exit to restart the deck.\033[0m\n" "$rc"
  NETDECK=1 "${SHELL:-/bin/bash}"
done'
INNER=(bash -c "$INNER_SCRIPT" "$DECK")
INNER_STR="$(printf '%q ' "${INNER[@]}")"

# ---- pick a terminal. In kiosk mode only Wayland-native ones that take options on the command line.
if [[ -n "${NETDECK_TERMINAL:-}" ]]; then
  TERM_APP=custom
elif [[ $MODE == kiosk-inner ]]; then
  for t in foot kitty alacritty; do have "$t" && { TERM_APP=$t; break; }; done
else
  for t in kitty alacritty foot wezterm gnome-terminal ptyxis kgx konsole xfce4-terminal tilix \
           x-terminal-emulator xterm; do
    have "$t" && { TERM_APP=$t; break; }
  done
fi
if [[ -z "${TERM_APP:-}" ]]; then
  notify-send "NETDECK//OS" "no terminal emulator found (sudo apt install foot)" 2>/dev/null
  echo "no terminal emulator found (sudo apt install foot)" >&2
  exit 1
fi

run_terminal() {
  local opts=()
  mapfile -t opts < <("$DECK" --term-opts "$TERM_APP" 2>/dev/null)
  case "$TERM_APP" in
    custom)
      # shellcheck disable=SC2086
      $NETDECK_TERMINAL "${INNER[@]}" ;;
    foot)
      if [[ $MODE == desktop ]]; then foot --fullscreen "${opts[@]}" "${INNER[@]}"
      else foot "${opts[@]}" "${INNER[@]}"; fi ;;
    kitty)
      kitty --start-as=fullscreen "${opts[@]}" "${INNER[@]}" ;;
    alacritty)
      alacritty -o window.startup_mode=\"Fullscreen\" "${opts[@]}" -e "${INNER[@]}" ;;
    wezterm)        wezterm start -- "${INNER[@]}" ;;
    gnome-terminal) gnome-terminal --wait --full-screen --hide-menubar -- "${INNER[@]}" ;;
    ptyxis)         ptyxis --new-window -x "$INNER_STR" ;;
    kgx)            kgx -- "${INNER[@]}" ;;
    konsole)        konsole --fullscreen -e "${INNER[@]}" ;;
    xfce4-terminal) xfce4-terminal --fullscreen -x "${INNER[@]}" ;;
    tilix)          tilix --full-screen -e "$INNER_STR" ;;
    x-terminal-emulator) x-terminal-emulator -e "${INNER[@]}" ;;
    xterm)          xterm -fullscreen -bg black -e "${INNER[@]}" ;;
  esac
}

# Relaunch loop: the deck drops a flag file and exits 75 when you apply a new font.
while :; do
  rm -f -- "${FLAG:?}"
  run_terminal
  [[ -e "$FLAG" ]] || break
done
