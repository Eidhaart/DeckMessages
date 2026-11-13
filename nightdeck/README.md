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

Setup uses sudo for Debian packages, the console autologin and the optional display settings only. It installs Python 3, Git, OpenSSH client, CA certificates, Zsh, nano, the w3m text browser, mpv and ffmpeg, then tries micro, QuickJS and the Bluetooth audio stack. It then downloads the current yt-dlp release into `~/.local/bin`. Rerun setup for an update. If dependencies are already installed, use `./setup.sh --skip-packages`. Setup leaves your login shell alone. It replaces the Nightdeck executable and the marked autostart block in your login profile (see below). To remove the executable, delete `~/.local/bin/nightdeck`.

## Raspberry Pi Touch Display 2 (5")

Run `./setup.sh --touch-display-2` once on the Pi, then reboot. Setup follows Raspberry Pi's Touch Display 2 documentation and backs up each file once (`*.nightdeck-backup`):

- **`/boot/firmware/config.txt`** gets a marked block with `dtoverlay=vc4-kms-dsi-ili9881-5inch,disable_touch`. That turns the touch driver off completely. Nightdeck is keyboard-only, so taps do nothing.
- **`/boot/firmware/cmdline.txt`** gets `video=DSI-1:720x1280@60,rotate=90` added to its single line. That turns the portrait 720×1280 panel's text console to landscape 1280×720. If the picture is upside down for the way you mounted the screen, run `./setup.sh --skip-packages --touch-display-2=270` instead.
- **Videos:** the console's `rotate=` doesn't apply to programs that draw straight to the screen, so Nightdeck reads it and passes the same rotation to mpv (`--video-rotate`). Videos then play in landscape too.
- **Font:** setup switches the console font to Terminus 16×32. On a 5" panel that gives about 80×22 characters, which is what Nightdeck is laid out for. The normal font would give about 160×45, too small to read.
- **Undo:** `./setup.sh --skip-packages --no-touch-display-2` removes the overlay block and the `video=DSI-1` setting, and restores the previous font.

**Connecting (Pi 4, power off):**
1. **Ribbon to the display:** the included 15-to-15-pin ribbon goes into the display with its metal contacts facing up, away from the display.
2. **Ribbon to the Pi:** the other end goes into the Pi's **DISPLAY** connector, with the contacts facing the USB and Ethernet ports.
3. **Power cable:** the GPIO power cable goes from the display's **J1** to the Pi's header: **red to pin 2 (5V), black to pin 6 (ground)**. A wrong connection can damage the display.

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

