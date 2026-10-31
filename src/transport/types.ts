// A transport is anything that can list conversations and move messages.
// The UI only talks to this interface, so the demo backend and the Matrix
// (Messenger bridge) backend are interchangeable.

export type MessageKind = "text" | "emote" | "notice" | "image" | "video" | "file" | "encrypted" | "system";

/** Delivery state of your own messages: sending → sent → read (or failed). */
export type MessageStatus = "sending" | "sent" | "read" | "failed";

export interface Message {
  id: string;
  roomId: string;
  sender: string;
  senderName: string;
  body: string;
  ts: number;
  self: boolean;
  kind: MessageKind;
  /** Media URL for image/video/file messages (may need auth, see Transport.fetchMedia). */
  mediaUrl?: string;
  /** Only set on your own messages. */
  status?: MessageStatus;
}

/**
 * dm: one-to-one chat, group: group chat, market: Marketplace / Facebook group listing chats,
 * business: pages and bots (Meta AI, companies), request: a Messenger message request,
 * bridge: the Messenger bridge bot's management room.
 */
export type RoomKind = "dm" | "group" | "market" | "business" | "request" | "bridge";

/** Kinds you can move a chat into by hand. */
export const MOVABLE_KINDS = ["dm", "group", "market", "business", "request"] as const;
export type MovableKind = (typeof MOVABLE_KINDS)[number];

export interface Room {
  id: string;
  name: string;
  unread: number;
  lastTs: number;
  kind: RoomKind;
  favorite: boolean;
  /** Pending invite that hasn't been accepted yet. */
  invite?: boolean;
  /** Room picture, or the other person's picture in a one-to-one chat. */
  avatarUrl?: string;
  /** The other person in a one-to-one chat (a Contact id). */
  peer?: string;
}

/** Someone you can message: everyone you share a chat with. */
export interface Contact {
  id: string;
  name: string;
  avatarUrl?: string;
  /** Existing one-to-one chat with them, if there is one. */
  roomId?: string;
}

export type LinkStatus = "connecting" | "online" | "offline" | "error";

export type TransportEvent =
  | { type: "rooms" }
  | { type: "message"; message: Message }
  | { type: "status"; status: LinkStatus; detail?: string };

export interface Transport {
  readonly kind: "demo" | "matrix";
  readonly selfId: string;
  start(): Promise<void>;
  stop(): Promise<void>;
  rooms(): Room[];
  messages(roomId: string): Message[];
  send(roomId: string, body: string, emote?: boolean): Promise<void>;
  /** Send an image or video (anything else goes as a file). */
  sendFile(roomId: string, file: File): Promise<void>;
  markRead(roomId: string): void;
  loadOlder(roomId: string): Promise<void>;
  acceptInvite(roomId: string): Promise<void>;
  setFavorite(roomId: string, favorite: boolean): Promise<void>;
  /** Pin a chat to a category, or null to go back to automatic sorting. */
  setCategory(roomId: string, kind: MovableKind | null): Promise<void>;
  /** Change the name shown next to your own messages. */
  setDisplayName(name: string): Promise<void>;
  contacts(): Contact[];
  /** Open the one-to-one chat with a contact, starting one if needed; returns its room id. */
  startChat(contactId: string): Promise<string>;
  /** Open (creating if needed) the chat with the Messenger bridge bot; returns its room id. */
  openBridge?(): Promise<string>;
  /** Resolve a media URL into something an <img> can display; `size` asks for a square thumbnail. */
  fetchMedia(url: string, size?: number): Promise<string>;
  on(listener: (e: TransportEvent) => void): () => void;
}

export class Emitter {
  private listeners = new Set<(e: TransportEvent) => void>();
  on(listener: (e: TransportEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
  emit(e: TransportEvent): void {
    for (const l of this.listeners) l(e);
  }
}
