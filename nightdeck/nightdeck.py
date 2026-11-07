#!/usr/bin/env python3
"""Nightdeck // cyberdeck field terminal."""
import curses
import datetime
import fcntl
import json
import locale
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unicodedata
import urllib.request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

VERSION = "2.0"
HOME = Path.home()
DATA = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share") / "nightdeck"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "nightdeck"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache") / "nightdeck"
REPOS = HOME / "repos"
NOTES = DATA / "notes"
THEMES = {
    "Cyberdeck": ("FF003C", "FFEE08", "00FFFF", "1DED83", "FAFAFA", "0E0E0E"),
    "Amber": ("FF8050", "FFCA70", "F5AA46", "FFE1A0", "FFF2D4", "161009"),
    "Ice": ("5CA7FF", "B3EAFF", "7BF5FF", "80FFD2", "EDF8FF", "0A1420"),
}
COLOR_ROLES = ("Header", "Selection", "Hints", "Vitals", "Text", "Background")
GLYPH_MODES = ("auto", "unicode", "console", "ascii")
SETTINGS_FILE = CONFIG / "settings.json"
COLOR = re.compile(r"[0-9a-fA-F]{6}")
FEEDS = (
    ("svt", "SE / SVT Nyheter", "https://www.svt.se/nyheter/rss.xml"),
    ("ekot", "SE / Ekot (broadcast headlines)", "https://api.sr.se/api/rss/program/4540"),
    ("bbc", "WORLD / BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("guardian", "WORLD / The Guardian", "https://www.theguardian.com/world/rss"),
)
LIMIT = 2 * 1024 * 1024
EXIT_SHELL = 10  # tells the login autostart to keep the shell open
HOST = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@:%-]*")
REMOTE_DIR = re.compile(r"[A-Za-z0-9_./~-]{0,200}")
CLAUDE_INSTALL = "curl -fsSL https://claude.ai/install.sh | bash"
VIDEOS = HOME / "Videos"
WATCH = DATA / "watchlist.json"
WATCH_MAX = 500
MEDIA_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".ts", ".ogv", ".flv",
             ".wmv", ".3gp", ".mp3", ".flac", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".aac"}
VIDEO_OUTPUTS = ("ask", "screen", "terminal")
# 480p H.264 fits the 800x480 panel and is what the Pi 3B can decode in hardware.
YTDL_FORMAT = "bestvideo[height<=?480][vcodec^=avc1]+bestaudio/best[height<=?480]/best"
MPV_KEYS = "space pause  //  left/right seek  //  9/0 volume  //  m mute  //  q stop"

# Color pairs
HEAD, SEL, HINT, VIT, TEXT, DIM, BADGE, SELBAR, KEYCAP = range(1, 10)

GLYPHS = {
    "unicode": {
        "h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "lj": "┤", "rj": "├",
        "full": "█", "empty": "░", "spark": "▁▂▃▄▅▆▇█", "spin": "▖▘▝▗", "ptr": "▶",
        "on": "●", "off": "○", "bar": "▌", "sep": "·", "up": "▲", "down": "▼",
        "noise": "▓▒░█▚▞▙▟", "keys": "↑↓", "wire": "///", "cursor": "█",
        "logo": ("█▄ █ █ █▀▀ █ █ ▀█▀ █▀▄ █▀▀ █▀▀ █▄▀",
                 "█ ▀█ █ █▄█ █▀█  █  █▄▀ ██▄ █▄▄ █ █"),
    },
    # Linux console fonts carry the VGA (CP437) set: box drawing, shades, half blocks, arrows.
    "console": {
        "h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "lj": "┤", "rj": "├",
        "full": "█", "empty": "░", "spark": "▄█", "spin": "░▒▓█", "ptr": "►",
        "on": "■", "off": "·", "bar": "▌", "sep": "·", "up": "▲", "down": "▼",
        "noise": "░▒▓█▀▄", "keys": "↑↓", "wire": "///", "cursor": "█",
        "logo": ("█▄ █ █ █▀▀ █ █ ▀█▀ █▀▄ █▀▀ █▀▀ █▄▀",
                 "█ ▀█ █ █▄█ █▀█  █  █▄▀ ██▄ █▄▄ █ █"),
    },
    "ascii": {
        "h": "-", "v": "|", "tl": "+", "tr": "+", "bl": "+", "br": "+", "lj": "[", "rj": "]",
        "full": "#", "empty": ".", "spark": "_.-=+*#@", "spin": "|/-\\", "ptr": ">",
        "on": "*", "off": "o", "bar": "|", "sep": "-", "up": "^", "down": "v",
        "noise": "#%@&$?!", "keys": "jk", "wire": "///", "cursor": "_",
        "logo": ("|\\ | | /~~ |_| ~|~ |~\\ |~~ /~~ |/",
                 "| \\| | \\_/ | |  |  |_/ |__ \\__ |\\"),
    },
}


def clean(value):
    return "".join(c for c in value if not unicodedata.category(c).startswith("C"))


def display_line(value):
    return re.sub(r"(?:https?|ssh)://[^/\s@]+@", "<credentials>@", clean(value))


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value)
    return clean(" ".join(" ".join(parser.parts).split()))


def public_url(value, schemes=("https",), allow_query=False):
    try:
        url = urlsplit(value)
        return (url.scheme in schemes and url.hostname and not url.username
                and not url.password and (allow_query or not url.query) and not url.fragment
                and not any(c.isspace() for c in value) and clean(value) == value)
    except ValueError:
        return False


def parse_feed(raw):
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", raw.replace(b"\0", b""), re.I):
        raise ValueError("Feed contains a document type or entity declaration.")
    root = ET.fromstring(raw)
    if root.tag == "rss":
        entries = root.findall("./channel/item")
    elif root.tag == "{http://www.w3.org/2005/Atom}feed":
        entries = root.findall("{*}entry")
    else:
        raise ValueError("Publisher did not return RSS or Atom.")
    results = []
    for entry in entries[:50]:
        link_node = next((n for n in entry.findall("{*}link")
                          if n.get("rel", "alternate") == "alternate"), None)
        link = (link_node.get("href") or link_node.text or "").strip() if link_node is not None else ""
        title = plain(entry.findtext("{*}title", ""))[:250]
        summary = (entry.findtext("{*}description") or entry.findtext("{*}summary")
                   or entry.findtext("{*}content") or "")
        if title:
            results.append({
                "title": title, "summary": plain(summary)[:5000],
                "date": clean(entry.findtext("{*}pubDate") or entry.findtext("{*}updated") or "")[:100],
                "link": link if public_url(link, ("https", "http"), allow_query=True) else "",
            })
    if not results:
        raise ValueError("Publisher returned no readable headlines.")
    return results


def refresh_feed(key, url):
    request = urllib.request.Request(url, headers={"User-Agent": "Nightdeck/" + VERSION})
    with urllib.request.urlopen(request, timeout=6) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise ValueError("Feed redirected away from HTTPS.")
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("Feed exceeded the 2 MiB limit.")
    entries = parse_feed(raw)
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CACHE, delete=False)
    temp = Path(file.name)
    try:
        with file:
            json.dump({"saved": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
                       "items": entries}, file, ensure_ascii=False)
        temp.replace(CACHE / (key + ".json"))
    finally:
        temp.unlink(missing_ok=True)
    return len(entries)


