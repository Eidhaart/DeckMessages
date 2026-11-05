# ▌CYBERDECK // oh-my-zsh theme // official 2077 palette
typeset -g CP_RED='#FF003C' CP_YEL='#FFEE08' CP_CYAN='#00FFFF' CP_GRN='#1DED83'
typeset -g CP_WHITE='#FAFAFA' CP_DARK='#0E0E0E' CP_DIM='#7A0A22'

ZSH_THEME_GIT_PROMPT_PREFIX="  %F{$CP_DIM}git:%F{$CP_CYAN}"
ZSH_THEME_GIT_PROMPT_SUFFIX="%f"
ZSH_THEME_GIT_PROMPT_DIRTY=" %F{$CP_RED}✱"
ZSH_THEME_GIT_PROMPT_CLEAN=" %F{$CP_GRN}✓"

_cp_venv() { [[ -n $VIRTUAL_ENV ]] && print -n "  %F{$CP_DIM}py:%F{$CP_GRN}${VIRTUAL_ENV:t}%f" }

#  EIDHAART  ~/Downloads  git:main ✱                    ERR 1  19:52:04
# // _
PROMPT='
%K{$CP_RED}%F{$CP_DARK}%B ${(U)USER} %b%k  %F{$CP_YEL}%(4~|…/%3~|%~)%f$(git_prompt_info)$(_cp_venv)
%F{$CP_RED}%B//%b%f '

RPROMPT='%(?..%K{$CP_YEL}%F{$CP_DARK}%B ERR %? %b%k%f  )%F{$CP_RED}%D{%H:%M:%S}%f'
PROMPT2='%F{$CP_DIM}// %f'
