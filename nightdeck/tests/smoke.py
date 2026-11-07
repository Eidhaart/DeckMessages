"""Terminal regression checks for Nightdeck. Needs: pip install pyte.

Run: python3 tests/smoke.py   (writes nothing outside a temporary HOME)
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Session

DOWN, UP = "\x1bOB", "\x1bOA"
QUIT = [("q", 0.5), (DOWN * 3, 0.2), ("\r", 1.0)]  # Jack out -> Disconnect
failures = []


def check(name, condition):
    print(("ok   " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)


def seed(home):
    cache = Path(home, ".cache/nightdeck")
    cache.mkdir(parents=True)
    (cache / "bbc.json").write_text(json.dumps({"saved": "2026-11-05T21:00+01:00", "items": [
        {"title": "Grid lights return to the old quarter", "summary": "Test summary.", "date": "today",
         "link": "https://example.com/a"}]}))
    repo = Path(home, "repos/demo")
    repo.mkdir(parents=True)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one\n")
    subprocess.run(git + ["add", "a.txt"], cwd=repo, check=True)
    subprocess.run(git + ["commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("two\n")


def scenario(cols, rows, term, lang, keys):
    with tempfile.TemporaryDirectory() as home:
        seed(home)
        s = Session(cols, rows, home=home, term=term, env={"LANG": lang, "LC_ALL": lang})
        s.pump(0.6)
        screens = []
        for key, wait in keys:
            s.send(key, wait)
            screens.append(s.text())
        code = s.finish()
        return code, screens, s.raw.decode("utf-8", "replace")


# 1. Full dashboard, ticker, git diff view, settings toggle, exit
code, screens, raw = scenario(80, 24, "xterm-256color", "C.UTF-8", [
    ("x", 0.6), ("1", 0.6), ("\x1bOB\x1bOB", 0.1), ("\r", 0.6), (DOWN, 0.2), ("\r", 0.8),
    ("\x1b", 0.3), ("\x1b", 0.3), ("\x1b", 0.3), ("9", 0.6), (DOWN + DOWN, 0.2), ("\r", 0.5),
    ("\x1b", 0.4)] + QUIT)
check("80x24 exits cleanly", code == 0 and "Traceback" not in raw)
check("dashboard shows modules and vitals", "MODULES" in screens[0] and "VITALS" in screens[0])
check("wire ticker shows cached headline", "Grid lights" in screens[0] or "Grid lights" in screens[1])
check("git repo opens with branch", "[main]" in screens[3] or "[main]" in screens[4])
check("working diff shows change", "+two" in screens[5] and "-one" in screens[5])
check("effects toggled off", "Effects / Off" in screens[11])
check("AI module removed", "AI terminal" not in screens[0] and "/ai" not in raw)

# 2. Narrow terminal, slash command with tab completion
code, screens, raw = scenario(42, 12, "xterm-256color", "C.UTF-8", [
    ("x", 0.5), ("/", 0.4), ("vit", 0.2), ("\t", 0.2), ("\r", 0.6), ("\x1b", 0.3)] + QUIT)
check("42x12 exits cleanly", code == 0 and "Traceback" not in raw)
check("narrow vitals line", "CPU" in screens[0])
check("tab completion opens vitals", "SYSTEM // local telemetry" in screens[4])

# 3. Linux console, 8 colors, ASCII glyphs under an invalid locale
code, screens, raw = scenario(80, 24, "linux", "nightdeck_invalid.UTF-8", [
    ("x", 0.6), ("j", 0.3), ("q", 0.5), ("jjj", 0.2), ("\r", 1.0)])  # TERM=linux arrows differ
check("linux console exits cleanly", code == 0 and "Traceback" not in raw)
check("console glyphs on TERM=linux", "► 01" in screens[0] and "▶" not in screens[0])
check("console palette repainted with theme", "\x1b]p1ff003c" in raw.lower() and "\x1b]p3ffee08" in raw.lower()
      and "\x1b]P0" in raw)
check("console palette restored on exit", raw.rstrip().endswith("\x1b]R") or "\x1b]R" in raw[-200:])

# 3b. Plain C locale falls back to ASCII glyphs
code, screens, raw = scenario(80, 24, "xterm-256color", "C", [("x", 0.6)] + QUIT)
check("C locale exits cleanly", code == 0 and "Traceback" not in raw)
check("ascii fallback used", "+-[ MODULES ]" in screens[0])

# 4. Boot sequence renders
with tempfile.TemporaryDirectory() as home:
    s = Session(80, 24, home=home)
    s.pump(1.2)
    check("boot sequence shows status lines", "[ OK ] KERNEL HANDSHAKE" in s.text())
    s.send("x", 0.4)
    for key, wait in QUIT:
        s.send(key, wait)
    check("boot then exit", s.finish() == 0)

# 5. Jack out menu, exit-to-shell code, Claude Code module
code, screens, raw = scenario(80, 24, "xterm-256color", "C.UTF-8", [
    ("x", 0.6), ("0", 0.6), ("\x1b", 0.4), ("5", 0.6), ("\x1b", 0.4), ("q", 0.5), (DOWN * 2, 0.2), ("\r", 1.0)])
check("0 opens jack out menu", "Power off the deck" in screens[1] and "Exit to shell" in screens[1])
check("claude code module", "CLAUDE CODE" in screens[3] and "Set remote host and project" in screens[3])
check("exit to shell returns code 10", code == 10)

# 6. Video player builds the right mpv command for the deck screen and for streams
import os
with tempfile.TemporaryDirectory() as home:
    fake = Path(home, "bin")
    fake.mkdir()
    (fake / "mpv").write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$HOME/mpv.args"\n')
    (fake / "mpv").chmod(0o755)
    (fake / "qjs").write_text("#!/bin/sh\n")
    (fake / "qjs").chmod(0o755)
    Path(home, "Videos").mkdir()
    Path(home, "Videos", "clip.mp4").write_bytes(b"x")
    env = {"PATH": f"{fake}:{os.environ['PATH']}", "DISPLAY": "", "WAYLAND_DISPLAY": ""}
    s = Session(80, 24, home=home, env=env)
    s.pump(0.6)
    for key, wait in [("x", 0.6), ("6", 0.6), (DOWN, 0.2), ("\r", 0.6), (DOWN * 2, 0.2), ("\r", 1.0)]:
        s.send(key, wait)
    played = Path(home, "mpv.args").read_text().splitlines() if Path(home, "mpv.args").exists() else []
    check("video plays on deck screen via DRM", "--vo=gpu,drm" in played and "--fs" in played
          and played[-2:] == ["--", str(Path(home, "Videos", "clip.mp4"))])
    Path(home, "mpv.args").unlink(missing_ok=True)
    for key, wait in [("\x1b", 0.4), (DOWN * 2, 0.2), ("\r", 0.5), ("https://example.com/v?id=1", 0.2),
                      ("\r", 1.0), ("\r", 0.5), ("ftp://x/y", 0.2), ("\r", 0.6)]:
        s.send(key, wait)
    played = Path(home, "mpv.args").read_text().splitlines() if Path(home, "mpv.args").exists() else []
    check("URL stream capped for the Pi", played[-1:] == ["https://example.com/v?id=1"]
          and any(a.startswith("--ytdl-format=") and "480" in a for a in played))
    check("non-http URL refused", "Use a plain http(s) URL" in s.text())
    for key, wait in [("\r", 0.3), ("\x1b", 0.4)] + QUIT:
        s.send(key, wait)
    check("video module exits cleanly", s.finish() == 0)

# 7. Watch list: links sent with `nightdeck add` download in the background, appear live and can be removed
FAKE_YTDLP = """#!/usr/bin/env python3
import sys, time
a = sys.argv[1:]
if "--version" in a:
    print("2026.10.26"); sys.exit()
