import { useEffect, useState } from "react";
import type { Transport } from "../transport/types";

interface Props {
  url?: string;
  name: string;
  transport: Transport;
  /** Rendered size in px; a thumbnail twice as large is fetched for sharp screens. */
  size?: number;
}

function initials(name: string) {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/);
  return ((words[0]?.[0] ?? "?") + (words.length > 1 ? words.at(-1)![0] : "")).toUpperCase();
}

// Same palette as nicknames, so a person keeps one colour everywhere.
function tone(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return `n${Math.abs(h) % 6}`;
}

export function Avatar({ url, name, transport, size = 28 }: Props) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    setSrc(null);
    if (!url) return;
    let live = true;
    transport.fetchMedia(url, size * 2).then(
      (u) => live && setSrc(u),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [url, size, transport]);

  return (
    <span className={`avatar ${src ? "" : tone(name)}`} style={{ width: size, height: size, fontSize: size * 0.4 }} aria-hidden>
      {src ? <img src={src} alt="" /> : initials(name)}
    </span>
  );
}
