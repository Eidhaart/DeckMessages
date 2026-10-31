import type { RoomMessageEventContent } from "matrix-js-sdk/lib/@types/events";
import {
  ClientEvent,
  createClient,
  EventStatus,
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
import {
  Emitter,
  type Contact,
  type Message,
  type MessageStatus,
  type Room,
  type RoomKind,
  type Transport,
} from "./types";

const FAVORITE_TAG = "m.favourite";
/** State events where bridges describe a portal room (the second is the older name). */
const BRIDGE_STATE = ["m.bridge", "uk.half-shot.bridge"];

type MessageContent = RoomMessageEventContent;

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
  /** Your own Messenger account id(s): the bridge's copy of you is excluded from "the other person". */
  private accountIds = new Set<string>();

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
      await c.startClient({ initialSyncLimit: 40 });
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
    c.on(RoomEvent.Tags, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.Receipt, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.LocalEchoUpdated, () => this.em.emit({ type: "rooms" }));
    c.on(RoomEvent.MyMembership, (room: MRoom, membership: string) => {
      if (membership === KnownMembership.Invite && this.session.autoJoin) {
        void this.acceptInvite(room.roomId);
      }
      this.em.emit({ type: "rooms" });
    });

    await c.startClient({ initialSyncLimit: 40 });
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
    const rooms = this.client.getVisibleRooms().filter((r) => {
      const m = r.getMyMembership();
      // The bridge groups its rooms into a "space"; that's a folder, not a chat.
      return (m === KnownMembership.Join || m === KnownMembership.Invite) && !r.isSpaceRoom();
    });
    this.learnAccountIds(rooms);
    return rooms
      .map((r): Room => {
        const kind = this.roomKind(r);
        const peer = kind === "dm" || kind === "request" ? this.people(r)[0] : undefined;
        const named = r.currentState.getStateEvents(EventType.RoomName, "")?.getContent().name;
        return {
          id: r.roomId,
          name: (!named && peer?.rawDisplayName) || r.name || r.roomId,
          unread: r.getUnreadNotificationCount(NotificationCountType.Total) ?? 0,
          lastTs: r.getLastActiveTimestamp() || 0,
          invite: r.getMyMembership() === KnownMembership.Invite,
          kind,
          favorite: FAVORITE_TAG in r.tags,
          avatarUrl: r.getMxcAvatarUrl() ?? peer?.getMxcAvatarUrl() ?? undefined,
          peer: peer?.userId,
        };
      })
      .sort((a, b) => b.lastTs - a.lastTs);
  }

  contacts(): Contact[] {
    const rooms = this.rooms();
    const dmWith = new Map(rooms.filter((r) => r.kind === "dm" && r.peer).map((r) => [r.peer!, r.id]));
    const byId = new Map<string, Contact>();
    for (const room of this.client.getRooms()) {
      if (room.getMyMembership() !== KnownMembership.Join || room.isSpaceRoom()) continue;
      for (const m of this.people(room)) {
        if (byId.has(m.userId)) continue;
        byId.set(m.userId, {
          id: m.userId,
          name: m.rawDisplayName,
          avatarUrl: m.getMxcAvatarUrl() ?? undefined,
          roomId: dmWith.get(m.userId),
        });
      }
    }
    return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
  }

  async startChat(contactId: string): Promise<string> {
    const find = () => this.rooms().find((r) => r.kind === "dm" && r.peer === contactId)?.id;
    const existing = find();
    if (existing) return existing;
    // Ghost user ids look like @facebook_<messenger id>:server; the bridge bot opens the chat.
    const localpart = contactId.slice(1, contactId.indexOf(":"));
    const remoteId = localpart.slice(localpart.indexOf("_") + 1);
    const bridgeRoom = await this.openBridge();
    await this.client.sendTextMessage(bridgeRoom, `start-chat ${remoteId}`);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        off();
        reject(new Error("the bridge didn't open the chat; see the bridge room"));
      }, 30_000);
      const off = this.em.on((e) => {
        const id = e.type === "rooms" ? find() : undefined;
        if (id) {
          clearTimeout(timer);
          off();
          resolve(id);
        }
      });
    });
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

  async sendFile(roomId: string, file: File) {
    const type = file.type || "application/octet-stream";
    const msgtype = type.startsWith("image/") ? MsgType.Image : type.startsWith("video/") ? MsgType.Video : MsgType.File;
    const info: Record<string, number | string> = { mimetype: type, size: file.size, ...(await mediaInfo(file, msgtype)) };
    const { content_uri } = await this.client.uploadContent(file, { name: file.name, type });
    await this.client.sendMessage(roomId, { msgtype, body: file.name, url: content_uri, info } as unknown as MessageContent);
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
  async fetchMedia(mxc: string, size?: number) {
    const key = `${mxc}@${size ?? 0}`;
    const cached = this.mediaCache.get(key);
    if (cached) return cached;
    const http = size
      ? this.client.mxcUrlToHttp(mxc, size, size, "crop", false, true, true)
      : this.client.mxcUrlToHttp(mxc, undefined, undefined, undefined, false, true, true);
    if (!http) throw new Error("bad media url");
    const res = await fetch(http, { headers: { Authorization: `Bearer ${this.session.accessToken}` } });
    if (!res.ok) throw new Error(`media ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    this.mediaCache.set(key, url);
    return url;
  }

  /** Open a DM with the bridge bot (the room where you log in to Messenger). */
  async openBridge(): Promise<string> {
    const existing = this.rooms().find((r) => r.kind === "bridge");
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

  async setDisplayName(name: string) {
    await this.client.setDisplayName(name);
  }

  async setFavorite(roomId: string, favorite: boolean) {
    if (favorite) await this.client.setRoomTag(roomId, FAVORITE_TAG, { order: 0.5 });
    else await this.client.deleteRoomTag(roomId, FAVORITE_TAG);
  }

  private isBot(userId: string) {
    return userId.startsWith(`@${this.session.bridgeBot}:`);
  }

  /** The bridge's stand-in for your own Messenger account (shows up when you write from your phone). */
  private isOwnGhost(userId: string) {
    const localpart = userId.slice(1, userId.indexOf(":"));
    return [...this.accountIds].some((id) => localpart.endsWith(`_${id}`));
  }

  /** Everyone in a room who isn't you, your Messenger stand-in, or the bridge bot. */
  private people(room: MRoom) {
    return room
      .getMembers()
      .filter((m) => m.membership === "join" || m.membership === "invite")
      .filter((m) => m.userId !== this.selfId && !this.isBot(m.userId) && !this.isOwnGhost(m.userId));
  }

  /** The bridge's own description of a portal: chat type, message request flag, account. */
  private bridgeInfo(room: MRoom) {
    const contents = BRIDGE_STATE.flatMap((t) => room.currentState.getStateEvents(t).map((e) => e.getContent()));
    contents.push(room.currentState.getStateEvents(EventType.RoomCreate, "")?.getContent() ?? {});
    const pick = (key: string) => contents.map((c) => c[key]).find((v) => v !== undefined);
    return {
      type: (pick("com.beeper.room_type.v2") ?? pick("com.beeper.room_type")) as string | undefined,
      request: !!pick("com.beeper.message_request"),
      account: pick("com.beeper.bridge_account_id") as string | undefined,
    };
  }

  /** Find your Messenger account id from portal metadata or the bridge bot's "Logged in as … (id)". */
  private learnAccountIds(rooms: MRoom[]) {
    for (const room of rooms) {
      const { account } = this.bridgeInfo(room);
      if (account) this.accountIds.add(String(account));
      const members = room.getJoinedMembers();
      if (members.length === 2 && members.some((m) => this.isBot(m.userId))) {
        for (const ev of room.getLiveTimeline().getEvents()) {
          if (!this.isBot(ev.getSender() ?? "")) continue;
          const id = /Logged in as .*\((\d+)\)/.exec(ev.getContent().body ?? "")?.[1];
          if (id) this.accountIds.add(id);
        }
      }
    }
  }

  private roomKind(room: MRoom): RoomKind {
    const members = room.getMembers().filter((m) => m.membership === "join" || m.membership === "invite");
    const people = this.people(room);
    if (people.length === 0 && members.some((m) => this.isBot(m.userId))) return "bridge";
    const info = this.bridgeInfo(room);
    if (info.request) return "request";
    if (info.type === "dm") return "dm";
    if (info.type) return "group";
    const mine = room.getMember(this.selfId)?.events.member;
    const isDirect = mine?.getContent().is_direct || mine?.getPrevContent().is_direct;
    return isDirect || people.length <= 1 ? "dm" : "group";
  }

  /** One name for you, whether you wrote from DeckMessages or the Messenger app. */
  private selfName(room: MRoom | null) {
    return room?.getMember(this.selfId)?.rawDisplayName ?? this.client.getUser(this.selfId)?.displayName ?? "you";
  }

  private status(ev: MatrixEvent, room: MRoom | null): MessageStatus {
    if (ev.status === EventStatus.NOT_SENT) return "failed";
    if (ev.status) return "sending";
    const readers = room?.getUsersReadUpTo(ev) ?? [];
    return readers.some((u) => u !== this.selfId && !this.isBot(u) && !this.isOwnGhost(u)) ? "read" : "sent";
  }

  private convert(ev: MatrixEvent): Message | null {
    const type = ev.getType();
    if (type !== EventType.RoomMessage && type !== EventType.RoomMessageEncrypted) return null;
    if (ev.isRedacted()) return null;
    const roomId = ev.getRoomId()!;
    const sender = ev.getSender() ?? "?";
    const room = this.client.getRoom(roomId);
    const member = room?.getMember(sender);
    // Messages you wrote in the Messenger app arrive from the bridge's stand-in for you: still you.
    const mine = sender === this.selfId;
    const self = mine || this.isOwnGhost(sender);
    const base = {
      id: ev.getId() ?? `${roomId}-${ev.getTs()}`,
      roomId,
      sender,
      // rawDisplayName: the SDK's `name` appends the user ID when two members have similar names.
      senderName: self ? this.selfName(room) : (member?.rawDisplayName ?? sender),
      ts: ev.getTs(),
      self,
      status: mine ? this.status(ev, room) : undefined,
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
      case MsgType.Video:
        return { ...base, kind: "video", body, mediaUrl: content.url };
      case MsgType.File:
      case MsgType.Audio:
        return { ...base, kind: "file", body, mediaUrl: content.url };
      default:
        return { ...base, kind: "text", body: ev.replacingEvent()?.getContent()["m.new_content"]?.body ?? body };
    }
  }
}

/** Width/height (and duration for videos) so other apps can lay the media out before it loads. */
async function mediaInfo(file: File, msgtype: string): Promise<Record<string, number>> {
  try {
    if (msgtype === MsgType.Image) {
      const bmp = await createImageBitmap(file);
      const info = { w: bmp.width, h: bmp.height };
      bmp.close();
      return info;
    }
    if (msgtype === MsgType.Video) {
      const url = URL.createObjectURL(file);
      const video = document.createElement("video");
      video.preload = "metadata";
      video.src = url;
      await new Promise((ok, fail) => {
        video.onloadedmetadata = ok;
        video.onerror = fail;
        setTimeout(fail, 5000);
      });
      URL.revokeObjectURL(url);
      return { w: video.videoWidth, h: video.videoHeight, duration: Math.round(video.duration * 1000) };
    }
  } catch {
    // Metadata is optional; send without it.
  }
  return {};
}
