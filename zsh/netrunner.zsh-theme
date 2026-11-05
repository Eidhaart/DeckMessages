# netrunner.zsh-theme - NETDECK//OS prompt for oh-my-zsh
#
#   ┏━ ◢ user@host // ~/projects/netdeck  ⎇ main ●                     ✗ 1 · 4s · 12:41:07
#   ┗━▶
#
# Colors follow the NETDECK skin: the deck's current theme (~/.config/netdeck/config.json), or $NETDECK_SKIN,
# or `deckskin <name>` to switch live. Truecolor where the terminal supports it, nearest 256 color elsewhere.

zmodload zsh/datetime 2>/dev/null
[[ $COLORTERM == (truecolor|24bit) ]] || zmodload zsh/nearcolor 2>/dev/null
setopt prompt_subst

# skin: pri acc hi txt dim line ok warn bad mag deep   (generated from netdeck.py THEMES)
typeset -gA NETDECK_SKINS
NETDECK_SKINS=(
  netrunner   '#ff1238 #1fe3f0 #f6e33b #ebe7ef #857e93 #5e1a2b #22f59a #f6e33b #ff4f5e #5b8cff #2a1318'
  arasaka     '#ff2a3c #00f0ff #fcee0a #e9dfe0 #8a3a40 #6a2f36 #00ff9f #fcee0a #ff2a3c #ff2e88 #2a1216'
  sodium      '#ffae3d #43dbe8 #ffd27a #e9e5da #8f98a8 #36485f #7ee3a0 #ffae3d #ff506a #b995ff #1a2230'
  matrix      '#3fe3ff #ff6fb1 #7deeff #dff6fb #5a7d88 #1e5a6a #5dffb0 #ffe14d #ff5577 #5dffb0 #0d2730'
  neon        '#ff3ea5 #2df0ff #ffe14d #f3e9ff #8a78b8 #57349f #5dffb0 #ffe14d #ff5a5a #ff7ad0 #251552'
  blackout    '#ffe600 #00e5ff #ffffff #f2f2f2 #8a8a8a #4a4a4a #3dff8a #ffe600 #ff5252 #ff8cff #1e1e1e'
  chrome      '#ff6a13 #c9d3dc #ffcc33 #e8ecef #6c7884 #434b56 #8be36b #ffcc33 #ff3b3b #c9d3dc #1f2329'
  ronin       '#d7263d #d4af37 #7fb8c9 #efe6e2 #7d6a66 #553c3e #9ccc65 #d4af37 #ff5f5f #7fb8c9 #241a1b'
  blood       '#ff2a1a #ff9c2a #ffd0c4 #ffe9e4 #7d5a54 #6e2020 #8be36b #ff9c2a #ff2a1a #ff6a50 #2a0b0b'
  ghost       '#e8f6ff #7cf9ff #fff38a #eef8ff #64798a #3a5361 #7cf7a0 #fff38a #ff6a8a #bff6ff #172028'
  astral      '#c39bff #ffd27a #7fd9ff #efe9fb #6f6488 #4f3a78 #8ef0c0 #ffd27a #ff6a8a #7fd9ff #24163a'
  resonance   '#7cf7e4 #c07bff #ff8ad8 #e6f4ff #66719a #353f6e #7cf7a0 #ffe28a #ff5c8a #ff8ad8 #141a33'
  hazard      '#ffc400 #ff7a1a #4fc3f7 #eceae4 #7b8088 #4a525c #7ed957 #ff7a1a #ff4d4d #4fc3f7 #22262b'
  noir        '#d9a35b #4fd1c5 #e86a92 #ece4d8 #857b6f #544c44 #9ccf7a #d9a35b #ff6b5b #e86a92 #24211e'
  spraypaint  '#ff2d95 #2de2e6 #ffd23f #f2f0f5 #7a7a90 #454558 #b8ff3c #ffd23f #ff4040 #b8ff3c #1e1e28'
  jade        '#e8c15a #3fe0b0 #f5dc8e #e6f2ee #5f8a80 #2a6159 #7ef0b0 #e8c15a #ff6270 #b995ff #12302b'
  rust        '#e2762a #6cc7b8 #c79cff #efe4d6 #8a7560 #664a31 #9bd16b #e2a03c #ff5a4a #c79cff #2a1f16'
  terminal    '#39ff7a #d6ff5c #7dffd0 #c9f7d6 #4f8a62 #1e6b3f #39ff7a #d6ff5c #ff5a4d #7dffd0 #0c2a16'
)

