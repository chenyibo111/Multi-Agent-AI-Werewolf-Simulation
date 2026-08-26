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
});
