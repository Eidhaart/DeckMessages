import { useMemo, useState } from "react";
import type { Contact, Transport } from "../transport/types";
import { Avatar } from "./Avatar";

interface Props {
  contacts: Contact[];
  transport: Transport;
  onPick(contact: Contact): void;
}

/** Everyone you share a chat with, A–Z, with a filter line at the top. */
export function ContactList({ contacts, transport, onPick }: Props) {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const hits = q ? contacts.filter((c) => c.name.toLowerCase().includes(q)) : contacts;
    const byLetter = new Map<string, Contact[]>();
    for (const c of hits) {
      const first = c.name.trim()[0]?.toUpperCase() ?? "#";
      const letter = /\p{L}/u.test(first) ? first : "#";
      byLetter.set(letter, [...(byLetter.get(letter) ?? []), c]);
    }
    return [...byLetter.entries()];
  }, [contacts, query]);

  return (
    <div className="contacts">
      <label className="contact-search">
        <span className="accent">&gt;</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="find contact"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        <span className="dim count">{contacts.length}</span>
      </label>
      {groups.map(([letter, list]) => (
        <section key={letter}>
          <div className="letter">{letter}</div>
          <ul>
            {list.map((c) => (
              <li key={c.id}>
                <button className="contact" onClick={() => onPick(c)}>
                  <Avatar url={c.avatarUrl} name={c.name} transport={transport} size={30} />
                  <span className="name">{c.name}</span>
                  <span className={`go ${c.roomId ? "open" : "new"}`}>{c.roomId ? "open ›" : "+ chat"}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {groups.length === 0 && (
        <div className="dim empty">{query ? `no one matches "${query}"` : "no contacts yet. they appear as chats sync."}</div>
      )}
    </div>
  );
}
