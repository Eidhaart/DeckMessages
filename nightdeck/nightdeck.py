#!/usr/bin/env python3
"""Nightdeck // cyberdeck field terminal."""
import curses
import datetime
import fcntl
import hashlib
import io
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
import tarfile
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
YTDLP_LOCAL = HOME / ".local/bin/yt-dlp"
DOWNLOADS = VIDEOS / "watchlist"
DL_STATES = ("", "downloading", "ready", "failed", "deleted")
DL_MIN_FREE = 500 * 1024 * 1024
# 480p H.264 + AAC in MP4: fits the 800x480 panel and plays with hardware decoding on a Pi 3B.
DL_FORMAT_MERGE = ("bestvideo[height<=?480][vcodec^=avc1]+bestaudio[ext=m4a]/"
                   "best[height<=?480][vcodec^=avc1]/best[height<=?480]/best")
DL_FORMAT_SINGLE = "best[height<=?480][vcodec^=avc1]/best[height<=?480]/best"
YTDLP_RELEASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
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
        "ok": "✓", "dl": "↓", "wait": "…", "bad": "!", "note": "♪",
        "logo": ("█▄ █ █ █▀▀ █ █ ▀█▀ █▀▄ █▀▀ █▀▀ █▄▀",
                 "█ ▀█ █ █▄█ █▀█  █  █▄▀ ██▄ █▄▄ █ █"),
    },
    # Linux console fonts carry the VGA (CP437) set: box drawing, shades, half blocks, arrows.
    "console": {
        "h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "lj": "┤", "rj": "├",
        "full": "█", "empty": "░", "spark": "▄█", "spin": "░▒▓█", "ptr": "►",
        "on": "■", "off": "·", "bar": "▌", "sep": "·", "up": "▲", "down": "▼",
        "noise": "░▒▓█▀▄", "keys": "↑↓", "wire": "///", "cursor": "█",
        "ok": "√", "dl": "↓", "wait": "·", "bad": "!", "note": "♪",
        "logo": ("█▄ █ █ █▀▀ █ █ ▀█▀ █▀▄ █▀▀ █▀▀ █▄▀",
                 "█ ▀█ █ █▄█ █▀█  █  █▄▀ ██▄ █▄▄ █ █"),
    },
    "ascii": {
        "h": "-", "v": "|", "tl": "+", "tr": "+", "bl": "+", "br": "+", "lj": "[", "rj": "]",
        "full": "#", "empty": ".", "spark": "_.-=+*#@", "spin": "|/-\\", "ptr": ">",
        "on": "*", "off": "o", "bar": "|", "sep": "-", "up": "^", "down": "v",
        "noise": "#%@&$?!", "keys": "jk", "wire": "///", "cursor": "_",
        "ok": "+", "dl": "v", "wait": ".", "bad": "!", "note": "BT",
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
                "video_out": "ask", "download": True,
                "bt_auto": ""}
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
    if isinstance(saved.get("bt_auto"), str) and (saved["bt_auto"] == "" or BT_MAC.fullmatch(saved["bt_auto"])):
        defaults["bt_auto"] = saved["bt_auto"]
    if isinstance(saved.get("download"), bool):
        defaults["download"] = saved["download"]
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
        self.audio = {}
        self.np, self.np_time = None, 0.0
        threading.Thread(target=self.music_monitor, daemon=True).start()
        if shutil.which("wpctl") or shutil.which("bluetoothctl"):
            threading.Thread(target=self.audio_monitor, daemon=True).start()
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
                    rgb = [(int(color[i:i+2], 16) * 1000 + 254) // 255 for i in (0, 2, 4)]
                    curses.init_color(index, *rgb)
            head, sel, hint, vit, text, dim, background = indexes
        else:
            self.basic = True
            head, sel, hint, vit, text, dim, background = (
                curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_CYAN, curses.COLOR_GREEN,
                curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_BLACK)
            if curses.can_change_color():
                # Linux console: repaint its 8 colors with the theme (restored when Nightdeck exits).
                dim = curses.COLOR_MAGENTA
                for index, color in zip((head, sel, hint, vit, text, dim, background), palette):
                    try:
                        curses.init_color(index, *[(int(color[i:i+2], 16) * 1000 + 254) // 255 for i in (0, 2, 4)])
                    except curses.error:
                        dim = curses.COLOR_RED
                        break
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
            bt = self.audio.get("bt")
            if bt and width >= 64:
                label = f"{self.g['note']} {bt[:14]}"
                self.put(0, label, HINT, True, column=right - len(label) - 2)
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
        if self.np:
            self.draw_np(height - 2, width, compact=True)
        self.keycaps(height - 1, hints)
        if title != self.shown_title:
            self.shown_title = title
            self.reveal(2, heading, SEL)
        else:
            self.put(2, heading, SEL, True)
        return height, width

    # ---------- widgets ----------

    def menu(self, title, choices, intro=None, selected=0, poll=False):
        """poll=True returns -1 about once a second so the caller can refresh (self.last_selected keeps place)."""
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
            if poll:
                self.screen.timeout(1000)
            try:
                key = self.screen.getch()
            finally:
                self.screen.timeout(-1)
            self.last_selected = selected
            if poll and key == -1:
                return -1
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
        if self.audio.get("volume") is not None:
            facts.append(("SND", f"{self.audio.get('sink', '')[:18]} "
                          f"{'muted' if self.audio.get('muted') else str(self.audio['volume']) + '%'}",
                          HINT if self.audio.get("bt") else TEXT))
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
        flash_tag, flash_tail = " LINK ", ""
        ready_seen = set()
        queue = 0
        self.shown_title = None
        glitch_at = time.monotonic() + random.uniform(2, 5)
        glitch = 0
        scroll = 0
        hints = [("/", "command"), ("0-9", "open"), (self.g["keys"], "move")]
        if shutil.which("wpctl"):
            hints.append(("+/-", "volume"))
        hints.append(("esc", "jack out"))
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
                ready = {item["url"] for item in fresh if item["state"] == "ready"}
                if watch_stamp is not None and len(fresh) > queue and fresh:
                    flash, flash_until = "NEW LINK " + self.g["ptr"] + " " + watch_label(fresh[0]), now + 10
                    flash_tag, flash_tail = " LINK ", "  (Video player " + self.g["ptr"] + " Watch list)"
                elif watch_stamp is not None and ready - ready_seen:
                    done = next(item for item in fresh if item["url"] in ready - ready_seen)
                    flash, flash_until = "READY " + self.g["ok"] + " " + watch_label(done), now + 10
                    flash_tag, flash_tail = " LINK ", "  (Video player " + self.g["ptr"] + " Watch list)"
                watch_stamp, queue, ready_seen = stamp, len(fresh), ready
            ticker = height >= 10
            bottom = height - (3 if ticker else 2)
            if ticker and now < flash_until:
                column = self.put(height - 2, flash_tag, SELBAR, True, column=1)
                shown = flash if not fx or int(now * 3) % 2 or now < flash_until - 8 else ""
                self.put(height - 2, " " + shown + flash_tail, SEL, True,
                         column=column, limit=width - column - 2)
            elif ticker and self.np:
                self.draw_np(height - 2, width)
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
                free_rows = bottom - (first + len(actions))  # rows left inside the box under the list
                if free_rows >= 1:
                    self.put(bottom - 1, "QUEUE".ljust(9) + f"{queue} new", VIT if queue else DIM, column=3)
                if free_rows >= 3:
                    session = str(datetime.timedelta(seconds=int(now - self.launched)))
                    self.put(bottom - 2, "SESSION ".ljust(9) + session, DIM, column=3)
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
            if key in (ord(" "), ord("["), ord("]")) and self.np:
                np_control(self.np, {ord(" "): "toggle", ord("["): "prev", ord("]"): "next"}[key])
                self.np_time = 0.0  # refresh the strip right away
            if key in (ord("+"), ord("="), ord("-"), ord("m")) and shutil.which("wpctl"):
                if key == ord("m"):
                    wpctl("set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
                else:
                    wpctl("set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%" + ("-" if key == ord("-") else "+"))
                _, volume, muted = audio_default()
                if volume is not None:
                    self.audio.update(volume=volume, muted=muted)
                    flash, flash_until = ("MUTED" if muted else f"VOLUME {volume}%"), now + 2.5
                    flash_tag, flash_tail = f" {self.g['note']} ", "  " + self.audio.get("sink", "")
            if key == ord("b"):
                for index, (alias, _, _) in enumerate(actions):
                    if alias == "bluetooth":
                        return index
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
            ("music", "Music & radio", self.music),
            ("news", "News wire", self.news),
            ("settings", "Settings", self.settings),
            ("bluetooth", "Bluetooth & sound", self.bluetooth),
            ("ssh", "SSH utilities", self.ssh),
            ("vitals", "System vitals", self.system),
            ("sheets", "Character sheets", lambda: self.view(
                "CHARACTER SHEETS", "Reserved.\n\nSlot allocated for a future module.")),
            ("exit", "Jack out", self.power),
        ]
        if self.preferences["bt_auto"] and shutil.which("bluetoothctl"):
            try:  # reconnect the chosen headphones in the background
                subprocess.Popen(["bluetoothctl", "connect", self.preferences["bt_auto"]], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                pass
        if self.preferences["download"] and ytdlp_path():
            spawn_worker()  # resume downloads interrupted by a shutdown
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
        try:
            console = os.ttyname(0) == "/dev/tty1"
        except OSError:
            console = False
        choices = ["Power off the deck", "Reboot", "Exit to shell",
                   "Log out (the deck restarts)" if console else "Disconnect", "Cancel"]
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
            intro = ["mpv ready." if mpv else "mpv is not installed.", ytdlp_status(),
                     "Keys while playing: " + MPV_KEYS]
            options = [] if mpv and shutil.which("qjs") else [("Install mpv and QuickJS", self.video_install)]
            options += [
                (f"Watch list ({sum(not i['done'] for i in load_watch())} new)", self.watch_list),
                ("Browse ~/Videos", lambda: self.video_pick(VIDEOS)),
                ("Play file by path", self.video_path),
                ("Play a URL or stream", self.video_url),
                ("Output / " + self.preferences["video_out"].capitalize(), self.video_output_cycle),
                ("Update yt-dlp", self.video_update),
            ]
            choice = self.menu("VIDEO // " + ("mpv" if mpv else "player offline"),
                               [label for label, _ in options], intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            options[choice][1]()

    def watch_badge(self, item):
        g = self.g
        if watch_file(item):
            return g["ok"]
        if item["state"] == "downloading":
            return g["dl"] + (item["progress"] or "")
        if item["state"] == "failed":
            return g["bad"]
        if item["state"] == "" and not item["done"] and self.preferences["download"]:
            return g["wait"]
        return " "

    def watch_list(self):
        selected = 0
        while True:
            items = load_watch()
            fresh = [item for item in items if not item["done"]]
            files = [(item, watch_file(item)) for item in items]
            stored = [(item, path) for item, path in files if path]
            watched_files = [(item, path) for item, path in stored if item["done"]]

            def total(pairs):
                return sum(path.stat().st_size for _, path in pairs if path.exists())
            try:
                free = size_label(shutil.disk_usage(HOME).free)
            except OSError:
                free = "?"
            busy = any(item["state"] == "downloading" for item in items)
            intro = [f"{len(fresh)} new  {self.g['sep']}  {len(stored)} downloaded "
                     f"({size_label(total(stored))})  {self.g['sep']}  {free} free on the SD card"]
            if not self.preferences["download"]:
                intro.append("Automatic downloads are off (Settings). Links stream when played.")
            if not items:
                intro += ["The list is empty. Send links from Ubuntu:", "$ deck-add https://youtu.be/..."]
            labels = [f"Play all new ({len(fresh)})",
                      f"Delete watched downloads ({len(watched_files)}, {size_label(total(watched_files))})",
                      "Clear watched (removes their entries and downloads)"] + [
                f"{self.g['off'] if item['done'] else self.g['on']} {self.watch_badge(item):<5}{watch_label(item)}"
                for item in items]
            choice = self.menu("WATCH LIST", labels, intro=intro, selected=selected, poll=busy)
            if choice == -1:
                selected = self.last_selected
                continue
            if choice is None:
                return
            selected = choice
            if choice == 0:
                if fresh:
                    self.play_items(fresh)
                continue
            if choice == 1:
                edit_watch(lambda items: [delete_download(i) for i in items if i["done"]])
                continue
            if choice == 2:
                edit_watch(drop_watched)
                selected = 0
                continue
            self.watch_item(items[choice - 3])

    def watch_item(self, item):
        url = item["url"]
        path = watch_file(item)
        options = []
        if path:
            options.append(("Play (downloaded)", lambda: self.play_items([item])))
        elif item["state"] == "downloading":
            options.append((f"Play stream now (slow start, download at {item['progress'] or '0%'})",
                            lambda: self.play_items([item])))
        else:
            options.append(("Play stream (slow start)", lambda: self.play_items([item])))
        options.append(("Listen in the background (audio only)",
                        lambda: self.music_start([watch_file(item) or item["url"]], "LINK", watch_label(item))))
        options.append(("Mark as " + ("new" if item["done"] else "watched"),
                        lambda: set_watch(url, done=not item["done"])))
        if path:
            options.append((f"Delete download ({size_label(path.stat().st_size)}), keep the link",
                            lambda: edit_watch(lambda items: [delete_download(i) for i in items
                                                              if i["url"] == url])))
        elif item["state"] in ("failed", "deleted") or (item["state"] == "ready" and not path):
            def again():
                set_watch(url, state="", progress="", error="", file="")
                spawn_worker()
            options.append(("Download again", again))

        def remove(items):
            for i in items:
                if i["url"] == url:
                    delete_download(i)
            items[:] = [i for i in items if i["url"] != url]
        options.append(("Remove from list" + (" and delete the download" if path else ""),
                        lambda: edit_watch(remove)))
        options.append(("Back", lambda: None))
        status = {"downloading": "Downloading " + (item["progress"] or ""), "failed": "Download failed: " + item["error"],
                  "deleted": "Download deleted.", "ready": "Downloaded: " + (item["file"] or "")}.get(
            item["state"], "Waiting to download." if self.preferences["download"] and not item["done"] else "")
        intro = [url, "Added " + (item["added"] or "?")] + ([status] if status else [])
        choice = self.menu("WATCH LIST // " + watch_label(item)[:50], [label for label, _ in options], intro=intro)
        if choice is not None:
            options[choice][1]()

    def play_items(self, items):
        targets = [watch_file(item) or item["url"] for item in items]
        if self.play(targets):
            urls = {item["url"] for item in items}
            edit_watch(lambda entries: [i.update(done=True) for i in entries if i["url"] in urls])

    def video_install(self):
        args = ["sudo", "apt-get", "install", "--no-install-recommends", "mpv", "quickjs"]
        if self.confirm("VIDEO // install player", args):
            self.run(args)
            if not ytdlp_path():
                self.video_update()

    def video_update(self):
        try:
            version = self.busy("VIDEO // yt-dlp", "Downloading the latest yt-dlp release", update_ytdlp)
            self.notice("VIDEO", f"yt-dlp {version} installed and checksum verified.")
        except (OSError, ValueError) as error:
            self.notice("VIDEO", f"Update failed: {error}", ok=False)

    def video_output_cycle(self):
        settings = dict(self.preferences)
        settings["video_out"] = VIDEO_OUTPUTS[(VIDEO_OUTPUTS.index(settings["video_out"]) + 1)
                                              % len(VIDEO_OUTPUTS)]
        save_settings(settings)
        self.preferences = settings

    def video_pick(self, root, on_play=None, kinds=MEDIA_EXT, label="VIDEO"):
        on_play = on_play or self.play
        root.mkdir(exist_ok=True)
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
                            and p.suffix.lower() in kinds), key=lambda p: p.name.lower())
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
            example = "movie.mp4" if label == "VIDEO" else "album/*.mp3"
            intro = None if files or dirs else [
                "Nothing here yet. Copy files from Ubuntu with:",
                f"$ scp {example} {self.user}@{self.host}.local:{where}/"]
            choice = self.menu(label + " // " + where, labels, intro=intro, selected=selected)
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
                on_play(files)
            elif index < len(dirs):
                current, selected = dirs[index], 0
            else:
                on_play(files[index - len(dirs):] if label == "MUSIC" else [files[index - len(dirs)]])

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
        ytdlp = ytdlp_path()
        if ytdlp:
            args.append("--script-opts-append=ytdl_hook-ytdl_path=" + ytdlp)
            if ytdlp_js_options(ytdlp):
                args.append("--ytdl-raw-options-append=js-runtimes=quickjs")
        if output == "screen":
            args += ["--fs", "--hwdec=auto-safe", "--profile=fast"]
            if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                args.append("--vo=gpu,drm")  # draw straight on the display, no desktop needed
        else:
            args += ["--vo=tct", "--hwdec=auto-copy-safe", "--framedrop=decoder+vo", "--really-quiet"]
            if self.basic:
                args.append("--vo-tct-256=yes")
        args += ["--", *map(str, targets)]
        code = self.run(args, pause=False)
        if code not in (0, None) and any(str(t).startswith(("http://", "https://")) for t in targets):
            self.notice("VIDEO", "The stream did not play. Video sites change often: choose "
                        "Update yt-dlp in Video player, then try again. " + ytdlp_status(), ok=False)
        return code == 0

    def music_monitor(self):
        """Background thread: what's playing (background player or Spotify), once a second."""
        last_spotify = False
        while True:
            try:
                local = music_status()
                spotify = spotify_status() if SPOTIFYD.exists() or shutil.which("spotifyd") else None
                spotify_playing = bool(spotify and not spotify["paused"])
                if spotify_playing and not last_spotify and local and not local["paused"]:
                    mpv_ipc(["set_property", "pause", True])  # Spotify took over: pause the deck player
                    local["paused"] = True
                last_spotify = spotify_playing
                if spotify_playing or (spotify and not local):
                    self.np = spotify
                else:
                    self.np = local or spotify
                self.np_time = time.monotonic()
            except Exception:  # the monitor must never take the deck down
                self.np = None
            for _ in range(10):
                time.sleep(0.1)
                if self.np_time == 0.0:  # a key asked for a refresh
                    break

    def draw_np(self, row, width, compact=False):
        """The now-playing strip: badge, equalizer, title — artist, progress."""
        np = self.np
        if not np:
            return
        g = self.g
        pos = np["pos"] + (0 if np["paused"] else max(0.0, time.monotonic() - self.np_time))
        if np["dur"]:
            pos = min(pos, np["dur"])
        if np["paused"]:
            eq = "||"
        elif self.preferences["fx"]:
            phase = int(time.monotonic() * 6)
            eq = "".join(g["spark"][(phase * (i + 3) + i * 5) % len(g["spark"])] for i in range(4))
        else:
            eq = g["note"]
        text = np["title"] + (f" {g['sep']} {np['artist']}" if np["artist"] else "")
        if np["live"]:
            tail = f"{g['on']} LIVE"
        else:
            tail = clock(pos) + (" / " + clock(np["dur"]) if np["dur"] else "")
        if compact:
            strip = f" {g['note']} {eq} {text}  {tail} "
            room = min(len(strip), max(0, width // 2))
            if room < 16:
                return
            if len(strip) > room:
                strip = f" {g['note']} {eq} " + text[:max(4, room - len(tail) - 10)] + f"{g['sep']}  {tail} "
            column = max(1, width - len(strip) - 3)
            self.put(row, g["lj"], DIM, column=column - 1)
            self.put(row, strip, HINT, column=column, limit=width - column - 2)
            self.put(row, g["rj"], DIM, column=min(width - 2, column + len(strip)))
            return
        column = self.put(row, f" {g['note']} ", KEYCAP, True, column=1)
        column = self.put(row, f" {np['src']} ", DIM, column=column)
        column = self.put(row, eq + " ", VIT, True, column=column)
        bar = ""
        if not np["live"] and np["dur"]:
            span = 10 if width >= 70 else 6
            filled = round(span * pos / np["dur"]) if np["dur"] else 0
            bar = g["full"] * filled + g["empty"] * (span - filled)
        right = len(tail) + (len(bar) + 1 if bar else 0) + 2
        self.put(row, text, TEXT, True, column=column, limit=max(0, width - column - right - 2))
        column = width - right - 1
        if bar:
            filled = bar.count(g["full"])
            column = self.put(row, bar[:filled], HINT, column=column)
            column = self.put(row, bar[filled:], DIM, column=column) + 1
        self.put(row, tail, HEAD if np["live"] else HINT, np["live"], column=column)

    def music_start(self, targets, source, name=""):
        if not targets:
            return
        try:
            self.busy("MUSIC", "Starting the player", lambda: music_play(targets, source, name))
            self.np_time = 0.0
        except (OSError, ValueError) as error:
            self.notice("MUSIC", f"Could not play: {error}", ok=False)

    def music(self):
        """Background music: radio, files, links and Spotify Connect, with a now-playing strip everywhere."""
        selected = 0
        while True:
            np = self.np
            intro = []
            options = []
            if np:
                pos = np["pos"] + (0 if np["paused"] else max(0.0, time.monotonic() - self.np_time))
                state = "Paused" if np["paused"] else "Playing"
                intro.append([(f"{state} {self.g['sep']} {np['src']}  ", DIM), (np["title"], TEXT)])
                if np["artist"]:
                    intro.append([(np["artist"], HINT)])
                if np["live"]:
                    intro.append([(f"{self.g['on']} LIVE", HEAD)])
                elif np["dur"]:
                    span = 30
                    filled = round(span * min(pos, np["dur"]) / np["dur"])
                    intro.append([(self.g["full"] * filled, HINT), (self.g["empty"] * (span - filled), DIM),
                                  (f" {clock(pos)} / {clock(np['dur'])}", TEXT)])
                if np["count"] > 1:
                    intro.append([(f"Track {np['index'] + 1} of {np['count']}", DIM)])
                if np["src"] == "SPOTIFY":
                    intro.append([("Spotify Connect: you can also control it from the Spotify app.", DIM)])
                options += [("Resume" if np["paused"] else "Pause", lambda: np_control(np, "toggle")),
                            ("Next", lambda: np_control(np, "next")), ("Previous", lambda: np_control(np, "prev"))]
                if not np["live"]:
                    options += [("Forward 30 s", lambda: np_control(np, "forward")),
                                ("Back 10 s", lambda: np_control(np, "back"))]
                options.append(("Stop", lambda: np_control(np, "stop")))
            else:
                intro.append([("Nothing playing. Music keeps going while you use the rest of the deck.", DIM)])
            intro.append([("Dashboard keys: space pause, [ ] previous/next, + - volume.", DIM)])
            options += [("Radio", self.radio),
                        ("Music files (~/Music)", lambda: self.video_pick(
                            MUSIC, on_play=lambda files: self.music_start(files, "MUSIC"), kinds=AUDIO_EXT,
                            label="MUSIC")),
                        ("Shuffle all music", self.music_shuffle),
                        ("Listen to a link (YouTube, SoundCloud...)", self.music_link),
                        ("Spotify", self.spotify)]
            labels = [label.split(" ")[0] for label, _ in options]
            if labels != getattr(self, "music_labels", labels):
                selected = 0  # controls appeared or vanished: start from the top
            self.music_labels = labels
            choice = self.menu("MUSIC & RADIO", [label for label, _ in options], intro=intro,
                               selected=selected, poll=True)
            if choice == -1:
                selected = self.last_selected
                continue
            if choice is None:
                return
            selected = choice
            options[choice][1]()
            self.np_time = 0.0
            time.sleep(0.15)

    def music_shuffle(self):
        files = [Path(folder, name) for folder, _, names in os.walk(MUSIC) for name in names
                 if Path(name).suffix.lower() in AUDIO_EXT][:5000]
        if not files:
            self.notice("MUSIC", "No music in ~/Music yet. Copy some from Ubuntu: scp -r album "
                        f"{self.user}@{self.host}.local:~/Music/", ok=False)
            return
        random.shuffle(files)
        self.music_start(files, "MUSIC", "Shuffle")

    def music_link(self):
        value = self.ask("MUSIC // link to play as audio", prefix="")
        if not value:
            return
        value = re.sub(r"\\([?=&#%+!*;~])", r"\1", value.strip())
        if not public_url(value, ("https", "http"), allow_query=True):
            self.notice("MUSIC", "Use a plain http(s) link.", ok=False)
            return
        self.music_start([value], "LINK", value)

    def radio(self):
        selected = 0
        while True:
            custom = load_stations()
            stations = list(STATIONS) + custom
            labels = [name for name, _ in stations] + ["All Sveriges Radio channels", "Add a station (stream URL)"]
            if custom:
                labels.append("Remove a station")
            choice = self.menu("MUSIC // radio", labels, selected=selected,
                               intro=["Live streams. They keep playing in the background."])
            if choice is None:
                return
            selected = choice
            if choice < len(stations):
                name, url = stations[choice]
                self.music_start([url], "RADIO", name)
                return
            action = labels[choice]
            if action.startswith("All Sveriges"):
                channels = self.busy("MUSIC // radio", "Fetching Sveriges Radio channels", sr_channels)
                if not channels:
                    self.notice("MUSIC", "Could not reach Sveriges Radio. Check the network.", ok=False)
                    continue
                pick = self.menu("MUSIC // Sveriges Radio", [name for name, _ in channels])
                if pick is not None:
                    self.music_start([channels[pick][1]], "RADIO", channels[pick][0])
                    return
            elif action.startswith("Add"):
                url = self.ask("RADIO // stream URL (http or https)", prefix="")
                if not url or not public_url(url.strip(), ("https", "http"), allow_query=True):
                    continue
                name = self.ask("RADIO // name for this station", prefix="") or url.strip()
                save_stations(custom + [(clean(name.strip())[:60], url.strip())])
                selected = len(STATIONS) + len(custom)  # land on the new station: Enter plays it
            else:
                pick = self.menu("MUSIC // remove station", [name for name, _ in custom])
                if pick is not None:
                    save_stations(custom[:pick] + custom[pick + 1:])

    def spotify(self):
        selected = 0
        while True:
            installed = SPOTIFYD.exists()
            missing = [tool for tool in ("playerctl", "pipewire-pulse") if not shutil.which(tool)]
            active = installed and user_systemctl("is-active", "nightdeck-spotifyd").stdout.strip() == "active"
            intro = ["Spotify Connect turns the deck into a speaker named \"Nightdeck\". Open Spotify on your "
                     "phone or computer on the same Wi-Fi, tap the devices icon and pick Nightdeck. "
                     "Needs Spotify Premium.",
                     "spotifyd: " + ("running" if active else "installed, not running" if installed else "not installed")]
            options = []
            if missing:
                intro.append("Needs: " + ", ".join(missing) + " (PipeWire's PulseAudio service and playerctl).")
                options.append(("Install Spotify support packages", self.spotify_packages))
            if not installed:
                options.append(("Install Spotify Connect (spotifyd)", self.spotify_install))
            else:
                options += [("Turn Spotify Connect " + ("off" if active else "on"), lambda: self.spotify_power(not active)),
                            ("Restart Spotify Connect", lambda: self.spotify_power(True, restart=True)),
                            ("Update spotifyd", self.spotify_install)]
            choice = self.menu("MUSIC // Spotify", [label for label, _ in options], intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            options[choice][1]()

    def spotify_packages(self):
        args = ["sudo", "apt-get", "install", "--no-install-recommends", *SPOTIFY_PACKAGES]
        if self.confirm("SPOTIFY // packages", args):
            self.run(args)

    def spotify_install(self):
        try:
            asset = self.busy("SPOTIFY", "Downloading spotifyd and checking its SHA-512", install_spotifyd)
        except (OSError, ValueError, tarfile.TarError) as error:
            self.notice("SPOTIFY", f"Install failed: {error}", ok=False)
            return
        self.spotify_power(True, restart=True)
        self.notice("SPOTIFY", f"Installed {asset}. Pick \"Nightdeck\" in the Spotify app's device list. "
                    "It starts automatically with the deck.")

    def spotify_power(self, on, restart=False):
        write_spotify_service()
        user_systemctl("daemon-reload")
        if on:
            result = user_systemctl("enable", "--now", "nightdeck-spotifyd")
            if restart and result.returncode == 0:
                result = user_systemctl("restart", "nightdeck-spotifyd")
        else:
            result = user_systemctl("disable", "--now", "nightdeck-spotifyd")
        if result.returncode:
            self.notice("SPOTIFY", "systemd said: " + clean(result.stderr.strip() or result.stdout.strip())[:200],
                        ok=False)

    def audio_monitor(self):
        """Background thread: refresh the connected Bluetooth device and sound output every few seconds."""
        while True:
            state = {}
            try:
                if shutil.which("bluetoothctl"):
                    connected = bt_devices("Connected")
                    state["bt"] = connected[0][1] if connected else ""
                if shutil.which("wpctl"):
                    sink, volume, muted = audio_default()
                    names = {item["id"]: item for item in audio_sinks()} if sink is not None else {}
                    if sink in names:
                        state.update(sink=names[sink]["desc"], volume=volume, muted=muted)
            except Exception:  # never let the monitor take the deck down
                pass
            self.audio = state
            time.sleep(5)

    def save_pref(self, **changes):
        settings = dict(self.preferences, **changes)
        save_settings(settings)
        self.preferences = settings

    def bluetooth(self):
        """Pair and connect Bluetooth devices and pick where sound goes."""
        selected = 0
        while True:
            missing = [tool for tool in ("bluetoothctl", "wpctl", "pw-dump") if not shutil.which(tool)]
            adapter = bt_adapter() if "bluetoothctl" not in missing else {}
            powered = adapter.get("Powered") == "yes"
            sink, volume, muted = audio_default() if "wpctl" not in missing else (None, None, False)
            sinks = audio_sinks() if "pw-dump" not in missing else []
            current = next((item["desc"] for item in sinks if item["id"] == sink), "unknown")
            intro = []
            options = []
            if missing:
                intro.append("Bluetooth sound needs: " + ", ".join(missing) + ".")
                options.append(("Install Bluetooth & sound support", self.bt_install))
            if "bluetoothctl" not in missing:
                if not adapter:
                    intro.append("No Bluetooth adapter found. Check: sudo systemctl status bluetooth")
                elif bt_blocked():
                    intro.append("Bluetooth is blocked (rfkill).")
                    options.append(("Unblock Bluetooth", lambda: self.run(["sudo", "rfkill", "unblock", "bluetooth"])))
                else:
                    connected = bt_devices("Connected") if powered else []
                    intro.append("Bluetooth " + ("on" if powered else "off") + (
                        f"  {self.g['sep']}  connected: " + ", ".join(name for _, name in connected) if connected else ""))
                    options.append(("Turn Bluetooth " + ("off" if powered else "on"), lambda: self.bt_power(not powered)))
                    if powered:
                        options[0:0] = [("Scan for devices", self.bt_scan), ("Paired devices", self.bt_paired)]
            if volume is not None:
                intro.append(f"Sound: {current}  {self.g['sep']}  " + ("muted" if muted else f"{volume}%"))
                options += [("Sound output", lambda: self.sound_output(sinks, sink)),
                            ("Volume / " + ("muted" if muted else f"{volume}%"), self.volume_menu)]
            if self.telemetry.link[0] and self.telemetry.link[0].startswith("wl"):
                intro.append("Tip: Wi-Fi and Bluetooth share one radio on the Pi 3B; sound may crackle "
                             "while Wi-Fi is busy. Downloaded videos sound best.")
            choice = self.menu("BLUETOOTH & SOUND", [label for label, _ in options], intro=intro, selected=selected)
            if choice is None:
                return
            selected = choice
            options[choice][1]()

    def bt_install(self):
        args = ["sudo", "apt-get", "install", "--no-install-recommends", *BT_PACKAGES]
        if self.confirm("BLUETOOTH // install", args):
            self.run(args)
            self.run(["systemctl", "--user", "enable", "--now", "pipewire.socket", "wireplumber.service"],
                     pause=False)
            self.notice("BLUETOOTH", "Installed. If sound devices don't show up, reboot the deck once.")

    def bt_power(self, on):
        code, out = self.busy("BLUETOOTH", "Turning Bluetooth " + ("on" if on else "off"),
                              lambda: btctl("power", "on" if on else "off"))
        if code and on:
            hint = " It is blocked: choose Unblock Bluetooth." if "Blocked" in out or bt_blocked() else ""
            self.notice("BLUETOOTH", "Could not turn Bluetooth on." + hint, ok=False)

    def bt_scan(self):
        paired = {mac for mac, _ in bt_devices("Paired")}

        def scan():
            btctl("--timeout", "12", "scan", "on", timeout=25)
            found = []
            for mac, name in bt_devices():
                if mac in paired or not name or re.fullmatch(r"[0-9A-F]{2}(?:-[0-9A-F]{2}){5}", name):
                    continue
                info = bt_info(mac)
                # BlueZ prints "RSSI: 0xffffffd0 (-48)" (newer) or "RSSI: -48" (older)
                raw = info.get("RSSI", "")
                rssi = re.search(r"\((-?\d+)\)", raw) or re.fullmatch(r"\s*(-?\d+)\s*", raw)
                found.append((int(rssi.group(1)) if rssi else -999, mac, info.get("Name") or name, info["kind"]))
            return sorted(found, reverse=True)
        found = self.busy("BLUETOOTH // scanning", "Scanning for 12 seconds. Put your device in pairing mode now.",
                          scan)
        if not found:
            self.notice("BLUETOOTH", "No new devices found. Put the device in pairing mode (often: hold the "
                        "power button until the light flashes) and scan again.", ok=False)
            return
        labels = [f"{name}" + (f"  [{kind}]" if kind else "") + (f"  {rssi} dBm" if rssi > -999 else "")
                  for rssi, mac, name, kind in found]
        choice = self.menu("BLUETOOTH // found " + str(len(found)), labels,
                           intro=["Choose a device to pair and connect. Nearest first."])
        if choice is not None:
            _, mac, name, _ = found[choice]
            self.bt_pair(mac, name)

    def bt_pair(self, mac, name):
        self.run(["bluetoothctl", "--timeout", "40", "pair", mac], pause=False)
        if bt_info(mac).get("Paired") != "yes":
            self.notice("BLUETOOTH", f"Pairing with {name} did not finish. Put it in pairing mode and try again. "
                        "If it asked for a PIN, type it on the device.", ok=False)
            return
        btctl("trust", mac)
        self.bt_connect(mac, name)

    def bt_connect(self, mac, name):
        def connect():
            btctl("connect", mac, timeout=30)
            info = bt_info(mac)
            if info.get("Connected") != "yes":
                return False, info
            if info["kind"] in ("headphones", "speaker"):
                for _ in range(16):  # PipeWire adds the Bluetooth output a moment after connecting
                    sink = next((item for item in audio_sinks() if item["bt"] and
                                 (item["desc"] == info.get("Alias") or item["desc"] == name)), None) or \
                        next((item for item in audio_sinks() if item["bt"]), None)
                    if sink:
                        wpctl("set-default", str(sink["id"]))
                        return True, info
                    time.sleep(0.5)
            return True, info
        ok, info = self.busy("BLUETOOTH", f"Connecting to {name}", connect)
        if not ok:
            self.notice("BLUETOOTH", f"Could not connect to {name}. Make sure it is on and nearby.", ok=False)
            return
        sound = info["kind"] in ("headphones", "speaker")
        self.notice("BLUETOOTH", f"Connected to {name}." + (" Sound now plays there." if sound else ""))

    def bt_paired(self):
        selected = 0
        while True:
            devices = bt_devices("Paired")
            if not devices:
                self.notice("BLUETOOTH", "No paired devices yet. Choose Scan for devices.", ok=False)
                return
            infos = [bt_info(mac) for mac, _ in devices]
            labels = [(self.g["on"] if info.get("Connected") == "yes" else self.g["off"]) + f" {name}"
                      + (f"  [{info['kind']}]" if info["kind"] else "")
                      + (f"  {info['battery']}%" if info["battery"] else "")
                      + ("  auto" if mac == self.preferences["bt_auto"] else "")
                      for (mac, name), info in zip(devices, infos)]
            choice = self.menu("BLUETOOTH // paired", labels, selected=selected)
            if choice is None:
                return
            selected = choice
            (mac, name), info = devices[choice], infos[choice]
            connected = info.get("Connected") == "yes"
            options = [("Disconnect" if connected else "Connect",
                        (lambda: self.busy("BLUETOOTH", f"Disconnecting {name}", lambda: btctl("disconnect", mac)))
                        if connected else (lambda: self.bt_connect(mac, name)))]
            sink = next((item for item in audio_sinks() if item["bt"]), None) if connected else None
            if sink:
                options.append(("Use for sound", lambda: wpctl("set-default", str(sink["id"]))))
            auto = mac == self.preferences["bt_auto"]
            options += [("Auto-connect at startup: " + ("on" if auto else "off"),
                         lambda: self.save_pref(bt_auto="" if auto else mac)),
                        ("Forget this device", lambda: (btctl("remove", mac),
                                                        self.save_pref(bt_auto="") if auto else None)),
                        ("Back", lambda: None)]
            intro = [f"{name}  {self.g['sep']}  {mac}" + (f"  {self.g['sep']}  {info['kind']}" if info["kind"] else ""),
                     ("Connected" if connected else "Not connected")
                     + (f"  {self.g['sep']}  battery {info['battery']}%" if info["battery"] else "")]
            action = self.menu("BLUETOOTH // " + name[:40], [label for label, _ in options], intro=intro)
            if action is not None:
                options[action][1]()

    def sound_output(self, sinks, current):
        if not sinks:
            self.notice("SOUND", "No sound outputs found. Is PipeWire running? Try rebooting the deck.", ok=False)
            return
        labels = [(self.g["on"] if item["id"] == current else self.g["off"]) + " " + item["desc"]
                  + ("  [Bluetooth]" if item["bt"] else "") for item in sinks]
        choice = self.menu("SOUND // output", labels, intro=["Where Nightdeck and videos play sound."])
        if choice is not None:
            wpctl("set-default", str(sinks[choice]["id"]))

    def volume_menu(self):
        selected = 0
        while True:
            _, volume, muted = audio_default()
            if volume is None:
                return
            choice = self.menu("SOUND // " + ("muted" if muted else f"{volume}%"),
                               ["Volume up 10%", "Volume down 10%", "Unmute" if muted else "Mute"],
                               intro=["On the dashboard: + and - change volume, m mutes."], selected=selected)
            if choice is None:
                return
            selected = choice
            if choice == 2:
                wpctl("set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
            else:
                wpctl("set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "10%" + ("+" if choice == 0 else "-"))

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
                "Watch list downloads / " + ("On" if p["download"] else "Off"),
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
            elif choice == 6:
                settings["download"] = not p["download"]
                if settings["download"]:
                    save_settings(settings)
                    spawn_worker()
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


BT_MAC = re.compile(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x01|\x02")
BT_KINDS = {"audio-headset": "headphones", "audio-headphones": "headphones", "audio-card": "speaker",
            "input-keyboard": "keyboard", "input-mouse": "mouse", "input-gaming": "controller",
            "input-tablet": "tablet", "phone": "phone", "computer": "computer"}
BT_PACKAGES = ["bluez", "pipewire", "wireplumber", "libspa-0.2-bluetooth", "rfkill"]


def btctl(*args, timeout=15):
    """Run one bluetoothctl command; returns (exit code, output without colors)."""
    try:
        result = subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout,
                                stdin=subprocess.DEVNULL, check=False, errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return result.returncode, ANSI.sub("", result.stdout + result.stderr)


def bt_devices(kind=None):
    """[(mac, name)] for all known, or 'Paired' / 'Connected' devices."""
    _, out = btctl("devices", *([kind] if kind else []))
    devices = []
    for line in out.splitlines():
        match = re.match(r"^\s*Device (" + BT_MAC.pattern + r") (.*)$", line.strip())
        if match:
            devices.append((match.group(1), clean(match.group(2))[:60]))
    return devices


def bt_info(mac):
    if not BT_MAC.fullmatch(mac):
        return {}
    _, out = btctl("info", mac)
    info = {}
    for line in out.splitlines():
        key, sep, value = line.strip().partition(": ")
        if sep and key and key not in info:
            info[key] = clean(value)[:80]
    battery = re.search(r"\((\d+)\)", info.get("Battery Percentage", ""))
    info["battery"] = battery.group(1) if battery else ""
    info["kind"] = BT_KINDS.get(info.get("Icon", ""), "")
    return info


def bt_adapter():
    code, out = btctl("show")
    if code or "Controller" not in out:
        return {}
    return {key: value for key, _, value in (line.strip().partition(": ") for line in out.splitlines()) if value}


def bt_blocked():
    for kind in Path("/sys/class/rfkill").glob("rfkill*"):
        try:
            if (kind / "type").read_text().strip() == "bluetooth" and (kind / "soft").read_text().strip() == "1":
                return True
        except OSError:
            pass
    return False


def audio_sinks():
    """[{id, desc, bt}] audio outputs from PipeWire."""
    try:
        raw = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=8, check=False).stdout
        objects = json.loads(raw) if raw.strip() else []
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    sinks = []
    for obj in objects if isinstance(objects, list) else []:
        props = ((obj or {}).get("info") or {}).get("props") or {}
        if obj.get("type") == "PipeWire:Interface:Node" and props.get("media.class") == "Audio/Sink":
            sinks.append({"id": int(obj.get("id", 0)), "bt": props.get("device.api") == "bluez5",
                          "desc": clean(str(props.get("node.description") or props.get("node.name") or "?"))[:60]})
    return sinks


def wpctl(*args):
    try:
        return subprocess.run(["wpctl", *args], capture_output=True, text=True, timeout=8, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def audio_default():
    """(sink id or None, volume percent or None, muted)."""
    match = re.search(r"id (\d+)", wpctl("inspect", "@DEFAULT_AUDIO_SINK@"))
    volume = re.search(r"Volume: ([0-9.]+)(.*)", wpctl("get-volume", "@DEFAULT_AUDIO_SINK@"))
    return (int(match.group(1)) if match else None,
            round(float(volume.group(1)) * 100) if volume else None,
            bool(volume and "MUTED" in volume.group(2)))


def load_watch():
    try:
        raw = json.loads(WATCH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = []
    for item in raw.get("items", []) if isinstance(raw, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("url"), str) and public_url(
                item["url"], ("https", "http"), allow_query=True):
            name = item.get("file") if isinstance(item.get("file"), str) else ""
            if name in (".", "..") or "/" in name or "\0" in name:
                name = ""
            items.append({"url": item["url"], "title": clean(str(item.get("title") or ""))[:200],
                          "added": clean(str(item.get("added") or ""))[:40],
                          "done": item.get("done") is True, "tried": item.get("tried") is True,
                          "file": name[:255],
                          "state": item.get("state") if item.get("state") in DL_STATES else "",
                          "progress": clean(str(item.get("progress") or ""))[:8],
                          "error": clean(str(item.get("error") or ""))[:200]})
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


def ytdlp_path():
    """Prefer the self-updating release in ~/.local/bin over Debian's older package."""
    if YTDLP_LOCAL.is_file() and os.access(YTDLP_LOCAL, os.X_OK):
        return str(YTDLP_LOCAL)
    return shutil.which("yt-dlp")


_YTDLP_VERSIONS = {}


def ytdlp_version(path):
    try:
        key = (path, Path(path).stat().st_mtime)
    except (OSError, TypeError):
        return ""
    if key not in _YTDLP_VERSIONS:
        try:
            out = subprocess.run([path, "--version"], capture_output=True, text=True,
                                 timeout=60, check=False).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        _YTDLP_VERSIONS[key] = out if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(?:\.\d+)?", out) else ""
    return _YTDLP_VERSIONS[key]


def ytdlp_js_options(path):
    """YouTube needs a JavaScript runtime since yt-dlp 2025.11. Deno has no 32-bit ARM build, so use QuickJS."""
    version = ytdlp_version(path)
    if version >= "2025.11" and not shutil.which("deno") and shutil.which("qjs"):
        return ["--js-runtimes", "quickjs"]
    return []


def ytdlp_status():
    path = ytdlp_path()
    if not path:
        return "YouTube: yt-dlp missing. Choose Update yt-dlp."
    version = ytdlp_version(path)
    if not version or version < "2025.11":
        return f"YouTube: yt-dlp {version or '(unknown version)'} is too old. Choose Update yt-dlp."
    if not (shutil.which("deno") or shutil.which("qjs")):
        return f"YouTube: yt-dlp {version}, needs QuickJS: sudo apt install quickjs"
    return f"YouTube: yt-dlp {version} + " + ("Deno" if shutil.which("deno") else "QuickJS") + " ready."


def fetch_url(url, limit):
    """Download over HTTPS with a size cap."""
    request = urllib.request.Request(url, headers={"User-Agent": "Nightdeck/" + VERSION})
    with urllib.request.urlopen(request, timeout=60) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise ValueError("Download redirected away from HTTPS.")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(url.rsplit("/", 1)[-1] + " is larger than expected.")
    return data


def install_binary(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        file.write(data)
    try:
        temp.chmod(0o755)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def update_ytdlp():
    """Download the latest official yt-dlp release, check its SHA-256, install it to ~/.local/bin."""
    def fetch(name, limit):
        return fetch_url(YTDLP_RELEASE + name, limit)
    sums = fetch("SHA2-256SUMS", 64 * 1024).decode("utf-8", "replace")
    expected = next((line.split()[0].lower() for line in sums.splitlines()
                     if len(line.split()) == 2 and line.split()[1].lstrip("*") == "yt-dlp"), None)
    if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Release checksums did not list yt-dlp.")
    binary = fetch("yt-dlp", 64 * 1024 * 1024)
    if hashlib.sha256(binary).hexdigest() != expected:
        raise ValueError("Checksum mismatch: download rejected.")
    install_binary(YTDLP_LOCAL, binary)
    return ytdlp_version(str(YTDLP_LOCAL)) or "installed"


# ---------- music: background mpv + Spotify Connect ----------

MUSIC = HOME / "Music"
AUDIO_EXT = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".aac", ".wma", ".aiff", ".alac"}
MUSIC_STATE = DATA / "music.json"
STATIONS_FILE = DATA / "stations.json"
STATIONS = (  # official stream addresses (Sveriges Radio API, SomaFM)
    ("SR P1", "https://www.sverigesradio.se/topsy/direkt/srapi/132.mp3"),
    ("SR P2", "https://www.sverigesradio.se/topsy/direkt/srapi/163.mp3"),
    ("SR P3", "https://www.sverigesradio.se/topsy/direkt/srapi/164.mp3"),
    ("SomaFM DEF CON Radio", "https://ice2.somafm.com/defcon-128-mp3"),
    ("SomaFM Vaporwaves", "https://ice2.somafm.com/vaporwaves-128-mp3"),
    ("SomaFM Groove Salad", "https://ice2.somafm.com/groovesalad-128-mp3"),
    ("SomaFM Drone Zone", "https://ice2.somafm.com/dronezone-128-mp3"),
)
SR_CHANNELS = "https://api.sr.se/api/v2/channels?format=json&pagination=false"
SPOTIFYD = HOME / ".local/bin/spotifyd"
SPOTIFYD_RELEASE = "https://github.com/Spotifyd/spotifyd/releases/latest/download/"
SPOTIFY_CONF = CONFIG / "spotifyd.conf"
SPOTIFY_UNIT = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "systemd/user/nightdeck-spotifyd.service"
SPOTIFY_PACKAGES = ["pipewire-pulse", "libpulse0", "playerctl", "dbus-user-session"]


def music_socket():
    path = Path(os.environ.get("XDG_RUNTIME_DIR") or CACHE) / "nightdeck-music.sock"
    if len(str(path)) <= 100:
        return path
    # Unix socket paths max out near 108 bytes: fall back to a private folder in /tmp.
    private = Path(tempfile.gettempdir()) / f"nightdeck-{os.getuid()}"
    try:
        private.mkdir(mode=0o700, exist_ok=True)
        info = private.lstat()
        if private.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise OSError("unsafe socket folder")
    except OSError:
        return path
    return private / "music.sock"


def mpv_ipc(*commands, timeout=0.5):
    """Send commands to the background player; returns their results, or None if it isn't running."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(music_socket()))
    except OSError:
        return None
    results, buffer = {}, b""
    with sock:
        try:
            sock.sendall("".join(json.dumps({"command": list(c), "request_id": i}) + "\n"
                                 for i, c in enumerate(commands, 1)).encode())
            end = time.monotonic() + timeout
            while len(results) < len(commands) and time.monotonic() < end:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(message, dict) and "request_id" in message:
                        results[message["request_id"]] = (message.get("data")
                                                          if message.get("error") == "success" else None)
        except OSError:
            pass
    return [results.get(i) for i in range(1, len(commands) + 1)]


def music_play(targets, source, name=""):
    """Play files/URLs in the background player (started on demand); pauses Spotify."""
    mpv = shutil.which("mpv")
    if not mpv:
        raise ValueError("mpv is not installed.")
    if mpv_ipc(["get_property", "pid"]) is None:
        path = music_socket()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        args = [mpv, "--idle=yes", "--no-video", "--no-terminal", "--audio-display=no",
                "--input-ipc-server=" + str(path), "--ytdl-format=bestaudio/best", "--cache=yes",
                "--demuxer-max-bytes=16MiB"]
        ytdlp = ytdlp_path()
        if ytdlp:
            args.append("--script-opts-append=ytdl_hook-ytdl_path=" + ytdlp)
            if ytdlp_js_options(ytdlp):
                args.append("--ytdl-raw-options-append=js-runtimes=quickjs")
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        end = time.monotonic() + 5
        while mpv_ipc(["get_property", "pid"]) is None:
            if time.monotonic() > end:
                raise ValueError("The background player did not start.")
            time.sleep(0.1)
    if shutil.which("playerctl"):
        subprocess.run(["playerctl", "-p", "spotifyd", "pause"], capture_output=True, timeout=3, check=False)
    commands = [["loadfile", str(targets[0]), "replace"]]
    commands += [["loadfile", str(target), "append"] for target in targets[1:]]
    mpv_ipc(*commands, ["set_property", "pause", False], timeout=3)
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    MUSIC_STATE.write_text(json.dumps({"source": source, "name": clean(name)[:80]}), encoding="utf-8")


def music_status():
    """Now-playing info from the background player, or None."""
    names = ("idle-active", "pause", "media-title", "metadata", "time-pos", "duration",
             "playlist-pos", "playlist-count")
    values = mpv_ipc(*[["get_property", name] for name in names])
    if values is None or values[0] is not False:
        return None
    _, paused, media_title, metadata, position, duration, index, count = values
    meta = {str(k).lower(): clean(str(v)) for k, v in (metadata or {}).items()} if isinstance(metadata, dict) else {}
    try:
        state = json.loads(MUSIC_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    source = state.get("source") if state.get("source") in ("RADIO", "MUSIC", "LINK") else "MUSIC"
    title, artist = meta.get("title", ""), meta.get("artist", "")
    if not title and meta.get("icy-title"):
        artist, _, title = meta["icy-title"].rpartition(" - ")
    station = clean(str(state.get("name") or meta.get("icy-name") or ""))
    title = title or (station if source == "RADIO" else "") or clean(str(media_title or ""))
    if source == "RADIO" and station and not artist:
        artist = station
    live = source == "RADIO" or not isinstance(duration, (int, float))
    return {"src": source, "title": title[:120], "artist": artist[:80], "paused": bool(paused),
            "pos": float(position) if isinstance(position, (int, float)) else 0.0,
            "dur": float(duration) if isinstance(duration, (int, float)) else 0.0, "live": live,
            "index": index if isinstance(index, int) else 0, "count": count if isinstance(count, int) else 0}


def spotify_status():
    if not shutil.which("playerctl"):
        return None
    try:
        result = subprocess.run(["playerctl", "-p", "spotifyd", "metadata", "--format",
                                 "{{status}}\t{{artist}}\t{{title}}\t{{mpris:length}}\t{{position}}"],
                                capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    parts = result.stdout.rstrip("\n").split("\t")
    if result.returncode or len(parts) != 5 or parts[0] not in ("Playing", "Paused"):
        return None
    status, artist, title, length, position = parts
    return {"src": "SPOTIFY", "title": clean(title)[:120], "artist": clean(artist)[:80],
            "paused": status == "Paused", "live": False, "index": 0, "count": 0,
            "pos": int(position) / 1e6 if position.isdigit() else 0.0,
            "dur": int(length) / 1e6 if length.isdigit() else 0.0}


def np_control(np, action):
    """toggle, next, prev, stop, forward, back for whatever is playing."""
    if np and np["src"] == "SPOTIFY":
        args = {"toggle": ["play-pause"], "next": ["next"], "prev": ["previous"], "stop": ["pause"],
                "forward": ["position", "30+"], "back": ["position", "10-"]}[action]
        subprocess.run(["playerctl", "-p", "spotifyd", *args], capture_output=True, timeout=3, check=False)
        return
    command = {"toggle": ["cycle", "pause"], "next": ["playlist-next", "weak"], "prev": ["playlist-prev", "weak"],
               "stop": ["quit"], "forward": ["seek", 30, "relative"], "back": ["seek", -10, "relative"]}[action]
    mpv_ipc(command)


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600 \
        else f"{seconds // 60}:{seconds % 60:02d}"


def load_stations():
    try:
        raw = json.loads(STATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [(clean(str(s.get("name")))[:60], s["url"]) for s in raw if isinstance(s, dict)
            and isinstance(s.get("url"), str) and public_url(s["url"], ("https", "http"), allow_query=True)][:100]


def save_stations(stations):
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATIONS_FILE.write_text(json.dumps([{"name": n, "url": u} for n, u in stations], ensure_ascii=False),
                             encoding="utf-8")


def sr_channels():
    """All Sveriges Radio channels with live streams (cached for offline menus)."""
    cache = CACHE / "sr-channels.json"
    try:
        data = json.loads(fetch_url(SR_CHANNELS, 2 * 1024 * 1024))
        channels = [(clean(str(c.get("name")))[:60], c["liveaudio"]["url"]) for c in data.get("channels", [])
                    if isinstance(c, dict) and isinstance(c.get("liveaudio"), dict)
                    and public_url(str(c["liveaudio"].get("url", "")), ("https", "http"), allow_query=True)]
        CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
        cache.write_text(json.dumps(channels, ensure_ascii=False), encoding="utf-8")
        return channels
    except (OSError, ValueError, KeyError, TypeError):
        try:
            return [tuple(c) for c in json.loads(cache.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []


def spotifyd_arch():
    return {"armv7l": "armv7", "armv8l": "armv7", "aarch64": "aarch64", "arm64": "aarch64",
            "x86_64": "x86_64", "amd64": "x86_64"}.get(os.uname().machine)


def install_spotifyd():
    """Download spotifyd's official 'default' build (with MPRIS), verify SHA-512, install to ~/.local/bin."""
    arch = spotifyd_arch()
    if not arch:
        raise ValueError(f"spotifyd has no build for {os.uname().machine}.")
    asset = f"spotifyd-linux-{arch}-default"
    sums = fetch_url(SPOTIFYD_RELEASE + asset + ".sha512", 64 * 1024).decode("utf-8", "replace")
    expected = next((token.lower() for token in sums.split() if re.fullmatch(r"[0-9a-fA-F]{128}", token)), None)
    if not expected:
        raise ValueError("The release checksum file was not readable.")
    blob = fetch_url(SPOTIFYD_RELEASE + asset + ".tar.gz", 64 * 1024 * 1024)
    if hashlib.sha512(blob).hexdigest() != expected:
        raise ValueError("Checksum mismatch: download rejected.")
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        member = next((m for m in archive.getmembers() if m.isfile() and Path(m.name).name == "spotifyd"), None)
        if member is None or member.size > 64 * 1024 * 1024:
            raise ValueError("The archive did not contain spotifyd.")
        install_binary(SPOTIFYD, archive.extractfile(member).read())
    write_spotify_service()
    return asset


def write_spotify_service(name="Nightdeck"):
    CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    SPOTIFY_CONF.write_text("\n".join([
        "# Written by Nightdeck. Spotify Connect speaker; pick it in the Spotify app (Premium).",
        "[global]",
        f'device_name = "{re.sub(r"[^A-Za-z0-9 _.-]", "", name)[:40] or "Nightdeck"}"',
        'device_type = "computer"',
        'backend = "pulseaudio"',
        "use_mpris = true",
        'dbus_type = "session"',
        "bitrate = 160",
        "volume_normalisation = true",
        f'cache_path = "{CACHE / "spotifyd"}"',
        "max_cache_size = 300000000",
        ""]), encoding="utf-8")
    SPOTIFY_UNIT.parent.mkdir(parents=True, exist_ok=True)
    SPOTIFY_UNIT.write_text("\n".join([
        "[Unit]", "Description=Spotify Connect for Nightdeck", "After=network-online.target pipewire-pulse.service", "",
        "[Service]", f"ExecStart={SPOTIFYD} --no-daemon --config-path {SPOTIFY_CONF}",
        "Restart=on-failure", "RestartSec=10", "", "[Install]", "WantedBy=default.target", ""]), encoding="utf-8")


def user_systemctl(*args):
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                              timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def watch_file(item):
    """The downloaded file for an entry, if it is still on disk."""
    if item["file"]:
        path = DOWNLOADS / item["file"]
        if path.parent == DOWNLOADS and path.is_file() and not path.is_symlink():
            return path
    return None


def delete_download(item):
    path = watch_file(item)
    if path:
        path.unlink(missing_ok=True)
    item.update(file="", state="deleted" if item["state"] == "ready" or path else item["state"], progress="")
    return path


def drop_watched(items):
    for item in items:
        if item["done"]:
            delete_download(item)
    items[:] = [item for item in items if not item["done"]]
    return len(items)


def set_watch(url, **fields):
    edit_watch(lambda items: [item.update(fields) for item in items if item["url"] == url])


def spawn_worker():
    """Start the background downloader (it exits at once if another one is running)."""
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "fetch"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def download_item(ytdlp, item):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    merge = bool(shutil.which("ffmpeg"))
    args = [ytdlp, *ytdlp_js_options(ytdlp), "--no-playlist", "--no-simulate", "--progress", "--newline",
            "--no-mtime", "--no-colors", "-f", DL_FORMAT_MERGE if merge else DL_FORMAT_SINGLE,
            "-o", str(DOWNLOADS / "%(title).80B [%(id)s].%(ext)s"),
            "--print", "video:TITLE %(title)s", "--print", "after_move:FILE %(filepath)s",
            "--progress-template",
            "download:PROG %(progress.downloaded_bytes)s %(progress.total_bytes,progress.total_bytes_estimate)s"]
    if merge:
        args += ["--merge-output-format", "mp4"]
    args += ["--", item["url"]]
    url, last, last_pct, saved = item["url"], 0.0, -10, ""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as errors:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
                                text=True, errors="replace")
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.startswith("TITLE "):
                set_watch(url, title=clean(line[6:])[:200])
            elif line.startswith("PROG "):
                parts = line.split()
                if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit() and int(parts[2]):
                    pct = min(100, int(parts[1]) * 100 // int(parts[2]))
                    if abs(pct - last_pct) >= 5 or time.monotonic() - last > 5:
                        last, last_pct = time.monotonic(), pct
                        set_watch(url, progress=f"{pct}%")
            elif line.startswith("FILE "):
                path = Path(line[5:]).resolve()
                if path.parent == DOWNLOADS.resolve() and path.is_file():
                    saved = path.name
        code = proc.wait()
        errors.seek(0)
        message = next((l.strip() for l in reversed(errors.read().splitlines()) if "ERROR" in l), "")
    if code == 0 and saved:
        set_watch(url, state="ready", file=saved, progress="", error="")
    else:
        set_watch(url, state="failed", progress="",
                  error=clean(message.replace("ERROR:", "").strip())[:200] or f"yt-dlp exit status {code}")


def run_downloads():
    """Background worker: download new watch-list links one at a time, oldest first."""
    if not load_settings()["download"]:
        fetch_titles()
        return
    ytdlp = ytdlp_path()
    if not ytdlp:
        return
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)

    def pending():
        return next((item for item in reversed(load_watch())
                     if not item["done"] and item["state"] == ""), None)
    while True:
        with open(DATA / "downloader.lock", "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return  # another worker is running and will pick up new links
            edit_watch(lambda items: [item.update(state="", progress="") for item in items
                                      if item["state"] == "downloading"])  # left over from a power cut
            while (item := pending()) is not None:
                if shutil.disk_usage(HOME).free < DL_MIN_FREE:
                    set_watch(item["url"], state="failed", error="Less than 500 MB free on the SD card.")
                    continue
                set_watch(item["url"], state="downloading", progress="0%", error="")
                try:
                    download_item(ytdlp, item)
                except OSError as error:
                    set_watch(item["url"], state="failed", error=clean(str(error))[:200])
        if pending() is None:  # re-check after unlocking so a link added just now isn't missed
            return


def watch_label(item):
    if item["title"]:
        return item["title"]
    url = urlsplit(item["url"])
    return (url.hostname or "") + url.path + ("?" + url.query if url.query else "")


def fetch_titles():
    """Look up titles for new links with yt-dlp. Runs detached after `nightdeck add`."""
    ytdlp = ytdlp_path()
    if not ytdlp:
        return
    extra = ytdlp_js_options(ytdlp)
    for url in [item["url"] for item in load_watch() if not item["title"] and not item["tried"]]:
        try:
            result = subprocess.run([ytdlp, *extra, "--no-warnings", "--skip-download", "--no-playlist",
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
             "       nightdeck clear           remove watched entries\n"
             "       nightdeck update-ytdlp    install or update yt-dlp for YouTube")
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
        if good and ytdlp_path():
            spawn_worker()
            if load_settings()["download"]:
                print("Downloading in the background on the deck.")
        return 0 if len(good) == len(links) and links else 1
    if name == "list":
        items = load_watch()
        for number, item in enumerate(items, 1):
            state = ("ready" if watch_file(item) else
                     {"downloading": "down " + item["progress"], "failed": "failed", "deleted": "deleted"}.get(
                         item["state"], "queued" if not item["done"] and load_settings()["download"] else ""))
            print(f"{number:3d} {'   ' if item['done'] else 'new'}  {state:<9} {watch_label(item)[:80]}")
        if not items:
            print("Watch list is empty. Add links with: nightdeck add URL")
        return 0
    if name == "remove" and len(rest) == 1 and rest[0].isdigit():
        index = int(rest[0]) - 1
        def change(items):
            if 0 <= index < len(items):
                delete_download(items[index])
                return items.pop(index)
            return None
        removed = edit_watch(change)
        print(f"Removed: {watch_label(removed)}" if removed else "No entry with that number.")
        return 0 if removed else 1
    if name == "clear":
        count = edit_watch(drop_watched)
        print(f"Removed watched entries. {count} left.")
        return 0
    if name == "update-ytdlp":
        try:
            print("[ OK ] yt-dlp " + update_ytdlp() + " installed in " + str(YTDLP_LOCAL))
        except (OSError, ValueError) as error:
            print(f"[ !! ] yt-dlp update failed: {error}", file=sys.stderr)
            return 1
        if not (shutil.which("deno") or shutil.which("qjs")):
            print("[ !! ] YouTube also needs QuickJS: sudo apt install quickjs")
        return 0
    if name == "fetch":
        run_downloads()
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
