import { THEMES, type Theme } from "./settings";
import { groupRooms } from "./rooms";
import type { Contact, MovableKind, Room } from "./transport/types";

export interface CommandContext {
  /** In sidebar order, so numbers match the sidebar. */
  rooms: Room[];
  activeRoom: Room | null;
  selfId: string;
  transportKind: "demo" | "matrix";
  print(text: string): void;
  select(roomId: string): void;
  step(delta: number): void;
  send(body: string, emote?: boolean): void;
  clear(): void;
  setTheme(t: Theme): void;
  setFx(on: boolean): void;
  setBoot(on: boolean): void;
  loadOlder(): void;
  accept(roomId: string): void;
  openBridge(): void;
  setFavorite(roomId: string, favorite: boolean): void;
  setCategory(roomId: string, kind: MovableKind | null): void;
  setDisplayName(name: string): void;
  contacts(): Contact[];
  openContact(contact: Contact): void;
  showContacts(): void;
  logout(): void;
  reboot(): void;
}

interface Command {
  usage: string;
  help: string;
  aliases?: string[];
  run(args: string, ctx: CommandContext): void;
}

function findRoom(query: string, rooms: Room[]): Room | undefined {
  const n = Number(query);
  if (Number.isInteger(n) && n >= 1 && n <= rooms.length) return rooms[n - 1];
  const q = query.toLowerCase();
  return rooms.find((r) => r.name.toLowerCase() === q) ?? rooms.find((r) => r.name.toLowerCase().includes(q));
}

const COMMANDS: Record<string, Command> = {
  help: {
    usage: "/help",
    help: "list commands",
    aliases: ["?"],
    run: (_a, ctx) => {
      ctx.print("available commands:");
      for (const c of Object.values(COMMANDS)) ctx.print(`  ${c.usage.padEnd(22)} ${c.help}`);
      ctx.print("keys: Alt+↑/↓ switch channel · Tab complete channel · ↑/↓ history · Ctrl+L clear");
    },
  },
  list: {
    usage: "/list",
    help: "list channels with their numbers",
    aliases: ["ls"],
    run: (_a, ctx) => {
      if (!ctx.rooms.length) return ctx.print("no channels. is the bridge logged in? try /bridge");
      let n = 0;
      for (const section of groupRooms(ctx.rooms)) {
        ctx.print(`// ${section.label}`);
        for (const r of section.rooms) {
          const flags = [r.unread ? `${r.unread} new` : "", r.invite ? "invite" : ""].filter(Boolean).join(", ");
          ctx.print(`  [${String(++n).padStart(2)}] ${r.name}${flags ? `  (${flags})` : ""}`);
        }
      }
    },
  },
  go: {
    usage: "/go <n|name>",
    help: "jack into a channel",
    aliases: ["j", "join", "q"],
    run: (a, ctx) => {
      if (!a) return ctx.print("usage: /go <number or name>");
      const r = findRoom(a, ctx.rooms);
      if (!r) return ctx.print(`no channel matches "${a}"`);
      ctx.select(r.id);
    },
  },
  next: { usage: "/next", help: "next channel", aliases: ["n"], run: (_a, ctx) => ctx.step(1) },
  prev: { usage: "/prev", help: "previous channel", aliases: ["p"], run: (_a, ctx) => ctx.step(-1) },
  me: {
    usage: "/me <action>",
    help: "send an action",
    run: (a, ctx) => (a ? ctx.send(a, true) : ctx.print("usage: /me <action>")),
  },
  accept: {
    usage: "/accept",
    help: "accept invite for current channel",
    run: (_a, ctx) => {
      if (!ctx.activeRoom?.invite) return ctx.print("no pending invite here");
      ctx.accept(ctx.activeRoom.id);
    },
  },
  move: {
    usage: "/move <category|auto>",
    help: "move this chat: direct, groups, marketplace, business, requests",
    run: (a, ctx) => {
      if (!ctx.activeRoom || ctx.activeRoom.kind === "bridge") return ctx.print("open a chat first");
      const names: Record<string, MovableKind | null> = {
        direct: "dm", dm: "dm", groups: "group", group: "group", marketplace: "market", market: "market",
        business: "business", requests: "request", request: "request", auto: null,
      };
      const key = a.toLowerCase();
      if (!(key in names)) return ctx.print("usage: /move direct|groups|marketplace|business|requests|auto");
      ctx.setCategory(ctx.activeRoom.id, names[key]);
      ctx.print(names[key] ? `moved to ${key}` : "back to automatic sorting");
    },
  },
  older: { usage: "/older", help: "pull older history", run: (_a, ctx) => ctx.loadOlder() },
  fav: {
    usage: "/fav",
    help: "add or remove current channel from favorites",
    aliases: ["star"],
    run: (_a, ctx) => {
      if (!ctx.activeRoom) return ctx.print("no channel selected");
      const favorite = !ctx.activeRoom.favorite;
      ctx.setFavorite(ctx.activeRoom.id, favorite);
      ctx.print(favorite ? "★ added to favorites" : "☆ removed from favorites");
    },
  },
  bridge: {
    usage: "/bridge",
    help: "open the Messenger bridge bot",
    run: (_a, ctx) => {
      if (ctx.transportKind === "demo") return ctx.print("demo mode has no bridge. /logout and connect a homeserver.");
      ctx.openBridge();
    },
  },
  clear: { usage: "/clear", help: "clear the screen", aliases: ["cls"], run: (_a, ctx) => ctx.clear() },
  theme: {
    usage: `/theme <${THEMES.join("|")}>`,
    help: "change colour scheme",
    run: (a, ctx) => {
      if (!THEMES.includes(a as Theme)) return ctx.print(`themes: ${THEMES.join(", ")}`);
      ctx.setTheme(a as Theme);
      ctx.print(`palette → ${a}`);
    },
  },
  fx: {
    usage: "/fx <on|off>",
    help: "toggle CRT effects",
    run: (a, ctx) => {
      if (a !== "on" && a !== "off") return ctx.print("usage: /fx on|off");
      ctx.setFx(a === "on");
      ctx.print(`crt fx ${a}`);
    },
  },
  boot: {
    usage: "/boot <on|off>",
    help: "toggle boot sequence",
    run: (a, ctx) => {
      if (a !== "on" && a !== "off") return ctx.print("usage: /boot on|off");
      ctx.setBoot(a === "on");
      ctx.print(`boot sequence ${a}`);
    },
  },
  contacts: {
    usage: "/contacts",
    help: "show your contact list",
    aliases: ["c"],
    run: (_a, ctx) => ctx.showContacts(),
  },
  msg: {
    usage: "/msg <name>",
    help: "open a chat with a contact",
    aliases: ["dm"],
    run: (a, ctx) => {
      if (!a) return ctx.print("usage: /msg <name>");
      const q = a.toLowerCase();
      const all = ctx.contacts();
      const hit = all.find((c) => c.name.toLowerCase() === q) ?? all.find((c) => c.name.toLowerCase().includes(q));
      if (!hit) return ctx.print(`no contact matches "${a}". try /contacts`);
      ctx.openContact(hit);
    },
  },
  nick: {
    usage: "/nick <name>",
    help: "change the name shown on your messages",
    aliases: ["name"],
    run: (a, ctx) => (a ? ctx.setDisplayName(a) : ctx.print("usage: /nick <name>")),
  },
  whoami: {
    usage: "/whoami",
    help: "show identity",
    run: (_a, ctx) => ctx.print(`${ctx.selfId} via ${ctx.transportKind === "demo" ? "demo uplink" : "matrix"}`),
  },
  reboot: { usage: "/reboot", help: "restart the deck", run: (_a, ctx) => ctx.reboot() },
  logout: { usage: "/logout", help: "disconnect and forget session", aliases: ["quit"], run: (_a, ctx) => ctx.logout() },
};

