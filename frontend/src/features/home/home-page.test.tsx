import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../lib/api-client";
import { loadRoomHistory, rememberRoom } from "../history/room-history";
import { HomePage } from "./HomePage";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("HomePage", () => {
  it("creates a selected-role room and navigates without storing a session token", async () => {
    const user = userEvent.setup();
    const api = {
      createRoom: vi.fn().mockResolvedValue({ roomId: "room-1", state: {}, events: [] }),
    } as unknown as ApiClient;
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<HomePage apiClient={api} />} />
          <Route path="/rooms/:roomId" element={<div>room loaded</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText("选择身份"), "seer");
    await user.click(screen.getByRole("button", { name: "开始对局" }));

    expect(api.createRoom).toHaveBeenCalledWith("seer");
    expect(screen.getByText("room loaded")).toBeVisible();
    expect(loadRoomHistory()).toEqual([expect.objectContaining({ roomId: "room-1" })]);
    expect(window.localStorage.getItem("session_token")).toBeNull();
  });

  it("shows an authorized room and removes it from local history after confirmed deletion", async () => {
    const user = userEvent.setup();
    rememberRoom({ roomId: "room-1", openedAt: "2026-08-27T10:00:00.000Z" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = {
      getRoom: vi.fn().mockResolvedValue({
        state: {
          game_id: "room-1", phase: "day_vote", status: "running", round_number: 2,
          participants: {}, waiting_for_human: true, human_actions: ["vote"], legal_target_ids: ["ai-1"],
          phase_text: "白天投票", view_mode: "active",
        },
        events: [],
      }),
      deleteRoom: vi.fn().mockResolvedValue(undefined),
    } as unknown as ApiClient;
    render(<MemoryRouter><HomePage apiClient={api} /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "继续对局" })).toBeVisible();
    expect(screen.getByText("白天投票")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "删除对局" }));

    expect(api.deleteRoom).toHaveBeenCalledWith("room-1");
    expect(loadRoomHistory()).toEqual([]);
    expect(screen.getByText("暂无本地对局记录")).toBeVisible();
  });
});
