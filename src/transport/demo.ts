import { Emitter, type Message, type Room, type Transport } from "./types";

// Offline backend with fictional contacts, so the UI can be explored and
// styled without a homeserver or Messenger account.

const SELF = "@you:deck.local";

interface Contact {
  id: string;
  name: string;
  replies: string[];
}

const CONTACTS: Contact[] = [
  {
    id: "!vex",
    name: "Vex // fixer",
    replies: [
      "Got a job if you want it. Pays in clean creds.",
      "Meet at the noodle stand under the overpass. 0200.",
      "Don't ping me on open channels, choom.",
      "Copy. I'll route it through the relay.",
    ],
  },
  {
    id: "!nyx",
    name: "Nyx",
    replies: [
      "lol you're still up?",
      "the rain hasn't stopped in like 3 days",
      "sending you that playlist rn",
      "ok but did you eat",
    ],
  },
  {
    id: "!crew",
    name: "Night Shift [group]",
    replies: [
      "[Kade] who took the last energy drink",
      "[Rho] deploy is green, going dark for a bit",
      "[Kade] anyone else's implant buzzing or just me",
      "[Rho] 👍",
    ],
  },
  {
    id: "!mom",
    name: "Mom",
    replies: ["Call me when you get a chance ❤️", "Are you wearing a jacket? It's cold out.", "Ok sweetie"],
  },
];

const SEED: Record<string, [string, string, number][]> = {
  // [sender, body, minutes ago]
  "!vex": [
    ["!vex", "You there?", 42],
    [SELF, "Always.", 41],
    ["!vex", "Got a package that needs moving across the district. Quiet work.", 40],
  ],
  "!nyx": [
    ["!nyx", "did you see the skyline tonight", 180],
    ["!nyx", "the ads were glitching purple everywhere", 179],
    [SELF, "yeah it looked unreal", 170],
  ],
  "!crew": [
    ["!crew", "[Rho] standup in 10", 600],
    ["!crew", "[Kade] skipping, my cyberdeck is rebooting", 598],
  ],
  "!mom": [["!mom", "Did you get home safe?", 1440]],
};

export class DemoTransport implements Transport {
  readonly kind = "demo" as const;
  readonly selfId = SELF;
  private em = new Emitter();
  private roomList: Room[];
  private logs = new Map<string, Message[]>();
  private replyIdx = new Map<string, number>();
  private timers: number[] = [];
  private seq = 0;

  constructor() {
    const now = Date.now();
    this.roomList = CONTACTS.map((c) => ({ id: c.id, name: c.name, unread: 0, lastTs: 0 }));
    for (const c of CONTACTS) {
      const msgs = (SEED[c.id] ?? []).map(([sender, body, mins]) =>
        this.make(c.id, sender, body, now - mins * 60_000),
      );
      this.logs.set(c.id, msgs);
      const room = this.room(c.id)!;
      room.lastTs = msgs.at(-1)?.ts ?? 0;
      room.unread = msgs.filter((m) => !m.self).length > 0 && c.id !== "!nyx" ? 1 : 0;
    }
  }

  on(l: Parameters<Transport["on"]>[0]) {
    return this.em.on(l);
  }

  async start() {
    this.em.emit({ type: "status", status: "connecting" });
    await new Promise((r) => setTimeout(r, 400));
    this.em.emit({ type: "status", status: "online", detail: "demo uplink" });
    // An unprompted message now and then, to show incoming traffic.
    this.timers.push(window.setTimeout(() => this.incoming("!nyx"), 9_000));
  }

  async stop() {
    this.timers.forEach(clearTimeout);
  }

  rooms() {
    return [...this.roomList].sort((a, b) => b.lastTs - a.lastTs);
  }

  messages(roomId: string) {
    return this.logs.get(roomId) ?? [];
  }

  async send(roomId: string, body: string, emote = false) {
    const msg = this.make(roomId, SELF, body, Date.now(), emote ? "emote" : "text");
    this.push(msg);
    const delay = 1200 + Math.random() * 2500;
    this.timers.push(window.setTimeout(() => this.incoming(roomId), delay));
  }

  markRead(roomId: string) {
    const room = this.room(roomId);
    if (room && room.unread) {
      room.unread = 0;
      this.em.emit({ type: "rooms" });
    }
  }

  async loadOlder(roomId: string) {
    const log = this.logs.get(roomId);
    if (!log) return;
    const first = log[0]?.ts ?? Date.now();
    const sys = this.make(roomId, "system", "── beginning of archived log ──", first - 1, "system");
    if (log[0]?.kind !== "system") log.unshift(sys);
    this.em.emit({ type: "rooms" });
  }

  async acceptInvite() {}

  async fetchMedia(url: string) {
    return url;
  }

  private incoming(roomId: string) {
    const contact = CONTACTS.find((c) => c.id === roomId);
    if (!contact) return;
    const i = this.replyIdx.get(roomId) ?? 0;
    this.replyIdx.set(roomId, i + 1);
    const room = this.room(roomId)!;
    room.unread += 1;
    this.push(this.make(roomId, roomId, contact.replies[i % contact.replies.length], Date.now()));
  }

  private push(msg: Message) {
    this.logs.get(msg.roomId)?.push(msg);
    const room = this.room(msg.roomId);
    if (room) room.lastTs = msg.ts;
    this.em.emit({ type: "message", message: msg });
    this.em.emit({ type: "rooms" });
  }

  private room(id: string) {
    return this.roomList.find((r) => r.id === id);
  }

  private make(roomId: string, sender: string, body: string, ts: number, kind: Message["kind"] = "text"): Message {
    const self = sender === SELF;
    const contact = CONTACTS.find((c) => c.id === sender);
    return {
      id: `demo-${++this.seq}`,
      roomId,
      sender,
      senderName: self ? "you" : (contact?.name.split(" ")[0] ?? sender),
      body,
      ts,
      self,
      kind,
    };
  }
}
