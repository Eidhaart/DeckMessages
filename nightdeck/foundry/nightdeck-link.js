// Nightdeck Link: streams characters to a Nightdeck cyberdeck and carries out its commands.
// Runs in the active GM's browser only. Settings are per browser (client scope) so players
// never see the link token.
const MODULE = "nightdeck-link";
const DEFAULT_URL = "__NIGHTDECK_URL__";
let socket = null;
let retry = 5000;
let pingTimer = null;
const watched = new Set();
const pending = new Map();

Hooks.once("init", () => {
  game.settings.register(MODULE, "url", {
    name: "Nightdeck address",
    hint: "The deck's link address, e.g. wss://nightdeck.your-tailnet.ts.net/link",
    scope: "client", config: true, type: String,
    default: DEFAULT_URL.startsWith("__") ? "" : DEFAULT_URL,
    onChange: () => reconnect(),
  });
  game.settings.register(MODULE, "token", {
    name: "Nightdeck link code",
    hint: "The secret code shown on the deck under Character sheets > Link setup.",
    scope: "client", config: true, type: String, default: "",
    onChange: () => reconnect(),
  });
});

Hooks.once("ready", () => {
  if (!isLinkGM()) return;
  connect();
  for (const hook of ["createActor", "deleteActor"]) Hooks.on(hook, () => schedule("list", sendActors));
  Hooks.on("updateActor", (actor, changes) => {
    if ("name" in changes || "ownership" in changes) schedule("list", sendActors);
    if (watched.has(actor.id)) schedule(actor.id, () => sendActor(actor));
  });
  const itemHook = (doc) => {
    const actor = doc.parent;
    if (actor && actor.documentName === "Actor" && watched.has(actor.id)) schedule(actor.id, () => sendActor(actor));
  };
  for (const hook of ["createItem", "updateItem", "deleteItem",
                      "createActiveEffect", "updateActiveEffect", "deleteActiveEffect"]) Hooks.on(hook, itemHook);
});

function isLinkGM() {
  if (!game.user.isGM) return false;
  const active = game.users.activeGM;
  return !active || active.isSelf;
}

function connect() {
  const url = game.settings.get(MODULE, "url");
  const token = game.settings.get(MODULE, "token");
  if (!url || !token) {
    console.log("Nightdeck Link | set the address and code in module settings to connect");
    return;
  }
  try {
    socket = new WebSocket(url);
  } catch (error) {
    console.warn("Nightdeck Link | bad address", error);
    return;
  }
  socket.onopen = () => {
    retry = 5000;
    send({
      type: "hello", token,
      world: { id: game.world.id, title: game.world.title, system: game.system.id,
               systemVersion: game.system.version, foundry: game.version },
      gm: game.user.name,
    });
    sendActors();
    for (const id of watched) {
      const actor = game.actors.get(id);
      if (actor) sendActor(actor);
    }
    clearInterval(pingTimer);
    pingTimer = setInterval(() => send({ type: "ping" }), 25000);
  };
  socket.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    handle(message).catch((error) => console.warn("Nightdeck Link |", error));
  };
  socket.onclose = (event) => {
    clearInterval(pingTimer);
    socket = null;
    if (event.code === 4001) {
      ui.notifications?.warn("Nightdeck Link: the deck refused the link code. Check the module settings.");
      return;
    }
    setTimeout(connect, retry);
    retry = Math.min(retry * 2, 60000);
  };
}

function reconnect() {
  if (socket) { socket.onclose = null; socket.close(); socket = null; }
  if (isLinkGM()) connect();
}

function send(message) {
  if (socket && socket.readyState === 1) socket.send(JSON.stringify(message));
}

function schedule(key, fn) {
  clearTimeout(pending.get(key));
  pending.set(key, setTimeout(() => { pending.delete(key); fn(); }, 150));
}

function owners(actor) {
  return game.users.filter((u) => !u.isGM && actor.testUserPermission(u, "OWNER")).map((u) => u.name);
}

function sendActors() {
  send({ type: "actors", list: game.actors.contents.map((a) => ({
    id: a.id, name: a.name, type: a.type, owners: owners(a), player: a.hasPlayerOwner })) });
}

// Copy prepared (derived) data, not just stored source: own enumerable properties, no functions.
function plain(value, depth = 0, seen = new WeakSet()) {
  if (value === null || typeof value !== "object") return typeof value === "function" ? undefined : value;
  if (depth > 10 || seen.has(value)) return undefined;
  seen.add(value);
  if (value instanceof Set) return [...value].map((v) => plain(v, depth + 1, seen));
  if (value instanceof Map) value = Object.fromEntries(value);
  if (Array.isArray(value)) return value.map((v) => plain(v, depth + 1, seen));
  const out = {};
  for (const key of Object.keys(value)) {
    if (key === "parent" || key.startsWith("_")) continue;
    const v = plain(value[key], depth + 1, seen);
    if (v !== undefined) out[key] = v;
  }
  return out;
}

function sendActor(actor) {
  send({ type: "actor", actorId: actor.id, data: {
    id: actor.id, name: actor.name, type: actor.type,
    system: plain(actor.system),
    items: actor.items.contents.map((i) => ({ id: i.id, name: i.name, type: i.type, system: plain(i.system) })),
    effects: actor.effects.contents.map((e) => ({ id: e.id, name: e.name, disabled: e.disabled })),
  } });
}

async function handle(message) {
  const reply = (body) => send({ type: "result", id: message.id, ...body });
  const actor = message.actorId ? game.actors.get(message.actorId) : null;
  switch (message.type) {
    case "welcome":
      return;
    case "watch":
      if (!actor) return;
      watched.add(actor.id);
      return sendActor(actor);
    case "update":
      if (!actor) return reply({ ok: false, error: "No such actor" });
      await actor.update(message.data);
      return reply({ ok: true });
    case "updateItem": {
      const item = actor?.items.get(message.itemId);
      if (!item) return reply({ ok: false, error: "No such item" });
      await item.update(message.data);
      return reply({ ok: true });
    }
    case "roll": {
      const roll = await new Roll(message.formula).evaluate();
      const dice = roll.dice.flatMap((d) => d.results.map((r) => r.result));
      let flavor = message.flavor || "";
      let glitch = false;
      if (message.pool) {  // Shadowrun pool: hits on 5-6, glitch when more than half the dice are 1s
        const ones = dice.filter((r) => r === 1).length;
        glitch = ones > dice.length / 2;
        const hits = roll.total;
        flavor += ` — ${hits} hit${hits === 1 ? "" : "s"}`;
        if (glitch) flavor += hits === 0 ? " — CRITICAL GLITCH!" : " — GLITCH!";
      }
      await roll.toMessage({ speaker: ChatMessage.getSpeaker({ actor }), flavor: `${flavor} (Nightdeck)` });
      return reply({ ok: true, total: roll.total, dice, glitch });
    }
    default:
      return;
  }
}
