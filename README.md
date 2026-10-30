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
- **Real Messenger chats:** through the [mautrix-meta](https://github.com/mautrix/meta) bridge on your own
  Matrix homeserver, with images, emotes, unread counts and read receipts. Encrypted rooms are supported for messages sent after you log in.
- **Demo mode:** a built-in offline backend with fictional contacts for trying the UI with no setup.

## Why a bridge?

Meta has no public API for personal Messenger accounts. DeckMessages is a [Matrix](https://matrix.org) client,
and a self-hosted bridge relays your Messenger chats into Matrix. **Setup guide: [docs/BRIDGE.md](docs/BRIDGE.md).**

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
bridge/                 docker-compose for Synapse + mautrix-meta
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

Needs Android Studio (SDK and NDK), `JAVA_HOME`, `ANDROID_HOME`, `NDK_HOME`, and the Rust Android targets:

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
npm run tauri android init      # generates src-tauri/gen/android (once)
npm run tauri android dev       # run on an emulator or a USB-connected phone
npm run tauri android build -- --apk
```

The phone must reach your homeserver over **HTTPS**.

## Roadmap ideas

- Native notifications (`tauri-plugin-notification`) and a background sync service on Android
- Typing indicators, reactions, replies and edits in the UI
- Sending images and files
- Login with a QR code or SSO
