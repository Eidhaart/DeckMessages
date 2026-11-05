# ▌CYBERDECK extras // auto-loaded from $ZSH_CUSTOM

ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=#6E1A2A'

typeset -gA ZSH_HIGHLIGHT_STYLES
ZSH_HIGHLIGHT_STYLES[command]='fg=#00FFFF'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=#00FFFF,bold'
ZSH_HIGHLIGHT_STYLES[alias]='fg=#00FFFF'
ZSH_HIGHLIGHT_STYLES[function]='fg=#00FFFF'
ZSH_HIGHLIGHT_STYLES[precommand]='fg=#FF003C,bold'
ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=#FF003C,bold,underline'
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=#FF003C'
ZSH_HIGHLIGHT_STYLES[path]='fg=#FFEE08'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=#1DED83'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=#1DED83'
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=#FFEE08'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=#FFEE08'
ZSH_HIGHLIGHT_STYLES[comment]='fg=#7A0A22,italic'
ZSH_HIGHLIGHT_STYLES[commandseparator]='fg=#FF003C'
ZSH_HIGHLIGHT_STYLES[redirection]='fg=#FF003C'

# dirs cyan · executables red · links yellow · archives green
export LS_COLORS='di=1;38;2;0;255;255:ex=1;38;2;255;0;60:ln=38;2;255;238;8:fi=38;2;250;250;250:*.tar=38;2;29;237;131:*.gz=38;2;29;237;131:*.zip=38;2;29;237;131:*.md=38;2;255;100;120:*.json=38;2;255;238;8'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu select

zmodload zsh/zselect 2>/dev/null
_cp_beat() { [[ ${CYBERDECK_ANIM:-1} == 1 ]] && zselect -t 3 2>/dev/null; return 0 }
_cp_line() { # label value [warn]
  local G=$'\e[38;2;29;237;131m' Y=$'\e[38;2;255;238;8m' R=$'\e[38;2;255;0;60m'
  local C=$'\e[38;2;0;255;255m' D=$'\e[38;2;122;10;34m' X=$'\e[0m'
  local tag="${G}[ OK ]"; [[ -n $3 ]] && tag="${Y}[ !! ]"
  local dots=${(l:$(( 20 - ${#1} ))::.:)}
  print -r -- " ${tag}${X} ${R}${1}${D} ${dots} ${C}${2}${X}"; _cp_beat
}
cyberdeck_banner() {
  local R=$'\e[38;2;255;0;60m' Y=$'\e[38;2;255;238;8m' C=$'\e[38;2;0;255;255m' G=$'\e[38;2;29;237;131m'
  local D=$'\e[38;2;122;10;34m' B=$'\e[1m' X=$'\e[0m' RB=$'\e[48;2;255;0;60m\e[38;2;14;14;14m\e[1m'
  local w=$(( COLUMNS > 64 ? 64 : COLUMNS - 2 ))

  # real readouts
  local ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
  local temp=""; local t; for t in /sys/class/thermal/thermal_zone*/temp(N); do
    [[ $(<${t:h}/type) == (x86_pkg_temp|cpu*|acpitz|k10temp) ]] && { temp=$(( $(<$t) / 1000 )); break } ; done
  local bat=""; [[ -r /sys/class/power_supply/BAT0/capacity ]] && bat=$(</sys/class/power_supply/BAT0/capacity)
  local mem=$(free -h | awk '/Mem/{print $3" / "$2}')
  local disk=$(df -h / | awk 'NR==2{print $5}')
  local up=$(uptime -p | sed 's/up //; s/ hours\?/ H/; s/ minutes\?/ MIN/; s/ days\?/ D/; s/,//g')


  print -r -- " ${RB} SYS.BOOT ${X} ${R}${B}${(U)HOST}${X}${R} // SIGNAL::ONLINE // $(LC_ALL=C date +'%a %d %b %H:%M' | tr a-z A-Z)${X}"; _cp_beat
  print -r -- " ${D}${(l:$w::─:)}${X}"; _cp_beat
  [[ -n $ip ]] && _cp_line "NEURAL LINK" "ESTABLISHED  $ip" || _cp_line "NEURAL LINK" "OFFLINE" warn
  [[ -n $temp ]] && { (( temp > 85 )) && _cp_line "CORE TEMP" "${temp}°C" warn || _cp_line "CORE TEMP" "${temp}°C" }
  [[ -n $bat ]] && { (( bat < 20 )) && _cp_line "CELL CHARGE" "${bat}%" warn || _cp_line "CELL CHARGE" "${bat}%" }
  _cp_line "RAM" "$mem"
  _cp_line "STORAGE" "${disk} USED"
  _cp_line "UPTIME" "${(U)up}"
  # glitch bar
  local bar="" i; for (( i=0; i<w; i++ )); do (( RANDOM % 11 == 0 )) && bar+="▂" || bar+="▁"; done
  print -r -- " ${R}${bar}${X}"
}
[[ -o interactive && $SHLVL -le 2 ]] && cyberdeck_banner
alias jack-in='clear && cyberdeck_banner'
