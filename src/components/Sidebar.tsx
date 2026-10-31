import type { Section, SectionId } from "../rooms";
import type { Contact, Transport } from "../transport/types";
import { Avatar } from "./Avatar";
import { ContactList } from "./ContactList";

export type SidebarView = "chats" | "contacts";

interface Props {
  view: SidebarView;
  sections: Section[];
  contacts: Contact[];
  collapsed: SectionId[];
  activeId: string | null;
  open: boolean;
  transport: Transport;
  onView(view: SidebarView): void;
  onSelect(id: string): void;
  onPickContact(contact: Contact): void;
  onToggleSection(id: SectionId): void;
  onToggleFavorite(id: string, favorite: boolean): void;
}

export function Sidebar(props: Props) {
  const { view, sections, collapsed, activeId, open, transport } = props;
  let n = 0;
  return (
    <aside className={`sidebar${open ? " open" : ""}`}>
      <div className="tabs" role="tablist">
        {(["chats", "contacts"] as const).map((v) => (
          <button key={v} role="tab" aria-selected={view === v} className={view === v ? "on" : undefined} onClick={() => props.onView(v)}>
            {v.toUpperCase()}
          </button>
        ))}
      </div>

      {view === "contacts" ? (
        <ContactList contacts={props.contacts} transport={transport} onPick={props.onPickContact} />
      ) : (
        <>
          {sections.map((s) => {
            const isCollapsed = collapsed.includes(s.id);
            const unread = s.rooms.reduce((sum, r) => sum + r.unread, 0);
            const start = n;
            n += s.rooms.length;
            return (
              <section key={s.id}>
                <button className="section-label" onClick={() => props.onToggleSection(s.id)} aria-expanded={!isCollapsed}>
                  <span className="caret">{isCollapsed ? "▸" : "▾"}</span>
                  {"// "}
                  {s.label} [{s.rooms.length}]
                  {isCollapsed && unread > 0 && <span className="dot" title={`${unread} unread`} />}
                </button>
                {!isCollapsed && (
                  <ul>
                    {s.rooms.map((r, i) => (
                      <li key={r.id} className={r.unread > 0 ? "unread" : undefined}>
                        <button
                          className={`room${r.id === activeId ? " active" : ""}`}
                          onClick={() => props.onSelect(r.id)}
                          title={r.name}
                        >
                          <span className="idx">{String(start + i + 1).padStart(2, "0")}</span>
                          {r.kind === "bridge" ? (
                            <span className="avatar sys">⚙</span>
                          ) : (
                            <Avatar url={r.avatarUrl} name={r.name} transport={transport} size={26} />
                          )}
                          <span className="name">{r.name}</span>
                          {r.unread > 0 && <span className="dot" title={`${r.unread} unread`} />}
                        </button>
                        <button
                          className={`star${r.favorite ? " on" : ""}`}
                          onClick={() => props.onToggleFavorite(r.id, !r.favorite)}
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
        </>
      )}
    </aside>
  );
}
