import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RoomSnapshot } from "../../lib/types";
import { ActionPanel } from "./ActionPanel";
import { RoomTimeline } from "./RoomTimeline";

const waitingSeerState: RoomSnapshot = {
  game_id: "room-1",
  phase: "night_seer",
  status: "running",
  round_number: 1,
  participants: {
    human: { participant_id: "human", display_name: "你", alive: true, role_id: "seer" },
    "ai-1": { participant_id: "ai-1", display_name: "AI 玩家 1", alive: true },
  },
  waiting_for_human: true,
  human_actions: ["inspect"],
  legal_target_ids: ["ai-1"],
  phase_text: "预言家查验",
  view_mode: "active",
};

describe("ActionPanel", () => {
  it("renders only server-provided targets and submits the selected legal action", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(undefined);
    render(<ActionPanel state={waitingSeerState} onSubmit={submit} pending={false} />);

    await user.click(screen.getByRole("button", { name: "AI 玩家 1" }));
    await user.click(screen.getByRole("button", { name: "确认查验" }));

    expect(screen.queryByRole("button", { name: "隐藏玩家" })).not.toBeInTheDocument();
    expect(submit).toHaveBeenCalledWith({ kind: "inspect", target_id: "ai-1" });
  });
});

describe("RoomTimeline", () => {
  it("renders unknown events as a safe generic line instead of serializing payload fields", () => {
    render(
      <RoomTimeline
        events={[
          {
            sequence: 3,
            event_type: "unrecognized",
            payload: { agent_memory: "never render", secret: "never render" },
            visibility: "public",
          },
        ]}
      />,
    );

    expect(screen.getByText("对局状态已更新。")) .toBeVisible();
    expect(document.body.textContent).not.toContain("agent_memory");
    expect(document.body.textContent).not.toContain("never render");
  });
});