const LOOKUP = new Map<string, Command>();
for (const [name, c] of Object.entries(COMMANDS)) {
  LOOKUP.set(name, c);
  c.aliases?.forEach((a) => LOOKUP.set(a, c));
}

export const COMMAND_NAMES = [...LOOKUP.keys()];

/** Returns true if input was a command (handled), false if it's a plain message. */
export function runCommand(input: string, ctx: CommandContext): boolean {
  if (!input.startsWith("/") || input.startsWith("//")) return false;
  const [, name, args = ""] = input.match(/^\/(\S+)\s*([\s\S]*)$/) ?? [];
  const cmd = LOOKUP.get(name?.toLowerCase() ?? "");
  if (!cmd) ctx.print(`unknown command: /${name}. try /help`);
  else cmd.run(args.trim(), ctx);
  return true;
}

/** Tab completion for commands and channel names. */
export function complete(input: string, rooms: Room[]): string | null {
  const cmdMatch = input.match(/^\/(\S*)$/);
  if (cmdMatch) {
    const hit = COMMAND_NAMES.find((n) => n.startsWith(cmdMatch[1].toLowerCase()) && n !== cmdMatch[1]);
    return hit ? `/${hit} ` : null;
  }
  const goMatch = input.match(/^\/(go|j|join|q)\s+(.+)$/i);
  if (goMatch) {
    const q = goMatch[2].toLowerCase();
    const hit = rooms.find((r) => r.name.toLowerCase().startsWith(q));
    return hit ? `/${goMatch[1]} ${hit.name}` : null;
  }
  return null;
}
