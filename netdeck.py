#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NETDECK//OS  -  a corp terminal, hijacked and bootstrapped for netrunners.

A full-screen cyberpunk dashboard for Linux terminals:
  * live system telemetry read straight from /proc (no dependencies)
  * a categorized browser of every installed program, with one-key launch
  * a command console that runs real commands, streams their output,
    and can drop you into a raw shell and back
  * boot sequence, glitches, scanlines, data rain and a CRT power-off

Python 3.8+ and curses only. Run:  python3 netdeck.py   (or `netdeck` once installed)
"""

import argparse
import curses
import getpass
import glob
import json
import locale
import math
import os
import pwd
import queue
import random
import re
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import deque

VERSION = "2.0.77"
HOME = os.path.expanduser("~")
CONF_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "netdeck")
DATA_DIR = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share"), "netdeck")
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(HOME, ".cache"), "netdeck")
CONF_FILE = os.path.join(CONF_DIR, "config.json")
HIST_FILE = os.path.join(DATA_DIR, "history")
SHARDS_FILE = os.path.join(DATA_DIR, "shards.log")

DEFAULT_LAYOUT = {"left": ["sys", "mem", "disk", "net", "bio", "procs"], "right": ["dock", "console"]}
DEFAULT_CONF = {
    "theme": "netrunner",     # built-in or a name from "themes"
    "fx": True,               # glitches, flicker, typing effect
    "scan": True,             # alternating scanline rows
    "boot": True,             # boot sequence on start
    "ticker": True,           # scrolling news ticker
    "neural": True,           # small neural-link readout in the top bar
    "font": "JetBrains Mono", # applied by netdeck-session (foot / kitty / alacritty)
    "font_size": 13,
    "layout": DEFAULT_LAYOUT,
    "dock": None,             # pinned commands; None = auto-pick from what is installed
    "overrides": {},          # per-theme color tweaks: {"netrunner": {"pri": "#ff2a6d"}}
    "themes": {},             # custom themes: {"mine": {"base": "netrunner", "pri": 198, ...}}
}

# --------------------------------------------------------------------------------------------
#  Look & feel
# --------------------------------------------------------------------------------------------

# Roles: bg/bg2 (alternating scanline rows), pri (frame + headers), acc (highlights),
# hi (hot text), dim (chrome), txt (body), ok/warn/bad (status), mag (2nd accent), deep (empty bars)
THEMES = {
    "netrunner": dict(bg=233, bg2=234, pri=203, acc=87, hi=227, dim=95, txt=224, ok=85, warn=215, bad=197, mag=199, deep=52),
    "arasaka":   dict(bg=232, bg2=233, pri=196, acc=255, hi=220, dim=88, txt=251, ok=121, warn=214, bad=196, mag=210, deep=52),
    "netwatch":  dict(bg=233, bg2=234, pri=39, acc=51, hi=231, dim=24, txt=153, ok=85, warn=221, bad=203, mag=141, deep=17),
    "toxic":     dict(bg=232, bg2=233, pri=82, acc=190, hi=231, dim=28, txt=157, ok=46, warn=226, bad=197, mag=135, deep=22),
    "afterlife": dict(bg=233, bg2=234, pri=207, acc=87, hi=227, dim=96, txt=225, ok=85, warn=215, bad=197, mag=171, deep=53),
    "amber":     dict(bg=232, bg2=233, pri=214, acc=230, hi=231, dim=94, txt=222, ok=150, warn=220, bad=202, mag=209, deep=52),
}
BASIC = dict(bg=curses.COLOR_BLACK, bg2=curses.COLOR_BLACK, pri=curses.COLOR_RED, acc=curses.COLOR_CYAN,
             hi=curses.COLOR_YELLOW, dim=curses.COLOR_BLUE, txt=curses.COLOR_WHITE, ok=curses.COLOR_GREEN,
             warn=curses.COLOR_YELLOW, bad=curses.COLOR_RED, mag=curses.COLOR_MAGENTA, deep=curses.COLOR_BLUE)

SPARK = "▁▂▃▄▅▆▇█"
KATA = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
RAIN_GLYPHS = KATA + "0123456789ABCDEF<>/\\=+*:"
GLITCH = "░▒▓█▀▄▌▐#$%&@*+=<>/\\|~^"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1b[@-Z\\-_]")

LOGO = [
    "███╗   ██╗███████╗████████╗██████╗ ███████╗ ██████╗██╗  ██╗",
    "████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔════╝██║ ██╔╝",
    "██╔██╗ ██║█████╗     ██║   ██║  ██║█████╗  ██║     █████╔╝ ",
    "██║╚██╗██║██╔══╝     ██║   ██║  ██║██╔══╝  ██║     ██╔═██╗ ",
    "██║ ╚████║███████╗   ██║   ██████╔╝███████╗╚██████╗██║  ██╗",
    "╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝",
]

BULLETINS = [
    "NETWATCH ADVISORY: rogue AI sighting past the Blackwall - all runners stay frosty",
    "ARASAKA STOCK +3.2% after orbital contract - your stolen deck doesn't care",
    "MAXTAC raid in Watson; avoid the Kabuki market tonight",
    "Night City forecast: acid drizzle, 31C, smog index CRITICAL",
    "Fixer board: 4 new gigs posted - eddies on delivery",
    "TRAUMA TEAM platinum response time down to 3m 40s",
    "Militech convoy rerouted through Santo Domingo - expect gridlock",
    "Corp telemetry for this node: BLACKHOLED",
    "Ripperdoc special: chrome tune-ups, no questions asked",
    "Afterlife reports record crowd; drinks named after dead legends",
    "Old Net static rising - signal integrity 87%",
    "Reminder: never jack in without a backup proxy, choom",
]

FEED = [
    ("NETWATCH", "dim", "sweep passed over subnet - signature masked"),
    ("ICE", "acc", "corp ICE heartbeat spoofed - checksum accepted"),
    ("PROXY", "acc", "chain rotated: 7 hops via Pacifica relay"),
    ("DAEMON", "mag", "ghostkey resident in kernel space - nominal"),
    ("TELEMETRY", "dim", "corp beacon blackholed - packets dropped"),
    ("FIXER", "hi", "new gig on the board - flagged for later"),
    ("BIOMON", "ok", "vitals nominal. stay frosty, choom"),
    ("OLDNET", "mag", "static beyond the wall... something is listening"),
    ("ICE", "warn", "black ICE probe deflected at port 2077"),
    ("CACHE", "dim", "shredding volatile logs - 0 traces left"),
    ("UPLINK", "acc", "encrypted tunnel re-keyed (x25519 / chacha20)"),
    ("SPOOF", "dim", "MAC rotated on the physical layer - ghosted"),
    ("NETWATCH", "warn", "agent ping on adjacent node - holding still"),
    ("DAEMON", "mag", "watchdog patched - corp kill-switch neutered"),
    ("FIXER", "hi", "message from an unknown sender: 'wake up, runner'"),
]

APP_CATS = [
    ("ICEBREAKERS", "security & forensics", {"Security"}),
    ("CODE FORGE", "development", {"Development", "IDE", "Debugger", "RevisionControl", "GUIDesigner"}),
    ("NET UPLINK", "internet & comms", {"Network", "WebBrowser", "Email", "Chat", "InstantMessaging",
                                        "P2P", "FileTransfer", "News", "RemoteAccess"}),
    ("MEDIA SYNTH", "audio & video", {"AudioVideo", "Audio", "Video", "Player", "Recorder", "Music", "TV"}),
    ("VISUAL CORTEX", "graphics", {"Graphics", "2DGraphics", "3DGraphics", "Photography",
                                   "RasterGraphics", "VectorGraphics", "Scanning"}),
    ("CORPO SUITE", "office", {"Office", "WordProcessor", "Spreadsheet", "Presentation", "Calendar",
                               "ContactManagement", "Finance"}),
    ("SIM ARCADE", "games", {"Game"}),
    ("DATA LAB", "science & education", {"Science", "Education", "Math", "Astronomy"}),
    ("SYS CORE", "system", {"System", "Monitor", "TerminalEmulator", "FileManager", "PackageManager"}),
    ("CONFIG MATRIX", "settings", {"Settings", "DesktopSettings", "HardwareSettings"}),
    ("UTILITIES", "accessories", {"Utility", "Accessories", "TextEditor", "Archiving", "Calculator", "Clock"}),
]

# --------------------------------------------------------------------------------------------
#  Terminal software catalog ("the black market")
#  Installed entries are launchable; missing ones can be installed from the arsenal (key i).
#  inst: space-separated methods tried in order - apt:<pkg>  snap:<pkg>[/classic]  pipx:<pkg>
#        cargo:<crate>  gh:<owner/extension>  sh:<SCRIPTS key>
# --------------------------------------------------------------------------------------------


def T(bins, desc, inst="", name=None, argv=None, cli=False, check=None):
    bins = bins.split("|")
    return dict(bins=bins, name=name or bins[0], desc=desc, inst=inst, argv=argv, cli=cli, check=check)


SCRIPTS = {
    "lazygit": (
        'ARCH=$(uname -m); [ "$ARCH" = aarch64 ] && ARCH=arm64; '
        'V=$(curl -fsSL https://api.github.com/repos/jesseduffield/lazygit/releases/latest '
        '| grep -Po \'"tag_name": *"v\\K[^"]*\') && '
        'curl -fLo /tmp/lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/v${V}/'
        'lazygit_${V}_Linux_${ARCH}.tar.gz" && tar xf /tmp/lazygit.tar.gz -C /tmp lazygit && '
        'sudo install /tmp/lazygit -D -t /usr/local/bin/'),
    "lazydocker": "curl -fsSL https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/"
                  "install_update_linux.sh | bash",
    "claude": "curl -fsSL https://claude.ai/install.sh | bash",
    "npm-codex": "(command -v npm >/dev/null || sudo apt install -y npm) && sudo npm install -g @openai/codex",
    "npm-gemini": "(command -v npm >/dev/null || sudo apt install -y npm) && sudo npm install -g @google/gemini-cli",
    "lazyvim": (
        'if [ -e "$HOME/.config/nvim" ]; then echo "~/.config/nvim already exists - back it up first: '
        'mv ~/.config/nvim ~/.config/nvim.bak"; exit 1; fi; '
        'sudo snap install nvim --classic && git clone --depth 1 https://github.com/LazyVim/starter "$HOME/.config/nvim" '
        '&& rm -rf "$HOME/.config/nvim/.git" && echo "LazyVim ready - the first launch downloads its plugins"'),
}

TUI_CATALOG = [
    ("CODE // IDE & EDITORS", "terminal IDEs, editors, AI coding agents", [
        T("nvim", "Neovim: the hackable editor, a full IDE with plugins", "apt:neovim snap:nvim/classic",
          name="Neovim"),
        T("lazyvim", "Neovim set up like VS Code: file tree, LSP, git, fuzzy finder", "sh:lazyvim", name="LazyVim",
          argv=["nvim"], check="~/.config/nvim/lua/config/lazy.lua"),
        T("hx|helix", "Helix: modern modal editor, language servers built in", "apt:helix snap:helix/classic",
          name="Helix"),
        T("micro", "Micro: easy editor with mouse, Ctrl+S, Ctrl+C - feels like a GUI", "apt:micro snap:micro/classic",
          name="Micro"),
        T("claude", "Claude Code: AI coding agent in your terminal", "sh:claude", name="Claude Code"),
        T("codex", "Codex CLI: OpenAI coding agent", "sh:npm-codex", name="Codex CLI"),
        T("gemini", "Gemini CLI: Google coding agent", "sh:npm-gemini", name="Gemini CLI"),
        T("aider", "Aider: AI pair programming in your git repo", "pipx:aider-chat", name="Aider"),
        T("vim", "Vim: the classic modal editor", "apt:vim", name="Vim"),
        T("emacs", "Emacs (terminal build): the extensible editor", "apt:emacs-nox", name="Emacs"),
        T("kak", "Kakoune: selection-first modal editor", "apt:kakoune", name="Kakoune"),
        T("nano", "Nano: simple, always there", "apt:nano", name="Nano"),
    ]),
    ("GIT // GITHUB", "version control and GitHub", [
        T("lazygit", "lazygit: the git client everyone loves - stage, commit, rebase with keys",
          "apt:lazygit sh:lazygit", name="lazygit"),
        T("gh", "GitHub CLI: PRs, issues, repos, actions  (try: gh pr list)", "apt:gh snap:gh", name="GitHub CLI",
          cli=True),
        T("gh-dash", "GitHub dashboard: your PRs and issues in a TUI", "gh:dlvhdr/gh-dash", name="gh-dash",
          argv=["gh", "dash"], check="~/.local/share/gh/extensions/gh-dash"),
        T("gitui", "gitui: blazing fast git TUI", "apt:gitui cargo:gitui", name="gitui"),
        T("tig", "tig: browse git history and blame", "apt:tig", name="tig"),
        T("delta", "delta: beautiful side-by-side git diffs", "apt:git-delta", name="delta", cli=True),
        T("lazydocker", "lazydocker: manage containers like lazygit", "sh:lazydocker", name="lazydocker"),
    ]),
    ("FILES // NAVIGATION", "file managers, search, viewers", [
        T("yazi", "Yazi: blazing fast file manager with image previews", "snap:yazi/classic", name="Yazi"),
        T("ranger", "ranger: vim-keyed file manager", "apt:ranger", name="ranger"),
        T("mc", "Midnight Commander: two-pane classic", "apt:mc", name="Midnight Commander"),
        T("nnn", "nnn: tiny, ultra fast file manager", "apt:nnn", name="nnn"),
        T("lf", "lf: terminal file manager", "apt:lf", name="lf"),
        T("ncdu", "ncdu: find what eats your disk", "apt:ncdu", name="ncdu"),
        T("fzf", "fzf: fuzzy-find anything", "apt:fzf", name="fzf"),
        T("glow", "glow: render markdown in the terminal", "apt:glow snap:glow", name="glow"),
        T("rg", "ripgrep: insanely fast grep", "apt:ripgrep", name="ripgrep", cli=True),
        T("fdfind|fd", "fd: simple, fast find", "apt:fd-find", name="fd", cli=True),
        T("batcat|bat", "bat: cat with syntax highlighting", "apt:bat", name="bat", cli=True),
        T("eza", "eza: modern ls with colors and icons", "apt:eza", name="eza", cli=True),
        T("zoxide", "zoxide: smarter cd that learns your habits", "apt:zoxide", name="zoxide", cli=True),
        T("duf", "duf: pretty disk usage", "apt:duf", name="duf", cli=True),
    ]),
    ("SYSTEM // CONTROL", "monitors, network, audio, multiplexers", [
        T("btop", "btop: gorgeous resource monitor", "apt:btop snap:btop", name="btop"),
        T("htop", "htop: interactive process viewer", "apt:htop", name="htop"),
        T("nmtui", "Wi-Fi & network settings", "apt:network-manager", name="nmtui (Wi-Fi)"),
        T("pulsemixer", "volume control for PulseAudio / PipeWire", "apt:pulsemixer", name="pulsemixer"),
        T("alsamixer", "ALSA sound mixer", "apt:alsa-utils", name="alsamixer"),
        T("zellij", "Zellij: friendly terminal workspace / multiplexer", "snap:zellij/classic", name="Zellij"),
        T("tmux", "tmux: terminal multiplexer", "apt:tmux", name="tmux"),
        T("glances", "glances: everything-at-a-glance monitor", "apt:glances", name="glances"),
        T("nvtop", "nvtop: GPU monitor", "apt:nvtop", name="nvtop"),
        T("btm", "bottom: graphical process monitor", "cargo:bottom", name="bottom"),
        T("s-tui", "s-tui: CPU frequency, temp and stress", "apt:s-tui", name="s-tui"),
        T("iotop", "iotop: disk I/O per process", "apt:iotop", name="iotop"),
        T("powertop", "powertop: battery drain hunter", "apt:powertop", name="powertop"),
        T("fastfetch", "fastfetch: system info with ASCII art", "apt:fastfetch", name="fastfetch", cli=True),
        T("neofetch", "neofetch: system info with ASCII art", "apt:neofetch", name="neofetch", cli=True),
        T("lynis", "lynis: security audit of this machine", "apt:lynis", name="lynis", cli=True),
    ]),
    ("NET // COMMS", "browsing, mail, chat, recon", [
        T("w3m", "w3m: text-mode web browser", "apt:w3m", name="w3m"),
        T("lynx", "lynx: classic text browser", "apt:lynx", name="lynx"),
        T("aerc", "aerc: modern email client", "apt:aerc", name="aerc"),
        T("neomutt", "neomutt: power-user email", "apt:neomutt", name="neomutt"),
        T("newsboat", "newsboat: RSS/Atom reader", "apt:newsboat", name="newsboat"),
        T("weechat", "WeeChat: IRC / Matrix chat", "apt:weechat", name="WeeChat"),
        T("irssi", "irssi: IRC client", "apt:irssi", name="irssi"),
        T("termshark", "termshark: Wireshark in the terminal", "apt:termshark", name="termshark"),
        T("trip", "trippy: traceroute meets ping, live", "snap:trippy", name="trippy"),
        T("mtr", "mtr: live route + latency", "apt:mtr-tiny", name="mtr"),
        T("nethogs", "nethogs: bandwidth per process", "apt:nethogs", name="nethogs"),
        T("iftop", "iftop: bandwidth per connection", "apt:iftop", name="iftop"),
        T("bmon", "bmon: interface bandwidth graphs", "apt:bmon", name="bmon"),
        T("nmap", "nmap: network scanner (your own network)", "apt:nmap", name="nmap", cli=True),
        T("speedtest-cli", "internet speed test", "apt:speedtest-cli", name="speedtest", cli=True),
        T("rtorrent", "rTorrent: BitTorrent client", "apt:rtorrent", name="rTorrent"),
        T("aria2c", "aria2: download accelerator", "apt:aria2", name="aria2", cli=True),
    ]),
    ("MEDIA // SYNTH", "music, video, visuals", [
        T("ncspot", "ncspot: Spotify client (premium)", "snap:ncspot", name="ncspot"),
        T("cmus", "cmus: music player for local files", "apt:cmus", name="cmus"),
        T("mpv", "mpv: plays anything", "apt:mpv", name="mpv"),
        T("cava", "cava: audio spectrum visualizer", "apt:cava", name="cava"),
        T("ncmpcpp", "ncmpcpp: MPD music client", "apt:ncmpcpp", name="ncmpcpp"),
        T("yt-dlp", "yt-dlp: download video / audio", "apt:yt-dlp", name="yt-dlp", cli=True),
    ]),
    ("DATA // DEV TOOLS", "databases, APIs, spreadsheets, REPLs", [
        T("harlequin", "Harlequin: SQL IDE in the terminal", "pipx:harlequin", name="Harlequin"),
        T("posting", "Posting: API client (Postman for the terminal)", "pipx:posting", name="Posting"),
        T("vd", "VisiData: explore CSV, JSON, Excel, SQLite", "apt:visidata", name="VisiData"),
        T("sc-im", "sc-im: spreadsheet calculator", "apt:sc-im", name="sc-im"),
        T("http", "HTTPie: friendly HTTP requests", "apt:httpie", name="HTTPie", cli=True),
        T("jq", "jq: slice and filter JSON", "apt:jq", name="jq", cli=True),
        T("ipython3", "IPython: better Python REPL", "apt:ipython3", name="IPython"),
        T("bpython", "bpython: fancy Python REPL", "apt:bpython", name="bpython"),
        T("litecli", "litecli: SQLite with autocomplete", "apt:litecli", name="litecli"),
        T("pgcli", "pgcli: Postgres with autocomplete", "apt:pgcli", name="pgcli"),
        T("mycli", "mycli: MySQL with autocomplete", "apt:mycli", name="mycli"),
    ]),
    ("PRODUCTIVITY", "calendar, tasks, notes, time", [
        T("calcurse", "calcurse: calendar and todo", "apt:calcurse", name="calcurse"),
        T("task", "Taskwarrior: task manager", "apt:taskwarrior", name="Taskwarrior", cli=True),
        T("khal", "khal: CalDAV calendar", "apt:khal", name="khal"),
        T("tty-clock", "tty-clock: big terminal clock  (try: tty-clock -c)", "apt:tty-clock", name="tty-clock"),
        T("bc", "bc: calculator", "apt:bc", name="bc"),
    ]),
    ("SIM // ARCADE", "games and eye candy", [
        T("cbonsai", "cbonsai: grow a bonsai  (try: cbonsai -l)", "apt:cbonsai", name="cbonsai"),
        T("cmatrix", "cmatrix: digital rain", "apt:cmatrix", name="cmatrix"),
        T("asciiquarium", "asciiquarium: an aquarium", "apt:asciiquarium", name="asciiquarium"),
        T("bastet", "bastet: tetris that hates you", "apt:bastet", name="bastet"),
        T("nsnake", "nsnake: snake", "apt:nsnake", name="nsnake"),
        T("ninvaders", "ninvaders: space invaders", "apt:ninvaders", name="ninvaders"),
        T("moon-buggy", "moon-buggy: drive across the moon", "apt:moon-buggy", name="moon-buggy"),
        T("greed", "greed: eat the numbers", "apt:greed", name="greed"),
        T("hollywood", "hollywood: look extremely busy", "apt:hollywood", name="hollywood"),
        T("sl", "sl: steam locomotive", "apt:sl", name="sl"),
        T("figlet", "figlet: big ASCII letters", "apt:figlet", name="figlet", cli=True),
        T("lolcat", "lolcat: rainbow everything", "apt:lolcat", name="lolcat", cli=True),
        T("cowsay", "cowsay: a talking cow", "apt:cowsay", name="cowsay", cli=True),
        T("fortune", "fortune: random wisdom", "apt:fortune-mod", name="fortune", cli=True),
    ]),
    ("CLI KIT", "classic command-line tools you already have", [
        T(b, d, cli=True) for b, d in [
            ("ssh", "secure shell uplink"), ("curl", "transfer URLs"), ("wget", "download files"),
            ("ping", "ICMP echo probe"), ("traceroute", "trace packet route"), ("dig", "DNS query"),
            ("whois", "domain lookup"), ("nc", "netcat - raw sockets"), ("ss", "socket stats"),
            ("ip", "routing / interfaces"), ("nmcli", "NetworkManager CLI"), ("rsync", "sync files"),
            ("scp", "secure copy"), ("git", "version control"), ("python3", "python"), ("node", "javascript"),
            ("docker", "containers"), ("podman", "containers"), ("make", "build automation"),
            ("gcc", "C compiler"), ("cargo", "rust toolchain"), ("go", "go toolchain"), ("sqlite3", "SQLite shell"),
            ("lsof", "open files"), ("strace", "syscall tracer"), ("free", "memory usage"),
            ("lsblk", "block devices"), ("lscpu", "CPU info"), ("lsusb", "USB devices"), ("lspci", "PCI devices"),
            ("sensors", "hardware temps"), ("journalctl", "system logs"), ("dmesg", "kernel log"),
            ("systemctl", "services"), ("ufw", "firewall"), ("tree", "directory tree"), ("tar", "archives"),
            ("unzip", "extract zip"), ("7z", "7-zip"), ("rclone", "cloud sync"), ("brightnessctl", "screen brightness"),
        ]
    ]),
]

# Programs that need the real terminal (they take over the screen or ask for input)
INTERACTIVE = set(
    "nano vim nvim vi emacs micro hx helix kak joe ne mcedit ssh mosh telnet ftp sftp htop btop bpytop top atop "
    "glances iotop nvtop powertop ranger mc nnn lf vifm yazi broot fzf ncdu lazygit tig tmux screen less more man "
    "mysql psql sqlite3 redis-cli python python3 ipython ipython3 node irb ghci lua bash zsh fish sh dash su sudo "
    "passwd nmtui alsamixer pulsemixer cmatrix asciiquarium pipes.sh hollywood sl cava ncmpcpp cmus mpv w3m lynx "
    "links irssi weechat iftop nethogs bmon mtr watch apt apt-get aptitude dpkg-reconfigure cfdisk fdisk parted "
    "gdb termshark tshark journalctl visudo crontab mutt neomutt newsboat calcurse bc gitui lazydocker zellij "
    "btm s-tui trip claude codex gemini aider aerc ncspot vd visidata sc-im harlequin posting bpython litecli "
    "pgcli mycli khal tty-clock cbonsai bastet nsnake ninvaders moon-buggy greed rtorrent glow k9s".split()
)
INTERACTIVE_PREFIX = ("gh dash", "gh auth login", "gh repo create", "git commit", "git rebase -i", "git add -p",
                      "docker run -it", "docker exec -it", "sudo ")
REPL_ONLY = set("python python3 ipython ipython3 node irb ghci lua bc sqlite3".split())


def install_script(spec, name):
    """Build a bash snippet that tries each install method in order."""
    branches = []
    for tok in spec.split():
        method, _, arg = tok.partition(":")
        if method == "apt":
            branches.append((f"apt-cache show {arg} >/dev/null 2>&1", f"sudo apt install -y {arg}"))
        elif method == "snap":
            pkg, _, opt = arg.partition("/")
            classic = " --classic" if opt == "classic" else ""
            branches.append((f"command -v snap >/dev/null && snap info {pkg} >/dev/null 2>&1",
                             f"sudo snap install {pkg}{classic}"))
        elif method == "pipx":
            branches.append(("true", f"(command -v pipx >/dev/null || sudo apt install -y pipx) && "
                                     f"pipx install {arg} && pipx ensurepath >/dev/null"))
        elif method == "cargo":
            branches.append(("command -v cargo >/dev/null", f"cargo install --locked {arg}"))
        elif method == "gh":
            branches.append(("true", "(command -v gh >/dev/null || sudo apt install -y gh) && "
                                     "(gh auth status >/dev/null 2>&1 || gh auth login) && "
                                     f"gh extension install {arg}"))
        elif method == "sh" and arg in SCRIPTS:
            branches.append(("true", SCRIPTS[arg]))
    if not branches:
        return None
    lines = []
    for i, (cond, cmd) in enumerate(branches):
        lines.append(f"{'if' if i == 0 else 'elif'} {cond}; then {cmd}")
    lines.append(f"else echo 'no install method for {name} works on this system - see its website'; exit 1")
    lines.append("fi")
    return "\n".join(lines)


def install_summary(spec):
    out = []
    for tok in spec.split():
        method, _, arg = tok.partition(":")
        out.append({"sh": "official installer", "gh": f"gh extension {arg}"}.get(method, f"{method} {arg.split('/')[0]}"))
    return " → ".join(out)

# --------------------------------------------------------------------------------------------
#  Helpers
# --------------------------------------------------------------------------------------------


def fmt_bytes(n, digits=1):
    n = float(n)
    for unit in "BKMGTP":
        if abs(n) < 1024 or unit == "P":
            return f"{int(n)}B" if unit == "B" else f"{n:.{digits}f}{unit}"
        n /= 1024.0
    return f"{n:.1f}P"


def fmt_rate(n):
    return fmt_bytes(n) + "/s"


def fmt_dur(sec):
    sec = int(sec)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    return f"{d}d {h:02d}:{m:02d}" if d else f"{h:02d}:{m:02d}:{s:02d}"


def readf(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def tilde(path):
    return "~" + path[len(HOME):] if path == HOME or path.startswith(HOME + os.sep) else path


def load_conf():
    conf = json.loads(json.dumps(DEFAULT_CONF))
    try:
        with open(CONF_FILE) as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            conf.update(user)
    except (OSError, ValueError):
        pass
    lay = conf.get("layout")
    if not isinstance(lay, dict) or not all(isinstance(lay.get(k), list) for k in ("left", "right")):
        conf["layout"] = json.loads(json.dumps(DEFAULT_LAYOUT))
    if conf.get("theme") not in all_themes(conf):
        conf["theme"] = "netrunner"
    return conf


ROLES = [("pri", "frame & headers"), ("acc", "highlights"), ("hi", "hot text"), ("txt", "body text"),
         ("dim", "labels & chrome"), ("deep", "empty bars & shadows"), ("bg", "background"),
         ("bg2", "scanline rows"), ("ok", "status ok"), ("warn", "warning"), ("bad", "alert"),
         ("mag", "second accent")]
CUBE = [0, 95, 135, 175, 215, 255]
BASE16 = ["000000", "800000", "008000", "808000", "000080", "800080", "008080", "c0c0c0",
          "808080", "ff0000", "00ff00", "ffff00", "0000ff", "ff00ff", "00ffff", "ffffff"]


def c256_to_hex(n):
    n = int(n)
    if n < 16:
        return "#" + BASE16[n]
    if n >= 232:
        v = 8 + 10 * (n - 232)
        return f"#{v:02x}{v:02x}{v:02x}"
    n -= 16
    return f"#{CUBE[n // 36]:02x}{CUBE[(n // 6) % 6]:02x}{CUBE[n % 6]:02x}"


def hex_to_256(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def q(v):
        return 0 if v < 48 else (1 if v < 115 else (v - 35) // 40)

    ci = 16 + 36 * q(r) + 6 * q(g) + q(b)
    cr, cg, cb = CUBE[q(r)], CUBE[q(g)], CUBE[q(b)]
    avg = (r + g + b) // 3
    gi = 232 + max(0, min(23, (avg - 3) // 10))
    gv = 8 + 10 * (gi - 232)
    dc = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
    dg = (gv - r) ** 2 + (gv - g) ** 2 + (gv - b) ** 2
    return gi if dg < dc else ci


def color_val(v):
    """Accept 0-255, "203" or "#ff5f5f" and return a 256-color index."""
    if isinstance(v, int):
        return max(0, min(255, v))
    v = str(v).strip()
    if v.startswith("#") or (len(v) in (3, 6) and not v.isdigit()):
        return hex_to_256(v)
    return max(0, min(255, int(v)))


def all_themes(conf):
    return list(THEMES) + [n for n in conf.get("themes", {}) if n not in THEMES]


def resolve_theme(conf, name=None):
    name = name or conf.get("theme", "netrunner")
    custom = conf.get("themes", {}).get(name)
    if isinstance(custom, dict):
        cols = dict(THEMES.get(custom.get("base", "netrunner"), THEMES["netrunner"]))
        src = custom
    else:
        cols = dict(THEMES.get(name, THEMES["netrunner"]))
        src = {}
    for d in (src, conf.get("overrides", {}).get(name, {})):
        for k, v in d.items():
            if k in cols:
                try:
                    cols[k] = color_val(v)
                except (ValueError, TypeError):
                    pass
    return cols


def save_conf(conf):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(CONF_FILE, "w") as fh:
            json.dump(conf, fh, indent=2)
    except OSError:
        pass


def ansi256(n):
    return f"\x1b[38;5;{n}m"


def bin_of(argv):
    """First real program in an argv (skips `env VAR=x`)."""
    i = 0
    if argv and os.path.basename(argv[0]) == "env":
        i = 1
        while i < len(argv) and ("=" in argv[i] or argv[i].startswith("-")):
            i += 1
    return os.path.basename(argv[i]) if i < len(argv) else ""


# --------------------------------------------------------------------------------------------
#  Telemetry (pure /proc + /sys)
# --------------------------------------------------------------------------------------------


class Stats:
    def __init__(self):
        self.ncpu = os.cpu_count() or 1
        self.prev_cpu = {}
        self.cpu = 0.0
        self.cores = []
        self.cpu_hist = deque([0.0] * 240, maxlen=240)
        self.cpu_jiffies = 0
        self.mem = dict(total=1, used=0, avail=0, cached=0, buffers=0, swap_total=0, swap_used=0)
        self.net_prev = None
        self.net_t = 0.0
        self.ifaces = {}
        self.rx = self.tx = 0.0
        self.rx_hist = deque([0.0] * 240, maxlen=240)
        self.tx_hist = deque([0.0] * 240, maxlen=240)
        self.procs = []
        self.proc_prev = {}
        self.proc_jiffies_prev = None
        self.nprocs = 0
        self.disks = []
        self.temps = []
        self.battery = None
        self.ips = []
        self.gateway = None
        self.gw_iface = None
        self.load = (0.0, 0.0, 0.0)
        self.uptime = 0.0
        self.tick = 0
        self._users = {}
        self.pagesize = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        self.update(full=True)

    def update(self, full=False):
        self.tick += 1
        for fn in (self._cpu, self._mem, self._net, self._misc):
            try:
                fn()
            except Exception:
                pass
        slow = [(2, self._procs), (5, self._disks), (5, self._temps), (5, self._battery), (10, self._ips)]
        for every, fn in slow:
            if full or self.tick % every == 0:
                try:
                    fn()
                except Exception:
                    pass

    def _cpu(self):
        cur = {}
        with open("/proc/stat") as fh:
            for line in fh:
                if not line.startswith("cpu"):
                    break
                p = line.split()
                cur[p[0]] = [int(v) for v in p[1:9]]

        def pct(key):
            a, b = self.prev_cpu.get(key), cur.get(key)
            if not a or not b:
                return 0.0
            dt = sum(b) - sum(a)
            idle = (b[3] + b[4]) - (a[3] + a[4])
            return 0.0 if dt <= 0 else max(0.0, min(100.0, 100.0 * (dt - idle) / dt))

        keys = sorted((k for k in cur if k != "cpu"), key=lambda k: int(k[3:]))
        self.cpu = pct("cpu")
        self.cores = [pct(k) for k in keys]
        self.ncpu = max(1, len(keys))
        if "cpu" in cur:
            self.cpu_jiffies = sum(cur["cpu"])
        self.prev_cpu = cur
        self.cpu_hist.append(self.cpu)

    def _mem(self):
        m = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, v = line.split(":", 1)
                m[k] = int(v.split()[0]) * 1024
        total = m.get("MemTotal", 1) or 1
        avail = m.get("MemAvailable", m.get("MemFree", 0))
        self.mem = dict(total=total, used=total - avail, avail=avail, cached=m.get("Cached", 0),
                        buffers=m.get("Buffers", 0), swap_total=m.get("SwapTotal", 0),
                        swap_used=m.get("SwapTotal", 0) - m.get("SwapFree", 0))

    def _net(self):
        now = time.time()
        cur = {}
        with open("/proc/net/dev") as fh:
            for line in fh.readlines()[2:]:
                name, data = line.split(":", 1)
                name = name.strip()
                if name == "lo":
                    continue
                f = data.split()
                cur[name] = (int(f[0]), int(f[8]))
        ifs, rx, tx = {}, 0.0, 0.0
        dt = max(1e-3, now - self.net_t)
        for n, (r, t) in cur.items():
            pr, pt = (self.net_prev or {}).get(n, (r, t))
            rr, tr = max(0.0, (r - pr) / dt), max(0.0, (t - pt) / dt)
            ifs[n] = (rr, tr, r, t)
            if not n.startswith(("veth", "br-", "docker", "virbr")):
                rx += rr
                tx += tr
        self.ifaces, self.rx, self.tx = ifs, rx, tx
        self.net_prev, self.net_t = cur, now
        self.rx_hist.append(rx)
        self.tx_hist.append(tx)

    def _misc(self):
        la = readf("/proc/loadavg").split()
        if len(la) >= 3:
            self.load = tuple(float(x) for x in la[:3])
        up = readf("/proc/uptime").split()
        if up:
            self.uptime = float(up[0])

    def _user(self, uid):
        name = self._users.get(uid)
        if name is None:
            try:
                name = pwd.getpwuid(uid).pw_name
            except KeyError:
                name = str(uid)
            self._users[uid] = name
        return name

    def _procs(self):
        total = self.cpu_jiffies
        dtotal = (total - self.proc_jiffies_prev) if self.proc_jiffies_prev else 0
        memtotal = self.mem.get("total", 1) or 1
        cur, out = {}, []
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat", "rb") as fh:
                    s = fh.read().decode("utf-8", "replace")
                lp, rp = s.index("("), s.rindex(")")
                comm = s[lp + 1:rp]
                rest = s[rp + 2:].split()
                jiff = int(rest[11]) + int(rest[12])
                rss = int(rest[21]) * self.pagesize
                uid = os.stat(f"/proc/{pid}").st_uid
            except (OSError, ValueError, IndexError):
                continue
            ipid = int(pid)
            cur[ipid] = jiff
            prev = self.proc_prev.get(ipid)
            cpu = (jiff - prev) / dtotal * 100.0 * self.ncpu if (prev is not None and dtotal > 0) else 0.0
            out.append([ipid, self._user(uid), cpu, rss / memtotal * 100.0, rss, rest[0], comm])
        self.proc_prev, self.proc_jiffies_prev = cur, total
        out.sort(key=lambda p: (p[2], p[4]), reverse=True)
        self.procs, self.nprocs = out, len(out)

    def _disks(self):
        real = {"ext2", "ext3", "ext4", "xfs", "btrfs", "vfat", "exfat", "ntfs", "ntfs3", "fuseblk",
                "f2fs", "zfs", "reiserfs", "jfs", "hfsplus"}
        seen, out = set(), []
        for line in readf("/proc/mounts").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            dev, mnt, fs = parts[0], parts[1].replace("\\040", " "), parts[2]
            if fs not in real or dev in seen or mnt.startswith("/snap"):
                continue
            seen.add(dev)
            try:
                st = os.statvfs(mnt)
            except OSError:
                continue
            total = st.f_blocks * st.f_frsize
            if total <= 0:
                continue
            used = total - st.f_bfree * st.f_frsize
            out.append((mnt, used, total, used / total * 100.0))
        if not out:
            try:
                st = os.statvfs("/")
                total = st.f_blocks * st.f_frsize
                used = total - st.f_bfree * st.f_frsize
                if total > 0:
                    out.append(("/", used, total, used / total * 100.0))
            except OSError:
                pass
        out.sort(key=lambda d: (d[0] != "/", d[0]))
        self.disks = out

    def _temps(self):
        best = {}
        for hw in glob.glob("/sys/class/hwmon/hwmon*"):
            name = readf(hw + "/name").strip() or os.path.basename(hw)
            for tf in glob.glob(hw + "/temp*_input"):
                try:
                    v = int(readf(tf).strip()) / 1000.0
                except ValueError:
                    continue
                if 0 < v < 150:
                    best[name] = max(best.get(name, 0), v)
        if not best:
            for tz in glob.glob("/sys/class/thermal/thermal_zone*"):
                try:
                    v = int(readf(tz + "/temp").strip()) / 1000.0
                except ValueError:
                    continue
                name = readf(tz + "/type").strip() or os.path.basename(tz)
                if 0 < v < 150:
                    best[name] = max(best.get(name, 0), v)
        self.temps = sorted(best.items(), key=lambda kv: -kv[1])[:4]

    def _battery(self):
        self.battery = None
        for p in glob.glob("/sys/class/power_supply/*"):
            if readf(p + "/type").strip() == "Battery":
                try:
                    cap = int(readf(p + "/capacity").strip())
                except ValueError:
                    continue
                self.battery = (cap, readf(p + "/status").strip() or "Unknown")
                return

    def _ips(self):
        self.gateway = self.gw_iface = None
        for line in readf("/proc/net/route").splitlines()[1:]:
            f = line.split()
            if len(f) > 2 and f[1] == "00000000":
                try:
                    self.gateway = socket.inet_ntoa(struct.pack("<L", int(f[2], 16)))
                    self.gw_iface = f[0]
                except (ValueError, struct.error):
                    pass
                break
        ips = []
        if shutil.which("ip"):
            try:
                out = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True, text=True,
                                     timeout=1).stdout
                for line in out.splitlines():
                    f = line.split()
                    if len(f) >= 4 and f[1] != "lo":
                        ips.append((f[1], f[3]))
            except (OSError, subprocess.SubprocessError):
                pass
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))
                ips.append((self.gw_iface or "net", s.getsockname()[0]))
                s.close()
            except OSError:
                pass
        ips.sort(key=lambda t: t[0] != self.gw_iface)
        self.ips = ips


def hex_to_ip(h):
    b = bytes.fromhex(h)
    if len(b) == 4:
        return socket.inet_ntoa(b[::-1])
    b = b"".join(b[i:i + 4][::-1] for i in range(0, 16, 4))
    ip = socket.inet_ntop(socket.AF_INET6, b)
    return ip[7:] if ip.startswith("::ffff:") else ip


def read_sockets():
    listen, estab = set(), []
    for fn in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in readf(fn).splitlines()[1:]:
            p = line.split()
            if len(p) < 4:
                continue
            try:
                lip, lport = p[1].split(":")
                rip, rport = p[2].split(":")
                if p[3] == "0A":
                    listen.add((hex_to_ip(lip), int(lport, 16)))
                elif p[3] == "01":
                    estab.append((hex_to_ip(lip), int(lport, 16), hex_to_ip(rip), int(rport, 16)))
            except (ValueError, OSError):
                continue
    return sorted(listen, key=lambda t: t[1]), estab


def read_arp():
    out = []
    for line in readf("/proc/net/arp").splitlines()[1:]:
        f = line.split()
        if len(f) >= 6 and f[3] != "00:00:00:00:00:00":
            out.append((f[0], f[3], f[5]))
    return out


def os_name():
    for line in readf("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return "Linux"


def cpu_model():
    for line in readf("/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware", "cpu model")):
            return re.sub(r"\s+", " ", line.split(":", 1)[1]).strip()
    return os.uname().machine


# --------------------------------------------------------------------------------------------
#  Program catalog
# --------------------------------------------------------------------------------------------


class App:
    __slots__ = ("name", "kind", "argv", "comment", "cats", "did", "terminal", "bin", "stem", "inst", "key")

    def __init__(self, name, kind, argv=None, comment="", cats=(), did="", terminal=False, inst="", key=""):
        self.name, self.kind, self.comment, self.cats, self.did = name, kind, comment, set(cats), did
        self.inst, self.key = inst, key or name.lower()
        self.argv = argv or [name]
        self.terminal = terminal
        self.bin = bin_of(self.argv).lower()
        stem = did[:-8] if did.endswith(".desktop") else did
        self.stem = stem.lower()


def parse_exec(s):
    s = s.replace("%%", "\x00")
    try:
        argv = shlex.split(s)
    except ValueError:
        argv = s.split()
    out = []
    for a in argv:
        if re.fullmatch(r"%[fFuUdDnNickvm]", a):
            continue
        out.append(re.sub(r"%[fFuUdDnNickvm]", "", a).replace("\x00", "%"))
    return [a for a in out if a]


def parse_desktop(path):
    data, in_sec = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    if in_sec:
                        break
                    in_sec = line == "[Desktop Entry]"
                    continue
                if in_sec and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if "[" not in k:
                        data[k] = v.strip()
    except OSError:
        return None
    return data


class Catalog:
    def __init__(self):
        self.ready = False
        self.desktop, self.bins, self.binset, self.cats, self.market = [], [], set(), [], []

    def app_dirs(self):
        data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share")
        data_dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
        bases = [data_home] + data_dirs + ["/usr/share", "/usr/local/share", "/var/lib/snapd/desktop",
                                           "/var/lib/flatpak/exports/share",
                                           os.path.join(HOME, ".local/share/flatpak/exports/share")]
        seen, out = set(), []
        for b in bases:
            d = os.path.realpath(os.path.join(b, "applications"))
            if d not in seen and os.path.isdir(d):
                seen.add(d)
                out.append(d)
        return out

    def load(self):
        try:
            self._load()
        finally:
            self.ready = True

    def _load(self):
        seen, desktop = set(), []
        for d in self.app_dirs():
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if not f.endswith(".desktop"):
                        continue
                    did = os.path.relpath(os.path.join(root, f), d).replace(os.sep, "-")
                    if did in seen:
                        continue
                    seen.add(did)
                    e = parse_desktop(os.path.join(root, f))
                    if not e or e.get("Type", "Application") != "Application":
                        continue
                    if e.get("NoDisplay", "").lower() == "true" or e.get("Hidden", "").lower() == "true":
                        continue
                    argv = parse_exec(e.get("Exec", ""))
                    if not argv:
                        continue
                    term = e.get("Terminal", "").lower() == "true"
                    cats = [c for c in e.get("Categories", "").split(";") if c]
                    desktop.append(App(e.get("Name", did), "tui" if term else "gui", argv,
                                       e.get("Comment") or e.get("GenericName", ""), cats, did, term))
        bins = set()
        for d in os.environ.get("PATH", "/usr/bin:/bin").split(":"):
            try:
                for ent in os.scandir(d):
                    try:
                        if ent.is_file() and os.access(ent.path, os.X_OK):
                            bins.add(ent.name)
                    except OSError:
                        pass
            except OSError:
                pass
        cats = []
        buckets = {t: [] for t, _, _ in APP_CATS}
        buckets["UNSORTED"] = []
        for app in desktop:
            for title, _desc, keys in APP_CATS:
                if app.cats & keys:
                    buckets[title].append(app)
                    break
            else:
                buckets["UNSORTED"].append(app)
        for title, desc, _ in APP_CATS + [("UNSORTED", "uncategorized programs", set())]:
            if buckets[title]:
                cats.append((title, desc, sorted(buckets[title], key=lambda a: a.name.lower())))
        market, descs = [], {}
        for title, desc, entries in TUI_CATALOG:
            apps = []
            for e in entries:
                found = next((b for b in e["bins"] if b in bins), None)
                if e["check"]:
                    found = e["bins"][0] if os.path.exists(os.path.expanduser(e["check"])) else None
                for b in e["bins"]:
                    descs[b] = e["desc"]
                key = e["bins"][0]
                if found:
                    argv = list(e["argv"] or [found])
                    if argv[0] == "nvim" and key == "lazyvim" and os.path.exists("/snap/bin/nvim"):
                        argv[0] = "/snap/bin/nvim"
                    app = App(e["name"], "bin" if e["cli"] else "tui", argv, e["desc"], inst=e["inst"], key=key)
                elif e["inst"]:
                    app = App(e["name"], "get", list(e["argv"] or [e["bins"][0]]), e["desc"], inst=e["inst"], key=key)
                else:
                    continue
                apps.append(app)
                if e["inst"]:
                    market.append(app)
            if apps:
                apps.sort(key=lambda a: a.kind == "get")
                cats.append((title, desc, apps))
        allbins = sorted(bins, key=str.lower)
        cats.append(("PATH // ALL", "every executable on $PATH",
                     [App(n, "tui" if n in INTERACTIVE else "bin", [n], descs.get(n, "")) for n in allbins]))
        self.desktop, self.bins, self.binset, self.cats, self.market = desktop, allbins, bins, cats, market

    def find(self, q):
        """Return (app, candidates). Exact match first, then unique substring match."""
        ql = q.lower()
        for a in self.desktop:
            if ql in (a.name.lower(), a.stem, a.stem.split(".")[-1], a.bin):
                return a, []
        part = [a for a in self.desktop if ql in a.name.lower() or ql in a.stem]
        if len(part) == 1:
            return part[0], []
        return None, part

    def exact(self, q):
        ql = q.lower()
        for a in self.desktop:
            if ql in (a.name.lower(), a.stem, a.stem.split(".")[-1]):
                return a
        return None

    def search(self, q):
        ql = q.lower()
        seen, out = set(), []
        for _t, _d, apps in self.cats:
            for a in apps:
                key = (a.kind == "gui", a.name.lower())
                if key in seen:
                    continue
                if ql in a.name.lower() or ql in a.comment.lower() or ql in a.stem:
                    seen.add(key)
                    out.append(a)
        out.sort(key=lambda a: (not a.name.lower().startswith(ql), a.kind != "gui", a.name.lower()))
        return out


# --------------------------------------------------------------------------------------------
#  Colors
# --------------------------------------------------------------------------------------------


class Pal:
    def __init__(self, conf, c256):
        self.c256 = c256
        self.cache = {}
        self.next = 1
        self.set(conf)

    def set(self, conf):
        self.name = conf["theme"]
        self.colors = resolve_theme(conf)
        self.t = self.colors if self.c256 else BASIC
        self.cache.clear()
        self.next = 1

    def raw(self, fg, bg):
        """Attribute for explicit 256-color indices (used by swatches)."""
        return self(None, None, _key=(fg, bg))

    def __call__(self, fg, bg="bg", bold=False, rev=False, _key=None):
        key = _key or (self.t[fg], self.t[bg])
        pair = self.cache.get(key)
        if pair is None:
            if self.next < curses.COLOR_PAIRS - 1:
                try:
                    curses.init_pair(self.next, key[0], key[1])
                    pair = self.next
                    self.next += 1
                except curses.error:
                    pair = 0
            else:
                pair = 0
            self.cache[key] = pair
        attr = curses.color_pair(pair)
        if bold:
            attr |= curses.A_BOLD
        if rev:
            attr |= curses.A_REVERSE
        return attr


# --------------------------------------------------------------------------------------------
#  The deck
# --------------------------------------------------------------------------------------------

COMMANDS = [
    # name, args, help, aliases
    ("help", "", "open the codex (this list)", ["?", "codex"]),
    ("apps", "[filter]", "arsenal: browse every installed program by category", ["programs", "arsenal"]),
    ("run", "<prog> [args]", "jack into a program - GUI detaches, TUI takes the screen", ["jack", "launch"]),
    ("spawn", "<cmd>", "start any command detached in the background", ["bg"]),
    ("exec", "<cmd>", "run a shell command, stream output here   (shortcut: !cmd)", ["x"]),
    ("shell", "", "drop into a raw shell - `exit` brings you back", ["sh", "term"]),
    ("open", "<path|url>", "open with the default handler", ["xdg"]),
    ("cd", "<dir>", "change the deck's working directory", []),
    ("procs", "", "process manager - flatline rogue daemons", ["ps", "tasks"]),
    ("kill", "<pid|name>", "terminate a process (SIGTERM)", ["flatline"]),
    ("scan", "", "recon: interfaces, neighbours, open ports, live links", ["recon"]),
    ("sysinfo", "", "hardware & identity dossier", ["whoami", "dossier"]),
    ("get", "<app>", "install a terminal app from the catalog (see apps)", ["install"]),
    ("pin", "<command>", "pin a command to the dock (Alt+1-9 launches)", []),
    ("unpin", "<n|command>", "remove a dock entry", []),
    ("settings", "", "tune everything: theme, colors, fonts, effects, panels  (F8)", ["tune", "config"]),
    ("theme", "[name|save <name>]", "switch skin, or save the current colors as a new theme", ["skin"]),
    ("color", "[role value]", "set a color: color pri #ff2a6d   (roles: color)", ["colour"]),
    ("font", "[family] [size]", "set the terminal font (applied by the NETDECK session)", []),
    ("fonts", "", "list installed monospace fonts", []),
    ("panel", "<name> [on|off]", "show/hide a dashboard panel", ["panels"]),
    ("relaunch", "", "restart the terminal window to apply font changes", []),
    ("wifi", "", "network & Wi-Fi settings (nmtui)", ["net"]),
    ("audio", "", "volume mixer", ["volume", "vol"]),
    ("bright", "<percent>", "screen brightness (brightnessctl)", ["brightness"]),
    ("fx", "[on|off|scan|boot]", "toggle effects, scanlines, boot sequence", []),
    ("glitch", "", "shake the signal", []),
    ("rain", "", "data rain screensaver", ["screensaver"]),
    ("memo", "<text>", "write a data shard to the vault", ["note", "shard"]),
    ("shards", "[n]", "read the latest data shards", ["notes"]),
    ("history", "", "command history", []),
    ("clear", "", "wipe the console", ["cls"]),
    ("update", "", "patch the system (apt update && upgrade)", ["patch"]),
    ("lock", "", "lock the session", []),
    ("suspend", "", "put the machine to sleep", []),
    ("reboot", "", "reboot the machine", []),
    ("poweroff", "", "shut the machine down", ["shutdown"]),
    ("logout", "", "end the session (log out)", []),
    ("quit", "", "jack out", ["exit", "jackout", "q"]),
]

PANELS = {  # name: title shown in settings
    "sys": "SYSCORE  cpu", "mem": "MEMORY", "disk": "STORAGE", "net": "NET UPLINK", "bio": "BIOMON  temps/power",
    "procs": "PROCESSES", "dock": "DOCK  pinned apps", "console": "CONSOLE", "neural": "NEURAL LINK  big panel",
    "stream": "DATASTREAM  hex",
}
PANEL_HOME = {"sys": "left", "mem": "left", "disk": "left", "net": "left", "bio": "left", "procs": "left",
              "stream": "left", "dock": "right", "neural": "right", "console": "right"}

KEYBAR = [("F1", "CODEX"), ("F2", "ARSENAL"), ("F3", "PROCS"), ("F4", "SHELL"), ("F5", "RECON"),
          ("F6", "RAIN"), ("F7", "DOSSIER"), ("F8", "TUNE"), ("F9", "SKIN"), ("F10", "JACK OUT")]


class Deck:
    def __init__(self, scr, args):
        self.scr = scr
        self.args = args
        self.conf = load_conf()
        if args.theme and args.theme in all_themes(self.conf):
            self.conf["theme"] = args.theme
        if args.no_fx:
            self.conf["fx"] = False
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        self.c256 = curses.COLORS >= 256
        if not self.c256:
            self.conf["scan"] = False
        self.pal = Pal(self.conf, self.c256)
        curses.raw()
        curses.noecho()
        scr.keypad(True)
        self.H, self.W = scr.getmaxyx()

        try:
            self.user = getpass.getuser()
        except Exception:
            self.user = "runner"
        self.host = socket.gethostname().split(".")[0] or "deck"
        self.node = f"{random.getrandbits(16):04X}"

        self.stats = Stats()
        self.catalog = Catalog()
        threading.Thread(target=self.catalog.load, daemon=True).start()

        self.console = deque(maxlen=3000)
        self.last_born = 0.0
        self.scroll = 0
        self.inp, self.cur = "", 0
        self.history = self._load_history()
        self.hpos = None
        self.cwd = os.getcwd() if os.path.isdir(os.getcwd()) else HOME
        self.oldcwd = self.cwd
        self.mode = "main"
        self.ov = {}
        self.confirm = None
        self.job = None
        self.jobq = queue.Queue()
        self.children = []
        self.glitch_until = 0.0
        self.now = time.time()
        self.next_glitch = self.now + random.uniform(25, 50)
        self.next_feed = self.now + random.uniform(5, 9)
        self.trace = random.uniform(4, 25)
        self.trace_rate = random.uniform(0.35, 0.9)
        self.last_stat = 0.0
        self.alert_cd = {}
        self.catalog_announced = False
        self.running = True
        self.pending = None  # deferred action run outside the draw loop
        self.kiosk = bool(os.environ.get("NETDECK_KIOSK"))
        self.exit_code = 0
        self.notes = deque()  # messages from background threads

    # ---------------------------------------------------------------- persistence
    def _load_history(self):
        return [l for l in readf(HIST_FILE).splitlines() if l.strip()][-500:]

    def _save_history(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(HIST_FILE, "w") as fh:
                fh.write("\n".join(self.history[-500:]) + "\n")
        except OSError:
            pass

    # ---------------------------------------------------------------- low-level drawing
    def put(self, y, x, s, attr=0):
        if y < 0 or y >= self.H or x >= self.W or not s:
            return
        if x < 0:
            s, x = s[-x:], 0
        s = s[: self.W - x]
        if not s:
            return
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass

    def bgr(self, y):
        return "bg2" if (self.conf["scan"] and y % 2) else "bg"

    def c(self, fg, y, bold=False, rev=False):
        return self.pal(fg, self.bgr(y), bold, rev)

    def inv(self, role, bold=True):
        return self.pal("bg", role, bold)

    def fill(self, y, x, w, role="txt"):
        if w > 0:
            self.put(y, x, " " * w, self.c(role, y))

    def heat(self, p):
        return "acc" if p < 50 else ("hi" if p < 80 else "bad")

    def bar(self, y, x, w, pct, role=None):
        if w <= 0:
            return
        pct = max(0.0, min(100.0, pct))
        n = int(round(pct / 100.0 * w))
        if pct > 0 and n == 0:
            n = 1
        self.put(y, x, "▊" * n, self.c(role or self.heat(pct), y, True))
        self.put(y, x + n, "▊" * (w - n), self.c("deep", y))

    def spark(self, y, x, w, data, role, peak=None):
        if w <= 0:
            return
        vals = list(data)[-w:]
        m = peak or max(max(vals) if vals else 0, 1e-9)
        s = "".join(SPARK[min(7, int(v / m * 7.999))] if v > 0 else " " for v in vals)
        self.put(y, x, "▁" * w, self.c("deep", y))
        for i, ch in enumerate(s):
            if ch != " ":
                self.put(y, x + i, ch, self.c(role, y))

    def gtext(self, s, chance=0.012):
        if self.conf["fx"] and random.random() < chance and s:
            s = list(s)
            for _ in range(random.randint(1, 2)):
                i = random.randrange(len(s))
                if s[i] != " ":
                    s[i] = random.choice(GLITCH)
            s = "".join(s)
        return s

    def panel(self, y, x, h, w, title, tag="", role="pri"):
        if h < 2 or w < 10:
            return
        label = f" {self.gtext(title)} "
        self.put(y, x, "◢", self.c(role, y, True))
        self.put(y, x + 1, label, self.inv(role))
        lx = x + 1 + len(label)
        self.put(y, lx, "━" * max(0, x + w - 1 - lx), self.c(role, y))
        if tag and w > len(label) + len(tag) + 8:
            self.put(y, x + w - 4 - len(tag), f" {tag} ", self.c("dim", y))
        self.put(y, x + w - 1, "┑", self.c(role, y))
        for yy in range(y + 1, y + h - 1):
            self.put(yy, x, "│", self.c("dim", yy))
            self.put(yy, x + w - 1, "│", self.c("dim", yy))
        yb = y + h - 1
        self.put(yb, x, "└" + "─" * (w - 2) + "┘", self.c("dim", yb))
        acc = min(6, w - 4)
        self.put(yb, x + w - 1 - acc, "━" * acc + "┙", self.c(role, yb))
        self.put(yb, x + 2, "▪▪▪", self.c("deep", yb))

    # ---------------------------------------------------------------- console log
    def log(self, segs, role="txt", tag=None, tag_role="dim"):
        if isinstance(segs, str):
            segs = [(segs, role)]
        if tag:
            segs = [(time.strftime("%H:%M:%S "), "dim"), (f"{tag:<9}", tag_role), (" ", "txt")] + list(segs)
        now = time.time()
        born = now if self.last_born < now - 0.6 else self.last_born + 0.01
        if born - now > 0.4:
            born = now
        self.last_born = born
        self.console.append((segs, born))
        if self.scroll:
            self.scroll += 1

    def ok(self, msg):
        self.log([("  ✓ ", "ok"), (msg, "txt")])

    def err(self, msg):
        self.log([("  ✗ ", "bad"), (msg, "bad")])

    def info(self, msg, role="txt"):
        self.log([("  ", "txt"), (msg, role)])

    def head(self, msg):
        self.log([(" ◢ ", "pri"), (msg, "hi")])

    # ---------------------------------------------------------------- ambient life
    def ambient(self, now):
        fx = self.conf["fx"]
        if now >= self.next_feed:
            tag, role, msg = random.choice(FEED)
            self.log(msg, "dim", tag=tag, tag_role=role)
            self.next_feed = now + random.uniform(9, 24)
        if fx and now >= self.next_glitch:
            self.glitch(random.uniform(0.12, 0.3))
            self.next_glitch = now + random.uniform(25, 70)
        self.trace += self.trace_rate * 0.08 * (1.6 if self.stats.rx + self.stats.tx > 200e3 else 1.0)
        if self.trace >= 100:
            self.trace = random.uniform(2, 12)
            self.trace_rate = random.uniform(0.35, 0.9)
            self.log("trace attempt deflected - proxy chain rerouted, trail burned", "warn",
                     tag="NETWATCH", tag_role="bad")
            self.glitch(0.35)

    def glitch(self, dur=0.25):
        if self.conf["fx"]:
            self.glitch_until = max(self.glitch_until, time.time() + dur)

    def alerts(self):
        st, now = self.stats, time.time()

        def fire(key, msg, role, tag):
            if now - self.alert_cd.get(key, 0) > 90:
                self.alert_cd[key] = now
                self.log(msg, role, tag=tag, tag_role=role)

        if st.cpu > 92:
            top = st.procs[0][6] if st.procs else "?"
            fire("cpu", f"thermal spike - cpu at {st.cpu:.0f}% (top: {top})", "warn", "BIOMON")
        mp = st.mem["used"] / st.mem["total"] * 100
        if mp > 90:
            fire("mem", f"memory saturation {mp:.0f}% - consider flatlining something", "bad", "BIOMON")
        if st.battery and st.battery[0] < 15 and st.battery[1].lower() == "discharging":
            fire("bat", f"power cell at {st.battery[0]}% - find a socket, choom", "bad", "POWER")
        if st.rx > 8e6:
            fire("rx", f"data surge ▼ {fmt_rate(st.rx)} incoming", "acc", "UPLINK")
        for mnt, _u, _t, p in st.disks:
            if p > 95:
                fire("disk" + mnt, f"storage {mnt} at {p:.0f}% - vault nearly full", "bad", "STORAGE")

    # ---------------------------------------------------------------- frame
    def resize(self):
        self.H, self.W = self.scr.getmaxyx()
        self.scr.clear()

    def draw(self):
        now = self.now
        H, W = self.H, self.W
        for y in range(H):
            self.fill(y, 0, W)
        if W < 80 or H < 24:
            msg = "VIEWPORT TOO SMALL"
            sub = f"need 80x24, have {W}x{H} - expand the terminal"
            self.put(H // 2 - 1, max(0, (W - len(msg)) // 2), msg, self.c("bad", H // 2 - 1, True))
            self.put(H // 2 + 1, max(0, (W - len(sub)) // 2), sub, self.c("dim", H // 2 + 1))
            return
        self.draw_header(now)
        self.draw_body(now)
        self.draw_prompt(now)
        self.draw_keybar()
        if self.mode == "apps":
            self.draw_apps()
        elif self.mode == "procs":
            self.draw_procs()
        elif self.mode == "help":
            self.draw_help()
        elif self.mode == "settings":
            self.draw_settings()
        if self.confirm:
            self.draw_confirm()
        if now < self.glitch_until:
            self.apply_glitch(1.0)
        elif self.conf["fx"] and random.random() < 0.035:
            self.apply_glitch(0.1)

    def apply_glitch(self, k):
        H, W = self.H, self.W
        n = 1 if k < 0.5 else random.randint(4, 10)
        for _ in range(n):
            y = random.randrange(H)
            x = random.randrange(W)
            ln = random.randint(6, max(7, min(60, W - x)))
            ln = min(ln, W - x)
            if k < 0.5:
                try:
                    self.scr.chgat(y, x, ln, self.c("dim", y))
                except curses.error:
                    pass
                continue
            role = random.choice(["bad", "acc", "hi", "mag", "pri"])
            if random.random() < 0.5:
                try:
                    self.scr.chgat(y, x, ln, self.pal(role, self.bgr(y), True, True))
                except curses.error:
                    pass
            else:
                self.put(y, x, "".join(random.choice(GLITCH) for _ in range(ln)), self.c(role, y, True))

    def draw_header(self, now):
        W = self.W
        y = 0
        self.put(y, 0, " " * W, self.c("txt", y))
        left = " ◢ NETDECK//OS "
        self.put(y, 0, left, self.inv("pri"))
        x = len(left)
        seg = f" v{VERSION} ░ ARASAKA SUBNET-07 ░ NODE 0x{self.node} ░ "
        self.put(y, x, seg, self.c("dim", y))
        x += len(seg)
        blink = int(now * 2) % 2 == 0
        st = " ▓ HIJACKED ▓ "
        self.put(y, x, st, self.inv("bad") if blink else self.c("bad", y, True))
        clock = time.strftime(" %H:%M:%S ")
        date = time.strftime(" %d.%m.%Y ")
        who = f" {self.user}@{self.host} "
        right_len = len(who) + len(date) + len(clock) + 2
        rx = W - right_len
        x += len(st)
        if self.conf.get("neural", True) and rx - x > 40:
            self.draw_neural_mini(y, rx - 33, now)
        if rx > x + 2:
            self.put(y, rx, who, self.c("acc", y, True))
            self.put(y, rx + len(who), "▐", self.c("pri", y))
            self.put(y, rx + len(who) + 1, date, self.c("txt", y))
            self.put(y, rx + len(who) + 1 + len(date), "▐", self.c("pri", y))
            self.put(y, W - len(clock), clock, self.inv("hi"))
        elif W - len(clock) > x:
            self.put(y, W - len(clock), clock, self.inv("hi"))
        # ticker
        y = 1
        if not self.conf.get("ticker", True):
            self.put(y, 0, "◤◢" + "━" * (W - 3) + "◣", self.c("deep", y))
            return
        st_ = self.stats
        mp = st_.mem["used"] / st_.mem["total"] * 100
        live = (f"CPU {st_.cpu:3.0f}%  MEM {mp:3.0f}%  NET ▼{fmt_rate(st_.rx):>10} ▲{fmt_rate(st_.tx):>10}  "
                f"PROCS {st_.nprocs:4d}  TRACE {self.trace:3.0f}%")
        text = "  ░▒▓  ".join([live] + BULLETINS) + "  ░▒▓  "
        off = int(now * 13) % len(text)
        view = (text[off:] + text)[: W - 4]
        self.put(y, 0, "◤◢ ", self.c("pri", y, True))
        self.put(y, 3, view, self.c("dim", y))
        # colour the live block when visible
        i = view.find("CPU ")
        if i >= 0:
            self.put(y, 3 + i, view[i:i + len(live)], self.c("pri", y))
        self.put(y, W - 1, "◣", self.c("pri", y, True))

    def draw_neural_mini(self, y, x, now):
        """A small live neural-link readout: waveform, sync and trace."""
        self.put(y, x, "◈", self.c("mag", y, True))
        for i in range(8):
            t = now * 3.2 + i * 0.7
            v = 0.5 + 0.32 * math.sin(t) + 0.15 * math.sin(t * 2.3)
            if int((now * 9) % 14) == i:
                v = 1.0
            self.put(y, x + 2 + i, SPARK[max(0, min(7, int(v * 7.99)))], self.c("acc", y))
        sync = 97.0 + 2.5 * math.sin(now * 0.7)
        self.put(y, x + 11, f"{sync:4.1f}%", self.c("txt", y))
        tr = self.trace
        role = "acc" if tr < 50 else ("hi" if tr < 80 else "bad")
        self.put(y, x + 18, "TRACE", self.c("dim", y))
        self.put(y, x + 24, f"{tr:3.0f}%", self.c(role, y, tr >= 80))

    # ---------------------------------------------------------------- body layout
    def draw_body(self, now):
        H, W = self.H, self.W
        top, bot = 2, H - 2
        bh = bot - top
        lay = self.conf["layout"]
        left = [p for p in lay.get("left", []) if p in PANELS]
        right = [p for p in lay.get("right", []) if p in PANELS]
        if not left and not right:
            right = ["console"]
        lw = 38 if W >= 150 else (36 if W >= 120 else (32 if W >= 96 else 30))
        if not right:
            lw = W
        elif not left:
            lw = 0
        for names, x, w in ((left, 0, lw), (right, lw, W - lw)):
            if not names or w < 20:
                continue
            y = top
            for name, h in self.alloc(names, bh, w):
                getattr(self, "draw_" + {"procs": "proc_panel"}.get(name, name))(y, x, h, w, now)
                y += h

    def panel_size(self, name, w):
        """(preferred height, grow weight) for a panel at a given width."""
        st, iw = self.stats, w - 4
        if name == "sys":
            n = len(st.cores)
            rows = math.ceil(n / max(1, iw // 2)) if n > 16 else math.ceil(n / (2 if n > 1 else 1))
            return 5 + rows, 0
        if name == "mem":
            return 5, 0
        if name == "disk":
            return 2 + min(4, max(1, len(st.disks))), 0
        if name == "net":
            return 7, 0
        if name == "bio":
            return 5 + len(st.temps[:3]) + (1 if st.battery else 0), 0
        if name == "procs":
            return 8, 2
        if name == "dock":
            n = max(1, len(self.dock_items()))
            return 2 + math.ceil(n / max(1, iw // 24)), 0
        if name == "neural":
            return 7, 0
        if name == "stream":
            return 6, 1
        return 6, 5  # console

    def alloc(self, names, avail, w):
        out, used = [], 0
        for n in names:
            h, g = self.panel_size(n, w)
            if used + h > avail:
                h = 5 if g else h
                if used + h > avail:
                    continue
            out.append([n, h, g])
            used += h
        extra = avail - used
        if extra > 0 and out:
            growers = [o for o in out if o[2]]
            if not growers:
                out[-1][1] += extra
            else:
                tot = sum(o[2] for o in growers)
                given = 0
                for o in growers:
                    add = extra * o[2] // tot
                    o[1] += add
                    given += add
                growers[-1][1] += extra - given
        return [(n, h) for n, h, _g in out]

    def dock_items(self):
        items = self.conf.get("dock")
        if items is None:
            items = self.auto_dock()
        return [i for i in items if isinstance(i, str) and i.strip()][:9]

    def auto_dock(self):
        if getattr(self, "_auto_dock", None) is not None:
            return self._auto_dock
        groups = [["nvim", "hx", "helix", "micro", "vim", "nano"], ["lazygit", "gitui", "tig"],
                  ["claude", "codex"], ["btop", "htop", "top"], ["yazi", "ranger", "nnn", "mc"],
                  ["firefox", "chromium", "google-chrome", "brave-browser"], ["nmtui"],
                  ["pulsemixer", "alsamixer"], ["ncspot", "cmus"]]
        picks = []
        for g in groups:
            hit = next((c for c in g if shutil.which(c)), None)
            if hit:
                picks.append(hit)
        if os.path.exists(os.path.expanduser("~/.local/share/gh/extensions/gh-dash")):
            picks.insert(2, "gh dash")
        self._auto_dock = picks[:9]
        return self._auto_dock

    def draw_dock(self, y, x, h, w, now):
        items = self.dock_items()
        self.panel(y, x, h, w, "DOCK", "ALT+1-9 · pin / unpin", role="acc")
        ix, iw = x + 2, w - 4
        if not items:
            self.put(y + 1, ix, "empty - pin something: pin nvim", self.c("deep", y + 1))
            return
        cell = 24
        per = max(1, iw // cell)
        for i, cmd in enumerate(items):
            r = y + 1 + i // per
            if r >= y + h - 1:
                break
            cx = ix + (i % per) * cell
            prog = cmd.split()[0]
            ok = bool(shutil.which(prog)) or (self.catalog.ready and self.catalog.exact(cmd) is not None)
            self.put(r, cx, f" {i + 1} ", self.inv("acc" if ok else "dim"))
            label = cmd if len(cmd) <= cell - 6 else cmd[: cell - 7] + "…"
            self.put(r, cx + 4, label, self.c("txt" if ok else "deep", r, ok))

    def draw_sys(self, y, x, h, w, now):
        st = self.stats
        self.panel(y, x, h, w, "SYSCORE", f"{st.ncpu} CORES")
        ix, iw = x + 2, w - 4
        r = y + 1
        pct = f"{st.cpu:5.1f}%"
        self.put(r, ix, "CPU", self.c("txt", r, True))
        self.bar(r, ix + 4, iw - 4 - len(pct) - 1, st.cpu)
        self.put(r, ix + iw - len(pct), pct, self.c(self.heat(st.cpu), r, True))
        r += 1
        self.spark(r, ix, iw, st.cpu_hist, "pri", peak=max(20.0, max(list(st.cpu_hist)[-iw:])))
        r += 1
        n = len(st.cores)
        if n > 16:
            per = max(1, iw // 2)
            for i, p in enumerate(st.cores):
                rr, cc = divmod(i, per)
                self.put(r + rr, ix + cc * 2, "█", self.c(self.heat(p) if p > 8 else "deep", r + rr))
            r += math.ceil(n / per)
        else:
            cols = 2 if n > 1 else 1
            cw = iw // cols
            for i, p in enumerate(st.cores):
                rr, cc = divmod(i, cols)
                cx = ix + cc * cw
                lab = f"{i:02d}"
                self.put(r + rr, cx, lab, self.c("dim", r + rr))
                num = f"{p:3.0f}"
                bw = cw - len(lab) - len(num) - 3
                self.bar(r + rr, cx + 3, bw, p)
                self.put(r + rr, cx + 3 + bw + 1, num, self.c("txt", r + rr))
            r += math.ceil(n / cols)
        la = st.load
        line = f"LOAD {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}"
        up = f"UP {fmt_dur(st.uptime)}"
        if len(line) + len(up) + 1 > iw:
            line = f"LOAD {la[0]:.2f}"
        self.put(r, ix, line, self.c("dim", r))
        self.put(r, ix + iw - len(up), up, self.c("acc", r))

    def draw_mem(self, y, x, h, w, now):
        m = self.stats.mem
        self.panel(y, x, h, w, "MEMORY", fmt_bytes(m["total"], 0))
        ix, iw = x + 2, w - 4
        rows = [("RAM", m["used"], m["total"]), ("SWP", m["swap_used"], m["swap_total"])]
        for i, (lab, used, tot) in enumerate(rows):
            r = y + 1 + i
            p = used / tot * 100 if tot else 0
            txt = f"{fmt_bytes(used)}/{fmt_bytes(tot, 0)}" if tot else "offline"
            self.put(r, ix, lab, self.c("txt", r, True))
            self.bar(r, ix + 4, iw - 4 - len(txt) - 1, p, "mag" if lab == "SWP" else None)
            self.put(r, ix + iw - len(txt), txt, self.c("txt", r))
        r = y + 3
        self.put(r, ix, f"CACHE {fmt_bytes(m['cached'])}", self.c("dim", r))
        av = f"FREE {fmt_bytes(m['avail'])}"
        self.put(r, ix + iw - len(av), av, self.c("ok", r))

    def draw_disk(self, y, x, h, w, now):
        st = self.stats
        self.panel(y, x, h, w, "STORAGE", f"{len(st.disks)} VOL")
        ix, iw = x + 2, w - 4
        for i, (mnt, used, tot, p) in enumerate(st.disks[: h - 2]):
            r = y + 1 + i
            name = mnt if len(mnt) <= 7 else "…" + mnt[-6:]
            txt = f"{p:3.0f}% {fmt_bytes(tot, 0):>5}"
            self.put(r, ix, f"{name:<7}", self.c("acc", r))
            self.bar(r, ix + 8, iw - 8 - len(txt) - 1, p)
            self.put(r, ix + iw - len(txt), txt, self.c("txt", r))

    def draw_bio(self, y, x, h, w, now):
        st = self.stats
        self.panel(y, x, h, w, "BIOMON", "VITALS", role="pri")
        ix, iw = x + 2, w - 4
        r = y + 1
        for name, t in st.temps[:3]:
            lab = name[:8].upper()
            txt = f"{t:3.0f}°C"
            self.put(r, ix, f"{lab:<8}", self.c("dim", r))
            self.bar(r, ix + 9, iw - 9 - len(txt) - 1, min(100, t), self.heat(t * 1.1))
            self.put(r, ix + iw - len(txt), txt, self.c(self.heat(t * 1.1), r, True))
            r += 1
        if st.battery:
            cap, status = st.battery
            tag = {"Charging": "CHG", "Discharging": "BAT", "Full": "FULL"}.get(status, status[:4].upper())
            txt = f"{cap:3d}% {tag}"
            self.put(r, ix, "POWER   ", self.c("dim", r))
            self.bar(r, ix + 9, iw - 9 - len(txt) - 1, cap, "ok" if cap > 30 else ("warn" if cap > 15 else "bad"))
            self.put(r, ix + iw - len(txt), txt, self.c("txt", r))
            r += 1
        pairs = [("ICE", "BYPASSED", "ok"), ("NETWATCH", "BLIND", "ok"), ("UPLINK", "ENCRYPTED", "acc")]
        for lab, val, role in pairs:
            if r >= y + h - 1:
                break
            dots = "·" * max(1, iw - len(lab) - len(val) - 2)
            self.put(r, ix, lab, self.c("dim", r))
            self.put(r, ix + len(lab) + 1, dots, self.c("deep", r))
            self.put(r, ix + iw - len(val), val, self.c(role, r, True))
            r += 1

    def draw_stream(self, y, x, h, w, now):
        self.panel(y, x, h, w, "DATASTREAM", "LIVE")
        ix, iw = x + 2, w - 4
        off = int(now * 5)
        nbytes = max(1, (iw - 10) // 3)
        for i in range(h - 2):
            r = y + 1 + i
            k = off + i
            rnd = random.Random(k * 7919)
            addr = f"{(k * 16) & 0xFFFFFF:06X}"
            self.put(r, ix, addr, self.c("dim", r))
            bx = ix + 8
            hot = rnd.randrange(nbytes * 3)
            for b in range(nbytes):
                v = rnd.randrange(256)
                role = "hi" if b == hot else ("pri" if v > 200 else "dim")
                self.put(r, bx + b * 3, f"{v:02X}", self.c(role, r, b == hot))

    def draw_net(self, y, x, h, w, now):
        st = self.stats
        iface = st.gw_iface or (st.ips[0][0] if st.ips else "—")
        self.panel(y, x, h, w, "NET UPLINK", iface.upper())
        ix, iw = x + 2, w - 4
        r = y + 1
        ip = st.ips[0][1] if st.ips else "no carrier"
        self.put(r, ix, "ADDR ", self.c("dim", r))
        self.put(r, ix + 5, ip, self.c("acc", r, True))
        gw = f"GW {st.gateway or '—'}"
        self.put(r, ix + iw - len(gw), gw, self.c("txt", r))
        r += 1
        if len(st.ips) > 1:
            extra = "  ".join(f"{n}:{a.split('/')[0]}" for n, a in st.ips[1:3])
            self.put(r, ix, extra[:iw], self.c("dim", r))
        else:
            self.put(r, ix, f"LINKS {len(st.ifaces)}  ·  HOST {self.host}"[:iw], self.c("dim", r))
        r += 1
        peak = max(max(st.rx_hist), max(st.tx_hist), 1024)
        for arrow, lab, val, hist, role in (("▼", "RX", st.rx, st.rx_hist, "acc"), ("▲", "TX", st.tx, st.tx_hist, "mag")):
            if r >= y + h - 2:
                break
            head = f"{arrow} {lab} {fmt_rate(val):>10} "
            self.put(r, ix, arrow, self.c(role, r, True))
            self.put(r, ix + 2, head[2:], self.c("txt", r))
            self.spark(r, ix + len(head), iw - len(head), hist, role, peak=peak)
            r += 1
        tot_rx = sum(v[2] for k, v in st.ifaces.items() if not k.startswith(("veth", "br-", "docker")))
        tot_tx = sum(v[3] for k, v in st.ifaces.items() if not k.startswith(("veth", "br-", "docker")))
        r = y + h - 2
        line = f"TOTAL ▼ {fmt_bytes(tot_rx)}  ▲ {fmt_bytes(tot_tx)}"
        self.put(r, ix, line[:iw], self.c("dim", r))
        peak_s = f"PEAK {fmt_rate(peak)}"
        if len(line) + len(peak_s) + 2 < iw:
            self.put(r, ix + iw - len(peak_s), peak_s, self.c("deep", r))

    def draw_neural(self, y, x, h, w, now):
        self.panel(y, x, h, w, "NEURAL LINK", "SYNAPSE", role="pri")
        ix, iw = x + 2, w - 4
        wave_h = h - 4
        if wave_h >= 2:
            rows = wave_h * 2
            for i in range(iw):
                t = now * 2.6 + i * 0.33
                v1 = math.sin(t) * 0.55 + math.sin(t * 0.43 + 1.7) * 0.3 + math.sin(t * 3.1) * 0.1
                v2 = math.sin(t * 0.8 + 2.4) * 0.45 + math.sin(t * 1.9) * 0.2
                # ECG spike travelling across
                ph = (i - (now * 18) % (iw + 12))
                if -2 <= ph <= 2:
                    v1 = [0.2, -0.9, 0.98, -0.6, 0.1][int(ph) + 2]
                for v, role in ((v2, "mag"), (v1, "acc")):
                    hy = int((max(-1, min(1, v)) + 1) / 2 * (rows - 1))
                    row = wave_h - 1 - hy // 2
                    self.put(y + 1 + row, ix + i, "▄" if hy % 2 == 0 else "▀", self.c(role, y + 1 + row, True))
        r = y + h - 3
        sync = 97.0 + 2.5 * math.sin(now * 0.7) + random.uniform(-0.2, 0.2)
        bpm = int(72 + 6 * math.sin(now * 0.3) + random.randint(-1, 1))
        line = f"SYNC {sync:4.1f}%  ♥ {bpm} BPM"
        self.put(r, ix, line[:iw], self.c("txt", r))
        r += 1
        tr = self.trace
        role = "acc" if tr < 50 else ("hi" if tr < 80 else "bad")
        lab = "TRACE"
        num = f"{tr:3.0f}%"
        self.put(r, ix, lab, self.c(role, r, tr >= 80 and int(now * 4) % 2 == 0))
        self.bar(r, ix + 6, iw - 6 - len(num) - 1, tr, role)
        self.put(r, ix + iw - len(num), num, self.c(role, r, True))

    def draw_proc_panel(self, y, x, h, w, now=None):
        st = self.stats
        ix, iw = x + 2, w - 4
        narrow = iw < 52
        self.panel(y, x, h, w, "PROCESSES", f"{st.nprocs} · F3" if narrow else f"{st.nprocs} ACTIVE · F3")
        r = y + 1
        wide = iw >= 70
        if narrow:
            hdr = f"{'PID':>6} {'CPU%':>5} {'MEM%':>5} PROCESS"
        else:
            hdr = f"{'PID':>7} {'USER':<9} {'CPU%':>5} {'MEM%':>5}  " + ("LOAD      " if wide else "") + "PROCESS"
        self.put(r, ix, hdr[:iw], self.c("dim", r, True))
        for i, p in enumerate(st.procs[: h - 3]):
            r = y + 2 + i
            pid, user, cpu, memp, _rss, state, comm = p
            role = "bad" if cpu > 50 else ("hi" if cpu > 15 else "txt")
            if narrow:
                self.put(r, ix, f"{pid:>6}", self.c("dim", r))
                self.put(r, ix + 7, f"{cpu:5.1f}", self.c(role, r, cpu > 15))
                self.put(r, ix + 13, f"{memp:5.1f}", self.c("txt", r))
                cx = ix + 19
            else:
                self.put(r, ix, f"{pid:>7}", self.c("dim", r))
                self.put(r, ix + 8, f"{user[:9]:<9}", self.c("bad" if user == "root" else "acc", r))
                self.put(r, ix + 18, f"{cpu:5.1f}", self.c(role, r, cpu > 15))
                self.put(r, ix + 24, f"{memp:5.1f}", self.c("txt", r))
                cx = ix + 31
                if wide:
                    self.bar(r, cx, 8, min(100, cpu))
                    cx += 10
            self.put(r, cx, comm[: ix + iw - cx], self.c("hi" if i == 0 else "txt", r, i == 0))

    def draw_console(self, y, x, h, w, now):
        if h < 3:
            return
        if self.job:
            tag = f"RUNNING {self.job[1][:20]} · ^C KILL"
        elif self.scroll:
            tag = f"SCROLL -{self.scroll} · PGDN"
        else:
            tag = "PGUP/PGDN SCROLL"
        self.panel(y, x, h, w, "CONSOLE // NETWATCH FEED", tag, role="acc")
        ix, iw = x + 2, w - 4
        view = h - 2
        need = view + self.scroll
        lines = []
        fx = self.conf["fx"]
        for segs, born in reversed(self.console):
            if fx:
                vis = int((now - born) * 900)
                if vis <= 0:
                    continue
                cut, out = vis, []
                for t, role in segs:
                    if cut <= 0:
                        break
                    out.append((t[:cut], role))
                    cut -= len(t)
                segs = out
            wrapped = self._wrap(segs, iw)
            lines[:0] = wrapped
            if len(lines) >= need:
                break
        maxscroll = max(0, len(lines) - view)
        if self.scroll > maxscroll and len(lines) < need:
            self.scroll = maxscroll
        end = len(lines) - self.scroll
        shown = lines[max(0, end - view): end]
        for i, segs in enumerate(shown):
            r = y + 1 + i
            cx = ix
            for t, role in segs:
                self.put(r, cx, t, self.c(role, r, role in ("hi", "ok", "bad")))
                cx += len(t)

    @staticmethod
    def _wrap(segs, width):
        lines, cur, ln = [], [], 0
        for text, role in segs:
            text = text.replace("\t", "    ")
            while text:
                space = width - ln
                if space <= 0:
                    lines.append(cur)
                    cur, ln, space = [], 0, width
                chunk, text = text[:space], text[space:]
                cur.append((chunk, role))
                ln += len(chunk)
        lines.append(cur)
        return lines

    def draw_prompt(self, now):
        y = self.H - 2
        W = self.W
        who = f" {self.user}@{self.host} "
        path = f" {tilde(self.cwd)} "
        if len(path) > W // 3:
            path = " …" + path[-(W // 3 - 2):]
        self.put(y, 0, who, self.inv("pri"))
        self.put(y, len(who), "▶", self.c("pri", y, True))
        self.put(y, len(who) + 1, path, self.c("acc", y, True))
        x0 = len(who) + 1 + len(path)
        self.put(y, x0, "▸ ", self.c("hi", y, True))
        x0 += 2
        avail = W - x0 - 2
        text = self.inp
        start = max(0, self.cur - avail + 1)
        vis = text[start:start + avail]
        if self.inp:
            self.put(y, x0, vis, self.c("txt", y, True))
        elif self.mode == "main" and not self.confirm:
            self.put(y, x0, "type a command · help · apps · shell · or any program name", self.c("deep", y))
        if int(now * 2.2) % 2 == 0 and self.mode == "main":
            cx = x0 + self.cur - start
            ch = text[self.cur] if self.cur < len(text) else " "
            self.put(y, cx, ch, self.pal("bg", "acc", True))

    def draw_keybar(self):
        y = self.H - 1
        x = 0
        for k, lab in KEYBAR:
            if k == "F10" and self.kiosk:
                lab = "LOG OUT"
            need = len(k) + len(lab) + 3
            if x + need > self.W - 1:
                break
            self.put(y, x, f"{k}", self.inv("acc"))
            self.put(y, x + len(k), f" {lab} ", self.c("txt", y))
            x += need
        tail = f" {self.pal.name.upper()} "
        if x + len(tail) < self.W:
            self.put(y, self.W - len(tail) - 1, tail, self.c("dim", y))

    # ---------------------------------------------------------------- overlays
    def box(self, title, hint="", w=None, h=None, role="acc"):
        W, H = self.W, self.H
        w = min(w or W - 6, W - 2)
        h = min(h or H - 4, H - 2)
        x = (W - w) // 2
        y = (H - h) // 2
        for yy in range(y, y + h):
            self.put(yy, x, " " * w, self.c("txt", yy))
        self.put(y, x, "╔" + "═" * (w - 2) + "╗", self.c(role, y, True))
        for yy in range(y + 1, y + h - 1):
            self.put(yy, x, "║", self.c(role, yy))
            self.put(yy, x + w - 1, "║", self.c(role, yy))
        self.put(y + h - 1, x, "╚" + "═" * (w - 2) + "╝", self.c(role, y + h - 1, True))
        lab = f" ◢ {title} ◣ "
        self.put(y, x + 3, lab, self.inv(role))
        if hint:
            hint = f" {hint} "
            self.put(y + h - 1, x + max(2, w - len(hint) - 3), hint[: w - 4], self.c("dim", y + h - 1))
        # drop shadow
        for yy in range(y + 1, min(self.H, y + h + 1)):
            self.put(yy, x + w, "▒", self.c("deep", yy))
        if y + h < self.H:
            self.put(y + h, x + 1, "▒" * (w - 1), self.c("deep", y + h))
        return y, x, h, w

    # -- apps
    def apps_view(self):
        if not self.catalog.ready:
            return []
        f = self.ov.get("filter", "")
        cats = [(f"SEARCH '{f}'", "matches across the arsenal", self.catalog.search(f))] if f else self.catalog.cats
        if not self.conf.get("show_missing", True):
            cats = [(t, d, [a for a in apps if a.kind != "get"]) for t, d, apps in cats]
            cats = [c for c in cats if c[2] or c[0].startswith("SEARCH")]
        return cats

    def draw_apps(self):
        y, x, h, w = self.box("ARSENAL // INSTALLED PROGRAMS",
                              "↑↓ select  ←→/TAB pane  ENTER jack in  / filter  ESC close")
        ov = self.ov
        if not self.catalog.ready:
            r = y + h // 2
            msg = "indexing arsenal" + "." * (int(self.now * 4) % 4)
            self.put(r, x + (w - len(msg)) // 2, msg, self.c("hi", r, True))
            return
        cats = self.apps_view()
        if not cats:
            return
        ov["cat"] = max(0, min(ov.get("cat", 0), len(cats) - 1))
        hint = "m: hide not-installed" if self.conf.get("show_missing", True) else "m: show installable"
        self.put(y + h - 1, x + 3, f" {hint} · i install ", self.c("dim", y + h - 1))
        lw = 30
        # filter line
        r = y + 1
        flt = ov.get("filter", "")
        caret = "█" if ov.get("typing") and int(self.now * 2.2) % 2 == 0 else " "
        self.put(r, x + 2, "FILTER ▸ ", self.c("dim", r))
        self.put(r, x + 11, (flt + caret) if (flt or ov.get("typing")) else "press / to search everything",
                 self.c("hi" if ov.get("typing") else "deep", r, True))
        cnt = f"{len(self.catalog.desktop)} desktop apps · {len(self.catalog.bins)} binaries"
        self.put(r, x + w - len(cnt) - 3, cnt, self.c("dim", r))
        r = y + 2
        self.put(r, x + 1, "─" * (w - 2), self.c("deep", r))
        list_top = y + 3
        list_h = h - 7
        # left: categories
        ctop = ov.get("ctop", 0)
        if ov["cat"] < ctop:
            ctop = ov["cat"]
        if ov["cat"] >= ctop + list_h:
            ctop = ov["cat"] - list_h + 1
        ov["ctop"] = ctop
        for i, (title, _desc, apps) in enumerate(cats[ctop:ctop + list_h]):
            idx = ctop + i
            rr = list_top + i
            sel = idx == ov["cat"]
            label = f" {title:<20}{len(apps):>5} "
            if sel:
                self.put(rr, x + 2, label, self.inv("pri" if ov.get("focus") == "cats" else "dim"))
            else:
                role = "acc" if title.startswith(("TERM", "PATH")) else "txt"
                self.put(rr, x + 2, label, self.c(role, rr))
        for rr in range(list_top, list_top + list_h):
            self.put(rr, x + lw + 2, "│", self.c("deep", rr))
        # right: apps
        title, desc, apps = cats[ov["cat"]]
        ax = x + lw + 4
        aw = w - lw - 7
        self.put(y + 3, ax, f"{title}", self.c("pri", y + 3, True))
        self.put(y + 3, ax + len(title) + 2, f"// {desc}"[: aw - len(title) - 2], self.c("dim", y + 3))
        alist_top = y + 4
        alist_h = list_h - 1
        ov["sel"] = max(0, min(ov.get("sel", 0), len(apps) - 1))
        top = ov.get("top", 0)
        if ov["sel"] < top:
            top = ov["sel"]
        if ov["sel"] >= top + alist_h:
            top = ov["sel"] - alist_h + 1
        ov["top"] = top
        nw = min(30, aw // 2)
        for i, a in enumerate(apps[top:top + alist_h]):
            idx = top + i
            rr = alist_top + i
            sel = idx == ov["sel"] and ov.get("focus") == "apps"
            kind = {"gui": "GUI", "tui": "TUI", "bin": "BIN", "get": "GET"}[a.kind]
            krole = {"gui": "acc", "tui": "hi", "bin": "dim", "get": "mag"}[a.kind]
            if sel:
                self.put(rr, ax - 1, " " * (aw + 1), self.inv("acc"))
                self.put(rr, ax, f"▶ {a.name[:nw - 2]:<{nw - 2}}", self.inv("acc"))
                self.put(rr, ax + nw + 1, kind, self.inv("acc"))
                self.put(rr, ax + nw + 5, a.comment[: aw - nw - 5], self.pal("bg", "acc", False))
            else:
                self.put(rr, ax, f"  {a.name[:nw - 2]}", self.c("dim" if a.kind == "get" else "txt", rr,
                                                               a.kind == "gui"))
                self.put(rr, ax + nw + 1, kind, self.c(krole, rr))
                self.put(rr, ax + nw + 5, a.comment[: aw - nw - 5], self.c("dim", rr))
        if len(apps) > alist_h:
            frac = top / max(1, len(apps) - alist_h)
            sy = alist_top + int(frac * (alist_h - 1))
            for rr in range(alist_top, alist_top + alist_h):
                self.put(rr, x + w - 3, "┃" if rr == sy else "│", self.c("pri" if rr == sy else "deep", rr))
        # detail
        r = y + h - 3
        self.put(r - 1, x + 1, "─" * (w - 2), self.c("deep", r - 1))
        if apps:
            a = apps[ov["sel"]]
            how = {"gui": "detached GUI", "tui": "takes the terminal", "bin": "output streams to console",
                   "get": "not installed · ENTER / i to install"}[a.kind]
            self.put(r, x + 2, "EXEC ▸ " if a.kind != "get" else "GET  ▸ ", self.c("dim", r))
            cmd = " ".join(a.argv) if a.kind != "get" else install_summary(a.inst)
            self.put(r, x + 9, cmd[: w - 14 - len(how)], self.c("hi", r))
            self.put(r, x + w - len(how) - 3, how, self.c("dim", r))

    def apps_key(self, k):
        ov = self.ov
        cats = self.apps_view()
        if ov.get("typing"):
            if k in ("\x1b",):
                ov["typing"] = False
                ov["filter"] = ""
            elif k in ("\n", "\r", curses.KEY_ENTER, curses.KEY_DOWN):
                ov["typing"] = False
                ov["focus"] = "apps"
                ov["sel"] = 0
            elif k in (curses.KEY_BACKSPACE, "\x7f", "\x08"):
                ov["filter"] = ov.get("filter", "")[:-1]
                ov["sel"] = ov["top"] = 0
            elif isinstance(k, str) and k.isprintable():
                ov["filter"] = ov.get("filter", "") + k
                ov["sel"] = ov["top"] = 0
                ov["cat"] = 0
                ov["focus"] = "apps"
            return
        if k in ("\x1b", "q", curses.KEY_F2):
            if ov.get("filter"):
                ov["filter"] = ""
                return
            self.mode = "main"
            return
        if k == "/":
            ov["typing"] = True
            ov["filter"] = ""
            return
        if k == "m":
            self.conf["show_missing"] = not self.conf.get("show_missing", True)
            save_conf(self.conf)
            ov["sel"] = ov["top"] = 0
            return
        if not cats:
            return
        focus = ov.get("focus", "cats")
        if k == "i" and focus == "apps":
            apps = cats[ov.get("cat", 0)][2]
            if apps:
                a = apps[max(0, min(ov.get("sel", 0), len(apps) - 1))]
                if a.inst:
                    self.mode = "main"
                    self.install_app(a)
            return
        if k in ("\t", curses.KEY_RIGHT, "l") and focus == "cats":
            ov["focus"] = "apps"
        elif k in ("\t", curses.KEY_LEFT, "h", curses.KEY_BTAB) and focus == "apps":
            ov["focus"] = "cats"
        elif k in (curses.KEY_UP, "k"):
            if focus == "cats":
                ov["cat"] = max(0, ov.get("cat", 0) - 1)
                ov["sel"] = ov["top"] = 0
            else:
                ov["sel"] = max(0, ov.get("sel", 0) - 1)
        elif k in (curses.KEY_DOWN, "j"):
            if focus == "cats":
                ov["cat"] = min(len(cats) - 1, ov.get("cat", 0) + 1)
                ov["sel"] = ov["top"] = 0
            else:
                ov["sel"] = ov.get("sel", 0) + 1
        elif k == curses.KEY_PPAGE:
            ov["sel"] = max(0, ov.get("sel", 0) - (self.H - 12))
        elif k == curses.KEY_NPAGE:
            ov["sel"] = ov.get("sel", 0) + (self.H - 12)
        elif k == curses.KEY_HOME:
            ov["sel"] = 0
        elif k == curses.KEY_END:
            ov["sel"] = 10 ** 9
        elif k in ("\n", "\r", curses.KEY_ENTER):
            if focus == "cats":
                ov["focus"] = "apps"
                return
            apps = cats[ov.get("cat", 0)][2]
            if apps:
                a = apps[max(0, min(ov.get("sel", 0), len(apps) - 1))]
                self.mode = "main"
                if a.kind == "get":
                    self.install_app(a)
                else:
                    self.launch_app(a)

    # -- procs
    def proc_list(self):
        ov = self.ov
        procs = list(self.stats.procs)
        f = ov.get("filter", "")
        if f:
            procs = [p for p in procs if f.lower() in p[6].lower() or f == str(p[0]) or f in p[1]]
        if ov.get("sort") == "mem":
            procs.sort(key=lambda p: p[4], reverse=True)
        elif ov.get("sort") == "pid":
            procs.sort(key=lambda p: p[0])
        return procs

    def draw_procs(self):
        y, x, h, w = self.box("PROCESS MANAGER // FLATLINE CONSOLE",
                              "↑↓ select  k SIGTERM  K SIGKILL  s sort  / filter  ESC close", role="pri")
        ov = self.ov
        procs = self.proc_list()
        r = y + 1
        flt = ov.get("filter", "")
        self.put(r, x + 2, f"SORT ▸ {ov.get('sort', 'cpu').upper():<4}   FILTER ▸ ", self.c("dim", r))
        caret = "█" if ov.get("typing") and int(self.now * 2.2) % 2 == 0 else ""
        self.put(r, x + 27, flt + caret or "—", self.c("hi", r, True))
        cnt = f"{len(procs)} processes"
        self.put(r, x + w - len(cnt) - 3, cnt, self.c("dim", r))
        r = y + 2
        hdr = f"  {'PID':>7}  {'USER':<10} {'ST':<2} {'CPU%':>6} {'MEM%':>6} {'RSS':>8}  LOAD        COMMAND"
        self.put(r, x + 1, hdr[: w - 2], self.c("dim", r, True))
        list_top, list_h = y + 3, h - 4
        ov["sel"] = max(0, min(ov.get("sel", 0), len(procs) - 1))
        top = ov.get("top", 0)
        if ov["sel"] < top:
            top = ov["sel"]
        if ov["sel"] >= top + list_h:
            top = ov["sel"] - list_h + 1
        ov["top"] = top
        for i, p in enumerate(procs[top:top + list_h]):
            rr = list_top + i
            pid, user, cpu, memp, rss, state, comm = p
            sel = top + i == ov["sel"]
            line = f"  {pid:>7}  {user[:10]:<10} {state:<2} {cpu:6.1f} {memp:6.1f} {fmt_bytes(rss):>8}  "
            if sel:
                self.put(rr, x + 1, " " * (w - 2), self.inv("pri"))
                self.put(rr, x + 1, "▶" + line[1:], self.inv("pri"))
                self.put(rr, x + 1 + len(line) + 12, comm[: w - len(line) - 15], self.inv("pri"))
            else:
                role = "bad" if cpu > 50 else ("hi" if cpu > 15 else "txt")
                self.put(rr, x + 1, line, self.c(role, rr))
                self.put(rr, x + 3 + 9, f"{user[:10]:<10}", self.c("bad" if user == "root" else "acc", rr))
                self.put(rr, x + 1 + len(line) + 12, comm[: w - len(line) - 15], self.c("txt", rr, True))
            self.bar(rr, x + 1 + len(line), 10, min(100, cpu))

    def procs_key(self, k):
        ov = self.ov
        if ov.get("typing"):
            if k == "\x1b":
                ov["typing"] = False
                ov["filter"] = ""
            elif k in ("\n", "\r", curses.KEY_ENTER):
                ov["typing"] = False
            elif k in (curses.KEY_BACKSPACE, "\x7f", "\x08"):
                ov["filter"] = ov.get("filter", "")[:-1]
            elif isinstance(k, str) and k.isprintable():
                ov["filter"] = ov.get("filter", "") + k
                ov["sel"] = 0
            return
        procs = self.proc_list()
        if k in ("\x1b", "q", curses.KEY_F3):
            self.mode = "main"
        elif k == "/":
            ov["typing"] = True
        elif k in (curses.KEY_UP, "\x10"):
            ov["sel"] = max(0, ov.get("sel", 0) - 1)
        elif k in (curses.KEY_DOWN, "j", "\x0e"):
            ov["sel"] = ov.get("sel", 0) + 1
        elif k == curses.KEY_PPAGE:
            ov["sel"] = max(0, ov.get("sel", 0) - (self.H - 10))
        elif k == curses.KEY_NPAGE:
            ov["sel"] = ov.get("sel", 0) + (self.H - 10)
        elif k == "s":
            order = ["cpu", "mem", "pid"]
            ov["sort"] = order[(order.index(ov.get("sort", "cpu")) + 1) % 3]
        elif k in ("k", "K", curses.KEY_DC) and procs:
            p = procs[max(0, min(ov.get("sel", 0), len(procs) - 1))]
            sig = signal.SIGKILL if k == "K" else signal.SIGTERM
            name = "SIGKILL" if sig == signal.SIGKILL else "SIGTERM"
            self.ask(f"FLATLINE {p[6]} (pid {p[0]}) with {name}?", lambda: self.send_signal(p[0], sig, p[6]))

    def send_signal(self, pid, sig, name):
        try:
            os.kill(pid, sig)
            self.log(f"{name} [{pid}] flatlined ({signal.Signals(sig).name})", "warn", tag="FLATLINE", tag_role="bad")
            self.glitch(0.2)
        except ProcessLookupError:
            self.err(f"pid {pid} already gone")
        except PermissionError:
            self.err(f"pid {pid}: ICE too thick - needs root (try: run sudo kill {pid})")

    # -- help
    def draw_help(self):
        y, x, h, w = self.box("CODEX // COMMAND REFERENCE", "↑↓ scroll  ESC close", role="hi")
        lines = []
        lines.append([("COMMANDS", "pri")])
        for name, args, desc, aliases in COMMANDS:
            al = ("  aka " + ", ".join(aliases)) if aliases else ""
            lines.append([(f"  {name:<9}", "acc"), (f"{args:<20}", "hi"), (desc, "txt"), (al, "dim")])
        lines.append([])
        lines.append([("ANYTHING ELSE", "pri")])
        lines.append([("  <program>   ", "acc"), ("any installed app or binary: GUI apps detach, TUI tools take the screen,", "txt")])
        lines.append([("              ", "acc"), ("everything else streams its output into the console (ls, git status, ping ...)", "txt")])
        lines.append([("  !<cmd>      ", "acc"), ("force a shell command into the console - pipes, globs, && all work", "txt")])
        lines.append([])
        lines.append([("KEYS", "pri")])
        keys = [("F1-F10", "see the bar at the bottom"), ("ALT+1 … ALT+9", "launch dock slot"),
                ("TAB", "complete commands, programs, paths"),
                ("↑ / ↓", "command history"), ("PGUP / PGDN", "scroll the console"),
                ("CTRL+C", "kill running job / clear input"), ("CTRL+L", "clear console"),
                ("CTRL+U / CTRL+W", "clear line / delete word"), ("CTRL+D", "jack out (on empty line)")]
        for k, d in keys:
            lines.append([(f"  {k:<18}", "hi"), (d, "txt")])
        view = h - 3
        self.ov["max"] = max(0, len(lines) - view)
        off = max(0, min(self.ov.get("off", 0), self.ov["max"]))
        self.ov["off"] = off
        for i, segs in enumerate(lines[off:off + view]):
            r = y + 2 + i
            cx = x + 3
            for t, role in segs:
                t = t[: max(0, x + w - 3 - cx)]
                self.put(r, cx, t, self.c(role, r, role in ("pri", "acc")))
                cx += len(t)

    def help_key(self, k):
        if k in (curses.KEY_UP, "k"):
            self.ov["off"] = max(0, self.ov.get("off", 0) - 1)
        elif k in (curses.KEY_DOWN, "j"):
            self.ov["off"] = self.ov.get("off", 0) + 1
        elif k == curses.KEY_NPAGE:
            self.ov["off"] = self.ov.get("off", 0) + 10
        elif k == curses.KEY_PPAGE:
            self.ov["off"] = max(0, self.ov.get("off", 0) - 10)
        else:
            self.mode = "main"

    # -- settings (F8)
    def mono_fonts(self):
        if getattr(self, "_fonts", None) is None:
            fonts = set()
            if shutil.which("fc-list"):
                try:
                    out = subprocess.run(["fc-list", ":spacing=mono", "family"], capture_output=True, text=True,
                                         timeout=4).stdout
                    for line in out.splitlines():
                        f = line.split(",")[0].strip()
                        if f:
                            fonts.add(f)
                except (OSError, subprocess.SubprocessError):
                    pass
            self._fonts = sorted(fonts, key=str.lower)
        return self._fonts

    def settings_rows(self):
        rows = [("sec", "LOOK", ""), ("theme", "theme", "Theme")]
        rows += [("color", r, lab) for r, lab in ROLES]
        rows += [("sec", "TYPE", ""), ("font", "font", "Font family"), ("size", "font_size", "Font size")]
        rows += [("sec", "EFFECTS", "")]
        rows += [("bool", k, lab) for k, lab in (("fx", "Glitches & animations"), ("scan", "Scanline rows"),
                                                 ("boot", "Boot sequence"), ("ticker", "News ticker"),
                                                 ("neural", "Neural readout in top bar"))]
        rows += [("sec", "PANELS", "")]
        rows += [("panel", p, lab) for p, lab in PANELS.items()]
        rows += [("sec", "ACTIONS", ""), ("act", "save", "Save colors as a new theme"),
                 ("act", "reset", "Reset this theme's colors"), ("act", "relaunch", "Apply font now (relaunch)")]
        return rows

    def settings_value(self, row):
        kind, key, _ = row
        c = self.conf
        if kind == "theme":
            return c["theme"] + ("  (custom)" if c["theme"] not in THEMES else "")
        if kind == "color":
            n = self.pal.colors[key]
            th = c["theme"]
            mod = key in c.get("overrides", {}).get(th, {})
            return f"{n:>3}  {c256_to_hex(n)}" + ("  *" if mod else "")
        if kind == "font":
            return c.get("font") or "(terminal default)"
        if kind == "size":
            return f"{c.get('font_size', 13)} pt"
        if kind == "bool":
            return "ON" if c.get(key, True) else "OFF"
        if kind == "panel":
            lay = c["layout"]
            return "LEFT" if key in lay["left"] else ("RIGHT" if key in lay["right"] else "OFF")
        return "↵"

    def draw_settings(self):
        y, x, h, w = self.box("TUNE // CUSTOMIZE THE DECK",
                              "↑↓ select  ←→ change  ENTER edit/toggle  r reset color  ESC save & close", role="mag")
        ov = self.ov
        rows = self.settings_rows()
        lw = min(66, w - 4)
        lh = h - 3
        sel = max(0, min(ov.get("sel", 1), len(rows) - 1))
        top = ov.get("top", 0)
        if sel < top:
            top = max(0, sel - 1)
        if sel >= top + lh:
            top = sel - lh + 1
        ov["top"] = top
        for i, row in enumerate(rows[top:top + lh]):
            r = y + 2 + i
            kind, key, label = row
            if kind == "sec":
                self.put(r, x + 3, f"── {key} " + "─" * (lw - len(key) - 6), self.c("pri", r, True))
                continue
            is_sel = top + i == sel
            val = self.settings_value(row)
            if is_sel and ov.get("edit") is not None:
                caret = "█" if int(self.now * 2.2) % 2 == 0 else " "
                val = ov["edit"] + caret
            if is_sel:
                self.put(r, x + 3, " " * lw, self.inv("mag"))
                self.put(r, x + 4, f"▶ {label}", self.inv("mag"))
                self.put(r, x + 36, val[: lw - 38], self.inv("mag"))
            else:
                self.put(r, x + 6, label, self.c("txt", r))
                role = {"ON": "ok", "OFF": "deep", "LEFT": "acc", "RIGHT": "acc"}.get(val, "hi")
                self.put(r, x + 36, val[: lw - 38], self.c(role, r, role != "deep"))
            if kind == "color":
                self.put(r, x + 3 + lw - 5, "    ", self.pal.raw(self.pal.colors["txt"], self.pal.colors[key]))
        # scrollbar
        if len(rows) > lh:
            frac = top / max(1, len(rows) - lh)
            sy = y + 2 + int(frac * (lh - 1))
            for rr in range(y + 2, y + 2 + lh):
                self.put(rr, x + lw + 4, "┃" if rr == sy else "│", self.c("mag" if rr == sy else "deep", rr))
        # live preview + help on the right
        px = x + lw + 7
        pw = w - lw - 10
        if pw >= 28:
            self.draw_settings_preview(y + 2, px, pw, rows[sel])

    def draw_settings_preview(self, y, x, w, row):
        kind, key, label = row
        ph = 9
        self.panel(y, x, ph, w, "PREVIEW", self.conf["theme"].upper())
        ix, iw = x + 2, w - 4
        self.put(y + 1, ix, "CPU", self.c("txt", y + 1, True))
        self.bar(y + 1, ix + 4, iw - 10, 37)
        self.put(y + 1, ix + iw - 5, " 37%", self.c("acc", y + 1, True))
        self.put(y + 2, ix, "MEM", self.c("txt", y + 2, True))
        self.bar(y + 2, ix + 4, iw - 10, 71)
        self.put(y + 2, ix + iw - 5, " 71%", self.c("hi", y + 2, True))
        self.spark(y + 3, ix, iw, [abs(math.sin(i * 0.4 + self.now)) * 100 for i in range(iw)], "pri", peak=100)
        self.put(y + 4, ix, "body text ", self.c("txt", y + 4))
        self.put(y + 4, ix + 10, "highlight ", self.c("acc", y + 4, True))
        self.put(y + 4, ix + 20, "hot", self.c("hi", y + 4, True))
        self.put(y + 5, ix, "✓ ok ", self.c("ok", y + 5, True))
        self.put(y + 5, ix + 6, "▲ warn ", self.c("warn", y + 5, True))
        self.put(y + 5, ix + 14, "✗ alert ", self.c("bad", y + 5, True))
        self.put(y + 5, ix + 23, "◆ accent", self.c("mag", y + 5, True))
        self.put(y + 6, ix, "labels and chrome", self.c("dim", y + 6))
        self.put(y + 7, ix, f" {self.user}@{self.host} ", self.inv("pri"))
        # palette strip for color rows
        r = y + ph + 1
        if kind == "color":
            cur = self.pal.colors[key]
            self.put(r, x, f"{label.upper()}  ·  ←→ step  ·  ENTER type #hex or 0-255", self.c("dim", r))
            n = max(4, min(32, (w - 2) // 2))
            start = max(0, min(256 - n, cur - n // 2))
            for i in range(n):
                v = start + i
                self.put(r + 1, x + i * 2, "  ", self.pal.raw(self.pal.colors["txt"], v))
                if v == cur:
                    self.put(r + 2, x + i * 2, "▲▲", self.c("hi", r + 2, True))
            return
        tips = {
            "theme": "←→ cycles built-in and custom themes. Save your tweaks with the action at the bottom.",
            "font": "←→ cycles installed monospace fonts, ENTER types any name. The NETDECK session and app-menu "
                    "launcher apply it (foot, kitty, alacritty). Use 'Apply font now' to see it.",
            "size": "←→ changes the size. Applied on relaunch.",
            "bool": "ENTER or ←→ toggles.",
            "panel": "ENTER toggles the panel. Columns and order live in ~/.config/netdeck/config.json → layout.",
            "act": "ENTER runs it.",
        }
        text = tips.get(kind, "")
        for i, line in enumerate(self._wrap([(text, "dim")], w)):
            self.put(r + i, x, "".join(t for t, _ in line), self.c("dim", r + i))

    def settings_key(self, k):
        ov = self.ov
        rows = self.settings_rows()
        sel = max(0, min(ov.get("sel", 1), len(rows) - 1))
        row = rows[sel]
        kind, key, _ = row
        if ov.get("edit") is not None:
            if k == "\x1b":
                ov["edit"] = None
            elif k in ("\n", "\r", curses.KEY_ENTER):
                text, ov["edit"] = ov["edit"].strip(), None
                self.settings_commit(row, text)
            elif k in (curses.KEY_BACKSPACE, "\x7f", "\x08"):
                ov["edit"] = ov["edit"][:-1]
            elif isinstance(k, str) and k.isprintable():
                ov["edit"] += k
            return
        if k in ("\x1b", "q", curses.KEY_F8):
            save_conf(self.conf)
            self.mode = "main"
            self.ok("settings saved")
            return
        if k in (curses.KEY_UP, "k", curses.KEY_DOWN, "j", curses.KEY_PPAGE, curses.KEY_NPAGE):
            step = {curses.KEY_UP: -1, "k": -1, curses.KEY_DOWN: 1, "j": 1,
                    curses.KEY_PPAGE: -10, curses.KEY_NPAGE: 10}[k]
            n = max(0, min(len(rows) - 1, sel + step))
            while 0 < n < len(rows) - 1 and rows[n][0] == "sec":
                n += 1 if step > 0 else -1
            if rows[n][0] == "sec":
                n = sel
            ov["sel"] = n
            return
        if k in (curses.KEY_LEFT, "h", curses.KEY_RIGHT, "l"):
            self.settings_adjust(row, -1 if k in (curses.KEY_LEFT, "h") else 1)
        elif k in ("\n", "\r", curses.KEY_ENTER, " "):
            if kind in ("color", "font", "size"):
                ov["edit"] = ""
            elif kind == "act" and key == "save":
                ov["edit"] = ""
            elif kind == "act" and key == "reset":
                self.conf.get("overrides", {}).pop(self.conf["theme"], None)
                self.pal.set(self.conf)
                self.scr.clear()
            elif kind == "act" and key == "relaunch":
                save_conf(self.conf)
                self.mode = "main"
                self.cmd_relaunch([], "")
            else:
                self.settings_adjust(row, 1)
        elif k == "r" and kind == "color":
            th = self.conf["theme"]
            self.conf.get("overrides", {}).get(th, {}).pop(key, None)
            self.pal.set(self.conf)

    def settings_adjust(self, row, d):
        kind, key, _ = row
        c = self.conf
        if kind == "theme":
            names = all_themes(c)
            i = names.index(c["theme"]) if c["theme"] in names else 0
            c["theme"] = names[(i + d) % len(names)]
            self.pal.set(c)
            self.scr.clear()
        elif kind == "color":
            self.set_color(key, (self.pal.colors[key] + d) % 256)
        elif kind == "font":
            fonts = self.mono_fonts()
            if fonts:
                i = fonts.index(c.get("font")) if c.get("font") in fonts else -1
                c["font"] = fonts[(i + d) % len(fonts)]
        elif kind == "size":
            c["font_size"] = max(6, min(40, int(c.get("font_size", 13)) + d))
        elif kind == "bool":
            c[key] = not c.get(key, True)
        elif kind == "panel":
            self.toggle_panel(key)

    def settings_commit(self, row, text):
        kind, key, _ = row
        if not text:
            return
        if kind == "color":
            try:
                self.set_color(key, color_val(text))
            except ValueError:
                self.err(f"'{text}' isn't a color - use #rrggbb or 0-255")
        elif kind == "font":
            self.conf["font"] = text
        elif kind == "size" and text.isdigit():
            self.conf["font_size"] = max(6, min(40, int(text)))
        elif kind == "act" and key == "save":
            self.save_theme(text)

    # -- confirm
    def ask(self, question, action):
        self.confirm = (question, action)

    def draw_confirm(self):
        q = self.confirm[0]
        w = max(44, len(q) + 8)
        y, x, h, w = self.box("CONFIRM", "", w=w, h=7, role="bad")
        self.put(y + 2, x + (w - len(q)) // 2, q, self.c("hi", y + 2, True))
        opts = "[ Y ] EXECUTE      [ N ] ABORT"
        self.put(y + 4, x + (w - len(opts)) // 2, opts, self.c("txt", y + 4))
        self.put(y + 4, x + (w - len(opts)) // 2 + 2, "Y", self.c("bad", y + 4, True))
        self.put(y + 4, x + (w - len(opts)) // 2 + 21, "N", self.c("acc", y + 4, True))

    # ---------------------------------------------------------------- input
    def handle_key(self, k):
        if k == curses.KEY_RESIZE:
            self.resize()
            return
        if self.confirm:
            q, action = self.confirm
            self.confirm = None
            if k in ("y", "Y"):
                action()
            else:
                self.info("aborted", "dim")
            return
        if self.mode == "apps":
            return self.apps_key(k)
        if self.mode == "procs":
            return self.procs_key(k)
        if self.mode == "help":
            return self.help_key(k)
        if self.mode == "settings":
            return self.settings_key(k)

        fkeys = {curses.KEY_F1: "help", curses.KEY_F2: "apps", curses.KEY_F3: "procs", curses.KEY_F4: "shell",
                 curses.KEY_F5: "scan", curses.KEY_F6: "rain", curses.KEY_F7: "sysinfo", curses.KEY_F8: "settings", curses.KEY_F9: "theme +",
                 curses.KEY_F10: "quit"}
        if k in fkeys:
            self.execute(fkeys[k], record=False)
            return
        if k in ("\n", "\r", curses.KEY_ENTER):
            line = self.inp
            self.inp, self.cur, self.hpos = "", 0, None
            self.scroll = 0
            self.execute(line)
        elif k in (curses.KEY_BACKSPACE, "\x7f", "\x08"):
            if self.cur > 0:
                self.inp = self.inp[: self.cur - 1] + self.inp[self.cur:]
                self.cur -= 1
        elif k == curses.KEY_DC:
            self.inp = self.inp[: self.cur] + self.inp[self.cur + 1:]
        elif k == curses.KEY_LEFT:
            self.cur = max(0, self.cur - 1)
        elif k == curses.KEY_RIGHT:
            self.cur = min(len(self.inp), self.cur + 1)
        elif k in (curses.KEY_HOME, "\x01"):
            self.cur = 0
        elif k in (curses.KEY_END, "\x05"):
            self.cur = len(self.inp)
        elif k == curses.KEY_UP:
            if self.history:
                self.hpos = len(self.history) - 1 if self.hpos is None else max(0, self.hpos - 1)
                self.inp = self.history[self.hpos]
                self.cur = len(self.inp)
        elif k == curses.KEY_DOWN:
            if self.hpos is not None:
                self.hpos += 1
                if self.hpos >= len(self.history):
                    self.hpos, self.inp = None, ""
                else:
                    self.inp = self.history[self.hpos]
                self.cur = len(self.inp)
        elif k == curses.KEY_PPAGE:
            self.scroll += max(1, self.H // 3)
        elif k == curses.KEY_NPAGE:
            self.scroll = max(0, self.scroll - max(1, self.H // 3))
        elif k == "\t":
            self.complete()
        elif k == "\x03":  # Ctrl+C
            if self.job:
                self.kill_job()
            elif self.inp:
                self.inp, self.cur = "", 0
            else:
                self.info("type `quit` or press F10 to jack out", "dim")
        elif k == "\x04":  # Ctrl+D
            if not self.inp:
                self.execute("quit", record=False)
        elif k == "\x0c":  # Ctrl+L
            self.console.clear()
            self.scroll = 0
        elif k == "\x15":  # Ctrl+U
            self.inp, self.cur = self.inp[self.cur:], 0
        elif k == "\x17":  # Ctrl+W
            left = self.inp[: self.cur].rstrip()
            i = left.rfind(" ") + 1
            self.inp = left[:i] + self.inp[self.cur:]
            self.cur = i
        elif k == "\x1b":
            self.scr.timeout(0)
            try:
                k2 = self.scr.get_wch()
            except curses.error:
                k2 = None
            if isinstance(k2, str) and k2 in "123456789" and k2:
                items = self.dock_items()
                i = int(k2) - 1
                if i < len(items):
                    self.log([("▶ ", "pri"), (items[i], "hi"), ("  (dock)", "dim")])
                    self.execute(items[i], record=False)
            elif k2 is None:
                self.inp, self.cur = "", 0
        elif isinstance(k, str) and k.isprintable():
            self.inp = self.inp[: self.cur] + k + self.inp[self.cur:]
            self.cur += len(k)

    def all_command_names(self):
        names = []
        for n, _a, _d, al in COMMANDS:
            names.append(n)
            names.extend(al)
        return names

    def complete(self):
        before = self.inp[: self.cur]
        parts = before.split(" ")
        word = parts[-1]
        first = len(parts) == 1
        cands = []
        if first:
            pool = set(self.all_command_names())
            if self.catalog.ready:
                pool |= self.catalog.binset
            cands = sorted(c for c in pool if c.startswith(word))
        else:
            cmd = parts[0].lower()
            if cmd in ("theme", "skin"):
                cands = [t for t in all_themes(self.conf) + ["+", "save"] if t.startswith(word)]
            elif cmd in ("get", "install"):
                cands = sorted(a.key for a in self.catalog.market if a.kind == "get" and a.key.startswith(word))
            elif cmd in ("panel", "panels"):
                cands = [p for p in PANELS if p.startswith(word)] if len(parts) == 2 else \
                    [o for o in ("on", "off") if o.startswith(word)]
            elif cmd in ("color", "colour") and len(parts) == 2:
                cands = [r for r, _ in ROLES if r.startswith(word)] + (["reset"] if "reset".startswith(word) else [])
            elif cmd == "fx":
                cands = [t for t in ("on", "off", "scan", "boot") if t.startswith(word)]
            elif cmd in ("run", "jack", "launch", "spawn", "bg", "exec", "x", "kill") and len(parts) == 2:
                pool = set()
                if self.catalog.ready:
                    pool |= self.catalog.binset
                    for a in self.catalog.desktop:
                        pool.add(a.stem.split(".")[-1] if "." in a.stem else a.stem)
                if cmd == "kill":
                    pool = {p[6] for p in self.stats.procs}
                cands = sorted(c for c in pool if c.lower().startswith(word.lower()))
            else:
                cands = self.path_cands(word, dirs_only=cmd == "cd")
        if not cands:
            return
        if len(cands) == 1:
            rep = cands[0]
            if not rep.endswith("/"):
                rep += " "
        else:
            rep = os.path.commonprefix(cands)
            shown = cands[:60]
            self.log([("  ", "txt"), ("  ".join(shown), "acc"),
                      (f"  (+{len(cands) - 60} more)" if len(cands) > 60 else "", "dim")])
        new_before = before[: len(before) - len(word)] + rep
        self.inp = new_before + self.inp[self.cur:]
        self.cur = len(new_before)

    def path_cands(self, word, dirs_only=False):
        exp = os.path.expanduser(word)
        base = exp if os.path.isabs(exp) else os.path.join(self.cwd, exp)
        d, prefix = os.path.split(base)
        try:
            ents = os.listdir(d or "/")
        except OSError:
            return []
        out = []
        head = word[: len(word) - len(prefix)]
        for e in sorted(ents):
            if not e.startswith(prefix) or (e.startswith(".") and not prefix.startswith(".")):
                continue
            full = os.path.join(d, e)
            isdir = os.path.isdir(full)
            if dirs_only and not isdir:
                continue
            out.append(head + e + ("/" if isdir else ""))
        return out

    # ---------------------------------------------------------------- command execution
    def execute(self, raw, record=True):
        line = raw.strip()
        if not line:
            return
        if record:
            if not self.history or self.history[-1] != line:
                self.history.append(line)
                self._save_history()
            self.log([("▶ ", "pri"), (line, "hi")])
        if line.startswith("!"):
            return self.exec_capture(line[1:].strip())
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if not parts:
            return
        cmd, args = parts[0], parts[1:]
        rest = line[len(line.split(None, 1)[0]):].strip()
        for name, _a, _d, aliases in COMMANDS:
            if cmd.lower() == name or cmd.lower() in aliases:
                return getattr(self, "cmd_" + name)(args, rest)
        self.fallback(parts, line)

    def fallback(self, parts, line):
        prog = parts[0]
        if self.catalog.ready and len(parts) == 1 and not shutil.which(prog):
            app = self.catalog.exact(prog)
            if app:
                return self.launch_app(app)
        if shutil.which(prog) or os.path.isfile(os.path.join(self.cwd, prog)):
            interactive = os.path.basename(prog) in INTERACTIVE or line.startswith(INTERACTIVE_PREFIX)
            if interactive and not (os.path.basename(prog) in REPL_ONLY and len(parts) > 1):
                return self.foreground(["bash", "-c", line] if shutil.which("bash") else line, shell=True,
                                       pause=os.path.basename(prog) in ("apt", "apt-get", "sudo", "watch") or False,
                                       label=prog)
            return self.exec_capture(line)
        if self.catalog.ready:
            app = self.catalog.exact(" ".join(parts))
            if app:
                return self.launch_app(app)
        hit = self.market_find(prog) if self.catalog.ready else None
        if hit and hit.kind == "get":
            return self.log([("  ✗ ", "bad"), (f"{hit.name} isn't installed yet - type ", "txt"),
                             (f"get {hit.key}", "hi"), (f" ({hit.comment})", "dim")])
        self.err(f"'{prog}' not recognized - no such command or program on this deck. try: help / apps")

    def launch_app(self, a):
        if a.kind == "gui":
            if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                self.log("no visual cortex detected ($DISPLAY unset) - GUI may fail to render", "warn",
                         tag="WARN", tag_role="warn")
            self.spawn(a.argv, a.name)
        elif a.kind == "tui":
            self.foreground(a.argv, pause=a.name in ("apt", "sudo"), label=a.name)
        else:
            self.exec_capture(" ".join(shlex.quote(p) for p in a.argv))

    def spawn(self, argv, label):
        try:
            p = subprocess.Popen(argv, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True,
                                 shell=isinstance(argv, str))
        except OSError as e:
            self.err(f"deploy failed: {e.strerror or e}")
            return
        self.children.append(p)
        self.log([("daemon deployed ▸ ", "txt"), (label, "hi"), (f"  [pid {p.pid}]", "dim")], tag="JACK-IN",
                 tag_role="ok")
        self.glitch(0.15)

    def reap(self):
        alive = []
        for p in self.children:
            if p.poll() is None:
                alive.append(p)
        self.children = alive

    def env(self):
        e = dict(os.environ)
        e["NETDECK"] = "1"
        return e

    def foreground(self, cmd, shell=False, pause=True, label=None, banner=True):
        label = label or (cmd if isinstance(cmd, str) else " ".join(cmd))
        t = self.pal.colors
        curses.def_prog_mode()
        curses.endwin()
        out = sys.stdout
        if isinstance(banner, str):
            out.write("\x1b[0m\x1b[2J\x1b[H" + banner)
        elif banner:
            out.write("\x1b[0m\x1b[2J\x1b[H")
            out.write(f"{ansi256(t['pri'])}◢ NETDECK{ansi256(t['dim'])} ▸ jacking into "
                      f"{ansi256(t['hi'])}{label}{ansi256(t['dim'])}  ·  cwd {tilde(self.cwd)}\x1b[0m\n\n")
        out.flush()
        old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)

        def pre():
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGQUIT, signal.SIG_DFL)

        t0 = time.time()
        try:
            if isinstance(cmd, str):
                rc = subprocess.call(cmd, shell=True, cwd=self.cwd, preexec_fn=pre, env=self.env())
            else:
                rc = subprocess.call(cmd, cwd=self.cwd, preexec_fn=pre, env=self.env())
        except OSError as e:
            out.write(f"\n{ansi256(t['bad'])}✗ {e}\x1b[0m\n")
            rc = 127
            pause = True
        finally:
            signal.signal(signal.SIGINT, old_int)
        dt = time.time() - t0
        if pause or (rc != 0 and dt < 2):
            out.write(f"\n{ansi256(t['pri'])}[ PROCESS TERMINATED · EXIT {rc} ]{ansi256(t['dim'])}"
                      f"  press ENTER to re-jack\x1b[0m ")
            out.flush()
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
        curses.reset_prog_mode()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.resize()
        role = "ok" if rc == 0 else "bad"
        self.log([("disconnected from ", "txt"), (label[:60], "hi"), (f"  exit {rc} · {dt:.1f}s", "dim")],
                 tag="JACK-OUT", tag_role=role)
        self.glitch(0.3)

    def exec_capture(self, cmdline):
        if not cmdline:
            return
        if self.job:
            self.err("a job is already running - Ctrl+C to kill it first")
            return
        sh = ["bash", "-c", cmdline] if shutil.which("bash") else ["sh", "-c", cmdline]
        e = self.env()
        e.update(TERM="dumb", COLUMNS=str(max(40, self.W - 40)), PAGER="cat", GIT_PAGER="cat",
                 SYSTEMD_PAGER="", NO_COLOR="1")
        try:
            p = subprocess.Popen(sh, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, start_new_session=True, env=e)
        except OSError as ex:
            self.err(f"exec failed: {ex}")
            return
        self.job = (p, cmdline, time.time())

        def reader():
            for raw in iter(p.stdout.readline, b""):
                self.jobq.put(("line", raw.decode("utf-8", "replace")))
            p.wait()
            self.jobq.put(("done", p.returncode))

        threading.Thread(target=reader, daemon=True).start()

    def drain_jobs(self):
        n = 0
        while n < 400:
            try:
                kind, val = self.jobq.get_nowait()
            except queue.Empty:
                break
            n += 1
            if kind == "line":
                text = ANSI_RE.sub("", val.rstrip("\n")).replace("\r", "")
                text = "".join(ch for ch in text if ch == "\t" or ch.isprintable())
                self.log([("  ", "txt"), (text, "txt")])
            else:
                if self.job:
                    dt = time.time() - self.job[2]
                    role = "ok" if val == 0 else "bad"
                    self.log([("  └─ ", "deep"), (f"exit {val}", role), (f" · {dt:.2f}s", "dim")])
                self.job = None

    def kill_job(self):
        if not self.job:
            return
        p = self.job[0]
        try:
            os.killpg(p.pid, signal.SIGINT if not getattr(p, "_netdeck_int", False) else signal.SIGKILL)
            p._netdeck_int = True
        except (ProcessLookupError, PermissionError):
            pass
        self.log("  ^C", "warn")

    # ---------------------------------------------------------------- commands
    def cmd_help(self, args, rest):
        self.mode, self.ov = "help", {}

    def cmd_apps(self, args, rest):
        self.mode = "apps"
        self.ov = {"cat": 0, "sel": 0, "top": 0, "focus": "cats", "filter": rest}
        if rest:
            self.ov["focus"] = "apps"

    def cmd_run(self, args, rest):
        if not args:
            return self.err("usage: run <program> [args]")
        prog = args[0]
        if len(args) == 1 and self.catalog.ready:
            app, cands = self.catalog.find(prog)
            if app and not (shutil.which(prog) and app.kind != "gui"):
                return self.launch_app(app)
            if not shutil.which(prog) and cands:
                self.info(f"{len(cands)} matches - be more specific:", "warn")
                for a in cands[:12]:
                    self.log([("    ", "txt"), (f"{a.stem.split('.')[-1]:<22}", "acc"), (a.name, "txt")])
                return
        if not shutil.which(prog) and not os.path.exists(os.path.join(self.cwd, prog)):
            return self.err(f"'{prog}' not found on this deck")
        self.foreground(["bash", "-c", rest] if shutil.which("bash") else rest, shell=False, label=rest)

    def cmd_spawn(self, args, rest):
        if not rest:
            return self.err("usage: spawn <command>")
        self.spawn(rest, rest)

    def cmd_exec(self, args, rest):
        if not rest:
            return self.err("usage: exec <command>   (or !<command>)")
        self.exec_capture(rest)

    def cmd_shell(self, args, rest):
        sh = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
        t = self.pal.colors
        cmd = [sh]
        if os.path.basename(sh) == "bash":
            os.makedirs(CACHE_DIR, exist_ok=True)
            rc = os.path.join(CACHE_DIR, "bashrc")
            p, a, h, d, x = t["pri"], t["acc"], t["hi"], t["dim"], t["txt"]
            with open(rc, "w") as fh:
                fh.write(
                    "[ -f ~/.bashrc ] && . ~/.bashrc\n"
                    f"PS1='\\[\\e[38;5;{p}m\\]┌─[\\[\\e[38;5;{a}m\\]\\u\\[\\e[38;5;{p}m\\]@\\[\\e[38;5;{h}m\\]"
                    f"\\h\\[\\e[38;5;{p}m\\]]─[\\[\\e[38;5;{x}m\\]\\w\\[\\e[38;5;{p}m\\]]─[\\[\\e[38;5;{d}m\\]"
                    f"RAW LINK\\[\\e[38;5;{p}m\\]]\\n└──╼ \\[\\e[38;5;{a}m\\]$\\[\\e[0m\\] '\n"
                    "deck() { exit; }\n"
                )
            cmd = [sh, "--rcfile", rc, "-i"]
        bar = "━" * min(70, self.W - 2)
        text = (f"{ansi256(t['pri'])}{bar}\n"
                f"{ansi256(t['pri'])} ◢ RAW SHELL LINK {ansi256(t['dim'])}// netdeck safeguards offline\n"
                f"{ansi256(t['dim'])}   type {ansi256(t['hi'])}exit{ansi256(t['dim'])} (or "
                f"{ansi256(t['hi'])}deck{ansi256(t['dim'])}) to jack back into the dashboard\n"
                f"{ansi256(t['pri'])}{bar}\x1b[0m\n\n")
        self.foreground(cmd, pause=False, label="raw shell", banner=text)

    def cmd_open(self, args, rest):
        if not rest:
            return self.err("usage: open <path|url>")
        opener = shutil.which("xdg-open") or shutil.which("gio")
        if not opener:
            return self.err("no opener (xdg-open) available")
        target = os.path.expanduser(rest)
        if not re.match(r"^[a-z]+://", target) and not os.path.isabs(target):
            target = os.path.join(self.cwd, target)
        argv = [opener, target] if opener.endswith("xdg-open") else [opener, "open", target]
        self.spawn(argv, rest)

    def cmd_cd(self, args, rest):
        target = rest or HOME
        if target == "-":
            target = self.oldcwd
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(self.cwd, target)
        target = os.path.normpath(target)
        if os.path.isdir(target):
            self.oldcwd, self.cwd = self.cwd, target
            self.info(f"→ {tilde(target)}", "acc")
        else:
            self.err(f"no such sector: {rest}")

    def cmd_procs(self, args, rest):
        self.mode, self.ov = "procs", {"sel": 0, "top": 0, "sort": "cpu", "filter": rest}

    def cmd_kill(self, args, rest):
        if not args:
            return self.err("usage: kill <pid|name>")
        sig = signal.SIGTERM
        tgt = args[-1]
        if args[0] in ("-9", "-KILL", "-SIGKILL"):
            sig = signal.SIGKILL
        if tgt.isdigit():
            pid = int(tgt)
            name = next((p[6] for p in self.stats.procs if p[0] == pid), str(pid))
            return self.send_signal(pid, sig, name)
        me = self.user
        hits = [p for p in self.stats.procs if p[6] == tgt and p[1] == me]
        if not hits:
            return self.err(f"no process named '{tgt}' owned by {me}")

        def doit():
            for p in hits:
                self.send_signal(p[0], sig, p[6])

        self.ask(f"FLATLINE {len(hits)} x {tgt}?", doit)

    def cmd_scan(self, args, rest):
        st = self.stats
        st._ips()
        self.head("RECON SWEEP // LOCAL SUBNET")
        self.log([("  host    ", "dim"), (f"{self.host}", "hi"), ("   gateway ", "dim"),
                  (f"{st.gateway or '—'}", "acc"), (f" via {st.gw_iface or '—'}", "dim")])
        for n, a in st.ips:
            rr, tr = st.ifaces.get(n, (0, 0, 0, 0))[:2]
            self.log([("  iface   ", "dim"), (f"{n:<14}", "acc"), (f"{a:<20}", "txt"),
                      (f"▼{fmt_rate(rr):>10} ▲{fmt_rate(tr):>10}", "dim")])
        arp = read_arp()
        self.log([("  neighbours on the wire: ", "dim"), (str(len(arp)), "hi")])
        for ip, mac, dev in arp[:16]:
            self.log([("    ◆ ", "mag"), (f"{ip:<16}", "txt"), (f"{mac:<19}", "dim"), (dev, "dim")])
        listen, estab = read_sockets()
        ports = ", ".join(f"{p}" + ("" if a in ("0.0.0.0", "::") else f"@{a}") for a, p in listen[:30])
        self.log([("  open ports (listening): ", "dim"), (ports or "none - deck is dark", "warn" if listen else "ok")])
        remotes = {}
        for _l, _lp, rip, rp in estab:
            if rip.startswith("127.") or rip == "::1":
                continue
            remotes.setdefault(rip, set()).add(rp)
        self.log([("  live links: ", "dim"), (f"{len(estab)} established", "hi"),
                  (f" · {len(remotes)} remote hosts", "dim")])
        for rip, prts in list(remotes.items())[:12]:
            self.log([("    ⇄ ", "acc"), (f"{rip:<40}", "txt"), (",".join(str(p) for p in sorted(prts)), "dim")])
        self.log("sweep complete - signature masked", "ok", tag="RECON", tag_role="ok")
        self.glitch(0.15)

    def cmd_sysinfo(self, args, rest):
        st = self.stats
        u = os.uname()
        de = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "none"
        pkgs = readf("/var/lib/dpkg/status").count("Status: install ok installed")
        rows = [
            ("HANDLE", f"{self.user}@{self.host}"),
            ("OS", os_name()),
            ("KERNEL", f"{u.release} ({u.machine})"),
            ("CPU", f"{cpu_model()} x{st.ncpu}"),
            ("MEMORY", f"{fmt_bytes(st.mem['used'])} / {fmt_bytes(st.mem['total'])}"),
            ("UPTIME", fmt_dur(st.uptime)),
            ("SHELL", os.environ.get("SHELL", "?")),
            ("TERMINAL", f"{os.environ.get('TERM', '?')} · {self.W}x{self.H} · "
                         f"{'256' if self.c256 else '8'} colors"),
            ("DESKTOP", de),
            ("PACKAGES", f"{pkgs} dpkg" if pkgs else "?"),
            ("ARSENAL", f"{len(self.catalog.desktop)} apps · {len(self.catalog.bins)} binaries"
                        if self.catalog.ready else "indexing..."),
            ("STATUS", "OWNED BY ARASAKA → HIJACKED"),
        ]
        self.head("IDENTITY DOSSIER")
        for k, v in rows:
            self.log([(f"  {k:<10}", "pri"), ("░ ", "deep"), (v, "hi" if k in ("HANDLE", "STATUS") else "txt")])

    def cmd_theme(self, args, rest):
        names = all_themes(self.conf)
        if not args:
            self.head("SKINS  (theme <name> · theme save <name> · F8 to edit colors)")
            for n in names:
                mark = "▶" if n == self.pal.name else " "
                tag = "  custom" if n not in THEMES else ""
                self.log([(f"  {mark} {n}", "hi" if n == self.pal.name else "txt"), (tag, "dim")])
            return
        if args[0].lower() == "save":
            if len(args) < 2:
                return self.err("usage: theme save <name>")
            return self.save_theme(args[1])
        name = args[0]
        if name == "+":
            name = names[(names.index(self.pal.name) + 1) % len(names)] if self.pal.name in names else names[0]
        if name not in names:
            return self.err(f"unknown skin '{name}' - options: {', '.join(names)}")
        self.set_theme(name)
        self.ok(f"skin loaded: {name}")

    def set_theme(self, name):
        self.conf["theme"] = name
        save_conf(self.conf)
        self.pal.set(self.conf)
        self.scr.clear()
        self.glitch(0.4)

    def save_theme(self, name):
        name = re.sub(r"[^A-Za-z0-9_-]", "", name)[:24]
        if not name or name in THEMES:
            return self.err("pick a new name (letters, digits, - and _), not a built-in theme")
        base = self.conf["theme"]
        base = self.conf.get("themes", {}).get(base, {}).get("base", base) if base not in THEMES else base
        theme = {"base": base}
        theme.update({r: self.pal.colors[r] for r, _ in ROLES})
        self.conf.setdefault("themes", {})[name] = theme
        self.set_theme(name)
        self.ok(f"theme saved as '{name}' - it's in ~/.config/netdeck/config.json")

    def cmd_fx(self, args, rest):
        a = args[0].lower() if args else ""
        if a in ("scan", "scanlines"):
            self.conf["scan"] = not self.conf["scan"]
            self.ok(f"scanlines {'on' if self.conf['scan'] else 'off'}")
        elif a == "boot":
            self.conf["boot"] = not self.conf.get("boot", True)
            self.ok(f"boot sequence {'on' if self.conf['boot'] else 'off'}")
        elif a in ("on", "off"):
            self.conf["fx"] = a == "on"
            self.ok(f"effects {a}")
        else:
            self.conf["fx"] = not self.conf["fx"]
            self.ok(f"effects {'on' if self.conf['fx'] else 'off'}  (fx scan / fx boot for more)")
        save_conf(self.conf)

    def cmd_glitch(self, args, rest):
        self.glitch_until = time.time() + 0.8  # forced, even with fx off

    def cmd_rain(self, args, rest):
        self.pending = self.rain

    def cmd_memo(self, args, rest):
        if not rest:
            return self.err("usage: memo <text>")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SHARDS_FILE, "a") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{rest}\n")
            self.log([("shard encrypted & stored ▸ ", "txt"), (rest, "hi")], tag="VAULT", tag_role="mag")
        except OSError as e:
            self.err(f"vault write failed: {e}")

    def cmd_shards(self, args, rest):
        n = int(args[0]) if args and args[0].isdigit() else 15
        lines = [l for l in readf(SHARDS_FILE).splitlines() if l.strip()]
        self.head(f"DATA SHARDS // {len(lines)} in vault")
        if not lines:
            self.info("vault empty. write one: memo <text>", "dim")
        for l in lines[-n:]:
            ts, _, txt = l.partition("\t")
            self.log([("  ◆ ", "mag"), (f"{ts}  ", "dim"), (txt, "txt")])

    def cmd_history(self, args, rest):
        self.head("COMMAND HISTORY")
        for i, h in enumerate(self.history[-25:], start=max(1, len(self.history) - 24)):
            self.log([(f"  {i:>4}  ", "dim"), (h, "txt")])

    def cmd_clear(self, args, rest):
        self.console.clear()
        self.scroll = 0

    def cmd_update(self, args, rest):
        self.foreground("sudo apt update && sudo apt full-upgrade", shell=True, label="system patch")

    def cmd_lock(self, args, rest):
        if self.kiosk:
            return self.err("the NETDECK session has no screen locker yet - use `logout` when you step away")
        for argv in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"],
                     ["gnome-screensaver-command", "-l"]):
            if shutil.which(argv[0]):
                return self.spawn(argv, "session lock")
        self.err("no lock mechanism found")

    def _power(self, verb, label):
        if not shutil.which("systemctl"):
            return self.err("systemctl not available")
        self.ask(f"{label} THE MACHINE?", lambda: self.spawn(["systemctl", verb], f"systemctl {verb}"))

    def cmd_suspend(self, args, rest):
        self._power("suspend", "SUSPEND")

    def cmd_reboot(self, args, rest):
        self._power("reboot", "REBOOT")

    def cmd_poweroff(self, args, rest):
        self._power("poweroff", "POWER OFF")

    def cmd_quit(self, args, rest):
        if self.kiosk:
            return self.cmd_logout(args, rest)
        self.running = False

    def cmd_logout(self, args, rest):
        if self.kiosk:
            return self.ask("END THE NETDECK SESSION AND LOG OUT?", self._stop)
        sid = os.environ.get("XDG_SESSION_ID")
        if not sid or not shutil.which("loginctl"):
            return self.err("can't find your login session - use your desktop's log-out menu")
        self.ask("LOG OUT OF THE DESKTOP SESSION?",
                 lambda: self.spawn(["loginctl", "terminate-session", sid], "log out"))

    def _stop(self):
        self.running = False

    def cmd_relaunch(self, args, rest):
        if not os.environ.get("NETDECK_SESSION"):
            return self.err("relaunch works inside the NETDECK session or the app-menu launcher - "
                            "otherwise close and reopen your terminal to apply font changes")
        save_conf(self.conf)
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            open(os.path.join(CACHE_DIR, "relaunch"), "w").close()
        except OSError as e:
            return self.err(f"relaunch failed: {e}")
        self.exit_code = 75
        self.running = False

    # -- catalog installs
    def market_find(self, q):
        ql = q.lower()
        m = self.catalog.market
        for a in m:
            if ql in (a.key.lower(), a.name.lower(), a.bin):
                return a
        part = [a for a in m if ql in a.name.lower() or ql in a.key.lower()]
        return part[0] if len(part) == 1 else None

    def cmd_get(self, args, rest):
        if not rest:
            return self.err("usage: get <app>   - browse what's available with: apps (F2)")
        if not self.catalog.ready:
            return self.err("arsenal still indexing - try again in a second")
        a = self.market_find(rest)
        if not a:
            cands = [x for x in self.catalog.market if rest.lower() in (x.name + " " + x.comment).lower()]
            if cands:
                self.info("did you mean:", "warn")
                for x in cands[:10]:
                    self.log([("    ", "txt"), (f"get {x.key:<16}", "acc"), (x.comment, "dim")])
                return
            return self.err(f"'{rest}' isn't in the catalog - try `apps` and press / to search")
        if a.kind != "get":
            return self.ok(f"{a.name} is already installed - type {a.argv[0]} to run it")
        self.install_app(a)

    def install_app(self, a):
        script = install_script(a.inst, a.name)
        if not script:
            return self.err(f"no installer known for {a.name}")

        def go():
            self.foreground(["bash", "-c", script], label=f"installing {a.name}", pause=True)

            def reload():
                self.catalog.load()
                hit = self.market_find(a.key)
                if hit and hit.kind != "get":
                    self.notes.append(([("installed ▸ ", "txt"), (a.name, "hi"), ("  run it: ", "dim"),
                                        (" ".join(hit.argv), "acc")], "txt", "ARSENAL", "ok"))
                else:
                    self.notes.append((f"{a.name} doesn't seem to be on PATH yet - open a new shell or "
                                       "log out/in if it was installed with pipx or snap", "warn", "ARSENAL", "warn"))

            threading.Thread(target=reload, daemon=True).start()

        self.ask(f"INSTALL {a.name.upper()}?  via {install_summary(a.inst)}", go)

    # -- dock
    def cmd_pin(self, args, rest):
        items = list(self.dock_items())
        if not rest:
            return self.cmd_dock()
        if rest in items:
            return self.info(f"'{rest}' is already pinned", "dim")
        if len(items) >= 9:
            return self.err("dock is full (9) - unpin something first")
        items.append(rest)
        self.conf["dock"] = items
        save_conf(self.conf)
        self.ok(f"pinned '{rest}' to dock slot {len(items)}  (Alt+{len(items)})")

    def cmd_unpin(self, args, rest):
        items = list(self.dock_items())
        if rest.isdigit() and 1 <= int(rest) <= len(items):
            gone = items.pop(int(rest) - 1)
        elif rest in items:
            items.remove(rest)
            gone = rest
        else:
            return self.err("usage: unpin <slot number|command>")
        self.conf["dock"] = items
        save_conf(self.conf)
        self.ok(f"unpinned '{gone}'")

    def cmd_dock(self):
        self.head("DOCK  (Alt+number launches · pin <cmd> · unpin <n>)")
        for i, c in enumerate(self.dock_items(), 1):
            self.log([(f"  {i}  ", "acc"), (c, "txt")])

    # -- customization
    def cmd_settings(self, args, rest):
        self.mode, self.ov = "settings", {"sel": 1, "top": 0}

    def cmd_color(self, args, rest):
        roles = dict(ROLES)
        if not args:
            self.head(f"COLORS · theme {self.conf['theme']}  (color <role> <#hex|0-255> · color reset)")
            for r, lab in ROLES:
                n = self.pal.colors[r]
                self.log([(f"  {r:<5}", "acc"), (f"{n:>4}  {c256_to_hex(n)}  ", "txt"), (lab, "dim")])
            return
        if args[0] == "reset":
            self.conf.get("overrides", {}).pop(self.conf["theme"], None)
            self.pal.set(self.conf)
            save_conf(self.conf)
            return self.ok("colors reset to theme defaults")
        if len(args) < 2 or args[0] not in roles:
            return self.err("usage: color <role> <#hex|0-255>   roles: " + " ".join(roles))
        try:
            val = color_val(args[1])
        except ValueError:
            return self.err(f"'{args[1]}' isn't a color - use #rrggbb or 0-255")
        self.set_color(args[0], val)
        save_conf(self.conf)
        self.ok(f"{args[0]} → {val} ({c256_to_hex(val)})")

    def set_color(self, role, val):
        th = self.conf["theme"]
        if th in self.conf.get("themes", {}):
            self.conf["themes"][th][role] = val
        else:
            self.conf.setdefault("overrides", {}).setdefault(th, {})[role] = val
        self.pal.set(self.conf)

    def cmd_font(self, args, rest):
        if not args:
            self.head("FONT")
            self.info(f"family {self.conf.get('font') or '(terminal default)'} · size {self.conf.get('font_size', 13)}")
            self.info("set with: font <family> [size]  ·  list fonts: fonts  ·  apply: relaunch", "dim")
            return
        size = None
        if args[-1].isdigit():
            size = int(args.pop())
        if args:
            self.conf["font"] = " ".join(args)
        if size:
            self.conf["font_size"] = max(6, min(40, size))
        save_conf(self.conf)
        self.ok(f"font: {self.conf.get('font')} {self.conf.get('font_size')}pt - type `relaunch` to apply")

    def cmd_fonts(self, args, rest):
        fonts = self.mono_fonts()
        self.head(f"MONOSPACE FONTS · {len(fonts)} installed")
        if not fonts:
            self.info("none found (fc-list missing?) - try: sudo apt install fonts-jetbrains-mono", "dim")
        for f in fonts:
            mark = "▶ " if f == self.conf.get("font") else "  "
            self.log([("  " + mark, "acc"), (f, "hi" if mark.strip() else "txt")])
        self.info("more fonts: sudo apt install fonts-jetbrains-mono fonts-firacode fonts-hack fonts-ibm-plex", "dim")

    def toggle_panel(self, name, on=None):
        lay = self.conf["layout"]
        present = any(name in lay[c] for c in ("left", "right"))
        if on is None:
            on = not present
        if not on:
            for c in ("left", "right"):
                if name in lay[c]:
                    lay[c].remove(name)
        elif not present:
            col = PANEL_HOME[name]
            order = ["sys", "mem", "disk", "net", "bio", "stream", "procs"] if col == "left" else \
                ["neural", "dock", "procs", "console"]
            lst = lay[col]
            idx = len(lst)
            for i, p in enumerate(lst):
                if p in order and name in order and order.index(p) > order.index(name):
                    idx = i
                    break
            lst.insert(idx, name)
        save_conf(self.conf)
        return on

    def cmd_panel(self, args, rest):
        if not args:
            self.head("PANELS  (panel <name> on|off · F8 for the full editor)")
            lay = self.conf["layout"]
            for p, lab in PANELS.items():
                where = "left" if p in lay["left"] else ("right" if p in lay["right"] else "off")
                self.log([(f"  {p:<8}", "acc"), (f"{where:<6}", "ok" if where != "off" else "deep"), (lab, "dim")])
            return
        name = args[0].lower()
        if name not in PANELS:
            return self.err("unknown panel - options: " + " ".join(PANELS))
        on = None if len(args) < 2 else args[1].lower() in ("on", "show", "1", "yes")
        self.ok(f"panel {name} {'on' if self.toggle_panel(name, on) else 'off'}")

    # -- hardware shortcuts
    def cmd_wifi(self, args, rest):
        if not shutil.which("nmtui"):
            return self.err("nmtui not found - get it with: get nmtui")
        self.foreground(["nmtui"], pause=False, label="network")

    def cmd_audio(self, args, rest):
        for prog in ("pulsemixer", "alsamixer"):
            if shutil.which(prog):
                return self.foreground([prog], pause=False, label="audio")
        self.err("no mixer found - get one with: get pulsemixer")

    def cmd_bright(self, args, rest):
        if not shutil.which("brightnessctl"):
            return self.err("brightnessctl not found - sudo apt install brightnessctl")
        if not args:
            return self.exec_capture("brightnessctl -m | cut -d, -f4")
        val = args[0].rstrip("%")
        if not val.lstrip("+-").isdigit():
            return self.err("usage: bright <percent>   e.g. bright 60")
        num = val.lstrip("+-")
        arg = f"+{num}%" if args[0].startswith("+") else (f"{num}%-" if args[0].startswith("-") else f"{num}%")
        self.exec_capture(f"brightnessctl set {arg} >/dev/null && brightnessctl -m | cut -d, -f4")

    # ---------------------------------------------------------------- full-screen scenes
    def wait(self, sec):
        """Sleep while watching for a keypress. Returns True if skipped."""
        end = time.time() + sec
        while True:
            left = end - time.time()
            if left <= 0:
                return False
            self.scr.timeout(max(1, int(min(left, 0.05) * 1000)))
            try:
                k = self.scr.get_wch()
            except curses.error:
                continue
            if k == curses.KEY_RESIZE:
                self.resize()
                continue
            return True

    def clear_bg(self):
        for y in range(self.H):
            self.fill(y, 0, self.W)

    def boot(self):
        H, W = self.H, self.W
        if W < 60 or H < 20:
            return
        fast = self.args.fast
        sp = 0.35 if fast else 1.0
        # CRT power-on: a line blooming into a screen
        cy = H // 2
        for i in range(1, 9):
            self.scr.erase()
            for y in range(H):
                self.put(y, 0, " " * W, self.pal("txt", "bg"))
            half = int(W / 2 * i / 8)
            self.put(cy, W // 2 - half, "━" * (half * 2), self.pal("acc", "bg", True))
            self.scr.refresh()
            if self.wait(0.018 * sp):
                return
        for i in range(1, 6):
            hh = int(H / 2 * i / 5)
            for y in range(cy - hh, cy + hh):
                self.put(y, 0, "░" * W if i < 5 else " " * W, self.pal("dim", "bg"))
            self.scr.refresh()
            if self.wait(0.02 * sp):
                return
        # BIOS
        self.scr.erase()
        self.clear_bg()
        st = self.stats
        y = 1
        hdr = "ARASAKA CORPORATION  //  SECURE FIRMWARE v7.77.2077  //  CLASSIFIED: BLACK"
        self.put(y, 2, hdr[: W - 4], self.c("pri", y, True))
        self.put(y + 1, 2, ("━" * len(hdr))[: W - 4], self.c("dim", y + 1))
        self.scr.refresh()
        y += 3
        total_kb = st.mem["total"] // 1024
        for i in range(0, 21):
            v = total_kb * i // 20
            self.put(y, 2, f"MEMORY TEST : {v:>12,} KB", self.c("txt", y))
            self.scr.refresh()
            if self.wait(0.02 * sp):
                return
        self.put(y, 32, " OK", self.c("ok", y, True))
        y += 1
        checks = [
            (f"CPU         : {cpu_model()[:48]} x{st.ncpu}", "OK", "ok"),
            (f"KERNEL      : {os.uname().release}", "OK", "ok"),
            ("NEURAL PORT : interface bus 0x7F", "DETECTED", "acc"),
            ("OPTICS      : retinal overlay driver", "OK", "ok"),
            ("ICE LAYER 1 : perimeter firewall", "ACTIVE", "warn"),
            ("ICE LAYER 2 : black ICE sentinel", "ACTIVE", "warn"),
            ("TELEMETRY   : corp beacon -> arasaka.subnet07", "ONLINE", "warn"),
            ("OWNER       : ARASAKA CORP. ASSET #77-0451", "LOCKED", "bad"),
        ]
        for text, res, role in checks:
            self.put(y, 2, text[: W - 20], self.c("txt", y))
            self.scr.refresh()
            if self.wait(0.07 * sp):
                return
            self.put(y, min(W - 14, 60), f"[ {res} ]", self.c(role, y, True))
            y += 1
        self.scr.refresh()
        if self.wait(0.3 * sp):
            return
        # intrusion
        y += 1
        for i in range(6):
            msg = " !! UNAUTHORIZED NEURAL HANDSHAKE DETECTED !! "
            self.put(y, 2, msg, self.inv("bad") if i % 2 == 0 else self.c("bad", y, True))
            self.scr.refresh()
            if self.wait(0.09 * sp):
                return
        y += 2
        steps = [
            "injecting daemon GHOSTKEY.EXE into firmware",
            "spoofing biometric owner hash",
            "suffocating ICE layer 1 + 2",
            "blackholing corp telemetry beacon",
            "rewriting asset ownership record",
            "routing uplink through 7-hop proxy chain",
        ]
        bw = 24
        hexx = min(W - 22, 72)
        for s in steps:
            if y >= H - 3:
                break
            self.put(y, 2, "> ", self.c("pri", y, True))
            bx = min(50, hexx - bw - 6)
            self.put(y, 4, f"{s:<44}"[: bx - 6], self.c("txt", y))
            for j in range(bw + 1):
                self.put(y, bx, "[", self.c("dim", y))
                self.bar(y, bx + 1, bw, j / bw * 100, "acc")
                self.put(y, bx + bw + 1, "]", self.c("dim", y))
                # hex rain on the right
                for hy in range(3, H - 1):
                    if random.random() < 0.3:
                        self.put(hy, hexx + 2, " ".join(f"{random.randrange(256):02X}" for _ in range((W - hexx - 3) // 3)),
                                 self.c(random.choice(["deep", "dim", "deep", "pri"]), hy))
                self.scr.refresh()
                if self.wait(0.012 * sp):
                    return
            self.put(y, bx + bw + 3, "DONE", self.c("ok", y, True))
            y += 1
        if y < H - 2:
            self.put(y + 1, 2, "ICE STATUS: FLATLINED.   OWNERSHIP: TRANSFERRED.", self.c("hi", y + 1, True))
        self.scr.refresh()
        if self.wait(0.5 * sp):
            return
        # logo decode
        self.logo_reveal(sp)

    def logo_reveal(self, sp=1.0):
        H, W = self.H, self.W
        lw = len(LOGO[0])
        big = W >= lw + 4 and H >= 16
        lines = LOGO if big else ["N E T D E C K"]
        lx = (W - len(lines[0])) // 2
        ly = H // 2 - len(lines) // 2 - 2
        frames = 22
        for f in range(frames + 1):
            self.scr.erase()
            self.clear_bg()
            keep = f / frames
            for i, line in enumerate(lines):
                y = ly + i
                for j, ch in enumerate(line):
                    if ch == " ":
                        continue
                    if random.random() > keep:
                        self.put(y, lx + j + random.choice((0, 0, 0, 1, -1)), random.choice(GLITCH + KATA),
                                 self.c(random.choice(["pri", "acc", "mag", "deep"]), y))
                    else:
                        role = "pri" if ch == "█" else "deep" if big else "pri"
                        self.put(y, lx + j, ch, self.c(role, y, ch == "█"))
            self.scr.refresh()
            if self.wait(0.035 * sp):
                return
        sub1 = "NODE HIJACKED  ·  ASSET #77-0451  ·  OWNERSHIP TRANSFERRED"
        sub2 = f"welcome back, {self.user}. the net is yours."
        y = ly + len(lines) + 1
        self.put(y, (W - len(sub1)) // 2, "", 0)
        for i in range(len(sub1) + 1):
            self.put(y, (W - len(sub1)) // 2, sub1[:i], self.c("acc", y, True))
            self.scr.refresh()
            if self.wait(0.008 * sp):
                return
        self.put(y + 2, (W - len(sub2)) // 2, sub2, self.c("hi", y + 2))
        tag = f"NETDECK//OS v{VERSION}"
        self.put(y + 4, (W - len(tag)) // 2, tag, self.c("dim", y + 4))
        self.scr.refresh()
        if self.wait(1.1 * sp):
            return
        # tear-away
        for _ in range(5):
            for _k in range(12):
                yy = random.randrange(H)
                try:
                    self.scr.chgat(yy, 0, W, self.pal(random.choice(["pri", "acc", "mag"]), "bg", True, True))
                except curses.error:
                    pass
            self.scr.refresh()
            if self.wait(0.03 * sp):
                return

    def rain(self):
        H, W = self.H, self.W
        drops = [[random.uniform(-H, 0), random.uniform(0.35, 1.3), random.randint(4, max(5, H // 2))]
                 for _ in range(W)]
        cells = {}
        msg = " NETDECK // IDLE  ·  any key to wake "
        self.scr.timeout(45)
        while True:
            self.scr.erase()
            for y in range(H):
                self.put(y, 0, " " * W, self.pal("txt", "bg"))
            for x, d in enumerate(drops):
                if x % 2:
                    continue
                d[0] += d[1]
                head = int(d[0])
                for t in range(d[2]):
                    y = head - t
                    if 0 <= y < H:
                        key = (x, y)
                        if key not in cells or random.random() < 0.06:
                            cells[key] = random.choice(RAIN_GLYPHS)
                        role = "hi" if t == 0 else ("acc" if t < 3 else ("pri" if t < d[2] // 2 else "deep"))
                        self.put(y, x, cells[key], self.pal(role, "bg", t < 3))
                if head - d[2] > H:
                    d[0] = random.uniform(-H // 2, 0)
                    d[1] = random.uniform(0.35, 1.3)
            my = H // 2
            self.put(my, (W - len(msg)) // 2, msg, self.pal("bg", "pri", True))
            self.put(my + 1, (W - len(msg)) // 2, time.strftime("%H:%M:%S").center(len(msg)), self.pal("pri", "bg", True))
            self.scr.refresh()
            try:
                k = self.scr.get_wch()
                if k == curses.KEY_RESIZE:
                    self.resize()
                    H, W = self.H, self.W
                    drops = [[random.uniform(-H, 0), random.uniform(0.35, 1.3), random.randint(4, max(5, H // 2))]
                             for _ in range(W)]
                    continue
                break
            except curses.error:
                pass
        self.scr.clear()
        self.glitch(0.3)

    def jack_out(self):
        H, W = self.H, self.W
        if not self.conf["fx"]:
            return
        self.glitch_until = 0
        for _ in range(3):
            self.apply_glitch(1.0)
            self.scr.refresh()
            time.sleep(0.04)
        cy = H // 2
        steps = 8
        for i in range(1, steps + 1):
            cut = int(cy * i / steps)
            for y in list(range(0, cut)) + list(range(H - cut, H)):
                self.put(y, 0, " " * W, self.pal("txt", "bg"))
            self.scr.refresh()
            time.sleep(0.022)
        for i in range(steps, 0, -1):
            for y in range(H):
                self.put(y, 0, " " * W, self.pal("txt", "bg"))
            half = int(W / 2 * i / steps)
            self.put(cy, W // 2 - half, "━" * (2 * half), self.pal("hi", "bg", True))
            self.scr.refresh()
            time.sleep(0.02)
        self.put(cy, W // 2, "•", self.pal("hi", "bg", True))
        self.scr.refresh()
        time.sleep(0.15)
        self.scr.erase()
        self.scr.refresh()

    # ---------------------------------------------------------------- main loop
    def run(self):
        if self.conf.get("boot", True) and not self.args.no_boot:
            self.boot()
        self.scr.clear()
        self.log([("NETDECK//OS ", "pri"), (f"v{VERSION} ", "dim"), ("online. node hijacked, ", "txt"),
                  ("corp ICE flatlined.", "ok")], tag="SYSTEM", tag_role="pri")
        self.log([("type ", "dim"), ("help", "hi"), (" for the codex · ", "dim"), ("apps", "hi"),
                  (" (F2) to browse your arsenal · ", "dim"), ("shell", "hi"), (" (F4) for a raw link", "dim")],
                 tag="SYSTEM", tag_role="pri")
        if not self.c256:
            self.log("terminal reports <256 colors - running in degraded palette (try TERM=xterm-256color)",
                     "warn", tag="WARN", tag_role="warn")
        self.scr.timeout(70)
        while self.running:
            self.now = time.time()
            if self.now - self.last_stat >= 1.0:
                self.stats.update()
                self.last_stat = self.now
                self.alerts()
                self.reap()
                if self.catalog.ready and not self.catalog_announced:
                    self.catalog_announced = True
                    c = self.catalog
                    self.log([("arsenal indexed ▸ ", "txt"), (f"{len(c.desktop)} desktop apps", "hi"),
                              (" · ", "dim"), (f"{len(c.bins)} binaries", "hi"),
                              (f" in {len(c.cats)} categories", "dim")], tag="ARSENAL", tag_role="acc")
            self.drain_jobs()
            while self.notes:
                self.log(*self.notes.popleft())
            self.ambient(self.now)
            self.scr.erase()
            self.draw()
            self.scr.refresh()
            if self.pending:
                fn, self.pending = self.pending, None
                fn()
                self.scr.timeout(70)
                continue
            try:
                k = self.scr.get_wch()
            except curses.error:
                continue
            except KeyboardInterrupt:
                k = "\x03"
            self.handle_key(k)
            # swallow a burst of keys (paste) quickly
            self.scr.timeout(0)
            for _ in range(256):
                try:
                    k = self.scr.get_wch()
                except curses.error:
                    break
                self.handle_key(k)
                if self.pending or not self.running:
                    break
            self.scr.timeout(70)
        if self.job:
            self.kill_job()
        save_conf(self.conf)
        self.jack_out()
        return self.exit_code


# --------------------------------------------------------------------------------------------
#  Entrypoints
# --------------------------------------------------------------------------------------------


def term_opts(term, conf):
    """Terminal options that apply the deck's font and background (used by netdeck-session)."""
    cols = resolve_theme(conf)
    bg, fg = c256_to_hex(cols["bg"]), c256_to_hex(cols["txt"])
    font = (conf.get("font") or "").strip()
    try:
        size = max(6, min(40, int(conf.get("font_size", 13))))
    except (TypeError, ValueError):
        size = 13
    if term == "foot":
        return ["-o", f"font={font or 'monospace'}:size={size}", "-o", f"colors.background={bg[1:]}",
                "-o", f"colors.foreground={fg[1:]}", "-o", "pad=0x0"]
    if term == "kitty":
        o = ["-o", f"font_size={size}", "-o", f"background={bg}", "-o", f"foreground={fg}",
             "-o", "window_padding_width=0", "-o", "hide_window_decorations=yes", "-o", "confirm_os_window_close=0"]
        return o + (["-o", f"font_family={font}"] if font else [])
    if term == "alacritty":
        o = ["-o", f"font.size={size}", "-o", f'colors.primary.background="{bg}"',
             "-o", f'colors.primary.foreground="{fg}"', "-o", "window.padding.x=0", "-o", "window.padding.y=0",
             "-o", 'window.decorations="None"']
        return o + (["-o", f'font.normal.family="{font}"'] if font else [])
    return []