def read_cache(key):
    try:
        cached = json.loads((CACHE / (key + ".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cached if isinstance(cached, dict) else {}


def git_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_TRACE") or key == "GIT_CURL_VERBOSE":
            env.pop(key)
    env["GIT_ALLOW_PROTOCOL"] = "https:ssh"
    return env


def repo_url(value):
    return public_url(value) or bool(re.fullmatch(
        r"[A-Za-z0-9._-]+@[A-Za-z0-9][A-Za-z0-9.-]*:[A-Za-z0-9._/~%-]+", value
    ))


def load_settings():
    defaults = {"theme": "Cyberdeck", "custom": list(THEMES["Cyberdeck"]),
                "fx": True, "boot": True, "glyphs": "auto", "claude_host": "", "claude_dir": "",
                "video_out": "ask"}
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(saved, dict):
        return defaults
    theme = saved.get("theme")
    if isinstance(theme, str) and (theme in THEMES or theme == "Custom"):
        defaults["theme"] = theme
    custom = saved.get("custom")
    if isinstance(custom, list) and len(custom) == len(COLOR_ROLES) and all(
        isinstance(value, str) and COLOR.fullmatch(value) for value in custom
    ):
        defaults["custom"] = custom
    if saved.get("video_out") in VIDEO_OUTPUTS:
        defaults["video_out"] = saved["video_out"]
    if isinstance(saved.get("claude_host"), str) and HOST.fullmatch(saved["claude_host"]):
        defaults["claude_host"] = saved["claude_host"]
    if isinstance(saved.get("claude_dir"), str) and REMOTE_DIR.fullmatch(saved["claude_dir"]):
        defaults["claude_dir"] = saved["claude_dir"]
    for flag in ("fx", "boot"):
        if isinstance(saved.get(flag), bool):
            defaults[flag] = saved[flag]
    if saved.get("glyphs") in GLYPH_MODES:
        defaults["glyphs"] = saved["glyphs"]
    return defaults


def save_settings(settings):
    CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG, delete=False) as file:
        path = Path(file.name)
        try:
            with file:
                json.dump(settings, file, indent=2)
            path.replace(SETTINGS_FILE)
        finally:
            path.unlink(missing_ok=True)


def network_link():
    """Default-route interface, local address and Wi-Fi signal. Sends no packets."""
    iface = ip = signal = None
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) > 2 and parts[1] == "00000000":
                iface = parts[0]
                break
    except OSError:
        pass
    if iface:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.0.2.1", 9))  # UDP connect only selects a route
                ip = probe.getsockname()[0]
        except OSError:
            pass
        try:
            for line in Path("/proc/net/wireless").read_text().splitlines()[2:]:
                name, _, rest = line.partition(":")
                if name.strip() == iface:
                    quality = float(rest.split()[1].rstrip("."))
                    signal = max(0, min(100, round(quality * 100 / 70)))
        except (OSError, ValueError, IndexError):
            pass
    return iface, ip, signal


class Telemetry:
    def __init__(self):
        self.previous = None
        self.history = []
        self.data = {}
        self.stamp = 0.0
        self.link_stamp = 0.0
        self.link = (None, None, None)
        self.traffic = None

    def cpu(self):
        try:
            values = [int(v) for v in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:9]]
        except (OSError, ValueError):
            return None
        idle, total = values[3] + (values[4] if len(values) > 4 else 0), sum(values)
        previous, self.previous = self.previous, (idle, total)
        if not previous or total <= previous[1]:
            return None
        return 100 * (1 - (idle - previous[0]) / (total - previous[1]))

    def throughput(self, iface, now):
        if not iface:
            return None
        try:
            for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
                name, _, rest = line.partition(":")
                if name.strip() == iface:
                    fields = rest.split()
                    sample = (now, int(fields[0]), int(fields[8]))
                    break
            else:
                return None
        except (OSError, ValueError, IndexError):
            return None
        previous, self.traffic = self.traffic, sample
        if not previous or sample[0] <= previous[0]:
            return None
        span = sample[0] - previous[0]
        return (max(0, sample[1] - previous[1]) / span, max(0, sample[2] - previous[2]) / span)

    def poll(self, force=False):
        now = time.monotonic()
        if not force and self.data and now - self.stamp < 1:
            return self.data
        self.stamp = now
        data = {"cpu": self.cpu()}
        if data["cpu"] is not None:
            self.history = (self.history + [data["cpu"]])[-120:]
        try:
            uptime = float(Path("/proc/uptime").read_text().split()[0])
            data["uptime"] = str(datetime.timedelta(seconds=int(uptime)))
            data["load"] = " ".join(Path("/proc/loadavg").read_text().split()[:3])
        except (OSError, ValueError, IndexError):
            pass
        try:
            mem = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, _, value = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    mem[key] = int(value.split()[0]) // 1024
            data["mem"] = (mem["MemTotal"] - mem["MemAvailable"], mem["MemTotal"])
        except (OSError, ValueError, IndexError, KeyError):
            pass
        try:
            disk = shutil.disk_usage(HOME)
            data["disk"] = (disk.used / 2**30, disk.total / 2**30, disk.free / 2**30)
        except OSError:
            pass
        try:
            data["temp"] = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
        except (OSError, ValueError):
            pass
        if force or now - self.link_stamp >= 5:
            self.link_stamp = now
            self.link = network_link()
        data["link"] = self.link
        data["net"] = self.throughput(self.link[0], now)
        self.data = data
        return data


def rate(value):
    for unit in ("B", "K", "M", "G"):
        if value < 1000 or unit == "G":
            return f"{value:.0f}{unit}/s" if unit == "B" else f"{value:.1f}{unit}/s"
        value /= 1024


def size_label(count):
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1000 or unit == "GB":
            return f"{count:.0f} {unit}" if unit == "B" else f"{count:.1f} {unit}"
        count /= 1000


def nearest_terminal_color(color):
    rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    cube = (0, 95, 135, 175, 215, 255)
    candidates = [(r, g, b) for r in cube for g in cube for b in cube]
    candidates.extend((level,) * 3 for level in range(8, 239, 10))
    return 16 + min(range(len(candidates)),
                    key=lambda index: sum((a - b) ** 2 for a, b in zip(rgb, candidates[index])))


def blend(top, bottom, amount):
    return "".join(f"{round(int(top[i:i+2], 16) * amount + int(bottom[i:i+2], 16) * (1 - amount)):02X}"
                   for i in (0, 2, 4))


