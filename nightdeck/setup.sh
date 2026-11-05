#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run setup as your normal Pi user. It uses sudo only for packages.' >&2
    exit 1
fi
case "${1-}" in
    '') sudo apt-get update
        sudo apt-get install --no-install-recommends python3 git openssh-client ca-certificates zsh nano w3m
        if ! command -v micro >/dev/null; then
            sudo apt-get install --no-install-recommends micro || printf '%s\n' 'Using nano.'
        fi ;;
    --skip-packages) ;;
    *) printf '%s\n' 'Usage: ./setup.sh [--skip-packages]' >&2; exit 2 ;;
esac
install -d "$HOME/.local/bin"
temp=$(mktemp "$HOME/.local/bin/.nightdeck.XXXXXX")
trap 'rm -f -- "$temp"' EXIT HUP INT TERM
install -m 0755 nightdeck.py "$temp"
mv -fT -- "$temp" "$HOME/.local/bin/nightdeck"
printf '%s\n' 'Launch with ~/.local/bin/nightdeck'
