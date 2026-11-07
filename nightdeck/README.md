# Nightdeck // Field Terminal

A keyboard-driven terminal dashboard for Raspberry Pi 3 Model B and Raspberry Pi OS Lite (Debian 13/Trixie, 32-bit). It runs as your own user on the Pi console or over SSH. The app uses Python's standard library and curses. It starts no background services and needs no desktop, browser engine, pip packages or database.

## Deploy from Ubuntu

Download **nightdeck.tar.gz** into Ubuntu's Downloads folder. Run these on Ubuntu, one at a time:

```sh
cd ~/Downloads
tar -tzf nightdeck.tar.gz
scp nightdeck.tar.gz deck@nightdeck.local:~/
ssh deck@nightdeck.local
```

If your network doesn't resolve the hostname, use your Pi's current IP address instead. Keep normal SSH host key verification enabled. After logging into the Pi, run:

```sh
cd ~
tar -xzf nightdeck.tar.gz
cd nightdeck
./setup.sh
~/.local/bin/nightdeck
```

Setup uses sudo for Debian packages and the console autologin only. It installs Python 3, Git, OpenSSH client, CA certificates, Zsh, nano, the w3m text browser and mpv, then tries micro and yt-dlp. Rerun setup for an update. If dependencies are already installed, use `./setup.sh --skip-packages`. Setup leaves your login shell alone. It replaces the Nightdeck executable and the marked autostart block in your login profile (see below). To remove the executable, delete `~/.local/bin/nightdeck`.

## Autostart and jack out

**On the Pi's screen**, setup turns on automatic login for your user on the first console (tty1), and Nightdeck opens as soon as the Pi has booted. No keyboard login is needed. It adds a systemd drop-in, `/etc/systemd/system/getty@tty1.service.d/nightdeck-autologin.conf`, which takes effect after a reboot. Anyone with the Pi's keyboard is then logged in as you. To keep the normal login prompt on the screen, run `./setup.sh --skip-packages --no-console`; SSH autostart still works. On the screen, Nightdeck repaints the console's 8 colors with your theme, so you get the real Cyberdeck red, yellow and cyan. The original colors come back when you leave Nightdeck. **Log out** from the Jack out menu restarts the deck there.

To get bigger text on a large monitor, run `sudo dpkg-reconfigure console-setup` and pick the Terminus font at a larger size. If the image is cut off at the edges, switch the monitor's picture size to "Just Scan", "1:1" or "Screen Fit".

**Over SSH**,

`./setup.sh` also makes Nightdeck open by itself when you log in over SSH. It adds a marked block to `~/.profile`, plus `~/.bash_profile`, `~/.bash_login` or `~/.zprofile` when you have them. Rerunning setup replaces the block, and `./setup.sh --skip-packages --no-autostart` removes it. The deck only starts for interactive SSH logins. `scp`, `ssh deck@nightdeck.local <command>` and logins on the Pi's own screen are untouched.

**Jack out** (**0**, **Esc** on the dashboard, or `/exit`) opens a menu:

- **Power off the deck** runs `sudo systemctl poweroff`. Wait for the green activity LED to stop before you unplug the Pi.
- **Reboot** runs `sudo systemctl reboot`.
- **Exit to shell** leaves Nightdeck and keeps your SSH session open with a normal shell.
- **Disconnect** leaves Nightdeck and logs out.

Raspberry Pi OS lets the first user run sudo without a password, so power off works right away. If your user needs a password, sudo asks for it. If Nightdeck crashes, the autostart drops you into a shell instead of logging you out, so you can't get locked out over SSH.

## Look

Nightdeck v2 has the same tools as before, with a livelier cyberdeck interface modeled on the DeckMessages terminal and the Cyberdeck Zsh banner:

- **Boot sequence.** A glitch-in logo and `[ OK ]`/`[ !! ]` readouts from the real machine: kernel, temperature, memory, network link, news cache and repositories. It lasts about two seconds, and any key skips it.
- **Dashboard.** A header with a pulsing link beacon and clock, a glitching block-letter logo, a boxed module list, and a vitals panel. The panel has live CPU, RAM, temperature and disk meters, network throughput, Wi-Fi signal, and a scrolling CPU trace. A **WIRE** ticker along the bottom scrolls cached headlines.
- **Screens.** Titles decrypt in when a screen opens. Menus have a highlight bar, a position counter and scroll markers. Text views have a scrollbar. Git output is colored: additions green, removals red, hunks cyan, untracked files red. News refresh runs behind an uplink animation, and leaving prints `CONNECTION TERMINATED`.
- **Lightweight.** It's still pure standard-library Python and curses. Animation redraws about seven times a second, and curses sends only changed cells, which is cheap on a Pi 3B even over SSH. Turn **Effects** off in Settings for a static screen that updates once a second.

## Controls and display

