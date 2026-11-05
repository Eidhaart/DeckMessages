# NETDECK//OS

A cyberpunk deck that takes over your whole Ubuntu screen, styled like a corp machine that was hijacked and rebuilt
for a netrunner. It isn't a window on your desktop. It can **be** the session: you log in, and the deck boots.

![NETDECK//OS dashboard](screenshot.png)

The deck itself is one Python file with no dependencies, using Python 3 and curses. It reads live telemetry from
`/proc` and `/sys`.

## Install

```bash
git clone https://github.com/Eidhaart/DeckMessages.git netdeck
cd netdeck
./install.sh --session
```

`--session` adds **NETDECK//OS** to the Ubuntu login screen. It installs
[`cage`](https://github.com/cage-kiosk/cage) (a tiny kiosk display server), the `foot` terminal and the JetBrains Mono
font if they're missing, which needs sudo once.

**One-time setup:** log out, click your name, click the **gear icon** in the bottom right, pick **NETDECK//OS**, and
log in. Ubuntu remembers that choice. From then on there's no desktop, no panel and no delay: the screen goes from
login straight into the deck's boot sequence.

- **No password at boot:** Settings → System → Users → **Automatic Login**. Power on, and the deck boots.
- **Back to normal Ubuntu:** F10 logs out. Pick "Ubuntu" with the gear icon.
- **Opening graphical apps:** apps like Firefox open fullscreen on top of the deck. Close them to return.
- **Emergency exit:** Ctrl+Alt+F3 switches to a text console.

### Other ways to run it

| Command | What you get |
|---|---|
| `./install.sh` | the `netdeck` command plus an app-menu entry that opens it fullscreen |
| `./install.sh --login` | opens the deck fullscreen on top of your normal desktop at login |
| `./install.sh --every-terminal` | opens the deck in every new terminal window |
| `./install.sh --uninstall` | removes everything, including the login session |
| `python3 netdeck.py` | run it once without installing |

## Make it yours (F8)

Press **F8** (or type `settings`) for the tuning screen, with a live preview:

- **Themes:** `netrunner`, `arasaka`, `netwatch`, `toxic`, `afterlife`, `amber`, plus any you save yourself.
- **Every color:** 12 roles (frames, highlights, text, background, scanlines, alerts…). Step with ←/→ or type a
  `#hex` value or a 0–255 number. **Save as new theme** keeps your mix.
- **Font family and size:** cycle through your installed monospace fonts. The NETDECK session and the app-menu
  launcher apply them to the terminal, and **Apply font now** restarts the window instantly.
- **Effects:** glitches, scanlines, boot sequence, news ticker, and the small neural-link readout in the top bar.
- **Panels:** turn any panel on or off, including CPU, memory, storage, network, vitals, processes, dock and console,
  plus the optional big neural-link and datastream panels.

The same things work as commands: `theme save mine`, `color pri #ff2a6d`, `font "Fira Code" 14`, `fonts`,
`panel neural on`, `relaunch`. Everything is saved to `~/.config/netdeck/config.json`, which you can also edit by hand.
`layout` controls which panels go in which column and in what order:

```json
"layout": {"left": ["sys", "mem", "disk", "net", "bio", "procs"], "right": ["dock", "console"]}
```

To force a particular terminal for the session, put `NETDECK_TERMINAL="kitty --start-as=fullscreen"` in
`~/.config/netdeck/session.conf`.

## The dock

Pin up to 9 commands and launch them with **Alt+1 … Alt+9**: `pin nvim`, `pin gh dash`, `pin firefox`, `unpin 3`.
On first run it fills itself with whatever good tools you already have.

## Arsenal (F2): every program, plus the black market

`apps` lists everything on the machine by category. It covers every desktop app, plus a curated catalog of about 140
**terminal apps**. You can install the ones you don't have yet right from the list: select one and press **Enter** or
**i**, or type `get <name>`. Installs try apt first, then snap, pipx or the project's official installer.
Press **m** to hide what isn't installed.

| Category | Highlights |
|---|---|
| CODE // IDE & EDITORS | **Neovim**, **LazyVim** (Neovim set up like VS Code), **Helix**, **Micro**, **Claude Code**, Codex CLI, Gemini CLI, Aider, Vim, Emacs |
| GIT // GITHUB | **lazygit**, **GitHub CLI** (`gh`), **gh-dash** (your PRs and issues dashboard), gitui, tig, delta, lazydocker |
| FILES // NAVIGATION | Yazi, ranger, Midnight Commander, nnn, ncdu, fzf, glow, ripgrep, fd, bat, eza, zoxide |
| SYSTEM // CONTROL | btop, htop, nmtui (Wi-Fi), pulsemixer, Zellij, tmux, glances, nvtop, powertop |
| NET // COMMS | w3m, aerc, neomutt, newsboat, WeeChat, termshark, trippy, mtr, nethogs |
| MEDIA // SYNTH | ncspot (Spotify), cmus, mpv, cava |
| DATA // DEV TOOLS | Harlequin (SQL IDE), Posting (API client), VisiData, sc-im, HTTPie, pgcli |
| PRODUCTIVITY · SIM // ARCADE | calcurse, Taskwarrior, tty-clock · cbonsai, bastet, nsnake, ninvaders, moon-buggy |

You can type any program name directly. Terminal apps take over the screen and give it back when they exit, graphical
apps open separately, and quick commands like `ls`, `git status` or `ping` stream their output into the console.

## Commands

**Tab** completes commands, programs, apps and paths. **↑/↓** walks your history.

| Command | What it does |
|---|---|
| `apps` / **F2** · `get <app>` | browse and launch everything · install from the catalog |
| `run <prog>` · `spawn <cmd>` · `!<cmd>` | launch (foreground) · launch detached · run a shell command into the console |
| `shell` / **F4** | your real shell with a themed prompt. `exit` comes back |
| `pin` · `unpin` | manage the dock (Alt+1-9) |
| `settings` / **F8** · `theme` / **F9** · `color` · `font` · `fonts` · `panel` · `relaunch` | customization |
| `wifi` · `audio` · `bright <n>` | network settings, volume mixer, screen brightness |
| `procs` / **F3** · `kill <pid\|name>` | process manager (sort, filter, kill) |
| `scan` / **F5** · `sysinfo` / **F7** | network recon · hardware and identity dossier |
| `open <path\|url>` · `cd <dir>` | default-app open · change the deck's working directory |
| `memo` · `shards` · `history` · `clear` · `rain` (**F6**) · `glitch` | notes, history, screensaver, effects |
| `update` · `lock` · `suspend` · `reboot` · `poweroff` · `logout` | system and power control (with confirmations) |
| `quit` / **F10** | jack out (in the NETDECK session: log out) |

Other keys: **PgUp/PgDn** scroll the console, **Ctrl+C** kills a running command, **Ctrl+L** clears the console.
