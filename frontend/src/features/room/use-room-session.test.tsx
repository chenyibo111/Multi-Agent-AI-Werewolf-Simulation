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

  it("resumes a running room that has no available human action after a restart", async () => {
    vi.stubGlobal("WebSocket", MockWebSocket);
    const stalled: RoomPayload = {
      ...payload,
      state: { ...payload.state, phase: "day_discussion", waiting_for_human: false, human_actions: [], view_mode: "spectating" },
    };
    const resumed: RoomPayload = {
      ...stalled,
      state: { ...stalled.state, phase: "day_vote" },
    };
    const api = {
      getRoom: vi.fn().mockResolvedValue(stalled),
      continueRoom: vi.fn().mockResolvedValue(resumed),
      submitCommand: vi.fn(),
    } as unknown as ApiClient;

    const { result, unmount } = renderHook(() => useRoomSession("room-1", api));

    await waitFor(() => expect(api.continueRoom).toHaveBeenCalledWith("room-1"));
    expect(result.current.snapshot?.phase).toBe("day_vote");

    act(unmount);
  });

  it("reloads globally visible history when automatic continuation turns the player into a spectator", async () => {
    vi.stubGlobal("WebSocket", MockWebSocket);
    const pendingAutomaticWork: RoomPayload = {
      ...payload,
      state: { ...payload.state, phase: "day_discussion", waiting_for_human: false, human_actions: [] },
    };
    const spectatorDelta: RoomPayload = {
      state: { ...pendingAutomaticWork.state, view_mode: "spectating" },
      events: [{ sequence: 9, event_type: "night_announcement", payload: { death_ids: ["human"] }, visibility: "public" }],
    };
    const globalHistory: RoomPayload = {
      state: spectatorDelta.state,
      events: [
        { sequence: 3, event_type: "inspection_result", payload: { target_id: "ai-1", is_wolf: true }, visibility: "private" },
        ...payload.events,
        ...spectatorDelta.events,
      ],
    };
    const api = {
      getRoom: vi.fn().mockResolvedValueOnce(pendingAutomaticWork).mockResolvedValueOnce(globalHistory),
      continueRoom: vi.fn().mockResolvedValue(spectatorDelta),
      submitCommand: vi.fn(),
    } as unknown as ApiClient;

    const { result, unmount } = renderHook(() => useRoomSession("room-1", api));

    await waitFor(() => expect(result.current.snapshot?.view_mode).toBe("spectating"));
    expect(result.current.events.map((event) => event.sequence)).toEqual([3, 7, 9]);

    act(unmount);
  });

  it("reloads globally visible history when a submitted action turns the player into a spectator", async () => {
    vi.stubGlobal("WebSocket", MockWebSocket);
    const spectatorDelta: RoomPayload = {
      state: {
        ...payload.state,
        phase: "day_discussion",
        waiting_for_human: false,
        human_actions: [],
        view_mode: "spectating",
      },
      events: [{ sequence: 9, event_type: "night_announcement", payload: { death_ids: ["human"] }, visibility: "public" }],
    };
    const globalHistory: RoomPayload = {
      state: spectatorDelta.state,
      events: [
        { sequence: 3, event_type: "inspection_result", payload: { target_id: "ai-1", is_wolf: true }, visibility: "private" },
        ...payload.events,
        ...spectatorDelta.events,
      ],
    };
    const api = {
      getRoom: vi.fn().mockResolvedValueOnce(payload).mockResolvedValueOnce(globalHistory),
      continueRoom: vi.fn(),
      submitCommand: vi.fn().mockResolvedValue(spectatorDelta),
    } as unknown as ApiClient;

    const { result, unmount } = renderHook(() => useRoomSession("room-1", api));
    await waitFor(() => expect(result.current.snapshot?.view_mode).toBe("active"));

    await act(async () => {
      await result.current.submitCommand({ kind: "inspect", target_id: "ai-1" });
    });

    await waitFor(() => expect(result.current.snapshot?.view_mode).toBe("spectating"));
    expect(result.current.events.map((event) => event.sequence)).toEqual([3, 7, 9]);
    expect(result.current.events[0]).toMatchObject({
      event_type: "inspection_result",
      visibility: "private",
    });

    act(unmount);
  });
});
