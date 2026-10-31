import type { Room } from "./transport/types";

export type SectionId = "favorites" | "dm" | "group" | "bridge";

export interface Section {
  id: SectionId;
  label: string;
  rooms: Room[];
}

const LABELS: Record<SectionId, string> = {
  favorites: "FAVORITES",
  dm: "DIRECT",
  group: "GROUPS",
  bridge: "SYSTEM",
};

/**
 * Splits rooms into sidebar sections. Favorites are pulled out of their usual section,
 * and each section is ordered by latest activity. Empty sections are dropped.
 */
export function groupRooms(rooms: Room[]): Section[] {
  const byRecent = [...rooms].sort((a, b) => b.lastTs - a.lastTs);
  const pick = (id: SectionId, test: (r: Room) => boolean): Section => ({
    id,
    label: LABELS[id],
    rooms: byRecent.filter(test),
  });
  return [
    pick("favorites", (r) => r.favorite),
    pick("dm", (r) => !r.favorite && r.kind === "dm"),
    pick("group", (r) => !r.favorite && r.kind === "group"),
    pick("bridge", (r) => !r.favorite && r.kind === "bridge"),
  ].filter((s) => s.rooms.length > 0);
}

/** Rooms in sidebar order; channel numbers (/go 3, the 01 02 … labels) index into this. */
export function orderedRooms(rooms: Room[]): Room[] {
  return groupRooms(rooms).flatMap((s) => s.rooms);
}
