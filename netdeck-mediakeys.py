#!/usr/bin/python3 -I
"""netdeck-mediakeys: laptop media keys for the NETDECK//OS login session.

GNOME handles volume / brightness / media keys in the Ubuntu session; the NETDECK session runs without GNOME,
so this small root service does it instead - but ONLY while the active session on seat0 is the NETDECK one.
It watches input devices for these keys and nothing else:

  volume up / down / mute, mic mute      -> PipeWire (wpctl) or PulseAudio (pactl), as the logged-in user
  brightness up / down                   -> /sys/class/backlight
  play-pause / next / previous / stop    -> netdeck --media (the deck's radio, else Spotify & co via playerctl)

Each action writes a one-line message to ~/.cache/netdeck/osd so the deck can show it as a toast.
Installed by install.sh --session as /usr/local/sbin/netdeck-mediakeys + netdeck-mediakeys.service.
"""
import glob
import os
import pwd
import select
import struct
import subprocess
import time

EV_KEY = 1
KEYS = {113: "mute", 114: "voldown", 115: "volup", 248: "micmute", 224: "brightdown", 225: "brightup",
        164: "playpause", 200: "playpause", 201: "playpause", 163: "next", 165: "prev", 166: "stop"}
REPEATABLE = {"voldown", "volup", "brightdown", "brightup"}
EVENT = struct.Struct("llHHi")  # struct input_event on 64-bit Linux
_session = {"t": 0.0, "user": None}


def deck_user():
    """The user of the active seat0 session if it is a NETDECK session, else None (cached for 2 s)."""
    now = time.monotonic()
    if now - _session["t"] < 2:
        return _session["user"]
    user = None
    try:
        sid = subprocess.run(["loginctl", "show-seat", "seat0", "-p", "ActiveSession", "--value"],
                             capture_output=True, text=True, timeout=2).stdout.strip()
        if sid:
            out = subprocess.run(["loginctl", "show-session", sid, "-p", "Desktop", "-p", "Name", "--value"],
                                 capture_output=True, text=True, timeout=2).stdout.split("\n")
            desktop, name = (out + ["", ""])[:2]
            if "netdeck" in desktop.lower() and name:
                user = pwd.getpwnam(name)
    except (OSError, subprocess.SubprocessError, KeyError):
        user = None
    _session.update(t=now, user=user)
    return user


def as_user(user, argv, capture=False):
    env = ["env", f"HOME={user.pw_dir}", f"XDG_RUNTIME_DIR=/run/user/{user.pw_uid}",
           f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{user.pw_uid}/bus",
           "PATH=/usr/local/bin:/usr/bin:/bin:/snap/bin:" + os.path.join(user.pw_dir, ".local/bin")]
    r = subprocess.run(["runuser", "-u", user.pw_name, "--"] + env + argv, capture_output=True, text=True, timeout=4)
    return r.stdout if capture else r.returncode == 0


def osd(user, text):
    as_user(user, ["sh", "-c", 'mkdir -p "$HOME/.cache/netdeck" && printf "%s\\n" "$1" > "$HOME/.cache/netdeck/osd"',
                   "sh", text])


def have(user, prog):
    return as_user(user, ["sh", "-c", f"command -v {prog} >/dev/null"])


def volume(user, action):
    if have(user, "wpctl"):
        sink, src = "@DEFAULT_AUDIO_SINK@", "@DEFAULT_AUDIO_SOURCE@"
        if action == "volup":
            as_user(user, ["wpctl", "set-mute", sink, "0"])
            as_user(user, ["wpctl", "set-volume", "-l", "1.0", sink, "5%+"])
        elif action == "voldown":
            as_user(user, ["wpctl", "set-volume", sink, "5%-"])
        elif action == "mute":
            as_user(user, ["wpctl", "set-mute", sink, "toggle"])
        elif action == "micmute":
            as_user(user, ["wpctl", "set-mute", src, "toggle"])
            out = as_user(user, ["wpctl", "get-volume", src], capture=True)
            return osd(user, "MIC|" + ("MUTED" if "MUTED" in out else "LIVE"))
        out = as_user(user, ["wpctl", "get-volume", sink], capture=True)  # "Volume: 0.45 [MUTED]"
        try:
            pct = round(float(out.split()[1]) * 100)
        except (IndexError, ValueError):
            pct = -1
        return osd(user, f"VOLUME|{pct}|{'MUTED' if 'MUTED' in out else ''}")
    if have(user, "pactl"):
        sink = "@DEFAULT_SINK@"
        cmd = {"volup": ["set-sink-volume", sink, "+5%"], "voldown": ["set-sink-volume", sink, "-5%"],
               "mute": ["set-sink-mute", sink, "toggle"], "micmute": ["set-source-mute", "@DEFAULT_SOURCE@", "toggle"]}
        as_user(user, ["pactl"] + cmd[action])
        out = as_user(user, ["pactl", "get-sink-volume", sink], capture=True)
        pct = next((int(t.rstrip("%")) for t in out.split() if t.endswith("%") and t[:-1].isdigit()), -1)
        muted = "yes" in as_user(user, ["pactl", "get-sink-mute", sink], capture=True)
        return osd(user, f"VOLUME|{pct}|{'MUTED' if muted else ''}")


def brightness(user, action):
    devs = sorted(glob.glob("/sys/class/backlight/*"))
    if not devs:
        return
    dev = devs[0]
    try:
        mx = int(open(f"{dev}/max_brightness").read())
        cur = int(open(f"{dev}/brightness").read())
    except (OSError, ValueError):
        return
    step = max(1, mx // 20)
    new = min(mx, cur + step) if action == "brightup" else max(max(1, mx // 100), cur - step)
    try:
        with open(f"{dev}/brightness", "w") as fh:
            fh.write(str(new))
    except OSError:
        return
    osd(user, f"BRIGHTNESS|{round(new * 100 / mx)}|")


def media(user, action):
    deck = os.path.join(user.pw_dir, ".local/bin/netdeck")
    if os.access(deck, os.X_OK):
        as_user(user, [deck, "--media", action])
    else:
        as_user(user, ["playerctl", {"playpause": "play-pause", "prev": "previous"}.get(action, action)])


def handle(action):
    user = deck_user()
    if not user:
        return  # Ubuntu (GNOME) or the login screen handles its own keys
    if action in ("volup", "voldown", "mute", "micmute"):
        volume(user, action)
    elif action in ("brightup", "brightdown"):
        brightness(user, action)
    else:
        media(user, action)


def main():
    fds = {}
    last_scan = 0.0
    while True:
        if time.monotonic() - last_scan > 5:  # pick up keyboards that come and go
            last_scan = time.monotonic()
            for path in glob.glob("/dev/input/event*"):
                if path not in fds.values():
                    try:
                        fds[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
                    except OSError:
                        pass
        if not fds:
            time.sleep(2)
            continue
        ready, _, _ = select.select(list(fds), [], [], 5)
        for fd in ready:
            try:
                data = os.read(fd, EVENT.size * 64)
            except OSError:
                os.close(fd)
                fds.pop(fd, None)
                continue
            for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _s, _us, etype, code, value = EVENT.unpack_from(data, i)
                action = KEYS.get(code) if etype == EV_KEY else None
                if action and (value == 1 or (value == 2 and action in REPEATABLE)):
                    try:
                        handle(action)
                    except Exception:
                        pass


if __name__ == "__main__":
    main()