The dashboard borrows the split navigation, clock and command prompt from [DeckMessages](https://github.com/Eidhaart/DeckMessages). On wider terminals, numbered modules sit beside live local vitals. On smaller terminals, a one-line CPU, RAM and temperature readout sits above the scrolling module list. Modules use the full width for diffs, headlines and other text.

- Press **1–9** to open a dashboard module directly and **0** to jack out. Or press **/** and type a command such as `git`, `news` or `claude`. **Tab** completes the name. Use **/help** for the command list.
- **Esc** goes back. On the dashboard, **Esc** opens the Jack out menu.

- **Up/Down** or **j/k** moves. **Enter** selects. In a text view, **Page Up/Down** scrolls by page.
- A compact terminal around **80 columns × 24 rows** fits an 800×480 display with an appropriate font. Menus scroll at smaller sizes and adapt when resized. The app uses the terminal's character grid and does not change the Pi's display settings.
- The default Cyberdeck palette matches the bundled Zsh theme. Colors in order: `#FF003C`, `#FFEE08`, `#00FFFF`, `#1DED83`, `#FAFAFA`, `#0E0E0E`. Curses programs these RGB values when the terminal advertises a mutable 256-color palette. Otherwise it uses available approximations, including the Linux console's basic colors. Let SSH forward your real terminal type.
- Micro normally saves with **Ctrl+S** and exits with **Ctrl+Q**. Nano saves with **Ctrl+O**, then **Enter**, and exits with **Ctrl+X**.

## Settings

- **Settings** (**9** or `/settings`) lets you pick Cyberdeck, Amber, Ice or a custom palette, with swatches of the current colors. Edit any color role using a six-digit hex value. Preferences apply immediately and are saved in `${XDG_CONFIG_HOME:-~/.config}/nightdeck/settings.json`. Basic-color terminals use the standard fallback palette.
- **Effects** turns animation on or off: glitch, ticker scroll, title decrypt and the blinking cursor. **Boot sequence** turns the startup animation on or off.
- **Glyphs** sets which characters are used for borders and meters. **Auto** uses full Unicode in terminal emulators, the VGA-safe set the Linux console font always has (`TERM=linux`, the Pi's own screen), and plain ASCII if the locale isn't UTF-8. Cycle to **Console** or **ASCII** if any symbol shows as a diamond or box.
- **Connect to Wi-Fi** opens NetworkManager's terminal picker with sudo. Select the network, enter its password in the picker, and return to Nightdeck. If the picker is missing, install `network-manager` while connected. Use the Pi console when switching the Wi-Fi that carries your SSH session. The Pi 3B requires a 2.4 GHz phone hotspot.

## Tools

- **Git workspace.** Clone HTTPS or SSH repositories into `~/repos`, or open an existing repository/worktree by its root path. View status, working and staged diffs, and branches. Edit a file, stage a literal path relative to the repo root, review the staged diff, and commit using Git's configured editor. Set `git config --global core.editor micro` (or `nano`) if you want the same editor for commit messages. Git may ask for your author name and email on the first commit.
- **Push.** Select a configured remote such as `origin`. The preview shows the resolved push destination and an explicit refspec for the checked-out branch. Push updates the branch of the same name, without force or automatic upstream configuration. The app requires one push URL. If the remote rejects the update, review and reconcile the histories through normal Git commands.
- **Authentication.** Use an existing SSH agent/key or Git credential helper. Enter HTTPS URLs without credentials or query strings. Nightdeck stores no credentials and disables inherited Git tracing for commands it runs. Git, your configured helpers/hooks, and SSH retain their normal behavior. Use trusted repositories and review staged content before committing or pushing. Diff views display your changes on screen.
- **Notes and quick edit.** Notes are plain text under `${XDG_DATA_HOME:-~/.local/share}/nightdeck/notes`. New note names without extensions get `.md`. Quick edit starts in your home directory. The browser skips symlinks and Git metadata. An editor opens a new path for you to save.
- **Zsh.** Run `./setup-oh-my-zsh.sh` from the extracted directory to enable your Cyberdeck prompt, startup banner and `jack-in` command in the Nightdeck Zsh menu. Setup reuses `~/.oh-my-zsh` or fetches a shallow copy from upstream GitHub. It writes a dedicated profile under `${XDG_CONFIG_HOME:-~/.config}/nightdeck/zsh`, so your regular Zsh configuration and login shell are preserved. The profile loads the Git plugin and disables automatic Oh My Zsh updates. The bundled Ptyxis palette is available for manual import on Ubuntu.
- **System and SSH.** Check uptime, load, memory, disk and CPU temperature when available. Connect using a hostname or an alias in your SSH config, edit that config, or inspect loaded agent identities.
- **News wire.** Select a publisher and choose **Refresh from publisher**. SVT provides Swedish headlines, Sveriges Radio Ekot provides broadcast headlines and article links, and BBC News and The Guardian provide world headlines. Choose a headline for a text view of the publisher's feed summary and link when supplied. After closing the summary, choose **Open in text browser** to visit the publisher through w3m. Press **q**, then confirm, to return. The page depends on network access and what the publisher serves to a text browser. Caches live under `${XDG_CACHE_HOME:-~/.cache}/nightdeck`, one file per publisher, and remain available offline after a successful refresh. Failed refreshes preserve the last good cache. Each source has a 2 MiB fetch limit and retains up to 50 entries.
- **Claude Code** (**5** or `/claude`). Claude Code needs a 64-bit (x64 or ARM64) system with 4 GB+ RAM, so it can't run on a Pi 3B with 32-bit Raspberry Pi OS. The module runs it on a bigger machine, such as your Ubuntu PC, over SSH. The deck is the screen and keyboard. Choose **Set remote host and project** and enter an SSH alias or `user@host` and a project folder such as `~/code/app`. **Launch** then runs `ssh -t <host>`, changes to that folder and starts `claude` in a login shell. **Install Claude Code on <host>** runs Anthropic's official installer (`curl -fsSL https://claude.ai/install.sh | bash`) on that machine. The other machine needs an SSH server (`sudo apt install openssh-server` on Ubuntu), and an SSH key from the Pi (`ssh-keygen`, then `ssh-copy-id user@host`) saves typing a password. On a supported 64-bit machine, the same module installs Claude Code locally and launches it in your home folder or a repository. Commands are shown for confirmation before they run.
- **Video player** (**6** or `/video`). Plays files and streams with mpv. **Browse ~/Videos** lists folders, video and audio files with their sizes, plus **Play all here** for a folder playlist. **Play file by path** takes any path, and **Play a URL or stream** takes an http(s) link. Copy videos over from Ubuntu with `scp movie.mp4 deck@nightdeck.local:~/Videos/`.
  - **Deck screen** plays full screen on the Pi's display through DRM, with no desktop needed and hardware H.264 decoding. Starting it from SSH still shows it on the Pi, and your SSH keyboard controls playback.
  - **This terminal** draws the video as colored text blocks in the terminal you're using. Sound always comes out of the Pi.
  - Over SSH, Nightdeck asks which to use each time. Fix the choice in **Settings / Video output**.
  - Keys while playing: **space** pause, **←/→** seek, **9/0** volume, **m** mute, **q** stop. mpv remembers where you stopped each file.
  - **Streaming.** With yt-dlp installed, YouTube and other unprotected streams play, and SVT Play links should too. Streams are capped at 480p H.264, which fits the 800×480 panel and is what the Pi 3B decodes in hardware. Disney+, Netflix and other DRM services need Widevine in a desktop browser. Widevine for Raspberry Pi is 64-bit only, so they can't play on this deck.
  - If setup ran with `--skip-packages`, the module offers **Install mpv and yt-dlp**. Debian's yt-dlp can lag behind YouTube changes. If YouTube stops working, a newer yt-dlp usually fixes it.
- **Watch list.** Send links to the deck from another computer and watch them later. On the Pi, `nightdeck add URL...` adds links to the top of the list. You can also pipe them in, one per line. `nightdeck list` shows the list, `nightdeck remove N` removes entry N, and `nightdeck clear` removes watched entries. The list lives in `${XDG_DATA_HOME:-~/.local/share}/nightdeck/watchlist.json`. If yt-dlp is installed, titles are looked up in the background. If Nightdeck is open, a new link flashes on the dashboard right away, and the **QUEUE** counter goes up. Open **Video player → Watch list** to play one link or **Play all new**. Played links are marked watched (`○`), and new ones show `●`.

  To send links from Ubuntu, add these to `~/.zshrc` or `~/.bashrc`:

  ```sh
  deck-add() { if [ $# -gt 0 ]; then printf '%s\n' "$@"; else cat; fi | ssh deck@nightdeck.local .local/bin/nightdeck add; }
  deck-list() { ssh deck@nightdeck.local .local/bin/nightdeck list; }
  ```

  Then run `deck-add 'https://www.youtube.com/watch?v=...'`. Put each link in single quotes, because `?` and `&` mean something to your shell. Run `deck-add` with no link to paste several, one per line, and finish with **Ctrl+D**. Links go to the Pi through stdin, so SSH never reinterprets them. With an SSH key set up (`ssh-copy-id deck@nightdeck.local`), you won't need a password.
- **System vitals.** The full telemetry view sits unnumbered below Settings and opens with `/vitals`. The dashboard panel shows the same readings live.
- **Character sheets.** Reserved menu entry. It sits unnumbered below Settings and opens with `/sheets`.

## Validation

Developers can run `python3 tests/smoke.py`, which needs `pip install pyte`. It drives the app in a pseudo-terminal at 80×24 and 42×12, on xterm, on the Linux console and under a C locale, and checks git diffs, the ticker, settings and a clean exit.


The release is designed for Python 3 on Linux and uses no architecture-specific bundled binaries. Local validation covers archive extraction, repeat installation, terminal navigation and core application paths. The physical Pi, its display and your Git credentials need their first check after deployment.
