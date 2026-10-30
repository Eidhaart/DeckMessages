import { forwardRef, useRef, useState, type KeyboardEvent } from "react";
import { complete } from "../commands";
import type { Room } from "../transport/types";

interface Props {
  channel: string;
  rooms: Room[];
  onSubmit(text: string): void;
}

export const Prompt = forwardRef<HTMLTextAreaElement, Props>(function Prompt({ channel, rooms, onSubmit }, ref) {
  const [value, setValue] = useState("");
  const history = useRef<string[]>([]);
  const cursor = useRef(-1);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = value.trim();
      if (!text) return;
      history.current.unshift(text);
      cursor.current = -1;
      setValue("");
      onSubmit(text);
    } else if (e.key === "Tab") {
      const hit = complete(value, rooms);
      if (hit) {
        e.preventDefault();
        setValue(hit);
      }
    } else if (e.key === "ArrowUp" && !e.altKey && !value.includes("\n")) {
      const next = Math.min(cursor.current + 1, history.current.length - 1);
      if (next >= 0) {
        e.preventDefault();
        cursor.current = next;
        setValue(history.current[next]);
      }
    } else if (e.key === "ArrowDown" && !e.altKey && cursor.current >= 0) {
      e.preventDefault();
      cursor.current -= 1;
      setValue(cursor.current >= 0 ? history.current[cursor.current] : "");
    }
  }

  return (
    <div className="prompt">
      <span className="ps1">
        <span className="accent2">deck</span>@<span className="accent">{channel}</span>
        <span className="dim">:~$</span>
      </span>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="type a message or /help"
        autoCapitalize="sentences"
        spellCheck={false}
        enterKeyHint="send"
      />
      <button
        className="send"
        aria-label="send"
        onClick={() => {
          const text = value.trim();
          if (text) {
            history.current.unshift(text);
            setValue("");
            onSubmit(text);
          }
        }}
      >
        ⏎
      </button>
    </div>
  );
});
