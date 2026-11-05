#!/usr/bin/env bash
# Style zsh + oh-my-zsh in the NETDECK//OS look.
#
#   ./zsh/install-zsh.sh            install zsh, oh-my-zsh, plugins and the netrunner theme
#   ./zsh/install-zsh.sh --default  ...and make zsh your login shell
#   ./zsh/install-zsh.sh --undo     put your previous ~/.zshrc back
#
# Your existing ~/.zshrc is backed up to ~/.zshrc.pre-netdeck before anything is written.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZSH_DIR="${ZSH:-$HOME/.oh-my-zsh}"
CUSTOM="${ZSH_CUSTOM:-$ZSH_DIR/custom}"
BACKUP="$HOME/.zshrc.pre-netdeck"
red=$'\e[38;5;197m'; cyan=$'\e[38;5;51m'; yel=$'\e[38;5;227m'; dim=$'\e[38;5;245m'; rst=$'\e[0m'
say() { printf '%s◢%s %s\n' "$red" "$rst" "$*"; }

DEFAULT=0; UNDO=0
for a in "$@"; do
  case "$a" in
    --default) DEFAULT=1 ;;
    --undo) UNDO=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) say "unknown option: $a"; exit 1 ;;
  esac
done

if (( UNDO )); then
  if [[ -f $BACKUP ]]; then
    cp "$BACKUP" "$HOME/.zshrc"
    say "restored your previous ~/.zshrc from $BACKUP"
  else
    say "no backup found ($BACKUP) - nothing to restore"
  fi
  exit 0
fi

need=()
for p in zsh git curl; do command -v "$p" >/dev/null || need+=("$p"); done
if (( ${#need[@]} )); then
  say "installing ${cyan}${need[*]}${rst} (sudo)"
  sudo apt-get install -y "${need[@]}"
fi

if [[ ! -d $ZSH_DIR ]]; then
  say "installing ${cyan}oh-my-zsh${rst}"
  RUNZSH=no CHSH=no KEEP_ZSHRC=yes ZSH="$ZSH_DIR" \
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
  say "oh-my-zsh already installed ${dim}($ZSH_DIR)${rst}"
fi

clone() {
  local url=$1 dest=$2
  if [[ -d $dest/.git ]]; then
    git -C "$dest" pull -q --ff-only || true
  else
    git clone -q --depth 1 "$url" "$dest"
  fi
}
mkdir -p "$CUSTOM/plugins" "$CUSTOM/themes"
clone https://github.com/zsh-users/zsh-autosuggestions "$CUSTOM/plugins/zsh-autosuggestions"
clone https://github.com/zsh-users/zsh-syntax-highlighting "$CUSTOM/plugins/zsh-syntax-highlighting"
say "plugins: ${cyan}autosuggestions, syntax-highlighting${rst} ${dim}+ git sudo extract history-substring-search fzf zoxide${rst}"

install -m 0644 "$HERE/netrunner.zsh-theme" "$CUSTOM/themes/netrunner.zsh-theme"
say "theme: ${cyan}netrunner${rst} ${dim}(follows your deck skin)${rst}"

if [[ -f $HOME/.zshrc ]] && ! grep -q "NETDECK//OS shell" "$HOME/.zshrc"; then
  cp "$HOME/.zshrc" "$BACKUP"
  say "backed up your old ~/.zshrc to ${cyan}$BACKUP${rst} ${dim}(move anything you want to keep into ~/.zshrc.local)${rst}"
fi
install -m 0644 "$HERE/zshrc" "$HOME/.zshrc"
say "wrote ${cyan}~/.zshrc${rst}"

if (( DEFAULT )) && [[ "$(getent passwd "$USER" | cut -d: -f7)" != "$(command -v zsh)" ]]; then
  say "making zsh your login shell (asks for your password)"
  chsh -s "$(command -v zsh)"
  say "done - it applies to new logins"
fi

printf '\n%s   try it now:%s zsh%s   %s· switch colors: deckskin <name> · follow the deck: deckskin sync%s\n' \
  "$dim" "$yel" "$rst" "$dim" "$rst"
if (( ! DEFAULT )); then
  printf '%s   make it your default shell:%s ./zsh/install-zsh.sh --default%s\n\n' "$dim" "$yel" "$rst"
fi
