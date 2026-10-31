import { useCallback, useEffect, useRef, useState } from "react";
import { Avatar } from "./components/Avatar";
import { BootSequence } from "./components/BootSequence";
import { LoginScreen } from "./components/LoginScreen";
import { Log } from "./components/Log";
import { Prompt } from "./components/Prompt";
import { Sidebar, type SidebarView } from "./components/Sidebar";
import { runCommand, type CommandContext } from "./commands";
import { groupRooms, type SectionId } from "./rooms";
import { loadSession, loadSettings, saveSession, saveSettings, type Settings } from "./settings";
import { DemoTransport } from "./transport/demo";
import { MatrixTransport, type MatrixSession } from "./transport/matrix";
import type { Contact, LinkStatus, Message, Transport } from "./transport/types";

type Phase = "boot" | "login" | "deck";

let sysSeq = 0;
const sysLine = (roomId: string, body: string): Message => ({
  id: `sys-${++sysSeq}`,
  roomId,
  sender: "system",
  senderName: "sys",
  body,
  ts: Date.now(),
  self: false,
  kind: "system",
});

function initialTransport(): Transport | null {
  const s = loadSession();
  return s ? new MatrixTransport(s) : null;
}

export default function App() {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [transport, setTransport] = useState<Transport | null>(initialTransport);
  const [phase, setPhase] = useState<Phase>(() => (settings.boot ? "boot" : transport ? "deck" : "login"));
  const [status, setStatus] = useState<{ status: LinkStatus; detail?: string }>({ status: "offline" });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sysLines, setSysLines] = useState<Message[]>([]);
  const [clearedAt, setClearedAt] = useState<Record<string, number>>({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [view, setView] = useState<SidebarView>("chats");
  const [clock, setClock] = useState(() => new Date());
  const [, setTick] = useState(0);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const updateSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((s) => {
      const next = { ...s, ...patch };
      saveSettings(next);
      return next;
    });
  }, []);

  // Wire up the transport: every event just triggers a re-render from its state.
  useEffect(() => {
    if (!transport || phase !== "deck") return;
    const off = transport.on((e) => {
      if (e.type === "status") setStatus({ status: e.status, detail: e.detail });
      setTick((t) => t + 1);
    });
    transport.start().catch((err) => setStatus({ status: "error", detail: String(err?.message ?? err) }));
    return () => {
      off();
      void transport.stop();
    };
  }, [transport, phase]);

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const sections = groupRooms(transport?.rooms() ?? []);
  const rooms = sections.flatMap((s) => s.rooms);
  const activeRoom = rooms.find((r) => r.id === activeId) ?? null;

  // Land on the most recent channel once rooms arrive.
  useEffect(() => {
    if (!activeId && rooms.length) setActiveId(rooms[0].id);
  }, [activeId, rooms.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const messages: Message[] = activeId && transport
    ? [
        ...transport.messages(activeId).filter((m) => m.ts > (clearedAt[activeId] ?? 0)),
        ...sysLines.filter((l) => l.roomId === activeId || l.roomId === "*"),
      ].sort((a, b) => a.ts - b.ts)
    : sysLines;

  useEffect(() => {
    if (activeId && activeRoom?.unread && document.hasFocus()) transport?.markRead(activeId);
  });

  const select = useCallback((id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
    promptRef.current?.focus();
  }, []);

  const step = useCallback(
    (delta: number) => {
      if (!rooms.length) return;
      const i = rooms.findIndex((r) => r.id === activeId);
      select(rooms[(i + delta + rooms.length) % rooms.length].id);
    },
    [rooms, activeId, select],
  );

  const print = (text: string) => setSysLines((l) => [...l, sysLine(activeId ?? "*", text)]);

  const openContact = (c: Contact) => {
    setView("chats");
    if (c.roomId) return select(c.roomId);
    print(`opening a channel to ${c.name}…`);
    transport?.startChat(c.id).then(select, (e) => print(`!! couldn't start a chat with ${c.name}: ${e?.message ?? e}`));
  };

  const attach = (file: File) => {
    if (!activeId || !transport) return print("open a chat first, then attach");
    const mb = (file.size / 1024 / 1024).toFixed(1);
    print(`uploading ${file.name} (${mb} MB)…`);
    transport.sendFile(activeId, file).catch((e) => print(`!! couldn't send ${file.name}: ${e?.message ?? e}`));
  };

  const logout = async () => {
    if (transport instanceof MatrixTransport) await transport.logout().catch(() => {});
    else await transport?.stop();
    saveSession(null);
    setTransport(null);
    setActiveId(null);
    setSysLines([]);
    setStatus({ status: "offline" });
    setPhase("login");
  };

  const ctx: CommandContext = {
    rooms,
    activeRoom,
    selfId: transport?.selfId ?? "nobody",
    transportKind: transport?.kind ?? "demo",
    print,
    select,
    step,
    send: (body, emote) => {
      if (!activeId || !transport) return print("no channel selected. /list then /go <n>");
      transport.send(activeId, body, emote).catch((err) => print(`!! send failed: ${err?.message ?? err}`));
    },
    clear: () => {
      if (activeId) setClearedAt((c) => ({ ...c, [activeId]: Date.now() }));
      setSysLines((l) => l.filter((x) => x.roomId !== activeId && x.roomId !== "*"));
    },
    setTheme: (theme) => updateSettings({ theme }),
    setFx: (fx) => updateSettings({ fx }),
    setBoot: (boot) => updateSettings({ boot }),
    loadOlder: () => activeId && void transport?.loadOlder(activeId),
    accept: (id) => transport?.acceptInvite(id).then(() => print("invite accepted"), (e) => print(`!! ${e.message}`)),
    setDisplayName: (name) => {
      transport?.setDisplayName(name).then(
        () => print(`you are now known as ${name}`),
        (e) => print(`!! couldn't change name: ${e?.message ?? e}`),
      );
    },
    contacts: () => transport?.contacts() ?? [],
    openContact,
    showContacts: () => {
      setView("contacts");
      setSidebarOpen(true);
    },
    setCategory: (id, kind) => {
      transport?.setCategory(id, kind).catch((e) => print(`!! couldn't move chat: ${e?.message ?? e}`));
    },
    setFavorite: (id, favorite) => {
      transport?.setFavorite(id, favorite).catch((e) => print(`!! couldn't update favorites: ${e?.message ?? e}`));
    },
    openBridge: () => {
      if (!transport?.openBridge) return;
      print("opening bridge console…");
      transport.openBridge().then(
        (id) => {
          select(id);
          setSysLines((l) => [
            ...l,
            sysLine(id, "bridge console. send `login` to link Messenger, `help` for bot commands."),
          ]);
        },
        (e) => print(`!! couldn't reach the bridge bot: ${e?.message ?? e}`),
      );
    },
    logout: () => void logout(),
    reboot: () => {
      setActiveId(null);
      setSysLines([]);
      setPhase("boot");
    },
  };

  function submit(text: string) {
    if (runCommand(text, ctx)) return;
    ctx.send(text.startsWith("//") ? text.slice(1) : text);
  }

  // Global shortcuts.
  useEffect(() => {
    if (phase !== "deck") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        e.preventDefault();
        step(e.key === "ArrowUp" ? -1 : 1);
      } else if (e.ctrlKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        ctx.clear();
      } else if (e.key === "Escape") {
        setSidebarOpen(false);
      } else if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1 && document.activeElement?.tagName !== "TEXTAREA") {
        promptRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const bootDone = useCallback(() => setPhase(transport ? "deck" : "login"), [transport]);

  const shellClass = `shell theme-${settings.theme}${settings.fx ? " fx" : ""}`;

  if (phase === "boot") {
    return (
      <div className={shellClass}>
        <BootSequence onDone={bootDone} />
      </div>
    );
  }

  if (phase === "login" || !transport) {
    return (
      <div className={shellClass}>
        <LoginScreen
          onDemo={() => {
            setTransport(new DemoTransport());
            setPhase("deck");
          }}
          onSession={(s: MatrixSession) => {
            saveSession(s);
            setTransport(new MatrixTransport(s));
            setPhase("deck");
          }}
        />
      </div>
    );
  }

  // The bridge bot's last message asks for a password or PIN: hide what's typed next.
  const lastLine = messages.findLast((m) => m.kind !== "system");
  const asksForSecret =
    activeRoom?.kind === "bridge" && !!lastLine && !lastLine.self && /password|\bpin\b/i.test(lastLine.body);

  const totalUnread = rooms.reduce((n, r) => n + (r.id === activeId ? 0 : r.unread), 0);

  return (
    <div className={shellClass}>
      <header className="topbar">
        <button className="menu" aria-label="channels" onClick={() => setSidebarOpen((o) => !o)}>
          ≡{totalUnread > 0 && <span className="dot" title={`${totalUnread} unread`} />}
        </button>
        <span className="brand glitch" data-text="DECK//MSG">
          DECK//MSG
        </span>
        <span className="channel">
          {activeRoom && activeRoom.kind !== "bridge" ? (
            <Avatar url={activeRoom.avatarUrl} name={activeRoom.name} transport={transport} size={28} />
          ) : (
            <span className="dim">#</span>
          )}
          <span className="title">{activeRoom?.name ?? "—"}</span>
        </span>
        <span className={`link ${status.status}`}>
          ● {status.status.toUpperCase()}
          {status.detail ? <span className="dim"> {status.detail}</span> : null}
        </span>
        <span className="clock">{clock.toLocaleTimeString([], { hour12: false })}</span>
      </header>

      <div className="deck-body">
        <Sidebar
          view={view}
          contacts={view === "contacts" ? transport.contacts() : []}
          transport={transport}
          onView={setView}
          onPickContact={openContact}
          sections={sections}
          collapsed={settings.shut}
          activeId={activeId}
          open={sidebarOpen}
          onSelect={select}
          onToggleSection={(id: SectionId) =>
            updateSettings({
              shut: settings.shut.includes(id)
                ? settings.shut.filter((c) => c !== id)
                : [...settings.shut, id],
            })
          }
          onToggleFavorite={(id, favorite) => ctx.setFavorite(id, favorite)}
        />
        {sidebarOpen && <div className="scrim" onClick={() => setSidebarOpen(false)} />}
        <main className="main">
          {activeRoom?.invite && (
            <div className="banner">
              ✉ pending invite —{" "}
              <button className="linkish" onClick={() => ctx.accept(activeRoom.id)}>
                accept
              </button>{" "}
              or type /accept
            </div>
          )}
          <Log
            messages={messages}
            transport={transport}
            roomKey={activeId}
            onTop={() => activeId && void transport.loadOlder(activeId)}
          />
          <Prompt
            ref={promptRef}
            channel={activeRoom?.name.split(/\s/)[0].toLowerCase() ?? "void"}
            rooms={rooms}
            literal={activeRoom?.kind === "bridge"}
            secret={asksForSecret}
            onSubmit={submit}
            onAttach={activeRoom && activeRoom.kind !== "bridge" ? attach : undefined}
          />
        </main>
      </div>

      <footer className="statusbar">
        <span>{transport.kind === "demo" ? "DEMO" : "MATRIX"}</span>
        <span className="dim">{transport.selfId}</span>
        <span className="hint dim">/help · Alt+↑↓ switch · Tab complete</span>
      </footer>
    </div>
  );
}
