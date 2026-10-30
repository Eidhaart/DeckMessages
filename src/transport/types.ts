// A transport is anything that can list conversations and move messages.
// The UI only talks to this interface, so the demo backend and the Matrix
// (Messenger bridge) backend are interchangeable.

export type MessageKind = "text" | "emote" | "notice" | "image" | "file" | "encrypted" | "system";

export interface Message {
  id: string;
  roomId: string;
  sender: string;
  senderName: string;
  body: string;
  ts: number;
  self: boolean;
  kind: MessageKind;
  /** Media URL for image/file messages (may need auth, see Transport.fetchMedia). */
  mediaUrl?: string;
}

export interface Room {
  id: string;
  name: string;
  unread: number;
  lastTs: number;
  /** Pending invite that hasn't been accepted yet. */
  invite?: boolean;
  /** Management room with the bridge bot (where you log in to Messenger). */
  bridgeBot?: boolean;
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
  markRead(roomId: string): void;
  loadOlder(roomId: string): Promise<void>;
  acceptInvite(roomId: string): Promise<void>;
  /** Open (creating if needed) the chat with the Messenger bridge bot; returns its room id. */
  openBridge?(): Promise<string>;
  /** Resolve a media URL into something an <img> can display. */
  fetchMedia(url: string): Promise<string>;
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
