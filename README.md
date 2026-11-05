# DeckMessages

A cyberpunk terminal client for Facebook Messenger, for desktop (Windows, macOS, Linux) and Android.

```
DECK//MSG   # Nyx                                         ● ONLINE  22:01:02
// CHANNELS │ 19:00 <Nyx> did you see the skyline tonight
01 # Nyx    │ 19:10 <you> yeah it looked unreal
02 # Vex    │ 22:00 * you pulls on a jacket
03 # Mom  1 │ deck@nyx:~$ _
```

- **Terminal UI:** CRT scanlines, flicker, glitch text and neon glow. Four palettes (`neon`, `amber`, `toxic`,
  `ice`) and a skippable boot sequence.
- **Commands:** `/list`, `/go <n|name>`, `/me`, `/theme`, `/fx`, `/bridge`, `/clear`, `/help`, and more.
  Tab completes commands and channel names, and Up/Down recalls history.
- **Keyboard first:** Alt+↑/↓ switches channels and Ctrl+L clears the screen. On phones, a slide-out channel
  drawer and a send button take over.
- **Real Messenger chats:** through the [mautrix-meta](https://github.com/mautrix/meta) bridge on a free cloud
  VM, set up with one command. Images, emotes, unread counts and read receipts work.
- **Demo mode:** a built-in offline backend with fictional contacts for trying the UI with no setup.

## Bonus: NETDECK//OS

[`cyberdeck/`](cyberdeck/README.md) holds a standalone, dependency-free terminal dashboard in the same style. It turns an
Ubuntu terminal into a hijacked-corp cyberdeck, with live telemetry, a categorized launcher for every installed
program, a command console and a drop-to-shell mode. Run `python3 cyberdeck/netdeck.py`.

## Why a bridge?

Meta has no public API for personal Messenger accounts. DeckMessages is a [Matrix](https://matrix.org) client,
and a bridge relays your Messenger chats into Matrix. It runs on a free cloud VM (no hardware or domain needed):

```bash
curl -fsSL https://raw.githubusercontent.com/Eidhaart/DeckMessages/HEAD/server/install.sh | sudo bash
```

**Step-by-step guide, including creating the free VM: [docs/SERVER.md](docs/SERVER.md).**

## Stack

[Tauri 2](https://tauri.app) wraps a React and TypeScript UI (Vite), so one codebase ships as a small native
desktop app and an Android APK. Matrix support comes from `matrix-js-sdk` with Rust crypto (WASM).

```
src/
  App.tsx               layout, state, shortcuts
  commands.ts           slash commands and tab completion
  transport/types.ts    backend interface the UI talks to
  transport/matrix.ts   Matrix / Messenger-bridge backend
  transport/demo.ts     offline demo backend
  components/           boot, login, sidebar, log, prompt
src-tauri/              native shell (desktop + Android)
server/install.sh       one-command server setup (Synapse + bridge + HTTPS)
```

## Development

Requires Node 22+ and Rust (stable). See the [Tauri prerequisites](https://tauri.app/start/prerequisites/) for
your OS. On Linux that means `libwebkit2gtk-4.1-dev`, among others.

```bash
npm install
npm run dev            # UI only, in the browser at http://localhost:1420
npm run tauri dev      # desktop app with hot reload
npm run tauri build    # installers in src-tauri/target/release/bundle/
```

### Android

**Easiest way to get the APK:** every push runs the *Android APK* workflow. Open the run under the repo's
**Actions** tab, download the `DeckMessages-android` artifact, unzip it, and install the APK on your phone
(allow installs from unknown sources when asked).

To keep updates installing over the old version, sign every build with the same key by adding these repo secrets:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 release.jks` |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | key alias |

Without them, each build gets a throwaway key and you'll need to uninstall before installing a new build.

**Building locally** needs the Android SDK and NDK, `JAVA_HOME`, `ANDROID_HOME`, `NDK_HOME`, and the Rust target.
The Android project is already generated in `src-tauri/gen/android`.

```bash
rustup target add aarch64-linux-android
npm run tauri android dev                              # run on a USB-connected phone or an emulator
npm run tauri android build -- --apk --target aarch64  # unsigned APK, sign with apksigner
```

The phone must reach your homeserver over **HTTPS**.

## Roadmap ideas

- Native notifications (`tauri-plugin-notification`) and a background sync service on Android
- Typing indicators, reactions, replies and edits in the UI
- Sending images and files
- Login with a QR code or SSO
