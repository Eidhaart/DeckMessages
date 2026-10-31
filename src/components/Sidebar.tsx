import type { Section, SectionId } from "../rooms";

interface Props {
  sections: Section[];
  collapsed: SectionId[];
  activeId: string | null;
  open: boolean;
  onSelect(id: string): void;
  onToggleSection(id: SectionId): void;
  onToggleFavorite(id: string, favorite: boolean): void;
}

export function Sidebar({ sections, collapsed, activeId, open, onSelect, onToggleSection, onToggleFavorite }: Props) {
  let n = 0;
  return (
    <aside className={`sidebar${open ? " open" : ""}`}>
      {sections.map((s) => {
        const isCollapsed = collapsed.includes(s.id);
        const unread = s.rooms.reduce((sum, r) => sum + r.unread, 0);
        const start = n;
        n += s.rooms.length;
        return (
          <section key={s.id}>
            <button className="section-label" onClick={() => onToggleSection(s.id)} aria-expanded={!isCollapsed}>
              <span className="caret">{isCollapsed ? "▸" : "▾"}</span>
              {"// "}
              {s.label} [{s.rooms.length}]
              {isCollapsed && unread > 0 && <span className="badge">{unread > 99 ? "99+" : unread}</span>}
            </button>
            {!isCollapsed && (
              <ul>
                {s.rooms.map((r, i) => (
                  <li key={r.id}>
                    <button
                      className={`room${r.id === activeId ? " active" : ""}`}
                      onClick={() => onSelect(r.id)}
                      title={r.name}
                    >
                      <span className="idx">{String(start + i + 1).padStart(2, "0")}</span>
                      <span className="name">
                        {r.kind === "bridge" ? "⚙ " : r.invite ? "✉ " : r.kind === "group" ? "# " : "@ "}
                        {r.name}
                      </span>
                      {r.unread > 0 && <span className="badge">{r.unread > 99 ? "99+" : r.unread}</span>}
                    </button>
                    <button
                      className={`star${r.favorite ? " on" : ""}`}
                      onClick={() => onToggleFavorite(r.id, !r.favorite)}
                      aria-label={r.favorite ? `remove ${r.name} from favorites` : `add ${r.name} to favorites`}
                    >
                      {r.favorite ? "★" : "☆"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {sections.length === 0 && <div className="dim empty">no signal…</div>}
    </aside>
  );
}
