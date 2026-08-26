import { describe, expect, it } from "vitest";

import { mergeRoomEvents } from "./event-store";

const event = (sequence: number) => ({
  sequence,
  event_type: "phase_changed",
  payload: { phase: "night_seer" },
  visibility: "public" as const,
});

describe("mergeRoomEvents", () => {
  it("keeps one ordered copy when REST and socket carry the same event", () => {
    expect(mergeRoomEvents([event(4)], [event(3), event(4)])).toEqual([event(3), event(4)]);
  });
});
