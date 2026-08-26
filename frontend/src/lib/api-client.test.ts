import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiRequestError } from "./api-client";

const createdRoomPayload = {
  room_id: "room-1",
  session_token: "must-not-be-read",
  state: {
    game_id: "room-1",
    phase: "night_seer",
    status: "running",
    round_number: 1,
    participants: {},
    waiting_for_human: true,
    human_actions: ["inspect"],
    legal_target_ids: ["ai-1"],
    phase_text: "预言家查验",
    view_mode: "active",
  },
  events: [],
};

afterEach(() => vi.restoreAllMocks());

describe("ApiClient", () => {
  it("creates a room with cookies but never returns session_token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(createdRoomPayload))));

    const payload = await new ApiClient("http://api.test").createRoom("seer");

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/api/rooms",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
    expect(payload.state.phase).toBe("night_seer");
    expect(payload).not.toHaveProperty("session_token");
  });

  it("turns a 422 response into a user-safe request error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "wrong_phase" }), { status: 422 })),
    );

    await expect(new ApiClient().continueRoom("room-1")).rejects.toEqual(
      new ApiRequestError("wrong_phase"),
    );
  });

  it("loads a completed report and deletes a room with the room cookie", async () => {
    const report = {
      winner_faction: "villager",
      participants: { "ai-1": { participant_id: "ai-1", display_name: "AI 玩家 1", alive: true, role_id: "wolf" } },
      events: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(new Response(JSON.stringify(report)))
        .mockResolvedValueOnce(new Response(null, { status: 204 })),
    );
    const client = new ApiClient("http://api.test");

    expect(await client.getReport("room-1")).toEqual(report);
    await client.deleteRoom("room-1");

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/rooms/room-1/report",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/rooms/room-1",
      expect.objectContaining({ credentials: "include", method: "DELETE" }),
    );
  });
});