class Deck:
    def __init__(self, screen):
        self.screen = screen
        self.screen.keypad(True)
        curses.set_escdelay(35)
        self.cursor(False)
        self.colors = False
        self.basic = True
        self.preferences = load_settings()
        self.telemetry = Telemetry()
        self.host = clean(socket.gethostname()) or "deck"
        self.user = clean(os.environ.get("USER") or "deck")
        self.shown_title = None
        self.started = self.launched = time.monotonic()
        self.wire = ""
        self.apply_theme()
        self.apply_glyphs()

    # ---------- look ----------

    def apply_glyphs(self):
        mode = self.preferences["glyphs"]
        if mode == "auto":
            try:  # what curses sees; Python's UTF-8 mode can mask a plain C locale
                encoding = locale.nl_langinfo(locale.CODESET)
            except (AttributeError, ValueError):
                encoding = locale.getpreferredencoding(False)
            encoding = (encoding or "").upper().replace("-", "")
            if encoding != "UTF8":
                mode = "ascii"
            else:
                mode = "console" if os.environ.get("TERM", "").startswith("linux") else "unicode"
        self.g = GLYPHS[mode]

    def apply_theme(self):
        if not curses.has_colors():
            return
        curses.start_color()
        name = self.preferences["theme"]
        palette = list(THEMES.get(name, self.preferences["custom"]))
        palette.insert(5, blend(palette[0], palette[5], 0.6))  # dim shade of the header color
        if curses.COLORS >= 256:
            self.basic = False
            indexes = [nearest_terminal_color(color) for color in palette]
            if curses.can_change_color():
                indexes = list(range(16, 16 + len(palette)))
                for index, color in zip(indexes, palette):
                    rgb = [round(int(color[i:i+2], 16) * 1000 / 255) for i in (0, 2, 4)]
                    curses.init_color(index, *rgb)
            head, sel, hint, vit, text, dim, background = indexes
        else:
            self.basic = True
            head, sel, hint, vit, text, dim, background = (
                curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_CYAN, curses.COLOR_GREEN,
                curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_BLACK)
        pairs = {HEAD: (head, background), SEL: (sel, background), HINT: (hint, background),
                 VIT: (vit, background), TEXT: (text, background), DIM: (dim, background),
                 BADGE: (background, head), SELBAR: (background, sel), KEYCAP: (background, hint)}
        for pair, (foreground, back) in pairs.items():
            curses.init_pair(pair, foreground, back)
        self.colors = True
        self.screen.clearok(True)

    def cursor(self, visible):
        try:
            curses.curs_set(int(visible))
        except curses.error:
            pass

    def style(self, pair=TEXT, bold=False, reverse=False):
        style = curses.color_pair(pair) if self.colors else 0
        if not self.colors and pair in (BADGE, SELBAR, KEYCAP):
            style |= curses.A_REVERSE
        if pair in (HEAD, BADGE, SELBAR) and self.basic:
            bold = True
        return style | (curses.A_BOLD if bold else 0) | (curses.A_REVERSE if reverse else 0)

    def put(self, row, value, pair=TEXT, bold=False, reverse=False, column=1, limit=None):
        height, width = self.screen.getmaxyx()
        if not 0 <= row < height or not 0 <= column < width:
            return column
        room = width - column - (1 if row == height - 1 else 0)
        if limit is not None:
            room = min(room, limit)
        if room <= 0:
            return column
        value = value[:room]
        try:
            self.screen.addnstr(row, column, value, room, self.style(pair, bold, reverse))
        except curses.error:
            pass
        return column + len(value)

    def rule(self, row, pair=DIM, column=0, length=None):
        width = self.screen.getmaxyx()[1]
        length = width - column if length is None else length
        self.put(row, self.g["h"] * max(0, length), pair, column=column)

    def box(self, top, left, height, width, title="", pair=DIM, title_pair=HINT):
        g = self.g
        if height < 2 or width < 4:
            return
        self.put(top, g["tl"] + g["h"] * (width - 2) + g["tr"], pair, column=left)
        for row in range(top + 1, top + height - 1):
            self.put(row, g["v"], pair, column=left)
            self.put(row, g["v"], pair, column=left + width - 1)
        self.put(top + height - 1, g["bl"] + g["h"] * (width - 2) + g["br"], pair, column=left)
        if title and width > len(title) + 6:
            column = self.put(top, g["lj"], pair, column=left + 2)
            column = self.put(top, " " + title + " ", title_pair, True, column=column)
            self.put(top, g["rj"], pair, column=column)

    def noise(self, text, amount):
        return "".join(random.choice(self.g["noise"]) if c != " " and random.random() < amount else c
                       for c in text)

    def keycaps(self, row, hints):
        _, width = self.screen.getmaxyx()
        column = 1
        for key, label in hints:
            if column + len(key) + len(label) + 4 > width:
                break
            column = self.put(row, " " + key + " ", KEYCAP, True, column=column)
            column = self.put(row, " " + label + "  ", DIM, column=column)

    def header(self):
        _, width = self.screen.getmaxyx()
        second = int(time.time())
        column = self.put(0, " " + self.g["bar"] + "NIGHTDECK ", BADGE, True, column=0)
        link = self.telemetry.data.get("link") or self.telemetry.link
        online = bool(link and link[1])
        status = "SIGNAL::ONLINE" if online else "SIGNAL::LOST"
        if width >= 56:
            column = self.put(0, " " + self.host.upper(), HEAD, True, column=column)
            self.put(0, " // " + status, HEAD if online else SEL, column=column)
        clock = datetime.datetime.now().strftime("%H:%M:%S")
        if width >= 34:
            beacon = self.g["on"] if second % 2 or not self.preferences["fx"] else self.g["off"]
            right = width - len(clock) - 4
            self.put(0, beacon, VIT if online else HEAD, True, column=right)
            self.put(0, clock, HINT, True, column=right + 2)

    def reveal(self, row, text, pair, column=1, bold=True):
        """Decrypt-style text reveal used on screen changes."""
        if not self.preferences["fx"]:
            self.put(row, text, pair, bold, column=column)
            return
        for step in range(1, 5):
            shown = len(text) * step // 4
            self.put(row, text[:shown] + self.noise(text[shown:], 0.9), pair, bold, column=column)
            self.screen.refresh()
            curses.napms(18)
        self.put(row, text, pair, bold, column=column)

    def frame(self, title, hints, info=""):
        if self.colors:
            self.screen.bkgd(" ", self.style(TEXT))
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        self.telemetry.poll()
        self.header()
        self.rule(1)
        heading = self.g["bar"] + " " + clean(title)
        if info and width > len(heading) + len(info) + 6:
            self.put(2, info, DIM, column=width - len(info) - 2)
        self.put(3, self.g["h"] * min(width - 2, len(heading) + 2), HEAD, column=1)
        self.rule(height - 2)
        self.keycaps(height - 1, hints)
        if title != self.shown_title:
            self.shown_title = title
            self.reveal(2, heading, SEL)
        else:
            self.put(2, heading, SEL, True)
        return height, width

    # ---------- widgets ----------

    def menu(self, title, choices, intro=None, selected=0):
        if not choices:
            self.view(title, "No entries.")
            return None
        selected = max(0, min(selected, len(choices) - 1))
        hints = [(self.g["keys"], "move"), ("enter", "select"), ("esc", "back")]
        while True:
            height, width = self.frame(title, hints, f"[{selected + 1:02d}/{len(choices):02d}]")
            row = 4
            for line in intro or []:
                if isinstance(line, list):  # pre-styled segments: [(text, pair), ...]
                    column = 2
                    for text, pair in line:
                        column = self.put(row, text, pair, True, column=column)
                    row += 1
                    continue
                pair = HINT if line.startswith("$ ") else TEXT
                for part in textwrap.wrap(display_line(line), max(1, width - 4)) or [""]:
                    if row < height - 4:
                        self.put(row, part, pair, column=2)
                        row += 1
            if intro:
                row += 1
            count = max(1, height - 2 - row)
            start = max(0, min(selected - count // 2, len(choices) - count))
            inner = max(1, width - 4)
            for index in range(start, min(len(choices), start + count)):
                number = f"{index + 1:02d}"
                text = clean(choices[index])
                line_row = row + index - start
                if index == selected:
                    self.put(line_row, f" {self.g['ptr']} {number}  {text}".ljust(inner), SELBAR, True,
                             column=1, limit=inner)
                else:
                    column = self.put(line_row, f"   {number}  ", DIM, column=1)
                    self.put(line_row, text, TEXT, column=column, limit=inner - column + 1)
            if start > 0:
                self.put(row, self.g["up"], HINT, True, column=width - 2)
            if start + count < len(choices):
                self.put(row + count - 1, self.g["down"], HINT, True, column=width - 2)
            key = self.screen.getch()
            if key in (27, ord("q")):
                return None
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(choices)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(choices)
            elif key == curses.KEY_PPAGE:
                selected = max(0, selected - count)
            elif key == curses.KEY_NPAGE:
                selected = min(len(choices) - 1, selected + count)
            elif key in (curses.KEY_HOME, ord("g")):
                selected = 0
            elif key in (curses.KEY_END, ord("G")):
                selected = len(choices) - 1

    @staticmethod
    def line_pair(line, kind):
        if kind != "git":
            if line.startswith(("# ", "## ", "### ")):
                return SEL, True
            return TEXT, False
        if line.startswith(("+++", "---")):
            return SEL, True
        if line.startswith("+"):
            return VIT, False
        if line.startswith("-"):
            return HEAD, False
        if line.startswith("@@"):
            return HINT, False
        if line.startswith(("diff ", "index ", "commit ")):
            return SEL, True
        if line.startswith("## "):
            return HINT, True
        if line.startswith("$ ") or line.startswith("Exit status"):
            return DIM, False
        if line.startswith("* "):
            return VIT, True
        if line.startswith("??"):
            return HEAD, False
        if re.match(r"^[MADRCU][ MADRCU] ", line):
            return VIT, False
        if re.match(r"^ [MADRCU] ", line):
            return SEL, False
        return TEXT, False

    def view(self, title, body, kind=None):
        offset = 0
        hints = [(self.g["keys"], "scroll"), ("pgup/dn", "page"), ("esc", "back")]
        while True:
            _, width = self.screen.getmaxyx()
            lines = []
            for line in body.splitlines():
                pair = self.line_pair(line, kind)
                for part in (textwrap.wrap(display_line(line.expandtabs(4)), max(1, width - 4),
                                           replace_whitespace=False) or [""]):
                    lines.append((part, pair))
            height, _ = self.screen.getmaxyx()
            page = max(1, height - 6)
            offset = max(0, min(offset, len(lines) - page))
            info = f"{100 * min(len(lines), offset + page) // max(1, len(lines)):3d}%"
            height, width = self.frame(title, hints, info if len(lines) > page else "")
            for row, (line, (pair, bold)) in enumerate(lines[offset:offset + page], 4):
                self.put(row, line, pair, bold, column=1)
            if len(lines) > page:
                thumb = max(1, page * page // len(lines))
                position = (page - thumb) * offset // max(1, len(lines) - page)
                for row in range(page):
                    inside = position <= row < position + thumb
                    self.put(4 + row, self.g["full"] if inside else self.g["v"],
                             HINT if inside else DIM, column=width - 2)
            key = self.screen.getch()
            if key in (27, ord("q"), 10, 13):
                return
            offset += {curses.KEY_DOWN: 1, ord("j"): 1, curses.KEY_UP: -1,
                       ord("k"): -1, curses.KEY_NPAGE: page, ord(" "): page,
                       curses.KEY_PPAGE: -page, curses.KEY_HOME: -len(lines),
                       ord("g"): -len(lines), curses.KEY_END: len(lines),
                       ord("G"): len(lines)}.get(key, 0)

    def notice(self, title, body, ok=True):
        tag = "[ OK ] " if ok else "[ !! ] "
        self.view(title, tag + body)

    def ask(self, label, hidden=False, prefix="> ", completions=None):
        value = ""
        hints = [("enter", "accept"), ("esc", "cancel")] + ([("tab", "complete")] if completions else [])
        self.cursor(not hidden)
        try:
            while True:
                height, width = self.frame(label, hints)
                matches = [c for c in completions or [] if c.startswith(value.lstrip("/"))]
                if completions:
                    self.put(7, "// available", DIM, column=2)
                    column, row = 2, 8
                    for name in completions:
                        if column + len(name) + 3 > width - 2:
                            column, row = 2, row + 1
                        if row >= height - 3:
                            break
                        column = self.put(row, "/" + name, VIT if name in matches and value else HINT,
                                          name in matches and bool(value), column=column) + 2
                self.put(4, "// input" + ("  (hidden)" if hidden else ""), DIM, column=2)
                column = self.put(5, self.g["ptr"] + " ", SEL, True, column=2)
                if hidden:
                    self.put(5, self.g["sep"] * min(len(value), width - 8), DIM, column=column)
                else:
                    column = self.put(5, prefix, HEAD, True, column=column)
                    self.put(5, value[-max(1, width - column - 2):], TEXT, True, column=column)
                key = self.screen.get_wch()
                if key == "\x1b":
                    return None
                if key in ("\n", "\r", curses.KEY_ENTER):
                    return value
                if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                    value = value[:-1]
                elif key == "\t" and completions and len(matches) == 1:
                    value = matches[0]
                elif isinstance(key, str) and key.isprintable() and len(value) < 4096:
                    value += key
        finally:
            self.cursor(False)

    def confirm(self, title, args):
        command = display_line(shlex.join(map(str, args)))
        return self.menu(title, ["Cancel", "Run command"],
                         intro=["Review the command before it runs:", "$ " + command]) == 1

    def busy(self, title, label, work):
        """Run work() in a thread while an uplink animation plays."""
        result = {}

        def target():
            try:
                result["value"] = work()
            except BaseException as error:  # re-raised on the curses thread
                result["error"] = error

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        step = 0
        while thread.is_alive():
            height, width = self.frame(title, [("wait", "uplink active")])
            spin = self.g["spin"][step % len(self.g["spin"])]
            self.put(5, spin + " " + label, HINT, True, column=2)
            span = max(4, min(40, width - 6))
            lit = step % (span + 6)
            trace = "".join(self.g["full"] if lit - 6 < i <= lit else self.g["empty"] for i in range(span))
            self.put(7, trace, VIT, column=2)
            self.put(8, self.noise("0x" + "".join(random.choice("0123456789ABCDEF") for _ in range(span - 2)), 0.1),
                     DIM, column=2)
            self.screen.refresh()
            thread.join(0.08)
            step += 1
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def run(self, args, cwd=None, pause=True, git=False, env=None):
        curses.def_prog_mode()
        curses.endwin()
        color = sys.stdout.isatty() and os.environ.get("TERM", "dumb") != "dumb"
        red, cyan, yellow, reset = ("\033[1;31m", "\033[36m", "\033[33m", "\033[0m") if color else ("",) * 4
        try:
            print(f"\n{red}{self.g['bar']}NIGHTDECK{reset} {cyan}$ "
                  + display_line(shlex.join(map(str, args))) + reset, flush=True)
            env = git_environment() if git else env
            code = subprocess.run(args, cwd=cwd, env=env, check=False).returncode
            if pause or code:
                print(f"\n{yellow}Exit status {code}{reset}")
                input("Press Enter to return to Nightdeck.")
            return code
        except (OSError, KeyboardInterrupt, EOFError) as exc:
            print("\nCommand interrupted or unavailable.", flush=True)
            if isinstance(exc, OSError):
                try:
                    input("Press Enter to return to Nightdeck.")
                except (EOFError, KeyboardInterrupt):
                    pass
            return None
        finally:
            curses.reset_prog_mode()
            self.screen.clearok(True)
            self.cursor(False)

    # ---------- boot / dashboard ----------

    def boot(self):
        height, width = self.screen.getmaxyx()
        if height < 12 or width < 40:
            return
        stats = self.telemetry.poll(force=True)
        _, ip, _ = stats.get("link", (None, None, None))
        feeds = sum(1 for key, _, _ in FEEDS if (CACHE / (key + ".json")).exists())
        try:
            repos = sum(1 for p in REPOS.iterdir() if (p / ".git").exists())
        except OSError:
            repos = 0
        temp = stats.get("temp")
        mem = stats.get("mem")
        steps = [
            ("KERNEL HANDSHAKE", os.uname().release, True),
            ("THERMAL SENSORS", f"{temp:.1f} C" if temp is not None else "NO PROBE", temp is None or temp < 75),
            ("MEMORY BANK", f"{mem[1]} MiB" if mem else "UNKNOWN", bool(mem)),
            ("NEURAL LINK", ip or "OFFLINE", bool(ip)),
            ("WIRE CACHE", f"{feeds}/{len(FEEDS)} FEEDS", feeds > 0),
            ("GIT WORKSPACE", f"{repos} REPOS", True),
        ]
        logo = self.g["logo"] if width >= len(self.g["logo"][0]) + 4 else ("NIGHTDECK",)
        if self.colors:
            self.screen.bkgd(" ", self.style(TEXT))
        self.screen.erase()
        self.screen.timeout(30)
        try:
            for step in range(8):
                for row, line in enumerate(logo):
                    self.put(1 + row, self.noise(line, 0.9 - step * 0.12), HEAD, True, column=2)
                self.put(1 + len(logo), f"FIELD TERMINAL // v{VERSION} // {self.host.upper()}", DIM, column=2)
                if self.screen.getch() != -1:
                    return
            self.screen.timeout(110)
            row = 3 + len(logo)
            leader = max(24, min(34, width - 32))
            for label, value, ok in steps:
                if row >= height - 2:
                    break
                tag, pair = ("[ OK ]", VIT) if ok else ("[ !! ]", SEL)
                column = self.put(row, tag, pair, True, column=2)
                column = self.put(row, " " + label + " ", HEAD, column=column)
                column = self.put(row, "." * max(2, leader - len(label)), DIM, column=column)
                self.put(row, " " + clean(value)[:width - column - 3], HINT, column=column)
                row += 1
                if self.screen.getch() != -1:
                    return
            if row + 1 < height - 1:
                self.screen.timeout(25)
                greeting = "WELCOME BACK, OPERATOR."
                for index in range(len(greeting) + 1):
                    self.put(row + 1, greeting[:index] + self.g["cursor"], SEL, True, column=2)
                    if self.screen.getch() != -1:
                        return
                self.screen.timeout(450)
                self.screen.getch()
        finally:
            self.screen.timeout(-1)
            self.started = time.monotonic()

    def jack_out(self):
        if not self.preferences["fx"]:
            return
        height, width = self.screen.getmaxyx()
        message = "[ CONNECTION TERMINATED ]"
        for step in range(6):
            self.screen.erase()
            span = max(0, (width - 2) * (5 - step) // 5)
            row = height // 2
            self.put(row - 1, self.g["h"] * span, DIM, column=(width - span) // 2)
            self.put(row, self.noise(message, 0.15 * step), HEAD, True,
                     column=max(0, (width - len(message)) // 2))
            self.put(row + 1, self.g["h"] * span, DIM, column=(width - span) // 2)
            self.screen.refresh()
            curses.napms(55)

    def load_wire(self):
        parts = []
        for key, label, _ in FEEDS:
            items = read_cache(key).get("items") or []
            tag = label.split("/")[-1].strip().split(" ")[0].upper()
            for item in items[:4]:
                if isinstance(item, dict) and item.get("title"):
                    parts.append(f"{tag} {self.g['ptr']} {clean(str(item['title']))}")
        gap = f"   {self.g['wire']}   "
        self.wire = gap.join(parts) + gap if parts else ""

    def meter(self, row, column, label, ratio, text, width):
        bar = max(4, width - 5 - len(text) - 1)
        ratio = 0.0 if ratio is None else max(0.0, min(1.0, ratio))
        filled = round(bar * ratio)
        pair = HEAD if ratio >= 0.9 else SEL if ratio >= 0.7 else VIT
        column = self.put(row, label.ljust(5), HINT, True, column=column)
        column = self.put(row, self.g["full"] * filled, pair, column=column)
        column = self.put(row, self.g["empty"] * (bar - filled), DIM, column=column)
        self.put(row, " " + text, TEXT, column=column)

    def graph(self, values, width, rows):
        """Multi-row bar graph of 0-100 values, newest on the right."""
        ticks = self.g["spark"]
        values = values[-width:]
        levels = [max(1, round(v / 100 * rows * len(ticks))) for v in values]
        lines = []
        for line in range(rows - 1, -1, -1):
            cells = []
            for level in levels:
                part = level - line * len(ticks)
                cells.append(" " if part <= 0 else ticks[min(len(ticks), part) - 1])
            lines.append("".join(cells).rjust(width))
        return lines

    def vitals_panel(self, top, left, height, width, stats, blink):
        self.box(top, left, height, width, "VITALS")
        column, inner = left + 2, width - 4
        bottom = top + height - 1
        rows = []
        cpu = stats.get("cpu")
        rows.append(("CPU", None if cpu is None else cpu / 100, "--" if cpu is None else f"{cpu:3.0f}%"))
        if "mem" in stats:
            used, total = stats["mem"]
            rows.append(("RAM", used / max(1, total), f"{used}/{total}M"))
        if "temp" in stats:
            rows.append(("TEMP", stats["temp"] / 85, f"{stats['temp']:.1f}C"))
        if "disk" in stats:
            used, total, free = stats["disk"]
            rows.append(("DISK", used / max(1, total), f"{free:.1f}G free"))
        row = top + 1
        for label, ratio, text in rows:
            if row >= bottom:
                return
            self.meter(row, column, label, ratio, text.rjust(11), inner)
            row += 1
        iface, ip, signal = stats.get("link") or (None, None, None)
        facts = [("LOAD", stats.get("load", "--"), TEXT), ("UP", stats.get("uptime", "--"), TEXT)]
        if ip:
            facts.append(("LINK", f"{iface} {ip}", VIT))
        else:
            facts.append(("LINK", "OFFLINE", HEAD))
        if stats.get("net"):
            down, up = stats["net"]
            facts.append(("NET", f"{self.g['down']} {rate(down)}  {self.g['up']} {rate(up)}", TEXT))
        if signal is not None:
            level = min(4, signal // 21)
            facts.append(("WIFI", (self.g["full"] * level).ljust(4, self.g["empty"]) + f" {signal}%", VIT))
        row += row < bottom - 4
        for label, value, pair in facts:
            if row >= bottom:
                return
            self.put(row, label.ljust(5), HINT, True, column=column)
            self.put(row, clean(value), pair, column=column + 5, limit=inner - 5)
            row += 1
        graph = min(5, bottom - row - 4)
        if graph >= 1 and self.telemetry.history:
            self.put(row + 1, "CPU TRACE", DIM, column=column)
            for line, text in enumerate(self.graph(self.telemetry.history, inner, graph)):
                self.put(row + 2 + line, text, VIT, column=column)
            row += 2 + graph
        if row < bottom - 1:
            prompt = f"{self.user}@{self.host}:~$ "
            here = self.put(bottom - 1, prompt[:inner], VIT, True, column=column)
            self.put(bottom - 1, "/help" + (self.g["cursor"] if blink else " "), TEXT,
                     column=here, limit=column + inner - here)

    def dashboard(self, actions, selected):
        self.load_wire()
        watch_stamp, flash, flash_until = None, "", 0.0
        queue = 0
        self.shown_title = None
        glitch_at = time.monotonic() + random.uniform(2, 5)
        glitch = 0
        scroll = 0
        hints = [("/", "command"), ("0-9", "open"), (self.g["keys"], "move"), ("esc", "jack out")]
        while True:
            fx = self.preferences["fx"]
            now = time.monotonic()
            stats = self.telemetry.poll()
            if self.colors:
                self.screen.bkgd(" ", self.style(TEXT))
            self.screen.erase()
            height, width = self.screen.getmaxyx()
            self.header()
            self.rule(1)
            self.keycaps(height - 1, hints)
            wide = width >= 64 and height >= 17
            top = 2
            if fx and now >= glitch_at:
                glitch, glitch_at = 3, now + random.uniform(3, 8)
            logo = self.g["logo"]
            if wide and height >= 21 and width >= len(logo[0]) + 30:
                for row, line in enumerate(logo):
                    if glitch:
                        shift = random.choice((-1, 1))
                        self.put(2 + row, self.noise(line, 0.08), HINT if row else HEAD, True,
                                 column=2 + shift)
                    else:
                        self.put(2 + row, line, HEAD, True, column=2)
                side = 2 + len(logo[0]) + 3
                self.put(2, f"FIELD TERMINAL // v{VERSION}", HINT, True, column=side)
                greeting = "WELCOME BACK, OPERATOR."
                typed = len(greeting) if not fx else min(len(greeting), int((now - self.started) * 28))
                tail = self.g["cursor"] if typed < len(greeting) or int(now * 2) % 2 else " "
                self.put(3, greeting[:typed] + tail, VIT, column=side)
                top = 5
            glitch = max(0, glitch - 1)
            try:
                stamp = WATCH.stat().st_mtime
            except OSError:
                stamp = 0
            if stamp != watch_stamp:  # links sent with `nightdeck add` show up here live
                items = load_watch()
                fresh = [item for item in items if not item["done"]]
                if watch_stamp is not None and len(fresh) > queue and fresh:
                    flash, flash_until = "NEW LINK " + self.g["ptr"] + " " + watch_label(fresh[0]), now + 10
                watch_stamp, queue = stamp, len(fresh)
            ticker = height >= 10
            bottom = height - (3 if ticker else 2)
            if ticker and now < flash_until:
                column = self.put(height - 2, " LINK ", SELBAR, True, column=1)
                shown = flash if not fx or int(now * 3) % 2 or now < flash_until - 8 else ""
                self.put(height - 2, " " + shown + "  (Video player " + self.g["ptr"] + " Watch list)", SEL, True,
                         column=column, limit=width - column - 2)
            elif ticker:
                text = self.wire or f"WIRE OFFLINE {self.g['sep']} open News to sync headlines   "
                column = self.put(height - 2, " WIRE ", BADGE, True, column=1)
                span = max(0, width - column - 2)
                if self.wire and len(text) > 0:
                    start = scroll % len(text)
                    text = (text * (span // len(text) + 2))[start:start + span]
                self.put(height - 2, " " + text, HINT, column=column, limit=span)
            if wide:
                left_width = 30
                count = max(1, bottom - top - 1)
                self.box(top, 1, bottom - top + 1, left_width, "MODULES")
                self.vitals_panel(top, left_width + 2, bottom - top + 1, width - left_width - 3,
                                  stats, int(now * 2) % 2 == 0)
                first, column, inner = top + 1, 2, left_width - 2
                info_row = bottom - 2
                if info_row > first + len(actions):
                    session = str(datetime.timedelta(seconds=int(now - self.launched)))
                    self.put(info_row, "SESSION ".ljust(9) + session, DIM, column=3)
                    self.put(info_row + 1, "QUEUE".ljust(9) + f"{queue} new", VIT if queue else DIM, column=3)
            else:
                cpu = stats.get("cpu")
                parts = [f"CPU {'--' if cpu is None else f'{cpu:.0f}%'}"]
                if "mem" in stats:
                    parts.append(f"RAM {100 * stats['mem'][0] // max(1, stats['mem'][1])}%")
                if "temp" in stats:
                    parts.append(f"{stats['temp']:.0f}C")
                self.put(2, f" {self.g['sep']} ".join(parts), VIT, True, column=1)
                self.rule(3)
                first, column, inner = 4, 1, width - 2
                count = max(1, bottom - first + 1)
            start = max(0, min(selected - count + 1, len(actions) - count))
            for index in range(start, min(len(actions), start + count)):
                row = first + index - start
                shortcut = (f"{index + 1:02d}" if index < 9 else
                            "00" if index == len(actions) - 1 else "--")
                name = actions[index][1]
                if index == selected:
                    self.put(row, f" {self.g['ptr']} {shortcut}  {name}".ljust(inner), SELBAR, True,
                             column=column, limit=inner)
                else:
                    here = self.put(row, f"   {shortcut}  ", DIM, column=column)
                    self.put(row, name, HEAD if index == len(actions) - 1 else TEXT,
                             column=here, limit=inner - (here - column))
            self.screen.timeout(140 if fx else 1000)
            try:
                key = self.screen.getch()
            finally:
                self.screen.timeout(-1)
            if fx:
                scroll += 1
            if key in (27, ord("q")):
                return len(actions) - 1
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if ord("1") <= key <= ord("9") and key - ord("1") < min(9, len(actions) - 1):
                return key - ord("1")
            if key == ord("0"):
                return len(actions) - 1
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(actions)
            if key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(actions)
            if key == ord("/"):
                aliases = [alias for alias, _, _ in actions] + ["help"]
                command = self.ask("DECK COMMAND // type a module name", prefix="/", completions=aliases)
                self.shown_title = None
                if not command:
                    continue
                name = command.strip().lstrip("/").lower()
                for index, (alias, _, _) in enumerate(actions):
                    if name == alias:
                        return index
                if name != "help":
                    self.notice("DECK COMMAND", "Unknown command. Type /help to list commands.", ok=False)
                    continue
                self.view("DECK COMMANDS", "\n".join(
                    f"/{alias:<9} {label}" for alias, label, _ in actions))

    def main(self):
        actions = [
            ("git", "Git workspace", self.git),
            ("edit", "Quick code editor", lambda: self.file_pick(HOME)),
            ("notes", "Notes", self.notes),
            ("zsh", "Zsh shell", self.zsh),
            ("claude", "Claude Code", self.claude),
            ("video", "Video player", self.video),
            ("ssh", "SSH utilities", self.ssh),
            ("news", "News wire", self.news),
            ("settings", "Settings", self.settings),
            ("vitals", "System vitals", self.system),
            ("sheets", "Character sheets", lambda: self.view(
                "CHARACTER SHEETS", "Reserved.\n\nSlot allocated for a future module.")),
            ("exit", "Jack out", self.power),
        ]
        if self.preferences["boot"]:
            self.boot()
        selected = 0
        while True:
            selected = self.dashboard(actions, selected)
            action = actions[selected][2]
            try:
                leave = action()
                if isinstance(leave, int) and not isinstance(leave, bool):
                    return leave
            except (OSError, ValueError, RuntimeError):
                self.notice("OPERATION FAILED",
                            "Check the path, permissions and installed commands, then retry.", ok=False)

    # ---------- modules ----------

    def power(self):
        """Jack out: power off, reboot or leave. Returns an exit code to leave Nightdeck."""
        choices = ["Power off the deck", "Reboot", "Exit to shell", "Disconnect", "Cancel"]
        intro = ["Power off shuts the Pi down. Wait for the green activity LED to stop "
                 "before you unplug it."]
        if os.environ.get("SSH_CONNECTION"):
            intro.append("This SSH session will drop.")
        choice = self.menu("JACK OUT // " + self.host.upper(), choices, intro=intro)
        if choice in (0, 1):
            verb = "poweroff" if choice == 0 else "reboot"
            if shutil.which("systemctl"):
                args = ["sudo", "systemctl", verb]
            else:
                args = ["sudo", verb]
            self.jack_out()
            if self.run(args, pause=False) == 0:
                self.screen.timeout(1000)
                try:
                    for left in range(30, 0, -1):  # the system ends this process as it shuts down
                        height, _ = self.frame("JACK OUT // " + verb.upper(), [("wait", "signal fading")])
                        self.put(5, ("Powering down." if choice == 0 else "Rebooting.") +
                                 " Hold on.", SEL, True, column=2)
                        self.put(7, self.g["full"] * left, HEAD, column=2)
                        self.screen.getch()
                finally:
                    self.screen.timeout(-1)
                self.notice("JACK OUT", "Still running 30 seconds after the " + verb +
                            " request. Check the system log.", ok=False)
            else:
                self.notice("JACK OUT", "The system did not accept the " + verb + " request. "
                            "Check that your user may run sudo.", ok=False)
            return None
        if choice == 2:
            return EXIT_SHELL
        if choice == 3:
            self.jack_out()
            return 0
        return None

    def git_view(self, label, args, repo):
        command = ["git", "--no-pager", "-c", "color.ui=false", *args]
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(command, cwd=repo, env=git_environment(),
                                    stdout=output, stderr=subprocess.STDOUT, check=False)
            output.seek(0)
            raw = output.read(128 * 1024 + 1)
        body = raw[:128 * 1024].decode("utf-8", errors="replace")
        if len(raw) > 128 * 1024:
            body += "\n[Output clipped at 128 KiB.]"
        self.view(label.upper() + " // " + clean(repo.name),
                  "$ " + shlex.join(command) + f"\nExit status {result.returncode}\n\n" +
                  (body or "(No output.)"), kind="git")

    def editor(self, path):
        editor = shutil.which("micro") or shutil.which("nano")
        if editor:
            self.run([editor, str(path)], cwd=path.parent, pause=False)
        else:
            self.notice("EDITOR", "Install micro or nano with setup.sh.", ok=False)

    def file_pick(self, root, notes=False):
        current = root
        while True:
            dirs = sorted(p for p in current.iterdir()
                          if p.is_dir() and not p.is_symlink() and p.name != ".git")
            files = sorted(p for p in current.iterdir()
                           if not p.is_symlink() and p.is_file() and p.name != ".git")
            actions = ["Parent directory", "New file"] + [p.name + "/" for p in dirs] + [p.name for p in files]
            selected = self.menu(("NOTES" if notes else "EDIT") + " // " + str(current.relative_to(root)), actions)
            if selected is None:
                return
            if selected == 0:
                if current == root:
                    return
                current = current.parent
            elif selected == 1:
                name = self.ask("NEW FILE // filename")
                if not name:
                    continue
                if name in (".", "..", ".git") or "/" in name:
                    self.notice("NEW FILE", "Use a single filename.", ok=False)
                    continue
                if notes and not Path(name).suffix:
                    name += ".md"
                path = current / name
                if path.exists() or path.is_symlink():
                    self.notice("NEW FILE", "That name already exists.", ok=False)
                    continue
                self.editor(path)
            elif selected - 2 < len(dirs):
                current = dirs[selected - 2]
            else:
                self.editor(files[selected - 2 - len(dirs)])

    def git(self):
        REPOS.mkdir(exist_ok=True)
        while True:
            repos = sorted(p for p in REPOS.iterdir() if not p.is_symlink() and p.is_dir()
                           and (p / ".git").exists())
            choice = self.menu("GIT // ~/repos", ["Clone repository", "Open repository by path"] +
                               [p.name for p in repos])
            if choice is None:
                return
            if choice == 0:
                remote = self.ask("CLONE // HTTPS or user@host:path", hidden=True)
                if remote is None:
                    continue
                if not repo_url(remote):
                    self.notice("CLONE", "Use a plain HTTPS URL or SSH user@host:path. "
                                "Supply credentials through Git or SSH.", ok=False)
                    continue
                name = self.ask("CLONE // destination name in ~/repos")
                if not name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
                    continue
                destination = REPOS / name
                if destination.exists() or destination.is_symlink():
                    self.notice("CLONE", "Destination already exists.", ok=False)
                    continue
                args = ["git", "clone", "--", remote, name]
                if self.confirm("CLONE // ~/repos", args):
                    self.run(args, REPOS, git=True)
                continue
            if choice == 1:
                value = self.ask("REPOSITORY // absolute path or ~/path")
                if not value:
                    continue
                repo = Path(value).expanduser().resolve()
                if not (repo / ".git").exists():
                    self.notice("GIT", "Select a repository root or worktree root.", ok=False)
                    continue
            else:
                repo = repos[choice - 2]
            self.repository(repo)

    def branch_of(self, repo):
        result = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=repo,
                                capture_output=True, text=True, check=False, env=git_environment())
        return clean(result.stdout.strip()) or "detached"

    def repository(self, repo):
        commands = [
            ("Status", ["status", "--short", "--branch"]),
            ("Diff / working tree", ["diff", "--no-ext-diff", "--no-textconv"]),
            ("Diff / staged", ["diff", "--cached", "--no-ext-diff", "--no-textconv"]),
            ("List branches", ["branch", "--list"]),
            ("Switch branch", ["switch", "--"]),
            ("Create and switch branch", ["switch", "-c"]),
            ("Edit files", None),
            ("Stage path", ["--literal-pathspecs", "add", "--"]),
            ("Commit staged changes", ["commit"]),
            ("Push current branch", ["push", "--no-follow-tags", "--recurse-submodules=no"]),
        ]
        selected = 0
        while True:
            choice = self.menu(f"GIT // {clean(repo.name)} [{self.branch_of(repo)}]",
                               [label for label, _ in commands], selected=selected)
            if choice is None:
                return
            selected = choice
            label, options = commands[choice]
            if options is None:
                self.file_pick(repo)
                continue
            if choice < 4:
                self.git_view(label, options, repo)
                continue
            args = ["git"] + options
            if choice in (4, 5, 7):
                value = self.ask("GIT // " + label)
                if not value or (choice in (4, 5) and value.startswith("-")):
                    continue
                args.append(value)
            if choice == 9:
                remote = self.ask("PUSH // remote name, e.g. origin")
                if not remote or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote):
                    continue
                current = subprocess.run(["git", "symbolic-ref", "--quiet", "HEAD"], cwd=repo,
                                         capture_output=True, text=True, check=False, env=git_environment())
                ref = current.stdout.strip()
                if current.returncode or not ref.startswith("refs/heads/"):
                    self.notice("PUSH", "Switch to a local branch before pushing.", ok=False)
                    continue
                config = subprocess.run(["git", "remote", "get-url", "--push", "--all", remote],
                                        cwd=repo, capture_output=True, text=True, check=False, env=git_environment())
                urls = config.stdout.splitlines()
                if config.returncode or len(urls) != 1 or not repo_url(urls[0]):
                    self.notice("PUSH", "Configure one HTTPS or SSH push URL without embedded credentials.",
                                ok=False)
                    continue
                args.extend(["--", urls[0], ref + ":" + ref])
            if choice in (4, 5, 7, 8, 9) and not self.confirm(label.upper() + " // " + clean(repo.name), args):
                continue
            self.run(args, repo, git=True)

    def news(self):
        selected = 0
        while True:
            labels = []
            for key, label, _ in FEEDS:
                count = len(read_cache(key).get("items") or [])
                labels.append(f"{label}  [{count} cached]" if count else f"{label}  [no cache]")
            source = self.menu("NEWS WIRE // Swedish and world", labels, selected=selected)
            if source is None:
                return
            selected = source
            key, label, url = FEEDS[source]
            pick = 0
            while True:
                cached = read_cache(key)
                items = [item for item in cached.get("items") or [] if isinstance(item, dict)]
                title = label + " // " + str(cached.get("saved", "no cache"))[:16]
                choice = self.menu(title, ["Refresh from publisher"] + [item.get("title", "") for item in items],
                                   selected=pick)
                if choice is None:
                    break
                pick = choice
                if choice == 0:
                    try:
                        count = self.busy("NEWS WIRE // " + label, "Pulling headlines from publisher",
                                          lambda: refresh_feed(key, url))
                        self.notice(label, f"Saved {count} headlines for offline reading.")
                    except (OSError, ValueError, ET.ParseError):
                        self.notice(label, "Refresh failed. Any previous cache is still available.", ok=False)
                    continue
                self.article(label, items[choice - 1])

    def article(self, label, item):
        summary = "\n\n".join(("# " + item.get("title", ""), item.get("date", ""),
                               item.get("summary") or "No summary supplied by the publisher.",
                               item.get("link", "")))
        self.view(label, summary)
        link = item.get("link", "")
        if not public_url(link, ("https", "http"), allow_query=True):
            return
        if self.menu("PUBLISHER PAGE // internet required", ["Back to headlines", "Open in text browser"]) != 1:
            return
        browser = shutil.which("w3m")
        if browser:
            self.run([browser, "-T", "text/html", link], pause=False)
        else:
            self.notice("TEXT BROWSER", "Install w3m or read the cached summary.", ok=False)

    def system(self):
        stats = self.telemetry.poll(force=True)
        iface, ip, signal = stats.get("link") or (None, None, None)
        lines = ["## IDENTITY", f"Host      {self.host}", f"User      {self.user}",
                 f"Kernel    {os.uname().release}", f"Machine   {os.uname().machine}", "", "## TELEMETRY"]
        if stats.get("cpu") is not None:
            lines.append(f"CPU       {stats['cpu']:.0f}%")
        if "load" in stats:
            lines.append(f"Load      {stats['load']}")
        if "uptime" in stats:
            lines.append(f"Uptime    {stats['uptime']}")
        if "mem" in stats:
            lines.append(f"Memory    {stats['mem'][0]} / {stats['mem'][1]} MiB")
        if "disk" in stats:
            lines.append(f"Storage   {stats['disk'][2]:.1f} GiB free of {stats['disk'][1]:.1f} GiB")
        if "temp" in stats:
            lines.append(f"CPU temp  {stats['temp']:.1f} C")
        lines += ["", "## LINK", f"Route     {iface or 'none'}", f"Address   {ip or 'offline'}"]
        if signal is not None:
            lines.append(f"Wi-Fi     {signal}%")
        self.view("SYSTEM // local telemetry", "\n".join(lines))

    def video(self):
        """Play local files or streams with mpv on the deck's screen or in this terminal."""
        selected = 0
        while True:
            mpv = shutil.which("mpv")
            intro = ["mpv ready." if mpv else "mpv is not installed.",
                     "Streams from YouTube and similar sites: " +
                     ("yt-dlp ready." if shutil.which("yt-dlp") else "install yt-dlp."),
                     "Keys while playing: " + MPV_KEYS]
            options = [] if mpv else [("Install mpv and yt-dlp", self.video_install)]
            options += [
                (f"Watch list ({sum(not i['done'] for i in load_watch())} new)", self.watch_list),
                ("Browse ~/Videos", lambda: self.video_pick(VIDEOS)),
                ("Play file by path", self.video_path),
                ("Play a URL or stream", self.video_url),
                ("Output / " + self.preferences["video_out"].capitalize(), self.video_output_cycle),
            ]
            choice = self.menu("VIDEO // " + ("mpv" if mpv else "player offline"),
                               [label for label, _ in options], intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            options[choice][1]()

    def watch_list(self):
        selected = 0
        while True:
            items = load_watch()
            fresh = [item for item in items if not item["done"]]
            labels = [f"Play all new ({len(fresh)})", "Clear watched"] + [
                (self.g["off"] if item["done"] else self.g["on"]) + " " + watch_label(item) for item in items]
            intro = None if items else [
                "The list is empty. Send links from Ubuntu:",
                "$ deck-add https://youtu.be/...",
                "README / Watch list shows how to set up deck-add."]
            choice = self.menu(f"WATCH LIST // {len(fresh)} new", labels, intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            if choice == 0:
                if fresh:
                    self.play_links([item["url"] for item in fresh])
                continue
            if choice == 1:
                edit_watch(drop_watched)
                selected = 0
                continue
            item = items[choice - 2]
            action = self.menu("WATCH LIST // " + watch_label(item)[:50],
                               ["Play", "Mark as " + ("new" if item["done"] else "watched"), "Remove", "Back"],
                               intro=[item["url"], "Added " + (item["added"] or "?")])
            if action == 0:
                self.play_links([item["url"]])
            elif action == 1:
                edit_watch(lambda items: [i.update(done=not i["done"]) for i in items
                                          if i["url"] == item["url"]])
            elif action == 2:
                edit_watch(lambda items: items.__setitem__(
                    slice(None), [i for i in items if i["url"] != item["url"]]))
                selected = max(0, selected - 1)

    def play_links(self, urls):
        if self.play(urls):
            edit_watch(lambda items: [i.update(done=True) for i in items if i["url"] in urls])

    def video_install(self):
        args = ["sudo", "apt-get", "install", "--no-install-recommends", "mpv", "yt-dlp"]
        if self.confirm("VIDEO // install player", args):
            self.run(args)

    def video_output_cycle(self):
        settings = dict(self.preferences)
        settings["video_out"] = VIDEO_OUTPUTS[(VIDEO_OUTPUTS.index(settings["video_out"]) + 1)
                                              % len(VIDEO_OUTPUTS)]
        save_settings(settings)
        self.preferences = settings

    def video_pick(self, root):
        VIDEOS.mkdir(exist_ok=True)
        current = root
        selected = 0
        while True:
            try:
                entries = list(current.iterdir())
            except OSError:
                self.notice("VIDEO", "That folder can't be read.", ok=False)
                return
            dirs = sorted((p for p in entries if p.is_dir() and not p.is_symlink()
                           and not p.name.startswith(".")), key=lambda p: p.name.lower())
            files = sorted((p for p in entries if p.is_file() and not p.is_symlink()
                            and p.suffix.lower() in MEDIA_EXT), key=lambda p: p.name.lower())
            labels = ["Parent directory"]
            if files:
                labels.append(f"Play all here ({len(files)})")
            labels += [p.name + "/" for p in dirs]
            for p in files:
                try:
                    labels.append(f"{p.name}  [{size_label(p.stat().st_size)}]")
                except OSError:
                    labels.append(p.name)
            where = "~/" + str(current.relative_to(HOME)) if current.is_relative_to(HOME) else str(current)
            intro = None if files or dirs else [
                "No videos here yet. Copy some from Ubuntu with:",
                f"$ scp movie.mp4 {self.user}@{self.host}.local:~/Videos/"]
            choice = self.menu("VIDEO // " + where, labels, intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            if choice == 0:
                if current == root:
                    return
                current, selected = current.parent, 0
                continue
            index = choice - (2 if files else 1)
            if index == -1:
                self.play(files)
            elif index < len(dirs):
                current, selected = dirs[index], 0
            else:
                self.play([files[index - len(dirs)]])

    def video_path(self):
        value = self.ask("VIDEO // file path, e.g. ~/Videos/clip.mp4", prefix="")
        if not value:
            return
        path = Path(value.strip()).expanduser()
        if not path.is_file():
            self.notice("VIDEO", "No file at that path.", ok=False)
            return
        self.play([path.resolve()])

    def video_url(self):
        value = self.ask("VIDEO // https URL of a video or stream", prefix="")
        if not value:
            return
        value = value.strip()
        if not public_url(value, ("https", "http"), allow_query=True):
            self.notice("VIDEO", "Use a plain http(s) URL without a login in it.", ok=False)
            return
        self.play([value])

    def video_output(self):
        """screen or terminal, or None when cancelled."""
        mode = self.preferences["video_out"]
        if mode != "ask":
            return mode
        if not os.environ.get("SSH_CONNECTION"):
            return "screen"
        choice = self.menu("VIDEO // play where?", ["Deck screen", "This terminal (text mode)"], intro=[
            "Deck screen plays full screen on the Pi's display. Use this SSH window as the remote.",
            "Text mode draws the video in this terminal with colored blocks. Sound comes out of the Pi.",
            "Set a fixed choice in Settings / Video output."])
        return None if choice is None else ("screen", "terminal")[choice]

    def play(self, targets):
        mpv = shutil.which("mpv")
        if not mpv:
            self.notice("VIDEO", "Install mpv first: choose Install mpv and yt-dlp.", ok=False)
            return
        output = self.video_output()
        if output is None:
            return
        args = [mpv, "--save-position-on-quit", "--ytdl-format=" + YTDL_FORMAT]
        if output == "screen":
            args += ["--fs", "--hwdec=auto-safe", "--profile=fast"]
            if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                args.append("--vo=gpu,drm")  # draw straight on the display, no desktop needed
        else:
            args += ["--vo=tct", "--hwdec=auto-copy-safe", "--framedrop=decoder+vo", "--really-quiet"]
            if self.basic:
                args.append("--vo-tct-256=yes")
        args += ["--", *map(str, targets)]
        return self.run(args, pause=False) == 0

    def claude(self):
        """Claude Code: run it here on 64-bit hardware, or on a bigger machine over SSH."""
        machine = os.uname().machine
        supported = machine in ("x86_64", "amd64", "aarch64", "arm64")
        selected = 0
        while True:
            local = shutil.which("claude")
            host = self.preferences["claude_host"]
            if local:
                status = "Installed on this device."
            elif supported:
                status = "Not installed on this device."
            else:
                status = (f"This device runs {machine} (32-bit). Claude Code needs a 64-bit "
                          "x64 or ARM64 system with 4 GB+ RAM, so run it on another machine over SSH.")
            intro = [status, "Remote host: " + (host or "not set") +
                     (f"  //  project: {self.preferences['claude_dir']}" if self.preferences["claude_dir"] else "")]
            options = []
            if local:
                options.append(("Launch Claude Code here", self.claude_local))
            elif supported:
                options.append(("Install Claude Code on this device", self.claude_install_local))
            options += [
                ("Launch on " + (host or "remote host"), self.claude_remote),
                ("Set remote host and project", self.claude_target),
                ("Install Claude Code on " + (host or "remote host"), self.claude_install_remote),
            ]
            choice = self.menu("CLAUDE CODE // " + ("local" if local else host or "uplink"),
                               [label for label, _ in options], intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            options[choice][1]()

    def claude_local(self):
        places = [HOME] + sorted(p for p in REPOS.iterdir() if p.is_dir() and (p / ".git").exists()) \
            if REPOS.is_dir() else [HOME]
        choice = self.menu("CLAUDE CODE // working directory",
                           ["~ (home)"] + ["~/repos/" + clean(p.name) for p in places[1:]])
        if choice is not None:
            self.run([shutil.which("claude") or "claude"], cwd=places[choice], pause=False)

    def claude_install_local(self):
        if not shutil.which("curl"):
            self.notice("CLAUDE CODE", "Install curl first: sudo apt install curl", ok=False)
            return
        intro = ["Runs Anthropic's official installer into ~/.local/bin. "
                 "Log in afterwards by launching Claude Code."]
        mem = self.telemetry.poll().get("mem")
        if mem and mem[1] < 3500:
            intro.append(f"This device has {mem[1]} MiB RAM. Claude Code asks for 4 GB and may run poorly.")
        args = ["bash", "-c", CLAUDE_INSTALL]
        intro.append("$ " + shlex.join(args))
        if self.menu("CLAUDE CODE // install", ["Cancel", "Run installer"], intro=intro) == 1:
            self.run(args)

    def claude_target(self):
        host = self.ask("CLAUDE CODE // SSH host alias or user@host", prefix="")
        if host is None:
            return
        host = host.strip()
        if host and not HOST.fullmatch(host):
            self.notice("CLAUDE CODE", "Use a host alias from ~/.ssh/config or user@host.", ok=False)
            return
        folder = self.ask("CLAUDE CODE // project folder on that host, e.g. ~/code/app (blank for home)",
                          prefix="")
        if folder is None:
            return
        folder = folder.strip()
        if not REMOTE_DIR.fullmatch(folder) or ".." in folder.split("/"):
            self.notice("CLAUDE CODE", "Use a plain path with letters, digits, . _ - / and ~.", ok=False)
            return
        settings = dict(self.preferences, claude_host=host, claude_dir=folder)
        save_settings(settings)
        self.preferences = settings
        if host:
            self.notice("CLAUDE CODE", f"Remote target set to {host}.")

    def remote_args(self, command):
        host = self.preferences["claude_host"]
        if not host:
            self.claude_target()
            host = self.preferences["claude_host"]
            if not host:
                return None
        folder = self.preferences["claude_dir"]
        if folder.startswith("~"):
            folder = folder[1:].lstrip("/")
            target = '"$HOME"/' + shlex.quote(folder) if folder else '"$HOME"'
        else:
            target = shlex.quote(folder) if folder else '"$HOME"'
        # A login shell puts ~/.local/bin, where the installer puts claude, on PATH.
        script = f"cd -- {target} && exec \"${{SHELL:-bash}}\" -lc {shlex.quote(command)}"
        return ["ssh", "-t", "--", host, script]

    def claude_remote(self):
        args = self.remote_args("claude")
        if args and self.confirm("CLAUDE CODE // uplink to " + self.preferences["claude_host"], args):
            self.run(args, pause=False)

    def claude_install_remote(self):
        args = self.remote_args(CLAUDE_INSTALL)
        if args and self.confirm("CLAUDE CODE // install on " + self.preferences["claude_host"], args):
            self.run(args)

    def ssh(self):
        choice = self.menu("SSH // client tools", ["Connect to host or alias", "Edit ~/.ssh/config",
                                                   "List agent identities"])
        if choice == 0:
            host = self.ask("SSH // host alias or user@host")
            if host and HOST.fullmatch(host):
                args = ["ssh", "--", host]
                if self.confirm("SSH CONNECT", args):
                    self.run(args)
        elif choice == 1:
            directory = HOME / ".ssh"
            directory.mkdir(mode=0o700, exist_ok=True)
            self.editor(directory / "config")
        elif choice == 2:
            self.run(["ssh-add", "-l"])

    def settings(self):
        selected = 0
        while True:
            p = self.preferences
            swatch = []
            for role, pair in zip(COLOR_ROLES[:5], (HEAD, SEL, HINT, VIT, TEXT)):
                swatch += [(self.g["full"] * 3, pair), (" " + role.upper() + "  ", DIM)]
            choice = self.menu("SETTINGS", [
                "Theme / " + p["theme"], "Customize colors",
                "Effects / " + ("On" if p["fx"] else "Off"),
                "Boot sequence / " + ("On" if p["boot"] else "Off"),
                "Glyphs / " + p["glyphs"].capitalize(),
                "Video output / " + p["video_out"].capitalize(),
                "Connect to Wi-Fi",
            ], intro=[swatch], selected=selected)
            if choice is None:
                return
            selected = choice
            settings = dict(p)
            if choice == 0:
                themes = [*THEMES, "Custom"]
                theme = self.menu("SETTINGS // theme", themes, selected=themes.index(p["theme"]))
                if theme is None:
                    continue
                settings["theme"] = themes[theme]
            elif choice == 1:
                colors = list(THEMES.get(settings["theme"], settings["custom"]))
                role = self.menu("SETTINGS // custom colors",
                                 [f"{name}  #{value}" for name, value in zip(COLOR_ROLES, colors)])
                if role is None:
                    continue
                value = self.ask(f"{COLOR_ROLES[role]} // enter a hex color")
                if value is None:
                    continue
                value = value.strip().removeprefix("#")
                if not COLOR.fullmatch(value):
                    self.notice("SETTINGS", "Enter six hexadecimal digits, e.g. FFEE08.", ok=False)
                    continue
                colors[role] = value.upper()
                settings.update(theme="Custom", custom=colors)
            elif choice == 2:
                settings["fx"] = not p["fx"]
            elif choice == 3:
                settings["boot"] = not p["boot"]
            elif choice == 4:
                settings["glyphs"] = GLYPH_MODES[(GLYPH_MODES.index(p["glyphs"]) + 1) % len(GLYPH_MODES)]
            elif choice == 5:
                settings["video_out"] = VIDEO_OUTPUTS[(VIDEO_OUTPUTS.index(p["video_out"]) + 1)
                                                      % len(VIDEO_OUTPUTS)]
            else:
                self.wifi()
                continue
            save_settings(settings)
            self.preferences = settings
            self.apply_theme()
            self.apply_glyphs()
            self.shown_title = None

    def wifi(self):
        app = shutil.which("nmtui")
        if not app:
            self.notice("WI-FI", "NetworkManager's nmtui is unavailable. Install the network-manager package.",
                        ok=False)
            return
        args = ["sudo", app, "connect"]
        intro = ["Choose a network and enter its password in NetworkManager."]
        if os.environ.get("SSH_CONNECTION"):
            intro.append("Switching Wi-Fi can disconnect this SSH session. "
                         "Use the Pi console if you need to stay connected.")
        intro.append("$ " + shlex.join(args))
        if self.menu("WI-FI // NetworkManager", ["Cancel", "Run command"], intro=intro) == 1:
            self.run(args, pause=False)

    def zsh(self):
        config = CONFIG / "zsh"
        env = None
        if (config / ".zshrc").is_file():
            env = dict(os.environ, ZDOTDIR=str(config))
        self.run(["zsh", "-i"], pause=False, env=env)

    def notes(self):
        NOTES.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.file_pick(NOTES, notes=True)


def load_watch():
    try:
        raw = json.loads(WATCH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = []
    for item in raw.get("items", []) if isinstance(raw, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("url"), str) and public_url(
                item["url"], ("https", "http"), allow_query=True):
            items.append({"url": item["url"], "title": clean(str(item.get("title") or ""))[:200],
                          "added": clean(str(item.get("added") or ""))[:40],
                          "done": item.get("done") is True, "tried": item.get("tried") is True})
    return items[:WATCH_MAX]


def edit_watch(change):
    """Load, change and save the watch list under a lock (the CLI and the app share it)."""
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(DATA / "watchlist.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        items = load_watch()
        result = change(items)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DATA, delete=False) as file:
            temp = Path(file.name)
        try:
            temp.write_text(json.dumps({"items": items[:WATCH_MAX]}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            temp.replace(WATCH)
        finally:
            temp.unlink(missing_ok=True)
        return result


def drop_watched(items):
    items[:] = [item for item in items if not item["done"]]
    return len(items)


def watch_label(item):
    if item["title"]:
        return item["title"]
    url = urlsplit(item["url"])
    return (url.hostname or "") + url.path + ("?" + url.query if url.query else "")


def fetch_titles():
    """Look up titles for new links with yt-dlp. Runs detached after `nightdeck add`."""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        return
    for url in [item["url"] for item in load_watch() if not item["title"] and not item["tried"]]:
        try:
            result = subprocess.run([ytdlp, "--no-warnings", "--skip-download", "--no-playlist",
                                     "--print", "title", "--", url],
                                    capture_output=True, text=True, timeout=90, check=False)
            title = clean(result.stdout.strip().splitlines()[0])[:200] if result.returncode == 0 \
                and result.stdout.strip() else ""
        except (OSError, subprocess.TimeoutExpired):
            title = ""

        def store(items, url=url, title=title):
            for item in items:
                if item["url"] == url:
                    item["title"], item["tried"] = title or item["title"], True
        edit_watch(store)


def command_line(args):
    usage = ("Usage: nightdeck                 open the deck\n"
             "       nightdeck add URL...      add links to the watch list (or one per line on stdin)\n"
             "       nightdeck list            show the watch list\n"
             "       nightdeck remove N        remove entry N from the list\n"
             "       nightdeck clear           remove watched entries")
    name, rest = args[0], args[1:]
    if name == "add":
        if not rest and sys.stdin.isatty():
            print(usage, file=sys.stderr)
            return 2
        links = rest or [line.strip() for line in sys.stdin.read(256 * 1024).splitlines()]
        # zsh's url-quote-magic escapes ?, = and & while pasting; inside quotes the backslashes stay.
        links = [re.sub(r"\\([?=&#%+!*;~])", r"\1", link) for link in links if link]
        good = [link for link in links if public_url(link, ("https", "http"), allow_query=True)]
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        def add(items):
            added = 0
            for link in good:
                existing = next((item for item in items if item["url"] == link), None)
                if existing:
                    items.remove(existing)
                    existing["done"] = False
                    items.insert(0, existing)
                else:
                    items.insert(0, {"url": link, "title": "", "added": stamp, "done": False, "tried": False})
                    added += 1
            return added
        added = edit_watch(add) if good else 0
        for link in links:
            ok = link in good
            print(("[ OK ] queued   " if ok else "[ !! ] skipped  ") + display_line(link)[:200]
                  + ("" if ok else "  (not an http(s) link)"))
        print(f"{added} new, {len(good) - added} moved to the top. Watch list: {len(load_watch())} links.")
        if good and shutil.which("yt-dlp"):
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "titles"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return 0 if len(good) == len(links) and links else 1
    if name == "list":
        items = load_watch()
        for number, item in enumerate(items, 1):
            print(f"{number:3d} {'   ' if item['done'] else 'new'}  {watch_label(item)[:90]}")
        if not items:
            print("Watch list is empty. Add links with: nightdeck add URL")
        return 0
    if name == "remove" and len(rest) == 1 and rest[0].isdigit():
        index = int(rest[0]) - 1
        removed = edit_watch(lambda items: items.pop(index) if 0 <= index < len(items) else None)
        print(f"Removed: {watch_label(removed)}" if removed else "No entry with that number.")
        return 0 if removed else 1
    if name == "clear":
        count = edit_watch(drop_watched)
        print(f"Removed watched entries. {count} left.")
        return 0
    if name == "titles":
        fetch_titles()
        return 0
    print(usage, file=sys.stderr if name not in ("help", "-h", "--help") else sys.stdout)
    return 0 if name in ("help", "-h", "--help") else 2


def configure_locale():
    for candidate in ("", "C.UTF-8", "C"):
        try:
            locale.setlocale(locale.LC_ALL, candidate)
        except locale.Error:
            continue
        if candidate:
            os.environ["LC_ALL"] = candidate
        return


if __name__ == "__main__":
    configure_locale()
    if len(sys.argv) > 1:
        try:
            sys.exit(command_line(sys.argv[1:]))
        except BrokenPipeError:  # output piped into e.g. head
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            sys.exit(1)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("nightdeck: the deck needs a terminal. Over SSH use `ssh -t`, "
              "or run `nightdeck help` for commands.", file=sys.stderr)
        sys.exit(2)
    try:
        os.environ["NIGHTDECK"] = "1"  # child shells must not autostart another deck
        sys.exit(curses.wrapper(lambda screen: Deck(screen).main()) or 0)
    except KeyboardInterrupt:
        sys.exit(130)
    except curses.error as error:
        print(f"nightdeck: this terminal can't run the deck ({error}). "
              "Check TERM, e.g. TERM=xterm-256color.", file=sys.stderr)
        sys.exit(2)
