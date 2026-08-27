import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(cleanup);

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

  it("submits the server-fixed antidote target without offering a target picker", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(undefined);
    const witchState: RoomSnapshot = {
      ...waitingSeerState,
      phase: "night_witch",
      human_actions: ["witch_save", "witch_poison", "noop"],
      fixed_target_ids: { witch_save: "ai-1" },
      legal_target_ids: ["ai-1"],
      participants: {
        ...waitingSeerState.participants,
        "ai-1": { participant_id: "ai-1", display_name: "AI 玩家 1", alive: true },
      },
    };
    render(<ActionPanel state={witchState} onSubmit={submit} pending={false} />);

    expect(screen.getByText("今晚被袭击：AI 玩家 1")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "确认使用解药" }));

    expect(submit).toHaveBeenCalledWith({ kind: "witch_save", target_id: "ai-1" });
  });
});

describe("RoomTimeline", () => {
  it("renders a private seer inspection result without exposing unrelated payload fields", () => {
    render(
      <RoomTimeline
        events={[
          {
            sequence: 3,
            event_type: "inspection_result",
            payload: { target_id: "ai-2", is_wolf: true, secret: "never render" },
            visibility: "private",
          },
        ]}
      />,
    );

    expect(screen.getByText("查验结果：ai-2 是狼人。")) .toBeVisible();
    expect(document.body.textContent).not.toContain("never render");
  });

  it("names the players who died in a public dawn announcement", () => {
    render(
      <RoomTimeline
        events={[
          {
            sequence: 3,
            event_type: "night_announcement",
            payload: { death_count: 2, death_ids: ["ai-1", "ai-2"] },
            visibility: "public",
          },
        ]}
      />,
    );

    expect(screen.getByText("天亮了，昨夜 ai-1、ai-2 出局。")) .toBeVisible();
  });

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
