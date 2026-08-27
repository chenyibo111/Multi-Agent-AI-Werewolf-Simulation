import { render, screen } from "@testing-library/react";
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
    render(<FinishedReport report={{ winner_faction: "villager", participants: { "ai-1": { participant_id: "ai-1", display_name: "AI 玩家 1", alive: false, role_id: "wolf" } }, events: [] }} />);

    expect(screen.getByText("完整复盘")).toBeVisible();
    expect(screen.getByText("AI 玩家 1 · wolf")).toBeVisible();
  });
});
