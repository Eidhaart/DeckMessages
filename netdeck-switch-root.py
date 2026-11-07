#!/usr/bin/python3 -I
"""netdeck-switch-root: move the calling user between the NETDECK//OS and Ubuntu login sessions.

Installed by `install.sh --session` as /usr/local/sbin/netdeck-switch-root (root-owned) with a sudo rule
that lets the installing user run it without a password. It does exactly this, nothing else:

  netdeck-switch-root deck|ubuntu   remember the target session for the user, enable GDM automatic login for
                                    this one switch, and restart the login screen so it logs straight back in
  netdeck-switch-root --restore     remove the temporary automatic-login lines again (also runs by itself
                                    ~60 s after a switch, and at the start of every session)

If automatic login does not happen, the login screen still shows with the target session preselected.
"""
import os
import pwd
import re
import subprocess
import sys

GDM_CONF = "/etc/gdm3/custom.conf"
BEGIN = "# >>> netdeck-switch (temporary, removed after login) >>>"
END = "# <<< netdeck-switch <<<"
MARKERS = ["/run/gdm3/gdm.ran-once.marker", "/run/gdm/gdm.ran-once.marker"]
SELF = "/usr/local/sbin/netdeck-switch-root"


def die(msg):
    print(f"netdeck-switch: {msg}", file=sys.stderr)
    sys.exit(1)


def calling_user():
    name = os.environ.get("SUDO_USER")
    if not name and os.environ.get("PKEXEC_UID", "").isdigit():
        name = pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name
    if not name or name == "root":
        die("run this through sudo or pkexec as your normal user")
    return pwd.getpwnam(name)


def ubuntu_session():
    for d, n in (("wayland-sessions", "ubuntu"), ("xsessions", "ubuntu"), ("wayland-sessions", "ubuntu-wayland"),
                 ("xsessions", "ubuntu-xorg")):
        if os.path.exists(f"/usr/share/{d}/{n}.desktop"):
            return n, ("wayland" if d.startswith("wayland") else "x11")
    return "ubuntu", "wayland"


def set_session(uid, session, kind):
    path = f"/org/freedesktop/Accounts/User{uid}"
    iface = "org.freedesktop.Accounts.User"
    ok = False
    for method, arg in (("SetSession", session), ("SetSessionType", kind), ("SetXSession", session)):
        r = subprocess.run(["busctl", "call", "org.freedesktop.Accounts", path, iface, method, "s", arg],
                           capture_output=True, text=True)
        ok = ok or (r.returncode == 0 and method != "SetSessionType")
    if not ok:
        die("could not set the default session through AccountsService")


def strip_block(lines):
    out, skip = [], False
    for line in lines:
        if line.strip() == BEGIN:
            skip = True
            continue
        if skip and line.strip() == END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return out


def enable_autologin(username, conf=GDM_CONF):
    """Add a marked automatic-login block under [daemon]. Returns False if autologin is already configured."""
    try:
        lines = open(conf).read().splitlines()
    except FileNotFoundError:
        lines = ["[daemon]"]
    lines = strip_block(lines)
    try:
        start = next(n for n, ln in enumerate(lines) if ln.strip() == "[daemon]")
    except StopIteration:
        lines += ["", "[daemon]"]
        start = len(lines) - 1
    end = next((n for n in range(start + 1, len(lines)) if lines[n].strip().startswith("[")), len(lines))
    # GDM (GKeyFile) uses the last value of a repeated key, so judge by the last one and append after it
    vals = [re.match(r"\s*AutomaticLoginEnable\s*=\s*(\S+)\s*$", ln) for ln in lines[start + 1:end]]
    vals = [m.group(1).lower() for m in vals if m]
    if vals and vals[-1] in ("true", "1"):
        return False  # the user already runs with automatic login - leave their setup alone
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = [BEGIN, "AutomaticLoginEnable=true", f"AutomaticLogin={username}", END]
    write(conf, lines)
    return True


def restore(conf=GDM_CONF):
    try:
        lines = open(conf).read().splitlines()
    except FileNotFoundError:
        return
    if BEGIN in (ln.strip() for ln in lines):
        write(conf, strip_block(lines))


def write(conf, lines):
    tmp = conf + ".netdeck-tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, conf)


def deck_sessions(username):
    """Login session ids of this user that run the NETDECK session."""
    out = []
    r = subprocess.run(["loginctl", "list-sessions", "--no-legend"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        f = line.split()
        if len(f) >= 3 and f[2] == username:
            d = subprocess.run(["loginctl", "show-session", f[0], "-p", "Desktop", "--value"],
                               capture_output=True, text=True).stdout.strip().lower()
            if "netdeck" in d:
                out.append(f[0])
    return out


def main():
    if os.geteuid() != 0:
        die("needs root (use: sudo netdeck-switch-root deck|ubuntu)")
    if len(sys.argv) != 2 or sys.argv[1] not in ("deck", "ubuntu", "--restore"):
        die("usage: netdeck-switch-root deck|ubuntu|--restore")
    if sys.argv[1] == "--restore":
        restore()
        return
    user = calling_user()
    if sys.argv[1] == "deck":
        if not os.path.exists("/usr/share/wayland-sessions/netdeck.desktop"):
            die("the NETDECK login session is not installed (run: ./install.sh --session)")
        session, kind = "netdeck", "wayland"
    else:
        session, kind = ubuntu_session()
    set_session(user.pw_uid, session, kind)
    if enable_autologin(user.pw_name):
        subprocess.run(["systemd-run", "--quiet", "--collect", "--on-active=60",
                        f"--unit=netdeck-switch-restore-{os.getpid()}", SELF, "--restore"], capture_output=True)
    for m in MARKERS:  # GDM only auto-logs in once per boot unless this marker is gone
        try:
            os.remove(m)
        except OSError:
            pass
    # This helper runs inside the session it may end, so the last steps run as a transient system job:
    # end the NETDECK session (when leaving it, so nothing it started keeps running), then restart the login screen.
    steps = []
    if sys.argv[1] == "ubuntu":
        steps += [f"loginctl terminate-session {sid}" for sid in deck_sessions(user.pw_name)
                  if re.fullmatch(r"[A-Za-z0-9]+", sid)]
    steps.append("systemctl restart display-manager")
    r = subprocess.run(["systemd-run", "--quiet", "--collect", "--no-block", f"--unit=netdeck-switch-{os.getpid()}",
                        "/bin/sh", "-c", "; ".join(steps)], capture_output=True)
    if r.returncode != 0:  # no systemd-run: do it directly
        for st in steps:
            subprocess.run(st.split())


if __name__ == "__main__":
    main()