url = a[-1]
if "broken" in url:
    print("ERROR: [generic] Video unavailable", file=sys.stderr); sys.exit(1)
vid = url.split("v=")[-1].split("&")[0] if "v=" in url else url.rstrip("/").split("/")[-1]
if "-o" not in a:
    print("Title of " + vid); sys.exit()
title = "Title of " + vid
path = a[a.index("-o") + 1].replace("%(title).80B", title).replace("%(id)s", vid).replace("%(ext)s", "mp4")
print("TITLE " + title, flush=True)
for n in (30, 60, 100):
    print(f"PROG {n} 100", flush=True); time.sleep(0.1)
open(path, "wb").write(bytes(2048))
print("FILE " + path, flush=True)
"""


def wait_for(condition, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.2)
    return False


with tempfile.TemporaryDirectory() as home:
    fake = Path(home, "bin")
    fake.mkdir()
    (fake / "mpv").write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$HOME/mpv.args"\n')
    (fake / "yt-dlp").write_text(FAKE_YTDLP)
    (fake / "qjs").write_text("#!/bin/sh\n")
    for tool in ("mpv", "yt-dlp", "qjs"):
        (fake / tool).chmod(0o755)
    env = dict(os.environ, HOME=home, PATH=f"{fake}:{os.environ['PATH']}")
    app = str(Path(__file__).resolve().parent.parent / "nightdeck.py")
    downloads = Path(home, "Videos", "watchlist")

    def cli(*args, **kw):
        return subprocess.run([sys.executable, app, *args], capture_output=True, text=True, env=env, **kw)

    def listing():
        return cli("list").stdout
    out = cli("add", input="https://www.youtube.com/watch?v=abc&t=10\nnot a link\nhttps://example.com/b?v=xyz\n")
    check("add via stdin keeps ? and & intact", "queued   https://www.youtube.com/watch?v=abc&t=10" in out.stdout
          and "skipped  not a link" in out.stdout and out.returncode == 1)
    out = cli("add", "https://www.youtube.com/watch\\?v\\=zsh1\\&t\\=5")
    check("zsh paste backslashes stripped", "queued   https://www.youtube.com/watch?v=zsh1&t=5" in out.stdout)
    cli("add", "https://example.com/broken")
    out = cli(stdin=subprocess.DEVNULL)
    check("no terminal gives a clear message", out.returncode == 2 and "needs a terminal" in out.stderr
          and "Traceback" not in out.stderr)
    check("links download in the background",
          wait_for(lambda: listing().count("ready") == 3 and "failed" in listing()))
    check("downloads saved as 480p files", len(list(downloads.glob("*.mp4"))) == 3)
    check("titles come from the download", "Title of abc" in listing())
    s = Session(80, 24, home=home, env={"PATH": env["PATH"], "DISPLAY": "", "WAYLAND_DISPLAY": ""})
    s.pump(0.6)
    s.send("x", 1.2)
    check("dashboard shows queue count", "QUEUE    4 new" in s.text())
    cli("add", "https://example.com/c?v=live")
    s.pump(0.8)
    check("new link flashes on the dashboard", b"NEW LINK" in s.raw and "QUEUE    5 new" in s.text())
    s.pump(2.5)
    check("finished download flashes READY", "READY " in s.raw.decode("utf-8", "replace")
          and "Title of live" in s.raw.decode("utf-8", "replace"))
    for key, wait in [("6", 0.6), ("\r", 0.8)]:
        s.send(key, wait)
    check("watch list shows download badges", "✓" in s.text() and "!" in s.text() and "4 downloaded" in s.text())
    s.send("\r", 1.0)
    played = Path(home, "mpv.args").read_text().splitlines() if Path(home, "mpv.args").exists() else []
    targets = played[played.index("--") + 1:] if "--" in played else []
    check("play all new uses downloads, streams the rest",
          [Path(t).name for t in targets] == ["Title of live [live].mp4", "broken", "Title of zsh1 [zsh1].mp4",
                                               "Title of xyz [xyz].mp4", "Title of abc [abc].mp4"]
          and targets[1] == "https://example.com/broken")
    check("mpv is pointed at our yt-dlp", any(arg == "--script-opts-append=ytdl_hook-ytdl_path=" + str(fake / "yt-dlp")
                                              for arg in played))
    check("played links marked watched", "0 new" in s.text())
    for key, wait in [(DOWN, 0.2), ("\r", 0.8)]:
        s.send(key, wait)
    check("delete watched downloads frees the files", not list(downloads.glob("*.mp4"))
          and "0 downloaded" in s.text() and listing().count("deleted") == 4)
    for key, wait in [("\x1b", 0.4), ("\x1b", 0.4)] + QUIT:
        s.send(key, wait)
    check("watch list exits cleanly", s.finish() == 0)
    cli("add", "https://example.com/d?v=keep")
    wait_for(lambda: (downloads / "Title of keep [keep].mp4").exists())
    out = cli("remove", "1")
    check("remove deletes that download", "Title of keep" in out.stdout
          and not (downloads / "Title of keep [keep].mp4").exists())
    out = cli("clear")
    check("clear removes watched", "0 left" in out.stdout)

# 8. YouTube needs a JavaScript runtime: QuickJS is enabled only for a new enough yt-dlp
import importlib.util
spec = importlib.util.spec_from_file_location("nightdeck_mod", Path(__file__).resolve().parent.parent / "nightdeck.py")
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)
with tempfile.TemporaryDirectory() as tmp:
    fake = Path(tmp)
    for name, body in (("new", "echo 2026.10.26"), ("old", "echo 2025.04.30"), ("qjs", "")):
        (fake / name).write_text("#!/bin/sh\n" + body + "\n")
        (fake / name).chmod(0o755)
    saved = os.environ["PATH"]
    os.environ["PATH"] = f"{fake}:/usr/bin:/bin"
    try:
        check("QuickJS enabled for current yt-dlp", nd.ytdlp_js_options(str(fake / "new")) == ["--js-runtimes", "quickjs"])
        check("old Debian yt-dlp gets no unknown flag", nd.ytdlp_js_options(str(fake / "old")) == [])
        nd.YTDLP_LOCAL = fake / "old"
        check("old yt-dlp flagged in the menu", "too old" in nd.ytdlp_status())
        nd.YTDLP_LOCAL = fake / "new"
        check("current yt-dlp + QuickJS reported ready", nd.ytdlp_status() == "YouTube: yt-dlp 2026.10.26 + QuickJS ready.")
    finally:
        os.environ["PATH"] = saved

# 9. Bluetooth & sound: scan, pair, connect headphones, sound switches to them, volume keys
FAKE_BT = r"""#!/usr/bin/env python3
import json, os, sys, time
state_file = os.path.join(os.environ["HOME"], "bt.json")
pool = {"AA:BB:CC:00:00:01": {"name": "WH-1000XM4", "icon": "audio-headset", "rssi": -48},
        "AA:BB:CC:00:00:02": {"name": "MX Keys", "icon": "input-keyboard", "rssi": -60}}
