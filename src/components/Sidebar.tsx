import type { Room } from "../transport/types";

interface Props {
  rooms: Room[];
  activeId: string | null;
  open: boolean;
  onSelect(id: string): void;
}

export function Sidebar({ rooms, activeId, open, onSelect }: Props) {
  return (
    <aside className={`sidebar${open ? " open" : ""}`}>
      <div className="section-label">// CHANNELS [{rooms.length}]</div>
      <ul>
        {rooms.map((r, i) => (
          <li key={r.id}>
            <button className={r.id === activeId ? "active" : undefined} onClick={() => onSelect(r.id)} title={r.name}>
              <span className="idx">{String(i + 1).padStart(2, "0")}</span>
              <span className="name">
                {r.bridgeBot ? "⚙ " : r.invite ? "✉ " : "# "}
                {r.name}
              </span>
              {r.unread > 0 && <span className="badge">{r.unread > 99 ? "99+" : r.unread}</span>}
            </button>
          </li>
        ))}
        {rooms.length === 0 && <li className="dim empty">no signal…</li>}
      </ul>
    </aside>
  );
}
