#!/usr/bin/env bash
# netdeck-nightdeck - jack into the nightdeck Raspberry Pi over SSH, with style.
#
#   nightdeck                  run the jack-in sequence, then: ssh deck@nightdeck.local
#   nightdeck htop             ...run a command on the Pi instead of a shell
#   nightdeck --quick          skip the sequence           nightdeck --force   try even if the probes fail
#
# While the sequence plays it really probes the Pi: mDNS lookup, latency, the SSH port and the host key.
# Settings (environment or ~/.config/netdeck/session.conf): NIGHTDECK_HOST NIGHTDECK_USER NIGHTDECK_PORT

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/netdeck/session.conf"
# shellcheck disable=SC1090
[[ -f $CONF ]] && . "$CONF"
HOST=${NIGHTDECK_HOST:-nightdeck.local}
USR=${NIGHTDECK_USER:-deck}
PORT=${NIGHTDECK_PORT:-22}
QUICK=0; FORCE=0; ARGS=()
for a in "$@"; do
  case "$a" in
    -q|--quick) QUICK=1 ;;
    -f|--force) FORCE=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) ARGS+=("$a") ;;
  esac
done
SSH=(ssh -o ConnectTimeout=6 -p "$PORT" "$USR@$HOST")

# not a terminal, or asked to be quick: just connect
if [[ ! -t 1 || $QUICK == 1 ]]; then exec "${SSH[@]}" "${ARGS[@]}"; fi

# ---- colors from the deck's current skin
declare -A C=([pri]="#ff1238" [acc]="#1fe3f0" [hi]="#f6e33b" [txt]="#ebe7ef" [dim]="#857e93" [line]="#5e1a2b"
              [ok]="#22f59a" [warn]="#f6e33b" [bad]="#ff4f5e" [mag]="#5b8cff")
DECK=$(command -v netdeck || echo "$HOME/.local/bin/netdeck")
if [[ -x $DECK ]]; then
  while read -r k v; do [[ -n $k && -n $v ]] && C[$k]=$v; done < <("$DECK" --palette 2>/dev/null)