try:
    st = json.load(open(state_file))
except OSError:
    st = {"powered": True, "known": {}}
a = sys.argv[1:]
if a[:1] == ["--timeout"]:
    a = a[2:]
cmd, rest = (a[0], a[1:]) if a else ("", [])
known = st["known"]
if cmd == "show":
    print("Controller B8:27:EB:00:00:00 (public)\n\tName: nightdeck\n\tPowered: " + ("yes" if st["powered"] else "no"))
elif cmd == "power":
    st["powered"] = rest[0] == "on"; print("Changing power " + rest[0] + " succeeded")
elif cmd == "devices":
    for mac, d in known.items():
        if not rest or (rest[0] == "Paired" and d.get("paired")) or (rest[0] == "Connected" and d.get("connected")):
            print(f"Device {mac} {d['name']}")
elif cmd == "scan":
    for mac, d in pool.items():
        known.setdefault(mac, dict(d)); print(f"\x1b[0;93m[NEW]\x1b[0m Device {mac} {d['name']}")
    time.sleep(0.3)
elif cmd == "info":
    d = known.get(rest[0])
    if not d:
        print("Device " + rest[0] + " not available"); sys.exit(1)
    yn = lambda v: "yes" if v else "no"
    print(f"Device {rest[0]} (public)\n\tName: {d['name']}\n\tAlias: {d['name']}\n\tIcon: {d['icon']}\n"
          f"\tPaired: {yn(d.get('paired'))}\n\tTrusted: {yn(d.get('trusted'))}\n\tConnected: {yn(d.get('connected'))}\n"
          f"\tRSSI: 0xffffffd0 ({d['rssi']})" + ("\n\tBattery Percentage: 0x50 (80)" if d.get("connected") else ""))
