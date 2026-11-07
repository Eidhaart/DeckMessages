#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run setup as your normal Pi user. It uses sudo only for packages and console login.' >&2
    exit 1
fi
packages=1
autostart=1
console=1
for arg in "$@"; do
    case $arg in
        --skip-packages) packages=0 ;;
        --no-autostart) autostart=0 ;;
        --no-console) console=0 ;;
        *) printf '%s\n' 'Usage: ./setup.sh [--skip-packages] [--no-autostart] [--no-console]' >&2; exit 2 ;;
    esac
done
if [ "$packages" -eq 1 ]; then
    sudo apt-get update
    sudo apt-get install --no-install-recommends python3 git openssh-client ca-certificates zsh nano w3m mpv
    if ! command -v micro >/dev/null; then
        sudo apt-get install --no-install-recommends micro || printf '%s\n' 'Using nano.'
    fi
    if ! command -v yt-dlp >/dev/null; then
        sudo apt-get install --no-install-recommends yt-dlp || printf '%s\n' 'Skipping yt-dlp: URL streams from video sites unavailable.'
    fi
fi
install -d "$HOME/.local/bin"
temp=$(mktemp "$HOME/.local/bin/.nightdeck.XXXXXX")
trap 'rm -f -- "$temp"' EXIT HUP INT TERM
install -m 0755 nightdeck.py "$temp"
mv -fT -- "$temp" "$HOME/.local/bin/nightdeck"

# Console boot: log this user in on the Pi's own screen (tty1) so the deck opens there.
user=$(id -un)
dropin=/etc/systemd/system/getty@tty1.service.d
conf="$dropin/nightdeck-autologin.conf"
if command -v systemctl >/dev/null && [ -d /etc/systemd/system ]; then
    if [ "$console" -eq 1 ] && [ "$autostart" -eq 1 ]; then
        conftemp=$(mktemp)
        cat > "$conftemp" <<EOF
# Written by Nightdeck setup.sh. Remove with: ./setup.sh --skip-packages --no-console
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $user --noclear %I \$TERM
EOF
        if ! cmp -s "$conftemp" "$conf" 2>/dev/null; then
            sudo install -d -m 0755 "$dropin"
            sudo install -m 0644 "$conftemp" "$conf"
            sudo systemctl daemon-reload || true
            printf '%s\n' "The Pi's screen now logs in as $user and opens Nightdeck after a reboot."
        fi
        rm -f -- "$conftemp"
    elif [ -f "$conf" ]; then
        sudo rm -f -- "$conf"
        sudo systemctl daemon-reload || true
        printf '%s\n' "Console autologin removed. It takes effect after a reboot."
    fi
else
    console=0
fi

# Login autostart: a marked block in each login profile. Only that block is ever changed.
begin='# >>> nightdeck autostart >>>'
end='# <<< nightdeck autostart <<<'
profiles="$HOME/.profile"
for file in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.zprofile"; do
    [ -f "$file" ] && profiles="$profiles $file"
done
case "$(getent passwd "$user" | cut -d: -f7)" in
    */zsh) case " $profiles " in *" $HOME/.zprofile "*) ;; *) profiles="$profiles $HOME/.zprofile" ;; esac ;;
esac
if [ "$console" -eq 1 ]; then
    where='{ [ -n "${SSH_CONNECTION-}" ] || [ "$(tty)" = /dev/tty1 ]; }'
    what='over SSH or on the Pi'"'"'s screen (tty1)'
else
    where='[ -n "${SSH_CONNECTION-}" ]'
    what='over SSH'
fi
for file in $profiles; do
    if [ -f "$file" ]; then
        sed -i "\|^$begin\$|,\|^$end\$|d" "$file"
    fi
    [ "$autostart" -eq 1 ] || continue
    cat >> "$file" <<EOF
$begin
# Open Nightdeck when you log in $what. Remove with: ./setup.sh --skip-packages --no-autostart
case \$- in *i*) _nightdeck_tty=1 ;; *) _nightdeck_tty= ;; esac
if [ -n "\$_nightdeck_tty" ] && $where && [ -z "\${NIGHTDECK-}" ] \\
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
    printf '%s\n' "Nightdeck opens automatically when you log in $what ($profiles)."
else
    printf '%s\n' 'Login autostart removed.'
fi
printf '%s\n' 'Launch with ~/.local/bin/nightdeck'