fi
fg() { local h=${1#\#}; printf '\e[38;2;%d;%d;%dm' "0x${h:0:2}" "0x${h:2:2}" "0x${h:4:2}"; }
bgc() { local h=${1#\#}; printf '\e[48;2;%d;%d;%dm' "0x${h:0:2}" "0x${h:2:2}" "0x${h:4:2}"; }
P=$(fg "${C[pri]}") A=$(fg "${C[acc]}") H=$(fg "${C[hi]}") T=$(fg "${C[txt]}") D=$(fg "${C[dim]}")
L=$(fg "${C[line]}") O=$(fg "${C[ok]}") Wn=$(fg "${C[warn]}") Bd=$(fg "${C[bad]}") B=$'\e[1m' R=$'\e[0m'
at() { printf '\e[%d;%dH' "$1" "$2"; }
rep() { local s; printf -v s '%*s' "$2" ''; printf '%s' "${s// /$1}"; }   # repeat a (multibyte) char
W=$(tput cols 2>/dev/null || echo 80); Hh=$(tput lines 2>/dev/null || echo 24)
ME=$(hostname -s 2>/dev/null || echo deck); ME=${ME^^}
SKIP=0
wait_cs() {  # wait N hundredths of a second; any key skips the show
  (( SKIP )) && return 1
  local k
  if read -rsn1 -t "$(printf '%d.%02d' $(( $1 / 100 )) $(( $1 % 100 )))" k 2>/dev/null; then SKIP=1; return 1; fi
  return 0
}

# ---- real probes, in the background
TMP=$(mktemp -d)
cleanup() { printf '\e[0m\e[?25h\e[?1049l'; rm -rf "$TMP"; }
trap 'cleanup; exit 130' INT
(
  ip=$(getent hosts "$HOST" 2>/dev/null | awk '{print $1; exit}')
  [[ -z $ip ]] && command -v avahi-resolve >/dev/null && ip=$(avahi-resolve -4 -n "$HOST" 2>/dev/null | awk '{print $2}')
  echo "${ip:-}" > "$TMP/ip.tmp"; mv "$TMP/ip.tmp" "$TMP/ip"
  if [[ -n $ip ]]; then
    ms=$(ping -c1 -W1 "$ip" 2>/dev/null | sed -n 's/.*time=\([0-9.]*\).*/\1/p')
    echo "${ms:-}" > "$TMP/ping.tmp"; mv "$TMP/ping.tmp" "$TMP/ping"
    if timeout 2 bash -c "</dev/tcp/$ip/$PORT" 2>/dev/null; then echo open; else echo closed; fi > "$TMP/port.tmp"
    mv "$TMP/port.tmp" "$TMP/port"
    fp=$(ssh-keyscan -T 2 -p "$PORT" -t ed25519 "$HOST" 2>/dev/null | ssh-keygen -lf - 2>/dev/null | awk '{print $2; exit}')
    known=new; ssh-keygen -F "$HOST" >/dev/null 2>&1 && known=known
    [[ $PORT != 22 ]] && ssh-keygen -F "[$HOST]:$PORT" >/dev/null 2>&1 && known=known
    echo "${fp:-}|$known" > "$TMP/key.tmp"; mv "$TMP/key.tmp" "$TMP/key"
  else
    : > "$TMP/ping"; echo closed > "$TMP/port"; echo "|new" > "$TMP/key"
  fi
) &
PROBE=$!

# ---- the sequence
printf '\e[?1049h\e[?25l\e[2J'
at 2 4; printf '%s%s' "$D" "NETDECK // REMOTE NODE // 遠隔接続"
right="TARGET ${USR^^}@${HOST^^}"
at 2 $(( W - ${#right} - 3 )); printf '%s%s' "$D" "$right"
at 3 4; printf '%s%s' "$L" "$(rep ─ $(( W - 6 )))"
at $(( Hh - 2 )) 4; printf '%s%s' "$L" "$(rep ─ $(( W - 6 )))"
at $(( Hh - 1 )) 4; printf '%s%s' "$D" "© 2077 ARASAKA // ALL ACTIVITY IS GHOSTED"
hint="ANY KEY SKIPS"; at $(( Hh - 1 )) $(( W - ${#hint} - 3 )); printf '%s%s' "$D" "$hint"

cw=64; x=$(( (W - cw) / 2 )); (( x < 3 )) && { x=3; cw=$(( W - 6 )); }
y=$(( Hh / 2 - 7 )); (( y < 5 )) && y=5
at "$y" "$x"; printf '%s%s%s' "$A$B" "遠隔 // TUNNELING TO NIGHTDECK" "$R"

# link diagram: YAGURA ◢━━━━━━━━━━◣ NIGHTDECK with packets running down the wire
dy=$(( y + 2 )); left="$ME"; rightn="NIGHTDECK"
wire=$(( cw - ${#left} - ${#rightn} - 4 )); wx=$(( x + ${#left} + 2 ))
at "$dy" "$x"; printf '%s%s%s %s◢' "$T$B" "$left" "$R" "$P"
at "$dy" $(( wx + wire )); printf '%s◣ %s%s%s' "$P" "$T$B" "$rightn" "$R"
draw_wire() {  # $1 = packet position, $2 = color
  local i s=""
  for (( i = 0; i < wire; i++ )); do
    if (( i == $1 || i == $1 - 8 || i == $1 - 16 )); then s+="■"; else s+="━"; fi
  done
  at "$dy" $(( wx + 1 )); printf '%s%s' "$2" "${s:0:wire-1}"
}

row=$(( y + 4 ))
line_out() {  # label detail result color
  at "$row" "$x"; printf '%s▸ %-15s %s' "$T" "$1" "$2"
  at "$row" $(( x + cw - ${#3} - 4 )); printf '%s[ %s ]%s' "$4$B" "$3" "$R"
  row=$(( row + 1 ))
}

shown_ip=0 shown_ping=0 shown_port=0 shown_key=0 ip="" ok=1 pos=0 t=0
while :; do
  draw_wire $(( pos % (wire + 16) )) "$P"
  pos=$(( pos + 2 )); t=$(( t + 1 ))
  if (( ! shown_ip )) && [[ -f $TMP/ip ]]; then
    ip=$(<"$TMP/ip"); shown_ip=1
    if [[ -n $ip ]]; then line_out "grid lookup" "$HOST → $ip" "FOUND" "$O"
    else line_out "grid lookup" "$HOST" "NO SIGNAL" "$Bd"; ok=0; fi
  fi
  if (( shown_ip && ! shown_ping )) && [[ -f $TMP/ping ]]; then
    ms=$(<"$TMP/ping"); shown_ping=1
    if [[ -n $ms ]]; then line_out "latency" "${ms} ms round trip" "OK" "$O"
    elif [[ -n $ip ]]; then line_out "latency" "no echo (ICMP filtered?)" "QUIET" "$Wn"; fi
  fi
  if (( shown_ping && ! shown_port )) && [[ -f $TMP/port ]]; then
    st=$(<"$TMP/port"); shown_port=1
    if [[ -n $ip ]]; then
      if [[ $st == open ]]; then line_out "port $PORT" "ssh daemon listening" "OPEN" "$O"
      else line_out "port $PORT" "no answer" "CLOSED" "$Bd"; ok=0; fi
    fi
  fi
  if (( shown_port && ! shown_key )) && [[ -f $TMP/key ]]; then
    IFS='|' read -r fp known < "$TMP/key"; shown_key=1
    if [[ -n $ip ]]; then
      if [[ -n $fp ]]; then
        short="ED25519 ${fp:0:26}…"
        if [[ $known == known ]]; then line_out "host key" "$short" "KNOWN" "$O"
        else line_out "host key" "$short" "NEW" "$Wn"; fi
      else line_out "host key" "unavailable" "?" "$Wn"; fi
      (( ok )) && line_out "operator" "$USR" "READY" "$O"
    fi
  fi
  (( shown_key )) && (( SKIP || t > 16 )) && break
  (( t > 80 )) && break   # probes hung: stop waiting
  wait_cs 4 || true
done
wait "$PROBE" 2>/dev/null

if (( ! ok && ! FORCE )); then
  row=$(( row + 1 ))
  at "$row" "$x"; printf '%s%s%s' "$Bd$B" "✗ NIGHTDECK ISN'T ANSWERING ON THE LOCAL GRID" "$R"
  at $(( row + 1 )) "$x"; printf '%s%s' "$D" "is the Pi powered and on this network?  (nightdeck --force tries anyway)"
  at $(( row + 3 )) "$x"; printf '%s%s' "$D" "press any key"
  read -rsn1 -t 15 _ 2>/dev/null
  cleanup; exit 1
fi

# tunnel bar, then the link line
row=$(( row + 1 ))
bw=$(( cw - 16 ))
for (( i = 0; i <= bw; i += 3 )); do
  at "$row" "$x"; printf '%s▸ tunnel  %s%s%s%s' "$T" "$A" "$(rep ▰ "$i")" "$L" "$(rep ▱ $(( bw - i )))"
  (( SKIP )) || sleep 0.012
done
draw_wire -99 "$O"
msg="◢ JACKED INTO NIGHTDECK"
at $(( row + 2 )) $(( (W - ${#msg}) / 2 )); printf '%s%s%s' "$O$B" "$msg" "$R"
(( SKIP )) || sleep 0.45
ms=$(<"$TMP/ping" 2>/dev/null)
cleanup
trap - INT

# connected: one header line in the normal screen, then the real session
printf '%s◢ NIGHTDECK%s %s//%s %s%s@%s%s %s//%s %s%s%s%s\n' "$P$B" "$R" "$L" "$R" "$A" "$USR" "$HOST" "$R" \
  "$L" "$R" "$D" "${ip:-?}" "${ms:+ // ${ms} ms}" "$R"
start=$(date +%s)
"${SSH[@]}" "${ARGS[@]}"
rc=$?
dur=$(( $(date +%s) - start ))
printf '%s◢ LINK SEVERED%s %s//%s %snightdeck // session %dm %02ds // exit %d%s\n' "$P$B" "$R" "$L" "$R" "$D" \
  $(( dur / 60 )) $(( dur % 60 )) "$rc" "$R"
exit "$rc"
