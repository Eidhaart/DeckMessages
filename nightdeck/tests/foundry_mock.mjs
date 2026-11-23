// A minimal stand-in for Foundry VTT that loads the real Nightdeck Link module (dev test only).
// Prints EVENT lines (JSON) for updates, item updates and chat messages.
import { pathToFileURL } from "node:url";

const log = (kind, data) => console.log("EVENT " + JSON.stringify({ kind, ...data }));
const hooks = {};
globalThis.Hooks = {
  on: (name, fn) => (hooks[name] ||= []).push(fn),
  once: (name, fn) => (hooks[name] ||= []).push(fn),
  call: (name, ...args) => (hooks[name] || []).forEach((fn) => fn(...args)),
};

function setPath(obj, path, value) {
  const keys = path.split(".");
  let node = obj;
  for (const key of keys.slice(0, -1)) node = node[key] ||= {};
  node[keys.at(-1)] = value;
}

class Item {
  constructor(parent, data) { Object.assign(this, data); this.parent = parent; }
  async update(changes) {
    for (const [k, v] of Object.entries(changes)) setPath(this, k, v);
    log("updateItem", { itemId: this.id, changes });
    Hooks.call("updateItem", this, changes);
  }
}
const collection = (list) => ({ contents: list, get: (id) => list.find((d) => d.id === id), map: (f) => list.map(f) });

class Actor {
  constructor(data) {
    Object.assign(this, data);
    this.documentName = "Actor";
    this.items = collection((data.items || []).map((i) => new Item(this, i)));
    this.effects = collection([]);
    this.hasPlayerOwner = true;
  }
  testUserPermission() { return true; }
  async update(changes) {
    for (const [k, v] of Object.entries(changes)) setPath(this, k, v);
    log("updateActor", { changes });
    Hooks.call("updateActor", this, changes);
  }
}

const actor = new Actor({
  id: "act1", name: "Kestrel", type: "Player",
  system: {
    attributes: { bod: { pool: 4 }, agi: { pool: 5 }, rea: { pool: 4 }, str: { pool: 3 }, wil: { pool: 3 },
                  log: { pool: 3 }, int: { pool: 4 }, cha: { pool: 2 }, edg: { pool: 4 }, mag: { pool: 0 },
                  res: { pool: 0 }, essence: { pool: 5.2 } },
    physical: { dmg: 0, max: 10 }, stun: { dmg: 2, max: 10 }, overflow: { dmg: 0, max: 8 },
    edge: { value: 3 },
    initiative: { physical: { pool: 8, dicePool: 1 } },
    defenserating: { physical: { pool: 7 } }, attackrating: { physical: { pool: 8 } },
    nuyen: 1200, karma: 5,
    skills: { firearms: { points: 4, pool: 9, specialization: "Pistols", poolS: 11 },
              stealth: { points: 3, pool: 8 }, athletics: { points: 0, pool: 0 } },
  },
  items: [{ id: "w1", name: "Ares Predator VI", type: "gear",
            system: { dmg: 3, stun: false, pool: 9, ammocap: 15, ammocount: 15 } }],
});
const users = [{ name: "GM", isGM: true }, { name: "Player One", isGM: false }];
users.filter = Array.prototype.filter.bind(users);
const settings = { url: process.env.NIGHTDECK_URL, token: process.env.NIGHTDECK_TOKEN };

globalThis.game = {
  user: { isGM: true, name: "GM" },
  users: Object.assign(users, { activeGM: { isSelf: true } }),
  world: { id: process.env.WORLD_ID || "world-sr6", title: process.env.WORLD_TITLE || "Seattle Nights" },
  system: { id: "shadowrun6-eden", version: "4.0.11" },
  version: "13.348",
  actors: collection([actor]),
  settings: { register: () => {}, get: (_, key) => settings[key] },
};
globalThis.ui = { notifications: { warn: (msg) => log("warn", { msg }) } };
globalThis.ChatMessage = { getSpeaker: ({ actor }) => ({ alias: actor?.name }) };
globalThis.Roll = class {
  constructor(formula) { this.formula = formula; }
  async evaluate() {
    const pool = this.formula.match(/^(\d+)d6cs>=5$/);
    const plain = this.formula.match(/^(\d+) \+ (\d+)d6$/);
    if (pool) {
      const n = Number(pool[1]);
      const results = Array.from({ length: n }, (_, i) => [6, 5, 1, 3, 2, 4][i % 6]);
      this.dice = [{ results: results.map((result) => ({ result })) }];
      this.total = results.filter((r) => r >= 5).length;
    } else if (plain) {
      const results = Array.from({ length: Number(plain[2]) }, () => 4);
      this.dice = [{ results: results.map((result) => ({ result })) }];
      this.total = Number(plain[1]) + results.reduce((a, b) => a + b, 0);
    }
    return this;
  }
  async toMessage(data) { log("chat", { formula: this.formula, total: this.total, flavor: data.flavor, speaker: data.speaker }); }
};

await import(pathToFileURL(process.argv[2]).href);
Hooks.call("init");
Hooks.call("ready");
log("started", {});
setInterval(() => {}, 1000);
