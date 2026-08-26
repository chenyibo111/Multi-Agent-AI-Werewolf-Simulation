import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../lib/api-client";
import { HomePage } from "./HomePage";

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
    expect(window.localStorage.getItem("werewolf-arena-room-id")).toBe("room-1");
    expect(window.localStorage.getItem("session_token")).toBeNull();
  });
});
