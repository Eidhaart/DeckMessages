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
display=keep
rotation=90
usage='Usage: ./setup.sh [--skip-packages] [--no-autostart] [--no-console] [--touch-display-2[=90|270]] [--no-touch-display-2]'
for arg in "$@"; do
    case $arg in
        --skip-packages) packages=0 ;;
        --no-autostart) autostart=0 ;;
        --no-console) console=0 ;;
        --touch-display-2) display=on ;;
        --touch-display-2=0|--touch-display-2=90|--touch-display-2=180|--touch-display-2=270)
            display=on; rotation=${arg#*=} ;;
        --no-touch-display-2) display=off ;;
        *) printf '%s\n' "$usage" >&2; exit 2 ;;
    esac
done
if [ "$packages" -eq 1 ]; then
    sudo apt-get update
    sudo apt-get install --no-install-recommends python3 git openssh-client ca-certificates zsh nano w3m mpv ffmpeg
    if ! command -v micro >/dev/null; then
        sudo apt-get install --no-install-recommends micro || printf '%s\n' 'Using nano.'
    fi
    # YouTube needs a JavaScript runtime for yt-dlp; QuickJS is the one that runs on 32-bit Pi OS.
    sudo apt-get install --no-install-recommends quickjs || printf '%s\n' 'Skipping QuickJS: YouTube may not play.'
    # Bluetooth headphones and speakers: PipeWire + WirePlumber with the BlueZ plugin.
    sudo apt-get install --no-install-recommends bluez pipewire wireplumber libspa-0.2-bluetooth rfkill \
        || printf '%s\n' 'Skipping Bluetooth audio packages.'
    # Spotify Connect (spotifyd, installed from the Music menu) plays through PipeWire's PulseAudio service.
    sudo apt-get install --no-install-recommends pipewire-pulse libpulse0 playerctl dbus-user-session \
        || printf '%s\n' 'Skipping Spotify support packages.'
fi
install -d "$HOME/.local/bin"
temp=$(mktemp "$HOME/.local/bin/.nightdeck.XXXXXX")
trap 'rm -f -- "$temp"' EXIT HUP INT TERM
install -m 0755 nightdeck.py "$temp"
mv -fT -- "$temp" "$HOME/.local/bin/nightdeck"
# Debian's yt-dlp falls behind YouTube; install the official release (checksum-verified) per user.
python3 "$HOME/.local/bin/nightdeck" update-ytdlp || printf '%s\n' 'yt-dlp update failed; retry later from Video player > Update yt-dlp.'

# Bluetooth control over D-Bus needs the bluetooth group (takes effect at the next login).
if getent group bluetooth >/dev/null && ! id -nG | tr ' ' '\n' | grep -qx bluetooth; then
    sudo usermod -aG bluetooth "$(id -un)" && printf '%s\n' 'Added you to the bluetooth group. Reboot or log in again.'
fi

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

# Raspberry Pi Touch Display 2 (5"): landscape, touch driver disabled, large console font.
# Only the marked block in config.txt is changed; the original files are backed up once.
if [ "$display" != keep ]; then
    bootcfg=/boot/firmware/config.txt
    dbegin='# >>> nightdeck display >>>'
    dend='# <<< nightdeck display <<<'
    if [ -f "$bootcfg" ]; then
        new=$(mktemp)
        sed "\|^$dbegin\$|,\|^$dend\$|d" "$bootcfg" > "$new"
        if [ "$display" = on ]; then
            cat >> "$new" <<EOF
$dbegin
# Raspberry Pi Touch Display 2 (5"): landscape, touch disabled. Remove: ./setup.sh --skip-packages --no-touch-display-2
[all]
dtoverlay=vc4-kms-dsi-ili9881-5inch,disable_touch,rotation=$rotation
$dend
EOF
        fi
        if ! cmp -s "$new" "$bootcfg"; then
            [ -f "$bootcfg.nightdeck-backup" ] || sudo cp "$bootcfg" "$bootcfg.nightdeck-backup"
            sudo cp "$new" "$bootcfg"
        fi
        rm -f -- "$new"
    else
        printf '%s\n' "No $bootcfg on this machine; skipping the display settings." >&2
    fi
    fontcfg=/etc/default/console-setup
    if [ -f "$fontcfg" ] && [ "$display" = on ]; then
        [ -f "$fontcfg.nightdeck-backup" ] || sudo cp "$fontcfg" "$fontcfg.nightdeck-backup"
        fonttemp=$(mktemp)
        grep -v -e '^FONTFACE=' -e '^FONTSIZE=' "$fontcfg" > "$fonttemp" || true
        printf '%s\n' 'FONTFACE="Terminus"' 'FONTSIZE="16x32"' >> "$fonttemp"
        cmp -s "$fonttemp" "$fontcfg" || sudo cp "$fonttemp" "$fontcfg"
        rm -f -- "$fonttemp"
    elif [ -f "$fontcfg.nightdeck-backup" ] && [ "$display" = off ]; then
        sudo cp "$fontcfg.nightdeck-backup" "$fontcfg"
        sudo rm -f -- "$fontcfg.nightdeck-backup"
    fi
    if [ "$display" = on ]; then
        printf '%s\n' "Touch Display 2: landscape (rotation $rotation), touch disabled, Terminus 16x32 font. Reboot to apply."
    else
        printf '%s\n' 'Touch Display 2 settings removed. Reboot to apply.'
    fi
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
