"""Terminal regression checks for Nightdeck. Needs: pip install pyte.

Run: python3 tests/smoke.py   (writes nothing outside a temporary HOME)
"""
import json, subprocess, sys, tempfile
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

print("\n" + ("ALL PASSED" if not failures else f"{len(failures)} FAILED"))
sys.exit(1 if failures else 0)