typeset -gA ND
_netdeck_skin_name() {
  [[ -n $NETDECK_SKIN && -n ${NETDECK_SKINS[$NETDECK_SKIN]} ]] && { print -r -- $NETDECK_SKIN; return }
  local conf="${XDG_CONFIG_HOME:-$HOME/.config}/netdeck/config.json" body
  if [[ -r $conf ]]; then
    body=$(<$conf)
    if [[ $body =~ '"theme": *"([A-Za-z0-9_-]+)"' && -n ${NETDECK_SKINS[$match[1]]} ]]; then
      print -r -- $match[1]; return
    fi
  fi
  print -r -- netrunner
}

netdeck_apply_skin() {
  local name=${1:-$(_netdeck_skin_name)}
  local -a c; c=(${=NETDECK_SKINS[$name]})
  (( ${#c} == 11 )) || { c=(${=NETDECK_SKINS[netrunner]}); name=netrunner }
  ND=(name $name pri $c[1] acc $c[2] hi $c[3] txt $c[4] dim $c[5] line $c[6] ok $c[7] warn $c[8] bad $c[9]
      mag $c[10] deep $c[11])

  ZSH_THEME_GIT_PROMPT_PREFIX="  %F{$ND[hi]}⎇ "
  ZSH_THEME_GIT_PROMPT_SUFFIX="%f"
  ZSH_THEME_GIT_PROMPT_DIRTY=" %F{$ND[mag]}●"
  ZSH_THEME_GIT_PROMPT_CLEAN=" %F{$ND[ok]}✓"

  # zsh-syntax-highlighting: commands cyan, structure red, strings yellow, errors alert
  if (( ${+ZSH_HIGHLIGHT_STYLES} )); then
    ZSH_HIGHLIGHT_STYLES[default]="fg=$ND[txt]"
    ZSH_HIGHLIGHT_STYLES[unknown-token]="fg=$ND[bad],bold"
    ZSH_HIGHLIGHT_STYLES[command]="fg=$ND[acc]"
    ZSH_HIGHLIGHT_STYLES[builtin]="fg=$ND[acc]"
    ZSH_HIGHLIGHT_STYLES[alias]="fg=$ND[acc],bold"
    ZSH_HIGHLIGHT_STYLES[function]="fg=$ND[acc],bold"
    ZSH_HIGHLIGHT_STYLES[precommand]="fg=$ND[pri],bold"
    ZSH_HIGHLIGHT_STYLES[reserved-word]="fg=$ND[pri]"
    ZSH_HIGHLIGHT_STYLES[commandseparator]="fg=$ND[pri]"
    ZSH_HIGHLIGHT_STYLES[redirection]="fg=$ND[pri]"
    ZSH_HIGHLIGHT_STYLES[path]="fg=$ND[txt],underline"
    ZSH_HIGHLIGHT_STYLES[globbing]="fg=$ND[mag]"
    ZSH_HIGHLIGHT_STYLES[single-hyphen-option]="fg=$ND[dim]"
    ZSH_HIGHLIGHT_STYLES[double-hyphen-option]="fg=$ND[dim]"
    ZSH_HIGHLIGHT_STYLES[single-quoted-argument]="fg=$ND[hi]"
    ZSH_HIGHLIGHT_STYLES[double-quoted-argument]="fg=$ND[hi]"
    ZSH_HIGHLIGHT_STYLES[dollar-quoted-argument]="fg=$ND[hi]"
    ZSH_HIGHLIGHT_STYLES[back-quoted-argument]="fg=$ND[mag]"
    ZSH_HIGHLIGHT_STYLES[comment]="fg=$ND[dim],italic"
  fi
  ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=$ND[dim]"
  # fzf in the same colors
  export FZF_DEFAULT_OPTS="--color=fg:$ND[txt],hl:$ND[acc],fg+:$ND[txt],hl+:$ND[acc],bg+:-1,info:$ND[dim],\
prompt:$ND[pri],pointer:$ND[pri],marker:$ND[hi],spinner:$ND[mag],header:$ND[dim],border:$ND[line] \
--prompt='◢ ' --pointer='▶' --marker='●' --border=sharp --layout=reverse --height=40%"
}

deckskin() {
  if [[ -z $1 ]]; then
    print -P "%F{$ND[dim]}skin:%f %F{$ND[acc]}$ND[name]%f   %F{$ND[dim]}options:%f ${(ok)NETDECK_SKINS}"
    print -P "%F{$ND[dim]}deckskin <name> switches this shell · deckskin sync follows the deck's theme%f"
    return
  fi
  if [[ $1 == sync ]]; then unset NETDECK_SKIN; netdeck_apply_skin; return; fi
  [[ -n ${NETDECK_SKINS[$1]} ]] || { print "unknown skin: $1"; return 1 }
  export NETDECK_SKIN=$1
  netdeck_apply_skin $1
}

# --- command timer
_nd_preexec() { _nd_start=$EPOCHREALTIME }
_nd_precmd() {
  local rc=$?
  _nd_rc=0
  _nd_took=""
  [[ -n $_nd_start ]] && _nd_rc=$rc   # only report codes of commands you actually ran
  if [[ -n $_nd_start ]]; then
    local d=$(( EPOCHREALTIME - _nd_start ))
    (( d >= 3 )) && _nd_took=$(printf '%ds' ${d%.*})
    (( d >= 60 )) && _nd_took=$(printf '%dm%02ds' $(( ${d%.*} / 60 )) $(( ${d%.*} % 60 )))
  fi
  unset _nd_start
}
autoload -Uz add-zsh-hook
add-zsh-hook preexec _nd_preexec
add-zsh-hook precmd _nd_precmd

_nd_right() {
  local out=""
  (( _nd_rc )) && out+="%F{$ND[bad]}✗ $_nd_rc%f %F{$ND[line]}·%f "
  [[ -n $_nd_took ]] && out+="%F{$ND[warn]}$_nd_took%f %F{$ND[line]}·%f "
  out+="%F{$ND[dim]}%D{%H:%M:%S}%f"
  print -rn -- $out
}

_nd_user() {
  local u="%F{$ND[acc]}%n%f%F{$ND[dim]}@%m%f"
  [[ $UID == 0 ]] && u="%F{$ND[bad]}%B%n%b%f%F{$ND[dim]}@%m%f"
  [[ -n $SSH_CONNECTION ]] && u+=" %F{$ND[mag]}⇄ ssh%f"
  [[ -n $NETDECK ]] && u+=" %F{$ND[dim]}// %F{$ND[hi]}deck link%f"
  print -rn -- $u
}

netdeck_apply_skin
PROMPT='%F{$ND[pri]}┏━ ◢%f $(_nd_user) %F{$ND[line]}//%f %F{$ND[txt]}%B%(5~|…/%3~|%~)%b%f$(git_prompt_info)
%F{$ND[pri]}┗━%(?.%F{$ND[pri]}.%F{$ND[bad]})▶%f '
RPROMPT='$(_nd_right)'
PROMPT2='%F{$ND[pri]}  ┃%f %F{$ND[dim]}%_%f %F{$ND[pri]}▸%f '
