import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../lib/api-client";
import type { RoomPayload } from "../../lib/types";
import { useRoomSession } from "./use-room-session";

const payload: RoomPayload = {
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
  events: [{ sequence: 7, event_type: "phase_changed", payload: {}, visibility: "public" }],
};

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {}
}

afterEach(() => {
  MockWebSocket.instances = [];
  vi.unstubAllGlobals();
});

describe("useRoomSession", () => {
  it("connects using only the latest visible event sequence", async () => {
    vi.stubGlobal("WebSocket", MockWebSocket);
    const api = {
      getRoom: vi.fn().mockResolvedValue(payload),
      continueRoom: vi.fn(),
      submitCommand: vi.fn(),
    } as unknown as ApiClient;

    const { result, unmount } = renderHook(() => useRoomSession("room-1", api));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(MockWebSocket.instances[0]?.url).toContain("after_sequence=7");
    expect(MockWebSocket.instances[0]?.url).not.toContain("token");
    await waitFor(() => expect(result.current.snapshot?.phase).toBe("night_seer"));

    act(unmount);
  });
});
