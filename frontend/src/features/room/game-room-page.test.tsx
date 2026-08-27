import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RoomSnapshot } from "../../lib/types";
import { ActionPanel } from "./ActionPanel";
import { PrivatePanel } from "./PrivatePanel";
import { PlayerRail } from "./PlayerRail";
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
  it("renders internal phase changes as Chinese stage names", () => {
    render(
      <RoomTimeline
        events={[{ sequence: 2, event_type: "phase_changed", payload: { phase: "night_seer" }, visibility: "public" }]}
      />,
    );

    expect(screen.getByText("阶段切换：预言家查验阶段")).toBeVisible();
  });

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

  it("renders witch target and action-result events with player names", () => {
    render(
      <RoomTimeline
        participants={{ "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: true } }}
        events={[
          {
            sequence: 3,
            event_type: "witch_night_target",
            payload: { target_id: "ai-1" },
            visibility: "private",
          },
          {
            sequence: 4,
            event_type: "witch_action_result",
            payload: {
              saved_target_id: "ai-1",
              poisoned_target_id: null,
              antidote_available: false,
              poison_available: true,
              secret: "never render",
            },
            visibility: "private",
          },
        ]}
      />,
    );

    expect(screen.getByText("女巫得知：今晚被袭击的是林小雨。")) .toBeVisible();
    expect(screen.getByText("女巫行动：救下林小雨；解药已用，毒药可用。")) .toBeVisible();
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

  it("renders the public vote breakdown with display names and abstentions", () => {
    render(
      <RoomTimeline
        participants={{
          "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: true },
          "ai-2": { participant_id: "ai-2", display_name: "周子墨", alive: true },
          "ai-3": { participant_id: "ai-3", display_name: "陈星河", alive: true },
        }}
        events={[
          {
            sequence: 3,
            event_type: "vote_result",
            payload: { votes: [{ actor_id: "ai-1", target_id: "ai-2" }, { actor_id: "ai-3", target_id: null }] },
            visibility: "public",
          },
        ]}
      />,
    );

    expect(screen.getByText("投票结果：林小雨 → 周子墨；陈星河 → 弃权。")) .toBeVisible();
  });

  it("falls back to an unknown vote target ID without rendering extra payload fields", () => {
    render(
      <RoomTimeline
        participants={{ "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: true } }}
        events={[
          {
            sequence: 4,
            event_type: "vote_result",
            payload: { votes: [{ actor_id: "ai-1", target_id: "missing-id", secret: "never render" }] },
            visibility: "public",
          },
        ]}
      />,
    );

    expect(screen.getByText("投票结果：林小雨 → missing-id。")) .toBeVisible();
    expect(document.body.textContent).not.toContain("never render");
  });

  it("renders a private wolf teammate suggestion with display names", () => {
    render(
      <RoomTimeline
        participants={{
          human: { participant_id: "human", display_name: "你", alive: true },
          "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: true },
          "ai-2": { participant_id: "ai-2", display_name: "周子墨", alive: true },
        }}
        events={[
          {
            sequence: 5,
            event_type: "wolf_team_suggestion",
            payload: { actor_id: "ai-1", target_id: "ai-2", message: "今晚先从周子墨开始。" },
            visibility: "private",
          },
        ]}
      />,
    );

    expect(screen.getByText("狼人同伴 林小雨 建议击杀 周子墨：今晚先从周子墨开始。")) .toBeVisible();
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

describe("PrivatePanel", () => {
  it("renders the active player's role in Chinese", () => {
    render(<PrivatePanel state={waitingSeerState} />);

    expect(screen.getByText("预言家")).toBeVisible();
  });

  it("shows an active wolf their living teammate", () => {
    render(<PrivatePanel state={{ ...waitingSeerState, participants: { ...waitingSeerState.participants, human: { participant_id: "human", display_name: "你", alive: true, role_id: "wolf" } }, wolf_teammates: [{ participant_id: "ai-1", display_name: "林小雨", seat_number: 2, alive: true }] }} />);

    expect(screen.getByText("你的狼人同伴：2号 林小雨")).toBeVisible();
  });

  it("shows a witch their current antidote and poison availability", () => {
    render(<PrivatePanel state={{
      ...waitingSeerState,
      participants: {
        ...waitingSeerState.participants,
        human: {
          participant_id: "human",
          display_name: "你",
          alive: true,
          role_id: "witch",
          private_state: { antidote_available: true, poison_available: false },
        },
      },
    }} />);

    expect(screen.getByText("解药：可用；毒药：已用")).toBeVisible();
  });
});

describe("PlayerRail", () => {
  it("shows explicit life status and Chinese labels only for authorized roles", () => {
    render(<PlayerRail state={{ ...waitingSeerState, participants: {
      "ai-1": { participant_id: "ai-1", display_name: "林小雨", seat_number: 4, alive: true, role_id: "witch" },
      "ai-2": { participant_id: "ai-2", display_name: "周子墨", seat_number: 5, alive: false },
    } }} />);

    expect(screen.getByText("4号 林小雨")).toBeVisible();
    expect(screen.getByText("存活")).toBeVisible();
    expect(screen.getByText("已出局")).toBeVisible();
    expect(screen.getByText("女巫")).toBeVisible();
    expect(screen.queryByText("狼人")).not.toBeInTheDocument();
  });
});
