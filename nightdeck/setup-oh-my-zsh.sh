#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run as your normal Pi user.' >&2
    exit 1
fi
config="${XDG_CONFIG_HOME:-$HOME/.config}/nightdeck/zsh"
if [ ! -e "$HOME/.oh-my-zsh" ] && [ ! -L "$HOME/.oh-my-zsh" ]; then
    git clone --depth 1 -- https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh"
fi
test -f "$HOME/.oh-my-zsh/oh-my-zsh.sh"
install -d -m 0700 "$config/custom/themes" "$config/cache"
install -m 0644 cyberdeck/cyberdeck.zsh-theme "$config/custom/themes/cyberdeck.zsh-theme"
install -m 0644 cyberdeck/cyberdeck-extras.zsh "$config/custom/cyberdeck-extras.zsh"
temp=$(mktemp "$config/.zshrc.XXXXXX")
trap 'rm -f -- "$temp"' EXIT HUP INT TERM
cat > "$temp" <<'ZSH'
export ZSH="$HOME/.oh-my-zsh"
export ZSH_CUSTOM="$ZDOTDIR/custom"
export ZSH_CACHE_DIR="$ZDOTDIR/cache"
zstyle ':omz:update' mode disabled
ZSH_THEME="cyberdeck"
plugins=(git)
source "$ZSH/oh-my-zsh.sh"
if [[ -o interactive && $SHLVL -gt 2 ]]; then
    cyberdeck_banner
fi
ZSH
mv -fT -- "$temp" "$config/.zshrc"
printf '%s\n' 'Open Zsh from Nightdeck to use your Cyberdeck theme.'