def list_apps_text():
    cat = Catalog()
    cat.load()
    t = THEMES["netrunner"]
    tty = sys.stdout.isatty()

    def col(n, s):
        return f"{ansi256(n)}{s}\x1b[0m" if tty else s

    for title, desc, apps in cat.cats:
        if title.startswith("PATH"):
            print(col(t["pri"], f"\n◢ {title}") + col(t["dim"], f"  // {desc}: {len(apps)} binaries (omitted)"))
            continue
        print(col(t["pri"], f"\n◢ {title}") + col(t["dim"], f"  // {desc} [{len(apps)}]"))
        for a in apps:
            print(f"   {col(t['acc'], f'{a.name[:34]:<34}')} {col(t['dim'], a.kind.upper())}  {a.comment[:70]}")


def main():
    ap = argparse.ArgumentParser(description="NETDECK//OS - cyberpunk terminal dashboard")
    ap.add_argument("--no-boot", action="store_true", help="skip the boot sequence")
    ap.add_argument("--fast", action="store_true", help="fast boot sequence")
    ap.add_argument("--no-fx", action="store_true", help="disable glitches and animations")
    ap.add_argument("--theme", help="color theme: " + ", ".join(THEMES) + " or a custom one")
    ap.add_argument("--term-opts", metavar="TERMINAL", help=argparse.SUPPRESS)
    ap.add_argument("--list-apps", action="store_true", help="print the categorized program list and exit")
    ap.add_argument("--version", action="version", version=f"NETDECK//OS {VERSION}")
    args = ap.parse_args()

    if args.list_apps:
        list_apps_text()
        return
    if args.term_opts:
        print("\n".join(term_opts(args.term_opts, load_conf())))
        return
    if not sys.platform.startswith("linux"):
        print("NETDECK//OS reads /proc - Linux only.")
        sys.exit(1)
    if not sys.stdout.isatty():
        print("NETDECK//OS needs an interactive terminal.")
        sys.exit(1)
    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")
    if os.environ.get("TERM", "") in ("xterm", "") and os.environ.get("COLORTERM"):
        os.environ["TERM"] = "xterm-256color"

    result = {"code": 0}

    def _run(scr):
        result["code"] = Deck(scr, args).run()

    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
    if result["code"] == 75:  # relaunching the terminal window
        sys.exit(75)
    sys.stdout.write("\x1b[0m")
    t = resolve_theme(load_conf())
    print(f"{ansi256(t['pri'])}◢ NETDECK{ansi256(t['dim'])} // jacked out. stay frosty, choom.\x1b[0m")
    sys.exit(result["code"] or 0)


if __name__ == "__main__":
    main()
