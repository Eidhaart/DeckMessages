# jackin - tune into NETDECK//OS from any zsh terminal.
#
#   jackin             jack into the NETDECK session: confirm, play the sequence, switch sessions
#   jackin --here      play the sequence, then open the deck inside this terminal instead
#   jackin --quick     skip the sequence (combine with --here)
#   nightdeck [cmd]    jack into the nightdeck Raspberry Pi (ssh deck@nightdeck.local) with its own sequence
#
# Any key skips the sequence; Ctrl+C aborts and leaves you in the shell.
# Installed into $ZSH_CUSTOM by zsh/install-zsh.sh (oh-my-zsh loads it automatically).

zmodload zsh/datetime 2>/dev/null

_jk_rgb() {  # "#rrggbb" -> truecolor escape (fg)
  local h=${1#\#}
  printf '\e[38;2;%d;%d;%dm' $((16#${h:0:2})) $((16#${h:2:2})) $((16#${h:4:2}))
}
_jk_bg() {
  local h=${1#\#}
  printf '\e[48;2;%d;%d;%dm' $((16#${h:0:2})) $((16#${h:2:2})) $((16#${h:4:2}))
}
_jk_at() { printf '\e[%d;%dH' $1 $2 }      # row col
_jk_wait() {                                # wait N hundredths; returns 1 once a key was pressed
  (( _jk_skip )) && return 1
  local k
  if read -s -t $(( $1 / 100.0 )) -k 1 k 2>/dev/null; then _jk_skip=1; return 1; fi
  return 0
}
_jk_type() {  # row col color text
  local row=$1 col=$2 color=$3 text=$4 i
  if (( _jk_skip )); then _jk_at $row $col; printf '%s%s' "$color" "$text"; return; fi
  for (( i = 1; i <= ${#text}; i += 2 )); do
    _jk_at $row $col; printf '%s%s' "$color" "${text[1,i]}"
    _jk_wait 1 || { _jk_at $row $col; printf '%s%s' "$color" "$text"; return }
  done
  _jk_at $row $col; printf '%s%s' "$color" "$text"
}

_jackin_sequence() {
  local -A c
  local name=${ND[name]:-netrunner}
  c=(pri ${ND[pri]:-#ff1238} acc ${ND[acc]:-#1fe3f0} hi ${ND[hi]:-#f6e33b} txt ${ND[txt]:-#ebe7ef}
     dim ${ND[dim]:-#857e93} line ${ND[line]:-#5e1a2b} ok ${ND[ok]:-#22f59a} warn ${ND[warn]:-#f6e33b}
     bad ${ND[bad]:-#ff4f5e} mag ${ND[mag]:-#5b8cff} deep ${ND[deep]:-#2a1318})
  local P=$(_jk_rgb $c[pri]) A=$(_jk_rgb $c[acc]) H=$(_jk_rgb $c[hi]) T=$(_jk_rgb $c[txt])
  local D=$(_jk_rgb $c[dim]) L=$(_jk_rgb $c[line]) O=$(_jk_rgb $c[ok]) M=$(_jk_rgb $c[mag])
  local B=$'\e[1m' R=$'\e[0m'
  local W=${COLUMNS:-80} Hh=${LINES:-24}
  local node=$(printf '%04X' $(( RANDOM % 65536 )))
  local host=${HOST%%.*} me=${USER:-$USERNAME}
  typeset -g _jk_skip=0

  printf '\e[?1049h\e[?25l\e[2J'         # alternate screen, hide cursor
  trap 'printf "\e[0m\e[?25h\e[?1049l"; trap - INT; return 130' INT

  # frame, like the deck's boot screens
  _jk_at 2 4; printf '%s%s' "$D" "NETDECK // NEURAL INTERFACE // 接続"
  local right="OPERATOR ${me:u}@${host:u} // NODE 0x$node"
  _jk_at 2 $(( W - ${#right} - 3 )); printf '%s%s' "$D" "$right"
  _jk_at 3 4; printf '%s%s' "$L" "${(l:$((W-6))::─:)}"
  _jk_at $(( Hh - 2 )) 4; printf '%s%s' "$L" "${(l:$((W-6))::─:)}"
  _jk_at $(( Hh - 1 )) 4; printf '%s%s' "$D" "© 2077 ARASAKA // ALL ACTIVITY IS GHOSTED"
  local hint="ANY KEY SKIPS"
  _jk_at $(( Hh - 1 )) $(( W - ${#hint} - 3 )); printf '%s%s' "$D" "$hint"

  local cw=62 x=$(( (W - 62) / 2 )) y=$(( Hh / 2 - 7 ))
  (( x < 3 )) && { x=3; cw=$(( W - 6 )) }
  (( y < 5 )) && y=5
  _jk_at $y $x; printf '%s%s%s' "$A$B" "端末 // TUNING IN" "$R"
  y=$(( y + 2 ))

  local -a steps=(
    "locating deck|${host}:0x$node|FOUND|ok"
    "neural handshake|operator ${me}|ACCEPTED|ok"
    "ICE perimeter|black ICE sentinel|BYPASSED|ok"
    "trace|netwatch sweep|MASKED|warn"
  )
  local s label detail res role row=$y
  for s in $steps; do
    label=${s%%|*}; s=${s#*|}; detail=${s%%|*}; s=${s#*|}; res=${s%%|*}; role=${s#*|}
    _jk_type $row $x "$T" "▸ ${(r:18::.:)label} $detail"
    _jk_wait 18
    _jk_at $row $(( x + cw - ${#res} - 4 )); printf '%s[ %s ]%s' "$(_jk_rgb $c[$role])$B" "$res" "$R"
    row=$(( row + 1 ))
  done

  # synapse sync bar with a hex stream underneath
  row=$(( row + 1 ))
  local bw=$(( cw - 26 )) i n pct hex b
  for (( i = 0; i <= 50; i++ )); do
    n=$(( i * bw / 50 )); pct=$(( i * 973 / 50 ))
    _jk_at $row $x
    printf '%s▸ synapse sync  %s%s%s%s  %s%3d.%d%%%s' "$T" "$A" "${(l:$n::▰:)}" "$L" "${(l:$((bw-n))::▱:)}" \
      "$H$B" $(( pct / 10 )) $(( pct % 10 )) "$R"
    hex=""
    repeat $(( cw / 3 )); do printf -v b '%02X ' $(( RANDOM % 256 )); hex+=$b; done
    _jk_at $(( row + 1 )) $(( x + 2 )); printf '%s%s' "$L" "$hex"
    _jk_wait 2 || break
  done
  n=$bw
  _jk_at $row $x
  printf '%s▸ synapse sync  %s%s  %s%3d.%d%%%s' "$T" "$A" "${(l:$n::▰:)}" "$H$B" 97 3 "$R"
  _jk_at $(( row + 1 )) $(( x + 2 )); printf '%s%s' "$D" "${(l:$((cw-2)):: :)}"

  # countdown with a little glitch
  row=$(( row + 3 ))
  local glyphs='░▒▓█▀▄#$%&@*+=<>/\|~^' word="JACKING IN" g k
  for k in 3 2 1; do
    repeat 3; do
      g=""
      for (( i = 1; i <= ${#word}; i++ )); do
        (( RANDOM % 4 )) && g+=${word[i]} || g+=${glyphs[$(( RANDOM % ${#glyphs} + 1 ))]}
      done
      _jk_at $row $(( (W - 16) / 2 )); printf '%s%s  %s%s%s' "$P$B" "$g" "$H" "$k" "$R"
      _jk_wait 8 || break 2
    done
    _jk_at $row $(( (W - 16) / 2 )); printf '%s%s  %s%s%s' "$P$B" "$word" "$H" "$k" "$R"
    _jk_wait 14 || break
  done

  # flash: bars sweep the screen, then the link line
  for (( i = 0; i < 6; i++ )); do
    _jk_at $(( RANDOM % (Hh - 2) + 2 )) 1; printf '%s%s%s' "$(_jk_bg $c[pri])" "${(l:$W:: :)}" "$R"
    _jk_at $(( RANDOM % (Hh - 2) + 2 )) 1; printf '%s%s%s' "$(_jk_bg $c[acc])" "${(l:$W:: :)}" "$R"
    sleep 0.03
  done
  printf '\e[2J'
  local done_msg="◢ LINK ESTABLISHED // WELCOME BACK, ${me:u}"
  _jk_at $(( Hh / 2 )) $(( (W - ${#done_msg}) / 2 )); printf '%s%s%s' "$O$B" "$done_msg" "$R"
  sleep 0.5
  printf '\e[0m\e[?25h\e[?1049l'
  trap - INT
  return 0
}

jackin() {
  emulate -L zsh
  setopt local_traps
  local mode=session quick=0 a
  for a in "$@"; do
    case $a in
      --here|-H|--terminal) mode=here ;;
      -s|--session) mode=session ;;
      -q|--quick) quick=1 ;;
      -h|--help) print "jackin [--here] [--quick]  -  switch to the NETDECK session (--here: open the deck in this terminal)"; return ;;
    esac
  done
  if [[ -n $NETDECK_KIOSK ]]; then
    print -P "%F{${ND[acc]:-cyan}}◢ already jacked in%f %F{${ND[dim]:-grey}}- this is the NETDECK session (F10 → U goes back to Ubuntu)%f"
    return 0
  fi
  local deck=${commands[netdeck]:-$HOME/.local/bin/netdeck}
  if [[ ! -x $deck ]]; then
    print -P "%F{${ND[bad]:-red}}✗ netdeck isn't installed%f - run ./install.sh in the netdeck folder"
    return 1
  fi
  if [[ $mode == session ]]; then
    local sw=${commands[netdeck-switch]:-$HOME/.local/bin/netdeck-switch}
    if [[ ! -x $sw || ! -e /usr/local/sbin/netdeck-switch-root ]]; then
      print -P "%F{${ND[bad]:-red}}✗ session switching isn't installed%f - run ./install.sh --session in the netdeck folder"
      print -P "%F{${ND[dim]:-grey}}  (jackin --here opens the deck in this terminal meanwhile)%f"
      return 1
    fi
    local ans
    print -nP "%F{${ND[warn]:-yellow}}◢ jack into the NETDECK session?%f %F{${ND[dim]:-grey}}apps open in Ubuntu will close%f %F{${ND[hi]:-yellow}}[Y/n]%f "
    read -k 1 ans; print
    [[ $ans == [nN] ]] && return 0
    (( quick )) || _jackin_sequence || return $?
    "$sw" deck
  else
    (( quick )) || _jackin_sequence || return $?
    "$deck" --no-boot
  fi
}

# nightdeck: jack into the Raspberry Pi. The sequence and real probes live in netdeck-nightdeck.
nightdeck() {
  local nd=${commands[netdeck-nightdeck]:-$HOME/.local/bin/netdeck-nightdeck}
  if [[ ! -x $nd ]]; then
    print -P "%F{${ND[bad]:-red}}✗ netdeck-nightdeck isn't installed%f - run ./install.sh in the netdeck folder"
    return 1
  fi
  "$nd" "$@"
}
compdef _ssh nightdeck 2>/dev/null
