import type { SectionId } from "./rooms";
import type { MatrixSession } from "./transport/matrix";

export const THEMES = ["neon", "amber", "toxic", "ice"] as const;
export type Theme = (typeof THEMES)[number];

export interface Settings {
  theme: Theme;
  /** CRT scanlines, flicker and glow. */
  fx: boolean;
  boot: boolean;
  /** Sidebar sections the user folded away. */
  collapsed: SectionId[];
}

const SETTINGS_KEY = "deck.settings";
const SESSION_KEY = "deck.session";

const DEFAULTS: Settings = { theme: "neon", fx: true, boot: true, collapsed: [] };

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable: settings just won't persist.
  }
}

export const loadSettings = (): Settings => ({ ...DEFAULTS, ...read<Partial<Settings>>(SETTINGS_KEY) });
export const saveSettings = (s: Settings) => write(SETTINGS_KEY, s);

export const loadSession = () => read<MatrixSession>(SESSION_KEY);
export const saveSession = (s: MatrixSession | null) => write(SESSION_KEY, s);
