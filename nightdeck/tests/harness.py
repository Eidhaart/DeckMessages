"""Drive nightdeck in a pseudo-terminal and capture screens with pyte (dev-only)."""
import fcntl, os, pty, select, struct, sys, termios, time, html
from pathlib import Path
import pyte

APP = Path(__file__).resolve().parent.parent / "nightdeck.py"


class Session:
    def __init__(self, cols=80, rows=24, home=None, env=None, term="xterm-256color"):
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.raw = b""
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update({"TERM": term, "HOME": home or os.environ["HOME"], "LANG": "C.UTF-8"})
            os.environ.update(env or {})
            os.execv(sys.executable, [sys.executable, str(APP)])
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.pid, self.fd = pid, fd

    def pump(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if ready:
                try:
                    data = os.read(self.fd, 65536)
                except OSError:
                    return False
                if not data:
                    return False
                self.raw += data
                self.stream.feed(data)
        return True

    def send(self, keys, wait=0.4):
        os.write(self.fd, keys.encode() if isinstance(keys, str) else keys)
        return self.pump(wait)

    def text(self):
        return "\n".join(self.screen.display)

    def finish(self, timeout=3):
        end = time.time() + timeout
        while time.time() < end:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                return os.waitstatus_to_exitcode(status)
            self.pump(0.1)
        os.kill(self.pid, 9)
        return None

    def html(self):
        rows = []
        for y in range(self.screen.lines):
            line = self.screen.buffer[y]
            cells = []
            for x in range(self.screen.columns):
                c = line[x]
                fg, bg = c.fg, c.bg
                if c.reverse:
                    fg, bg = bg, fg
                def col(v, default):
                    if v == "default":
                        return default
                    names = {"red": "#cd0000", "green": "#00cd00", "yellow": "#cdcd00", "brown": "#aa5500", "blue": "#0000ee",
                             "magenta": "#cd00cd", "cyan": "#00cdcd", "white": "#e5e5e5", "black": "#000",
                             "brightred": "#ff0000", "brightgreen": "#00ff00", "brightyellow": "#ffff00",
                             "brightcyan": "#00ffff", "brightwhite": "#fff"}
                    return names.get(v, "#" + v if len(v) == 6 else default)
                style = f"color:{col(fg, '#fafafa')};background:{col(bg, '#0e0e0e')}"
                if c.bold:
                    style += ";font-weight:bold"
                cells.append(f'<span style="{style}">{html.escape(c.data or " ")}</span>')
            rows.append("".join(cells))
        return ("<html><body style='margin:0;background:#0e0e0e'><pre style=\"font:16px/20px 'DejaVu Sans Mono',monospace;"
                "margin:8px;background:#0e0e0e\">" + "\n".join(rows) + "</pre></body></html>")
