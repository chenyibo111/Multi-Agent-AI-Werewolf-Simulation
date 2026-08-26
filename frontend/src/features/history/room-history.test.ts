import { afterEach, describe, expect, it } from "vitest";

import { loadRoomHistory, rememberRoom, removeRoom } from "./room-history";

afterEach(() => localStorage.clear());

describe("room history", () => {
  it("keeps only room IDs and newest open times without duplicating a room", () => {
    rememberRoom({ roomId: "room-1", openedAt: "2026-08-27T08:00:00.000Z" });
    rememberRoom({ roomId: "room-2", openedAt: "2026-08-27T09:00:00.000Z" });
    rememberRoom({ roomId: "room-1", openedAt: "2026-08-27T10:00:00.000Z" });

    expect(loadRoomHistory()).toEqual([
      { roomId: "room-1", openedAt: "2026-08-27T10:00:00.000Z" },
      { roomId: "room-2", openedAt: "2026-08-27T09:00:00.000Z" },
    ]);
    expect(localStorage.getItem("werewolf-arena-room-history")).not.toContain("session_token");
  });

  it("removes an inaccessible room from the browser-local index", () => {
    rememberRoom({ roomId: "room-1", openedAt: "2026-08-27T08:00:00.000Z" });

    removeRoom("room-1");

    expect(loadRoomHistory()).toEqual([]);
  });
});