elif cmd == "pair":
    known[rest[0]]["paired"] = True; print("Attempting to pair with " + rest[0] + "\nPairing successful")
elif cmd == "trust":
    known[rest[0]]["trusted"] = True
elif cmd == "connect":
    known[rest[0]]["connected"] = True; print("Connection successful")
elif cmd == "disconnect":
    known[rest[0]]["connected"] = False
elif cmd == "remove":
    known.pop(rest[0], None)
json.dump(st, open(state_file, "w"))
"""
FAKE_PWDUMP = r"""#!/usr/bin/env python3
import json, os
try:
    st = json.load(open(os.path.join(os.environ["HOME"], "bt.json")))
except OSError:
    st = {"known": {}}
nodes = [{"id": 40, "type": "PipeWire:Interface:Node",
          "info": {"props": {"media.class": "Audio/Sink", "node.description": "Built-in Audio HDMI", "device.api": "alsa"}}}]
for mac, d in st["known"].items():
    if d.get("connected") and d["icon"].startswith("audio"):
        nodes.append({"id": 77, "type": "PipeWire:Interface:Node",
                      "info": {"props": {"media.class": "Audio/Sink", "node.description": d["name"], "device.api": "bluez5"}}})
print(json.dumps(nodes))
"""
FAKE_WPCTL = r"""#!/usr/bin/env python3
import json, os, sys
path = os.path.join(os.environ["HOME"], "wp.json")
try:
    st = json.load(open(path))