On the Linux console (the Pi's own screen), Nightdeck draws only with characters that every console-setup font contains, checked against the Terminus and Fixed fonts. The NIGHTDECK logo there is drawn with double box lines, which render cleanly even with the large Terminus font.

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

- **Settings** (**9** or `/settings`) lets you pick a theme (Cyberdeck, Amber, Ice, Netrunner, Synthwave, Vaporwave, Matrix, Toxic, Arasaka, Blood Moon, Ghost or Neon Tide) or a custom palette, with swatches of the current colors. Edit any color role using a six-digit hex value. Preferences apply immediately and are saved in `${XDG_CONFIG_HOME:-~/.config}/nightdeck/settings.json`. Basic-color terminals use the standard fallback palette.
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
  - **Streaming.** With yt-dlp installed, YouTube and other unprotected streams play, and SVT Play links should too. Streams use H.264, which every Pi decodes in hardware. They're capped at 720p on a Pi 4 or 5 (the 1280×720 Touch Display 2) and at 480p on a Pi 3 or older. Netflix, Disney+ and Prime Video are copy-protected, so mpv can't play them. Use **Streaming TV** instead.
  - **YouTube setup.** Debian's yt-dlp package falls behind YouTube, and YouTube refuses old versions with "The page needs to be reloaded". So setup downloads the official yt-dlp release into `~/.local/bin/yt-dlp` and checks it against the release's SHA-256 checksums. Nightdeck always hands mpv that copy. Current yt-dlp also needs a JavaScript runtime for YouTube. Deno, the default, has no 32-bit ARM build, so setup installs **QuickJS** (`quickjs`, the `qjs` command), and Nightdeck enables it for yt-dlp automatically. The Video player menu shows the yt-dlp version and whether YouTube is ready.
  - **When YouTube breaks.** Choose **Video player → Update yt-dlp**, or run `nightdeck update-ytdlp`. YouTube changes often, and a fresh yt-dlp is the usual fix. If a stream fails, Nightdeck says so and points you there. If setup ran with `--skip-packages`, the module offers **Install mpv and QuickJS**. QuickJS is slower than Deno, so a YouTube link can take several seconds longer to start on a Pi 3B.
- **Watch list.** Send links to the deck from another computer and watch them later. On the Pi, `nightdeck add URL...` adds links to the top of the list. You can also pipe them in, one per line. `nightdeck list` shows the list, `nightdeck remove N` removes entry N, and `nightdeck clear` removes watched entries. The list lives in `${XDG_DATA_HOME:-~/.local/share}/nightdeck/watchlist.json`. If yt-dlp is installed, titles are looked up in the background. If Nightdeck is open, a new link flashes on the dashboard right away, and the **QUEUE** counter goes up. Open **Video player → Watch list** to play one link or **Play all new**. Played links are marked watched (`○`), and new ones show `●`.

  **Background downloads.** Each new link is downloaded on the Pi straight away, one at a time, as H.264 MP4 (720p on a Pi 4/5, 480p on a Pi 3) into `~/Videos/watchlist/`. It plays instantly later, even offline, and the slow YouTube start happens while you're not watching. Watch list badges show `…` (waiting), `↓45%` (downloading), `✓` (ready) and `!` (failed). The list refreshes on its own while a download runs, and the dashboard flashes **READY** when one finishes. Downloads continue after you log out. If the Pi powers off mid-download, the download resumes the next time Nightdeck starts. A link that isn't downloaded yet can still be streamed, with the slow start. ffmpeg (installed by setup) joins YouTube's separate video and audio. Downloads pause when the system drive has less than 500 MB free. Turn them off under **Settings → Watch list downloads**.

  **Removing videos.** Open an entry for **Delete download** (frees the space but keeps the link, and **Download again** brings it back) or **Remove from list** (deletes the download too). At the top of the list, **Delete watched downloads** frees everything you've seen, and **Clear watched** removes watched entries and their files. The header shows how much the downloads take and how much space is free. From a shell, `nightdeck list` shows each entry's download state, and `nightdeck remove N` and `nightdeck clear` delete the matching files.

  To send links from Ubuntu, add these to `~/.zshrc` or `~/.bashrc`:

  ```sh
  deck-add() { if [ $# -gt 0 ]; then printf '%s\n' "$@"; else cat; fi | ssh deck@nightdeck.local .local/bin/nightdeck add; }
  deck-list() { ssh deck@nightdeck.local .local/bin/nightdeck list; }
  ```

  Then run `deck-add 'https://www.youtube.com/watch?v=...'`. Put each link in single quotes, because `?` and `&` mean something to your shell. Run `deck-add` with no link to paste several, one per line, and finish with **Ctrl+D**. Links go to the Pi through stdin, so SSH never reinterprets them. With an SSH key set up (`ssh-copy-id deck@nightdeck.local`), you won't need a password.
- **Music & radio** (**7** or `/music`). Music plays in the background. It keeps going while you use the rest of the deck, and even after you leave Nightdeck, until you stop it.
  - **Now-playing strip.** On the dashboard, a strip replaces the news ticker while something plays: `♪ SOURCE ▄▂█▆ Title · Artist ███░░░░ 1:23 / 3:45`, with `● LIVE` for radio. On every other screen, a compact version sits in the bottom divider line. The equalizer moves while playing and shows `||` when paused.
  - **Keys.** On the dashboard, **space** pauses or resumes, **[** and **]** go to the previous or next track, and **+**, **-** and **m** set the volume. The Music screen also has Pause, Next, Previous, Forward 30 s, Back 10 s and Stop.
  - **Radio** includes Sveriges Radio P1, P2 and P3, and SomaFM's DEF CON Radio, Vaporwaves, Groove Salad and Drone Zone. **All Sveriges Radio channels** lists every SR channel, including all P4 local stations, from SR's official API. **Add a station** saves any stream URL, and the list remembers it.
  - **Music files** browses `~/Music` and plays from the chosen track to the end of the folder, or a whole folder with **Play all here**. **Shuffle all music** shuffles everything in `~/Music`. Copy music from Ubuntu with `scp -r album deck@nightdeck.local:~/Music/`.
  - **Listen to a link** plays a YouTube or SoundCloud link as audio only. Watch-list entries also have **Listen in the background**, which uses the download when there is one.
  - **Spotify (Spotify Connect).** Spotify has no app for the Pi, so the deck becomes a Spotify speaker called **Nightdeck**. Choose **Music → Spotify → Install Spotify Connect**. Nightdeck downloads the official [spotifyd](https://github.com/Spotifyd/spotifyd) build for your Pi (`armv7`), checks it against the release's SHA-512 checksum, and installs it to `~/.local/bin`. It then starts it as a user service, so it runs whenever the deck is on. On your phone or computer, on the same Wi-Fi, open Spotify, tap the devices icon and pick **Nightdeck**. There's no password to type, but it needs **Spotify Premium**. The strip shows the Spotify track and progress, and space, [ and ] control it. When Spotify starts playing, the deck's own player pauses, and starting radio or music on the deck pauses Spotify. Sound goes through PipeWire, so Bluetooth headphones work. Setup installs the packages this needs: `pipewire-pulse`, `libpulse0`, `playerctl` and `dbus-user-session`.
- **Streaming TV** (`/tv`, or **Video player → Streaming TV**). Netflix, Disney+, Prime Video, SVT Play, YouTube or any website, in a full-screen Chromium browser with Widevine copy protection. It needs **64-bit Raspberry Pi OS** on a Pi 4 or 5.
  - **Install:** the first time, choose **Install streaming support**, about 300 MB. That installs `cage` (a kiosk display layer that shows one app full screen, no desktop), `chromium`, `rpi-chromium-mods`, `libwidevinecdm0` (Widevine) and `wlr-randr`.
  - **Use:** start it from the **deck's own screen and keyboard**; it can't open over SSH. Use the keyboard's touchpad and keys in the browser. **Ctrl+W** or **Alt+F4** closes it and returns to Nightdeck. Logins are remembered in `~/.local/share/nightdeck/browser`, and background music pauses while a show plays.
  - **Rotation:** the browser is rotated to match the Touch Display 2 console rotation.
  - **Service support:** Netflix, Disney+ and Prime Video don't officially support Linux. Copy-protected video works on 64-bit Raspberry Pi OS, but a service can refuse or limit quality; Prime Video in Linux browsers is often SD only.
- **Bluetooth & sound** (**b** on the dashboard, or `/bluetooth`). Connect Bluetooth headphones and speakers, plus keyboards and game controllers, and choose where sound plays.
  - **Scan for devices** searches for 12 seconds. Put the device in pairing mode first; usually that means holding the power button until a light flashes. Named devices are listed nearest first, with their type.
  - **Pairing:** choose a device to pair it. If the device asks for a PIN or confirmation, answer it in the terminal that opens. Nightdeck then trusts and connects it. Headphones and speakers become the sound output straight away, and videos play through them.
  - **Paired devices** lists each device with `●` when connected and its battery level when the device reports one. A device can be connected or disconnected, used for sound, set to auto-connect when Nightdeck starts, or forgotten. Trusted headphones usually reconnect by themselves when switched on.
  - **Sound output** chooses between HDMI, the headphone jack and Bluetooth. **Volume** sets the level and mute. On the dashboard, **+** and **-** change the volume by 5%, **m** mutes, and the level flashes on the ticker. The header shows `♪ name` while a device is connected, and the vitals panel shows the current output and volume (**SND**).
  - Setup installs BlueZ, PipeWire, WirePlumber, the PipeWire Bluetooth plugin and rfkill, and adds you to the `bluetooth` group. Reboot once after setup. Without those, the module offers **Install Bluetooth & sound support**. If Bluetooth is soft-blocked, it offers **Unblock Bluetooth**.
  - **Pi 3B limits.** Wi-Fi and Bluetooth share one radio, so audio can crackle while Wi-Fi is busy, for example when streaming. Downloaded videos sound best, and Ethernet or a USB Bluetooth dongle avoids the problem. Bluetooth adds a little audio delay, which mpv compensates for in video. Headset microphones and calls aren't supported.
- **System vitals** and **SSH utilities** sit unnumbered below Settings and open with `/vitals` and `/ssh`. The dashboard panel shows the same readings live.
- **Character sheets.** Reserved menu entry. It sits unnumbered below Settings and opens with `/sheets`.

## Validation

Developers can run `python3 tests/smoke.py`, which needs `pip install pyte`. It drives the app in a pseudo-terminal at 80×24 and 42×12, on xterm, on the Linux console and under a C locale, and checks git diffs, the ticker, settings and a clean exit.


The release is designed for Python 3 on Linux and uses no architecture-specific bundled binaries. Local validation covers archive extraction, repeat installation, terminal navigation and core application paths. The physical Pi, its display and your Git credentials need their first check after deployment.
