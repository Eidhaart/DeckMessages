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
log in. From then on there's no desktop, no panel and no delay: the screen goes from login straight into the
deck's boot sequence. `--session` also removes any older autostart, so the deck never pops up inside Ubuntu.

### Switching between the deck and Ubuntu

| From | How |
|---|---|
| the deck | **F10** → **U** (Ubuntu desktop), or type `ubuntu` |
| Ubuntu | open **Jack into NETDECK** from the app menu (pin it to the dock), or run `netdeck-switch deck` |
| any terminal | `netdeck-switch deck` / `netdeck-switch ubuntu` |

After you confirm, you're logged straight into the other session with no password. The switch sets the session the
login screen remembers, turns on automatic login for that one restart, and restarts the login screen. Automatic login
turns itself off again about a minute later, and again at every login. If your machine doesn't auto-login, you land on
the login screen with the right session already selected. Apps open in the session you leave are closed, so save
your work first.

This uses a small root helper, `/usr/local/sbin/netdeck-switch-root`, which does only this. A sudo rule in
`/etc/sudoers.d/netdeck` lets your user run it without a password. `./install.sh --uninstall` removes both.

- **No password at boot:** Settings → System → Users → **Automatic Login**. Power on, and the deck boots.
- **Multiple monitors:** in the NETDECK session the deck uses only the laptop's built-in screen, and other monitors
  are switched off for that session. Your Ubuntu session keeps its own monitor setup. To use a different screen, put
  `NETDECK_OUTPUT="HDMI-A-1"` in `~/.config/netdeck/session.conf` (`wlr-randr` in the deck's shell lists the names).
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

## Live news (F6)

The ticker and the **NEWSFEED 報道** panel show real headlines, alternating Swedish and world news:

| Sverige | World |
|---|---|
| SVT Nyheter, Ekot (Sveriges Radio), DN, Aftonbladet, Expressen | BBC World, The Guardian, Al Jazeera |

Press **F6** (or type `news`) for the reader. It has tabs for all, Sweden and world, and shows a summary of the selected
story. **Enter** downloads the article and shows the full text inside the deck, **o** opens it in your browser, and
**r** refreshes. Feeds refresh every 15 minutes in the background, and new headlines pop up as a toast. The last
fetch is cached, so headlines appear instantly at boot and work offline.

Change the sources with `news sources`, `news add <rss url> [se|world] [name]`, `news rm <n>` and `news reset`.
Settings (F8) turns live news off. If you've customized your layout, add the panel with `panel news on`.

## Streaming and YouTube

| Command | What it does |
|---|---|
| `netflix` · `prime` · `disney` · `svtplay` | opens the service in a fullscreen browser app window |
| `stream` | opens the **STREAM // MEDIA** menu (also in the arsenal, F2) |
| `yt <search>` | YouTube inside the deck: search, then **Enter** plays in a window, **a** plays audio only with terminal controls, **t** plays the video in the terminal itself, **o** opens it in the browser |

- **Browser:** Netflix, Prime and Disney+ are web-only on Linux. Chrome, Chromium and Brave include the DRM they need,
  so the deck uses one of those if installed. Firefox works too after you allow DRM when it asks. In the NETDECK
  session the window covers the deck; close it (Ctrl+W) to return.
- **YouTube** needs `yt-dlp` and `mpv`. Press **i** in the YouTube screen to install whichever is missing. A fresh
  `yt-dlp` comes from pipx, because older apt versions stop working with YouTube.
- **In-terminal playback (t)** uses real images in kitty and foot (sixel), and colored blocks elsewhere.
- **Pin** any of them to the dock: `pin netflix`, `pin yt`.

## Music in the background

```
▌ ♪ Nightride FM // 音楽                    ▅▃▇▂▆  ▶
▌ Le Groupe Fantastique — Counterfeit
▌ ● LIVE  4:12   alt+p pause · alt+n next · alt+x stop
```

A small **NOW PLAYING** rectangle sits in the bottom-right corner whenever something plays. It shows the station or
player, the artist and title, and a progress bar, or `● LIVE` for radio. The deck stays fully usable underneath.

- **`music`** opens the station picker. All stations are free and need no account:
  - **Nightride FM:** Nightride, Chillsynth, Darksynth, Datawave, Spacesynth
  - **SomaFM:** DEF CON Radio, Synphaera, Vaporwaves, Groove Salad, Drone Zone
  - **Sveriges Radio:** P1, P2, P3
  - `music darksynth` tunes in directly.
- **Spotify:** `spotify` opens the desktop app (`sudo snap install spotify`) or the web player. Its track shows in
  the rectangle too, as does audio from any other app or browser tab, once `playerctl` is installed
  (`get playerctl`).
- **YouTube:** in the YouTube screen, **b** plays a video's audio in the background.
- **Controls:**
  - **Alt+P** play/pause · **Alt+N** next · **Alt+B** back · **Alt+X** stop. For radio, next and back hop between
    stations.
  - Typed: `play`, `next`, `prev`, `stop`, `vol +10`.
- **Keeps playing:** background music continues when you leave the deck, and the rectangle picks it up again next
  time. Settings (F8) can hide the rectangle. Radio and YouTube audio need `mpv` (`get mpv`).

## nightdeck (the Raspberry Pi)

```bash
nightdeck            # from zsh, or type it in the deck
```

This plays a jack-in sequence while it really probes the Pi: it looks up `nightdeck.local` on your network,
measures latency, checks the SSH port and shows the Pi's host-key fingerprint (KNOWN, or NEW on first contact). Then
it runs `ssh deck@nightdeck.local`. When you leave, it prints the session length. If the Pi isn't answering, it says
so instead of hanging.

`nightdeck htop` runs a command on the Pi, `nightdeck --quick` skips the show, and any key skips it mid-way.
`nightdeck --force` connects even if the probes fail. To use a different host, user or port, put
`NIGHTDECK_HOST=...`, `NIGHTDECK_USER=...` or `NIGHTDECK_PORT=...` in `~/.config/netdeck/session.conf`.
For login without a password: `ssh-copy-id deck@nightdeck.local` (once).

## Cyberpunk zsh (oh-my-zsh)

`zsh/` styles your everyday terminal to match the deck: oh-my-zsh, a two-line HUD prompt, and themed syntax
highlighting, autosuggestions and fzf.

```bash
./zsh/install-zsh.sh            # zsh, oh-my-zsh, plugins, the netrunner theme  (--default also makes zsh your shell)
```

```
◢ NETDECK // you@laptop // zsh 5.9 // 05.11.2026 18:49 // link stable
┏━ ◢ you@laptop // ~/projects/netdeck  ⎇ main ●
┗━▶ git status                                                     ✗ 1 · 4s · 18:49:35
```

- **Colors follow the deck's skin** automatically. `deckskin sodium` switches the current shell, and `deckskin sync`
  follows the deck again. Truecolor where the terminal supports it.
- **The prompt shows:** your user (red when you're root), the folder, the git branch (● for uncommitted changes),
  `⇄ ssh` over SSH, and `deck link` inside the deck's shell. On the right: the exit code when a command fails, how
  long slow commands took, and the time.
- **Plugins:** autosuggestions, syntax highlighting, history substring search (type, then ↑), git, sudo (Esc Esc),
  extract, colored man pages, fzf and zoxide when installed.
- **`jackin`:** takes you from Ubuntu into the NETDECK session. It asks once (apps open in Ubuntu will close), plays
  a full-screen jack-in sequence in your skin's colors (handshake, ICE bypass, synapse sync, glitching countdown),
  then switches sessions. `jackin --here` opens the deck inside the current terminal instead, `--quick` skips the
  show, and any key skips it mid-way.
- **Shortcuts:** `deck`, `skin`, and `ls`/`ll`/`tree` through eza when it's installed.
- Your old `~/.zshrc` is saved as `~/.zshrc.pre-netdeck` (`--undo` restores it). Put your own lines in
  `~/.zshrc.local`, which future updates never overwrite.

## Make it yours (F8)

Press **F8** (or type `settings`) for the tuning screen, with a live preview:

- **18 themes**, built on the palettes from RunDeck and SixthDeck:
  - `netrunner` (default): midnight blue-black, red structure, cyan data, yellow alerts
  - `arasaka`: blood-black, corp red, chrome white
  - `sodium`, `matrix`, `neon`, `blackout`, `chrome`, `ronin`, `blood`, `ghost`, `astral`, `resonance`, `hazard`,
    `noir`, `spraypaint`, `jade`, `rust`, `terminal`
- **Every color:** 14 roles, including structure, data, text, borders, header bars, background and alerts. Step with
  ←/→ or type a `#hex` value. **Save as new theme** keeps your mix.
- **Exact colors:** on terminals that allow it (foot, kitty, alacritty, GNOME Terminal), the deck loads your exact hex
  values into the terminal's palette. Elsewhere it uses the nearest of the 256 standard colors.
- **Font family and size:** cycle through your installed monospace fonts. The NETDECK session and the app-menu
  launcher apply them to the terminal, and **Apply font now** restarts the window instantly.
- **Look and effects:** panel ornament (corner brackets, barcode or none), Japanese labels, glitches, scanlines,
  boot sequence, news ticker, neural readout and toast notifications.
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
| `news` (**F6**) · `memo` · `shards` · `history` · `clear` · `rain` · `glitch` | notes, history, screensaver, effects |
| `update` · `lock` · `suspend` · `reboot` · `poweroff` · `logout` | system and power control (with confirmations) |
| `quit` / **F10** | jack out (in the NETDECK session: log out) |

Other keys: **PgUp/PgDn** scroll the console, **Ctrl+C** kills a running command, **Ctrl+L** clears the console.