except OSError:
    st = {"default": 40, "volume": 0.40, "muted": False}
a = sys.argv[1:]
if a[0] == "inspect":
    print(f"id {st['default']}, type PipeWire:Interface:Node")
elif a[0] == "get-volume":
    print(f"Volume: {st['volume']:.2f}" + (" [MUTED]" if st["muted"] else ""))
elif a[0] == "set-volume":
    step = a[-1]
    delta = float(step[:-2]) / 100 * (1 if step.endswith("+") else -1)
    st["volume"] = round(min(1.0, max(0.0, st["volume"] + delta)), 2)
elif a[0] == "set-mute":
    st["muted"] = not st["muted"]
elif a[0] == "set-default":
    st["default"] = int(a[1])
json.dump(st, open(path, "w"))
"""
with tempfile.TemporaryDirectory() as home:
    fake = Path(home, "bin")
    fake.mkdir()
    for name, body in (("bluetoothctl", FAKE_BT), ("pw-dump", FAKE_PWDUMP), ("wpctl", FAKE_WPCTL)):
        (fake / name).write_text(body)
        (fake / name).chmod(0o755)
    s = Session(80, 24, home=home, env={"PATH": f"{fake}:{os.environ['PATH']}"})
    s.pump(0.6)
    s.send("x", 1.0)
    check("dashboard shows volume keys", "+/-" in s.text())
    s.send("b", 1.5)
    menu_text = s.text()
    check("b opens Bluetooth & sound", "BLUETOOTH & SOUND" in menu_text and "Bluetooth on" in menu_text
          and "Built-in Audio HDMI" in menu_text and "40%" in menu_text)
    s.send("\r", 3.0)
    found = s.text()
    check("scan lists named devices nearest first", "WH-1000XM4  [headphones]  -48 dBm" in found
          and found.index("WH-1000XM4") < found.index("MX Keys"))
    s.send("\r", 4.0)
    wp = json.loads(Path(home, "wp.json").read_text()) if Path(home, "wp.json").exists() else {}
    check("pairing connects and switches sound to headphones",
          "Connected to WH-1000XM4. Sound now plays there." in s.text() and wp.get("default") == 77)
    bt = json.loads(Path(home, "bt.json").read_text())["known"]["AA:BB:CC:00:00:01"]
    check("headphones paired and trusted", bt.get("paired") and bt.get("trusted") and bt.get("connected"))
    s.send("\r", 1.5)
    check("menu shows connected device and its output", "connected: WH-1000XM4" in s.text()
          and "Sound: WH-1000XM4" in s.text())
    for key, wait in [(DOWN, 0.2), ("\r", 2.0)]:
        s.send(key, wait)
    check("paired list shows battery", "● WH-1000XM4  [headphones]  80%" in s.text())
    for key, wait in [("\r", 1.5), (DOWN * 2, 0.2), ("\r", 1.0)]:
        s.send(key, wait)
    prefs = json.loads(Path(home, ".config/nightdeck/settings.json").read_text())
    check("auto-connect at startup saved", prefs.get("bt_auto") == "AA:BB:CC:00:00:01")
    for key, wait in [("\x1b", 0.6), ("\x1b", 0.6)]:
        s.send(key, wait)
    s.pump(6.0)
    check("header shows connected headphones", "♪ WH-1000XM4" in s.text())
    check("vitals show the sound output", "SND  WH-1000XM4 40%" in s.text())
    s.send("+", 0.8)
    check("+ raises volume with a flash", "VOLUME 45%" in s.raw.decode("utf-8", "replace")
          and json.loads(Path(home, "wp.json").read_text())["volume"] == 0.45)
    s.send("m", 0.8)
    check("m mutes", json.loads(Path(home, "wp.json").read_text())["muted"] is True)
    for key, wait in QUIT:
        s.send(key, wait)
    check("bluetooth session exits cleanly", s.finish() == 0)

print("\n" + ("ALL PASSED" if not failures else f"{len(failures)} FAILED"))
sys.exit(1 if failures else 0)
