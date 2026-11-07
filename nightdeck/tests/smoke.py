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

print("\n" + ("ALL PASSED" if not failures else f"{len(failures)} FAILED"))
sys.exit(1 if failures else 0)
