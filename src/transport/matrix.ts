import {
  ClientEvent,
  createClient,
  EventType,
  KnownMembership,
  MatrixEventEvent,
  MsgType,
  NotificationCountType,
  Preset,
  RoomEvent,
  SyncState,
  type MatrixClient,
  type MatrixEvent,
  type Room as MRoom,
} from "matrix-js-sdk";
import { Emitter, type Message, type Room, type Transport } from "./types";

// Messenger has no public API for personal chats, so DeckMessages reaches it
// through a Matrix homeserver running the mautrix-meta bridge. Every Messenger
// thread shows up as a Matrix room; this transport is a regular Matrix client.

export interface MatrixSession {
  baseUrl: string;
  userId: string;
  accessToken: string;
  deviceId: string;
  /** Localpart of the bridge bot, "facebookbot" by default in mautrix-meta. */
  bridgeBot: string;
  /** Auto-accept invites to new portal rooms created by the bridge. */
  autoJoin: boolean;
}

export async function matrixLogin(
  baseUrl: string,
  user: string,
  password: string,
): Promise<Pick<MatrixSession, "baseUrl" | "userId" | "accessToken" | "deviceId">> {
  const url = baseUrl.replace(/\/+$/, "");
  const tmp = createClient({ baseUrl: url });
  const res = await tmp.loginRequest({
    type: "m.login.password",
    identifier: { type: "m.id.user", user },
    password,
    initial_device_display_name: "DeckMessages",
  });
  return { baseUrl: url, userId: res.user_id, accessToken: res.access_token, deviceId: res.device_id };
}

export class MatrixTransport implements Transport {
  readonly kind = "matrix" as const;
  readonly selfId: string;
  private client: MatrixClient;
  private em = new Emitter();
  private mediaCache = new Map<string, string>();
  private wired = false;

  constructor(private session: MatrixSession) {
    this.selfId = session.userId;
    this.client = createClient({
      baseUrl: session.baseUrl,
      accessToken: session.accessToken,
      userId: session.userId,
      deviceId: session.deviceId,
    });
  }

  on(l: Parameters<Transport["on"]>[0]) {
    return this.em.on(l);
  }

  async start() {
    const c = this.client;
    this.em.emit({ type: "status", status: "connecting", detail: "handshake" });
    if (this.wired) {
      await c.startClient({ initialSyncLimit: 40, lazyLoadMembers: true });
      return;
    }
    this.wired = true;

    // Encrypted portals need the Rust crypto stack (WASM). If it can't load,
    // keep going: unencrypted bridges still work and encrypted lines render as such.
    try {
      await c.initRustCrypto({ cryptoDatabasePrefix: `deck-${this.session.deviceId}` });
    } catch (err) {
      console.warn("crypto unavailable", err);
    }

    c.on(ClientEvent.Sync, (state: SyncState, _prev, data) => {
      if (state === SyncState.Prepared || state === SyncState.Syncing) {
        this.em.emit({ type: "status", status: "online", detail: new URL(this.session.baseUrl).host });
        this.em.emit({ type: "rooms" });
      } else if (state === SyncState.Reconnecting) {
        this.em.emit({ type: "status", status: "connecting", detail: "reconnecting" });
      } else if (state === SyncState.Error) {
        this.em.emit({ type: "status", status: "error", detail: data?.error?.message ?? "sync error" });
      } else if (state === SyncState.Stopped) {
        this.em.emit({ type: "status", status: "offline" });
      }
    });

    c.on(RoomEvent.Timeline, (ev: MatrixEvent, room: MRoom | undefined, toStart: boolean | undefined) => {
      if (!room) return;
      if (!toStart) {
        const msg = this.convert(ev);
        if (msg) this.em.emit({ type: "message", message: msg });
      }
      this.em.emit({ type: "rooms" });
    });

    c.on(MatrixEventEvent.Decrypted, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.Name, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.Receipt, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.MyMembership, (room: MRoom, membership: string) => {
      if (membership === KnownMembership.Invite && this.session.autoJoin) {
        void this.acceptInvite(room.roomId);
      }
      this.em.emit({ type: "rooms" });
    });

    await c.startClient({ initialSyncLimit: 40, lazyLoadMembers: true });
  }

  async stop() {
    this.client.stopClient();
    for (const url of this.mediaCache.values()) URL.revokeObjectURL(url);
    this.mediaCache.clear();
  }

  async logout() {
    try {
      await this.client.logout(true);
    } finally {
      await this.stop();
    }
  }

