import { useState, type FormEvent } from "react";
import { matrixLogin, type MatrixSession } from "../transport/matrix";

interface Props {
  onSession(s: MatrixSession): void;
  onDemo(): void;
}

export function LoginScreen({ onSession, onDemo }: Props) {
  const [baseUrl, setBaseUrl] = useState("https://");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [bridgeBot, setBridgeBot] = useState("metabot");
  const [autoJoin, setAutoJoin] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const creds = await matrixLogin(baseUrl, user, password);
      onSession({ ...creds, bridgeBot: bridgeBot.trim() || "metabot", autoJoin });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div className="panel">
        <div className="panel-title">// JACK IN</div>
        <p className="dim">
          Messenger has no public API for personal chats, so the deck reaches it through your own Matrix homeserver
          running the <span className="accent">mautrix-meta</span> bridge. Setup: <code>docs/BRIDGE.md</code>.
        </p>
        <form onSubmit={submit}>
          <label>
            <span>homeserver</span>
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://matrix.example.com" autoCapitalize="off" spellCheck={false} />
          </label>
          <label>
            <span>user</span>
            <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="@you:example.com" autoCapitalize="off" autoComplete="username" spellCheck={false} />
          </label>
          <label>
            <span>passphrase</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <label>
            <span>bridge bot</span>
            <input value={bridgeBot} onChange={(e) => setBridgeBot(e.target.value)} autoCapitalize="off" spellCheck={false} />
          </label>
          <label className="check">
            <input type="checkbox" checked={autoJoin} onChange={(e) => setAutoJoin(e.target.checked)} />
            <span>auto-accept chat invites from the bridge</span>
          </label>
          {error && <div className="error">!! {error}</div>}
          <div className="actions">
            <button type="submit" disabled={busy || !user || !password}>
              {busy ? "connecting…" : "> connect"}
            </button>
            <button type="button" className="ghost" onClick={onDemo}>
              &gt; demo mode
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
