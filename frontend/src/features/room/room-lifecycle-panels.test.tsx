import { render, screen, within } from "@testing-library/react";
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
    expect(screen.getByText("AI 玩家 1 · 狼人")).toBeVisible();
  });

  it("renders the complete safe event timeline from a finished report", () => {
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

    expect(within(container).getByRole("heading", { name: "完整事件时间线" })).toBeVisible();
    expect(within(container).getByText("查验结果：林小雨 是狼人。")).toBeVisible();
    expect(within(container).queryByText("must-not-render")).not.toBeInTheDocument();
  });
});