  rooms(): Room[] {
    return this.client
      .getVisibleRooms()
      .filter((r) => {
        const m = r.getMyMembership();
        return m === KnownMembership.Join || m === KnownMembership.Invite;
      })
      .map((r) => ({
        id: r.roomId,
        name: r.name || r.roomId,
        unread: r.getUnreadNotificationCount(NotificationCountType.Total) ?? 0,
        lastTs: r.getLastActiveTimestamp() || 0,
        invite: r.getMyMembership() === KnownMembership.Invite,
        bridgeBot: this.isBridgeBotRoom(r),
      }))
      .sort((a, b) => b.lastTs - a.lastTs);
  }

  messages(roomId: string): Message[] {
    const room = this.client.getRoom(roomId);
    if (!room) return [];
    const out: Message[] = [];
    for (const ev of room.getLiveTimeline().getEvents()) {
      const m = this.convert(ev);
      if (m) out.push(m);
    }
    return out;
  }

  async send(roomId: string, body: string, emote = false) {
    if (emote) await this.client.sendEmoteMessage(roomId, body);
    else await this.client.sendTextMessage(roomId, body);
  }

  markRead(roomId: string) {
    const room = this.client.getRoom(roomId);
    const last = room?.getLiveTimeline().getEvents().at(-1);
    if (!room || !last || !room.getUnreadNotificationCount(NotificationCountType.Total)) return;
    this.client.sendReadReceipt(last).catch(() => {});
    room.setUnreadNotificationCount(NotificationCountType.Total, 0);
    room.setUnreadNotificationCount(NotificationCountType.Highlight, 0);
    this.em.emit({ type: "rooms" });
  }

  async loadOlder(roomId: string) {
    const room = this.client.getRoom(roomId);
    if (room) await this.client.scrollback(room, 40);
    this.em.emit({ type: "rooms" });
  }

  async acceptInvite(roomId: string) {
    await this.client.joinRoom(roomId);
    this.em.emit({ type: "rooms" });
  }

  /** Authenticated media needs the access token, so download to a blob URL. */
  async fetchMedia(mxc: string) {
    const cached = this.mediaCache.get(mxc);
    if (cached) return cached;
    const http = this.client.mxcUrlToHttp(mxc, undefined, undefined, undefined, false, true, true);
    if (!http) throw new Error("bad media url");
    const res = await fetch(http, { headers: { Authorization: `Bearer ${this.session.accessToken}` } });
    if (!res.ok) throw new Error(`media ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    this.mediaCache.set(mxc, url);
    return url;
  }

  /** Open a DM with the bridge bot (the room where you log in to Messenger). */
  async openBridge(): Promise<string> {
    const existing = this.rooms().find((r) => r.bridgeBot);
    if (existing) return existing.id;
    const server = this.selfId.slice(this.selfId.indexOf(":") + 1);
    const res = await this.client.createRoom({
      invite: [`@${this.session.bridgeBot}:${server}`],
      is_direct: true,
      preset: Preset.TrustedPrivateChat,
      name: "Messenger bridge",
    });
    this.em.emit({ type: "rooms" });
    return res.room_id;
  }

  private isBridgeBotRoom(room: MRoom) {
    const bot = `@${this.session.bridgeBot}:`;
    const members = room.getMembers().filter((m) => m.membership === "join" || m.membership === "invite");
    return members.length <= 2 && members.some((m) => m.userId.startsWith(bot));
  }

  private convert(ev: MatrixEvent): Message | null {
    const type = ev.getType();
    if (type !== EventType.RoomMessage && type !== EventType.RoomMessageEncrypted) return null;
    if (ev.isRedacted()) return null;
    const roomId = ev.getRoomId()!;
    const sender = ev.getSender() ?? "?";
    const member = this.client.getRoom(roomId)?.getMember(sender);
    const base = {
      id: ev.getId() ?? `${roomId}-${ev.getTs()}`,
      roomId,
      sender,
      senderName: member?.name ?? sender,
      ts: ev.getTs(),
      self: sender === this.selfId,
    };

    if (ev.isEncrypted() && (ev.isDecryptionFailure() || ev.getType() === EventType.RoomMessageEncrypted)) {
      return { ...base, kind: "encrypted", body: "▒▒▒ encrypted payload — unable to decrypt ▒▒▒" };
    }

    const content = ev.getContent();
    // Edits arrive as new events; show the replacement text only.
    if (content["m.relates_to"]?.rel_type === "m.replace") return null;
    const body: string = content.body ?? "";
    switch (content.msgtype) {
      case MsgType.Emote:
        return { ...base, kind: "emote", body };
      case MsgType.Notice:
        return { ...base, kind: "notice", body };
      case MsgType.Image:
        return { ...base, kind: "image", body, mediaUrl: content.url };
      case MsgType.File:
      case MsgType.Video:
      case MsgType.Audio:
        return { ...base, kind: "file", body, mediaUrl: content.url };
      default:
        return { ...base, kind: "text", body: ev.replacingEvent()?.getContent()["m.new_content"]?.body ?? body };
    }
  }
}
