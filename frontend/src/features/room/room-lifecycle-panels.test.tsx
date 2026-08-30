import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FinishedReport } from "./FinishedReport";
import { SpectatorPanel } from "./SpectatorPanel";

describe("room lifecycle panels", () => {
  it("labels a dead player as a global-view spectator", () => {
    render(<SpectatorPanel />);

    expect(screen.getByText("你已出局，正在以全局视角旁观对局。")).toBeVisible();
    expect(screen.queryByText("你的身份")).not.toBeInTheDocument();
  });

  it("renders revealed roles from the safe finished report", () => {
    render(<FinishedReport report={{ winner_faction: "wolf", participants: { "ai-1": { participant_id: "ai-1", display_name: "AI 玩家 1", alive: false, role_id: "wolf" } }, events: [] }} />);

    expect(screen.getByText("完整复盘")).toBeVisible();
    expect(screen.getByText("狼人阵营获胜")).toBeVisible();
    expect(screen.getByText("AI 玩家 1 · 狼人 · 已出局")).toBeVisible();
  });

  it("reveals the complete safe event timeline on demand from a finished report", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <FinishedReport
        report={{
          winner_faction: "villager",
          participants: {
            "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: false, role_id: "wolf" },
          },
          events: [
            {
              sequence: 3,
              event_type: "inspection_result",
              payload: { target_id: "ai-1", is_wolf: true, server_secret: "must-not-render" },
              visibility: "private",
            },
          ],
        }}
      />,
    );

    expect(within(container).getByText("查看完整事件时间线")).toBeVisible();
    await user.click(within(container).getByText("查看完整事件时间线"));
    expect(within(container).getByRole("heading", { name: "完整事件时间线" })).toBeVisible();
    expect(within(container).getByText("查验结果：林小雨 是狼人。")).toBeVisible();
    expect(within(container).queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("organizes the finished report into night and day recap blocks before the detailed audit", () => {
    const { container } = render(
      <FinishedReport
        report={{
          winner_faction: "good",
          participants: {
            human: { participant_id: "human", display_name: "你", alive: true, role_id: "seer" },
            "ai-1": { participant_id: "ai-1", display_name: "林小雨", alive: false, role_id: "wolf" },
          },
          events: [
            { sequence: 2, event_type: "phase_changed", payload: { phase: "night_wolf" }, visibility: "public" },
            { sequence: 3, event_type: "night_announcement", payload: { death_ids: [] }, visibility: "public" },
            { sequence: 4, event_type: "phase_changed", payload: { phase: "day_discussion" }, visibility: "public" },
            { sequence: 5, event_type: "public_speech", payload: { actor_id: "human", text: "我先听听大家的看法。" }, visibility: "public" },
            { sequence: 6, event_type: "phase_changed", payload: { phase: "day_vote" }, visibility: "public" },
            { sequence: 7, event_type: "execution", payload: { target_id: "ai-1" }, visibility: "public" },
            { sequence: 8, event_type: "phase_changed", payload: { phase: "night_wolf" }, visibility: "public" },
            { sequence: 9, event_type: "game_finished", payload: { winner_faction: "good" }, visibility: "public" },
          ],
        }}
      />,
    );

    const recap = within(screen.getByLabelText("按回合复盘"));
    expect(recap.getByRole("heading", { name: "第 1 夜" })).toBeVisible();
    expect(recap.getByRole("heading", { name: "第 1 天" })).toBeVisible();
    expect(recap.queryByRole("heading", { name: "第 2 夜" })).not.toBeInTheDocument();
    expect(recap.getByText("平安夜，昨夜无人出局。")).toBeVisible();
    expect(recap.getByText("林小雨 被放逐出局。")).toBeVisible();
    expect(within(container).getByText("查看完整事件时间线")).toBeVisible();
  });
});
