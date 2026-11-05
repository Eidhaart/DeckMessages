#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run setup as your normal Pi user. It uses sudo only for packages.' >&2
    exit 1
fi
packages=1
autostart=1
for arg in "$@"; do
    case $arg in
        --skip-packages) packages=0 ;;
        --no-autostart) autostart=0 ;;
        *) printf '%s\n' 'Usage: ./setup.sh [--skip-packages] [--no-autostart]' >&2; exit 2 ;;
    esac
done
if [ "$packages" -eq 1 ]; then
    sudo apt-get update
    sudo apt-get install --no-install-recommends python3 git openssh-client ca-certificates zsh nano w3m
    if ! command -v micro >/dev/null; then
        sudo apt-get install --no-install-recommends micro || printf '%s\n' 'Using nano.'
    fi
fi
install -d "$HOME/.local/bin"
temp=$(mktemp "$HOME/.local/bin/.nightdeck.XXXXXX")
trap 'rm -f -- "$temp"' EXIT HUP INT TERM
install -m 0755 nightdeck.py "$temp"
mv -fT -- "$temp" "$HOME/.local/bin/nightdeck"

# Login autostart: a marked block in each login profile. Only that block is ever changed.
begin='# >>> nightdeck autostart >>>'
end='# <<< nightdeck autostart <<<'
profiles="$HOME/.profile"
for file in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.zprofile"; do
    [ -f "$file" ] && profiles="$profiles $file"
done
case "$(getent passwd "$(id -un)" | cut -d: -f7)" in
    */zsh) case " $profiles " in *" $HOME/.zprofile "*) ;; *) profiles="$profiles $HOME/.zprofile" ;; esac ;;
esac
for file in $profiles; do
    if [ -f "$file" ]; then
        sed -i "\|^$begin\$|,\|^$end\$|d" "$file"
    fi
    [ "$autostart" -eq 1 ] || continue
    cat >> "$file" <<EOF
$begin
# Open Nightdeck when you log in over SSH. Remove with: ./setup.sh --skip-packages --no-autostart
case \$- in *i*) _nightdeck_tty=1 ;; *) _nightdeck_tty= ;; esac
if [ -n "\$_nightdeck_tty" ] && [ -n "\${SSH_CONNECTION-}" ] && [ -z "\${NIGHTDECK-}" ] \\
        && [ -t 0 ] && [ -t 1 ] && [ -x "\$HOME/.local/bin/nightdeck" ]; then
    unset _nightdeck_tty
    NIGHTDECK=1; export NIGHTDECK
    "\$HOME/.local/bin/nightdeck"
    [ \$? -eq 0 ] && exit 0
fi
unset _nightdeck_tty
$end
EOF
done
if [ "$autostart" -eq 1 ]; then
    printf '%s\n' "Nightdeck opens automatically on SSH login ($profiles)."
else
    printf '%s\n' 'SSH login autostart removed.'
fi
printf '%s\n' 'Launch with ~/.local/bin/nightdeck'
