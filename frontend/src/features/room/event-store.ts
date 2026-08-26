import type { RoomEvent } from "../../lib/types";

export function mergeRoomEvents(current: RoomEvent[], incoming: RoomEvent[]): RoomEvent[] {
  return [...new Map([...current, ...incoming].map((event) => [event.sequence, event])).values()].sort(
    (left, right) => left.sequence - right.sequence,
  );
}
