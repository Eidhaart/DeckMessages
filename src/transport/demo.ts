import { Emitter, type Contact, type Message, type Room, type Transport } from "./types";

// Offline backend with fictional contacts, so the UI can be explored and
// styled without a homeserver or Messenger account.

const SELF = "@you:deck.local";

interface Persona {
  id: string;
  name: string;
  kind: "dm" | "group" | "request";
  replies: string[];
}

const CONTACTS: Persona[] = [
  {
    id: "!vex",
    name: "Vex // fixer",
    kind: "dm",
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
    kind: "dm",
    replies: [
      "lol you're still up?",
      "the rain hasn't stopped in like 3 days",
      "sending you that playlist rn",
      "ok but did you eat",
    ],
  },
  {
    id: "!crew",
    name: "Night Shift",
    kind: "group",
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
    kind: "dm",
    replies: ["Call me when you get a chance ❤️", "Are you wearing a jacket? It's cold out.", "Ok sweetie"],
  },
  {
    id: "!ash",
    name: "Ash Kuroda",
    kind: "request",
    replies: ["cool, how much?", "can you ship to the east district?"],
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
  "!ash": [["!ash", "hey, saw your post about the synth. still selling?", 300]],
};

/** People you only know from the group chat: they show up in contacts without a chat yet. */
const GROUP_PEOPLE = [
  { id: "@kade", name: "Kade" },
  { id: "@rho", name: "Rho" },
];

export class DemoTransport implements Transport {
  readonly kind = "demo" as const;
  readonly selfId = SELF;
  private em = new Emitter();
  private roomList: Room[];
  private logs = new Map<string, Message[]>();
  private replyIdx = new Map<string, number>();
  private timers: number[] = [];
  private seq = 0;
  private selfName = "you";

  constructor() {
    const now = Date.now();
    this.roomList = CONTACTS.map((c) => ({
      id: c.id,
      name: c.name,
      unread: 0,
      lastTs: 0,
      kind: c.kind,
      favorite: c.id === "!nyx",
      peer: c.kind === "group" ? undefined : c.id,
    }));
    for (const c of CONTACTS) {
      const msgs = (SEED[c.id] ?? []).map(([sender, body, mins]) =>
        this.make(c.id, sender, body, now - mins * 60_000),
      );
      for (const m of msgs) if (m.self) m.status = "read";
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
    this.sendOwn(this.make(roomId, SELF, body, Date.now(), emote ? "emote" : "text"));
  }

  async sendFile(roomId: string, file: File) {
    const kind = file.type.startsWith("image/") ? "image" : file.type.startsWith("video/") ? "video" : "file";
    const msg = this.make(roomId, SELF, file.name, Date.now(), kind);
    msg.mediaUrl = URL.createObjectURL(file);
    this.sendOwn(msg);
  }

  contacts(): Contact[] {
    const dms = this.roomList.filter((r) => r.peer);
    const people: Contact[] = [
      ...dms.map((r) => ({ id: r.peer!, name: r.name, roomId: r.id })),
      ...GROUP_PEOPLE.filter((p) => !dms.some((r) => r.peer === p.id)),
    ];
    return people.sort((a, b) => a.name.localeCompare(b.name));
  }

  async startChat(contactId: string) {
    const existing = this.roomList.find((r) => r.peer === contactId);
    if (existing) return existing.id;
    const person = GROUP_PEOPLE.find((p) => p.id === contactId);
    const room: Room = {
      id: `!dm-${contactId.slice(1)}`,
      name: person?.name ?? contactId,
      unread: 0,
      lastTs: Date.now(),
      kind: "dm",
      favorite: false,
      peer: contactId,
    };
    this.roomList.push(room);
    this.logs.set(room.id, []);
    this.em.emit({ type: "rooms" });
    return room.id;
  }

  /** Your message goes sending → sent, and is marked read when the other side answers. */
  private sendOwn(msg: Message) {
    msg.status = "sending";
    this.push(msg);
    this.timers.push(
      window.setTimeout(() => {
        msg.status = "sent";
        this.em.emit({ type: "rooms" });
      }, 500),
    );
    const delay = 1200 + Math.random() * 2500;
    this.timers.push(window.setTimeout(() => this.incoming(msg.roomId), delay));
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

  async setDisplayName(name: string) {
    this.selfName = name;
    for (const log of this.logs.values()) for (const m of log) if (m.self) m.senderName = name;
    this.em.emit({ type: "rooms" });
  }

  async setFavorite(roomId: string, favorite: boolean) {
    const room = this.room(roomId);
    if (room) room.favorite = favorite;
    this.em.emit({ type: "rooms" });
  }

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
    for (const m of this.logs.get(roomId) ?? []) if (m.self) m.status = "read";
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
      senderName: self ? this.selfName : (contact?.name.split(" ")[0] ?? sender),
      body,
      ts,
      self,
      kind,
    };
  }
}
