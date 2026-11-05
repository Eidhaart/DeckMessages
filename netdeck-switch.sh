#!/usr/bin/env bash
# netdeck-switch deck|ubuntu [--gui]
# Log out of this session and straight back in to the other one (NETDECK//OS or the Ubuntu desktop).
# --gui asks for confirmation in a dialog (used by the "Jack into NETDECK" app-menu launcher).
set -u
HELPER=/usr/local/sbin/netdeck-switch-root
target="${1:-}"
case "$target" in
  deck)   label="NETDECK//OS" ;;
  ubuntu) label="the Ubuntu desktop" ;;
  *) echo "usage: netdeck-switch deck|ubuntu" >&2; exit 2 ;;
esac
if [[ ! -x $HELPER ]]; then
  msg="Session switching isn't installed - run ./install.sh --session in the netdeck folder."
  [[ "${2:-}" == --gui ]] && command -v zenity >/dev/null && zenity --error --text="$msg" 2>/dev/null
  echo "$msg" >&2
  exit 1
fi
if [[ "${2:-}" == --gui ]]; then
  if command -v zenity >/dev/null; then
    zenity --question --title="NETDECK//OS" --icon-name=utilities-terminal \
      --text="Switch to $label?\n\nApps open in this session will close - save your work first." \
      --ok-label="Jack in" --cancel-label="Stay" 2>/dev/null || exit 0
  fi
  sudo -n "$HELPER" "$target" 2>/dev/null || pkexec "$HELPER" "$target"
else
  sudo -n "$HELPER" "$target" 2>/dev/null || sudo "$HELPER" "$target"
fi
