import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Message, Transport } from "../transport/types";

const time = (ts: number) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
const day = (ts: number) => new Date(ts).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });

// Stable per-sender colour from a small neon-safe palette.
function nickClass(sender: string) {
  let h = 0;
  for (const ch of sender) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return `nick n${Math.abs(h) % 6}`;
}

function Media({ msg, transport }: { msg: Message; transport: Transport }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const playable = msg.kind === "image" || msg.kind === "video";

  useEffect(() => {
    if (!msg.mediaUrl || !playable) return;
    let live = true;
    transport.fetchMedia(msg.mediaUrl).then(
      (u) => live && setSrc(u),
      () => live && setFailed(true),
    );
    return () => {
      live = false;
    };
  }, [msg.mediaUrl, playable, transport]);

  if (!playable || failed || !msg.mediaUrl) return <span className="tag">[FILE] {msg.body}</span>;
  return (
    <span className="media">
      <span className="tag">{msg.kind === "video" ? "[VID]" : "[IMG]"} {msg.body}</span>
      {src && msg.kind === "image" && <img src={src} alt={msg.body} loading="lazy" />}
      {src && msg.kind === "video" && <video src={src} controls preload="metadata" playsInline />}
    </span>
  );
}

const MARKS: Record<NonNullable<Message["status"]>, [string, string]> = {
  sending: ["·", "sending"],
  sent: ["✓", "sent"],
  read: ["✓✓", "seen"],
  failed: ["!", "not sent"],
};

interface Props {
  messages: Message[];
  transport: Transport;
  roomKey: string | null;
  onTop(): void;
}

export function Log({ messages, transport, roomKey, onTop }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const prevHeight = useRef(0);
  const prevFirst = useRef<string | undefined>(undefined);

  // Stick to the bottom on new messages; keep position when older history is prepended.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const first = messages[0]?.id;
    if (prevFirst.current && first !== prevFirst.current && !stick.current) {
      el.scrollTop += el.scrollHeight - prevHeight.current;
    } else if (stick.current) {
      el.scrollTop = el.scrollHeight;
    }
    prevFirst.current = first;
    prevHeight.current = el.scrollHeight;
  }, [messages]);

  useLayoutEffect(() => {
    stick.current = true;
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [roomKey]);

  function onScroll() {
    const el = ref.current!;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    prevHeight.current = el.scrollHeight;
    if (el.scrollTop === 0) onTop();
  }

  // Like Messenger: only your latest message shows sent/seen, plus any that failed.
  const lastOwn = messages.findLast((m) => m.self && m.status)?.id;

  let lastDay = "";
  return (
    <div className="log" ref={ref} onScroll={onScroll}>
      {messages.map((m) => {
        const d = day(m.ts);
        const divider = d !== lastDay && m.kind !== "system" ? (lastDay = d) : null;
        return (
          <div key={m.id}>
            {divider && <div className="day">── {divider} ──</div>}
            <Line msg={m} transport={transport} showStatus={m.id === lastOwn || m.status === "failed"} />
          </div>
        );
      })}
    </div>
  );
}

function Line({ msg: m, transport, showStatus }: { msg: Message; transport: Transport; showStatus: boolean }) {
  if (m.kind === "system") {
    return (
      <div className="line system">
        <span className="ts">{time(m.ts)}</span>
        <span className="body">{m.body}</span>
      </div>
    );
  }
  const who = m.self ? "nick self" : nickClass(m.sender);
  const mark = showStatus && m.status ? MARKS[m.status] : null;
  const status = mark && (
    <span className={`mark ${m.status}`} title={mark[1]}>
      {mark[0]}
    </span>
  );
  return (
    <div className={`line ${m.kind}${m.self ? " mine" : ""}`}>
      <span className="ts">{time(m.ts)}</span>
      {m.kind === "emote" ? (
        <span className="body">
          * <span className={who}>{m.senderName}</span> {m.body}
          {status}
        </span>
      ) : (
        <>
          <span className={who}>&lt;{m.senderName}&gt;</span>
          <span className="body">
            {m.kind === "image" || m.kind === "video" || m.kind === "file" ? <Media msg={m} transport={transport} /> : m.body}
            {status}
          </span>
        </>
      )}
    </div>
  );
}
