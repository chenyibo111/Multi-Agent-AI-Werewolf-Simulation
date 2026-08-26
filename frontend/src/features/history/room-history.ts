export type RoomHistoryEntry = {
  roomId: string;
  openedAt: string;
};

const storageKey = "werewolf-arena-room-history";

export function loadRoomHistory(): RoomHistoryEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isRoomHistoryEntry) : [];
  } catch {
    return [];
  }
}

export function rememberRoom(entry: RoomHistoryEntry): void {
  persist([entry, ...loadRoomHistory().filter((item) => item.roomId !== entry.roomId)]);
}

export function removeRoom(roomId: string): void {
  persist(loadRoomHistory().filter((item) => item.roomId !== roomId));
}

function persist(entries: RoomHistoryEntry[]): void {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

function isRoomHistoryEntry(value: unknown): value is RoomHistoryEntry {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Record<string, unknown>;
  return typeof entry.roomId === "string" && typeof entry.openedAt === "string";
}
