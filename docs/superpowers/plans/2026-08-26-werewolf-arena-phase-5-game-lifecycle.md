# Phase 5 Game Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a local browser safely resume, observe, replay, and delete its own Werewolf Arena rooms.

**Architecture:** Keep browser history as a non-sensitive local room-ID index and retain room-scoped cookies as the only authority. REST and WebSocket room snapshots stay privacy-filtered during play; a new finished-only report route projects final roles and non-server events separately. React renders history, spectator state, and final replay strictly from those server projections.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy/aiosqlite, Pydantic, React 19, TypeScript, Vite, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-26-werewolf-arena-phase-5-game-lifecycle-design.md`

## Global Constraints

- Keep the product to one local human plus five AI players; do not add accounts, device identities, cloud deployment, multiplayer, or a rule editor.
- Browser history must never persist a session token, role-private state, event payload, model output, prompt, key, or chain of thought.
- Room cookies/Bearer tokens remain the only authorization mechanism; never add a global room-enumeration endpoint.
- Live room snapshots and WebSocket events must never disclose other players' roles or private events after human death or before completion.
- Full report data is available only to an authorized room session after `finished` and excludes server-only events and forbidden payload fields.
- Write a failing automated test before every production behavior change; run the focused test red, then green, before proceeding.

---

### Task 1: Separate finished reports from live room projections

**Files:**
- Modify: `backend/src/werewolf_arena/api/dependencies.py`
- Modify: `backend/src/werewolf_arena/api/routes/rooms.py`
- Modify: `backend/src/werewolf_arena/domain/projection.py`
- Modify: `backend/tests/domain/test_projection.py`
- Modify: `backend/tests/api/test_rooms.py`

**Interfaces:**
- Consumes: `AuthorizedRoom.viewer`, `project_state()`, and `project_events()`.
- Produces: `project_finished_report(state: GameState) -> dict[str, object]` and `GET /api/rooms/{room_id}/report`.

- [ ] **Step 1: Write the failing projection and route tests**

```python
def test_finished_room_snapshot_keeps_other_roles_outside_the_report() -> None:
    state = finished_state_with_private_event()
    snapshot = project_state(state, ViewerContext("human", ViewerKind.ALIVE_HUMAN))
    report = project_finished_report(state)

    assert "role_id" not in snapshot["participants"]["ai-1"]
    assert report["participants"]["ai-1"]["role_id"] == "wolf"
    assert all(event["visibility"] != "server" for event in report["events"])

def test_finished_report_requires_room_session_and_rejects_running_rooms(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "arena.db")
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={}).json()
        response = client.get(f"/api/rooms/{created['room_id']}/report")
    assert response.status_code == 409
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend; uv run pytest tests/domain/test_projection.py tests/api/test_rooms.py -q`  
Expected: FAIL because `project_finished_report` and `/report` do not exist, or because a live finished snapshot exposes other roles.

- [ ] **Step 3: Implement the minimal projection boundary**

```python
def viewer_for_participant(state: GameState, participant: Participant) -> ViewerContext:
    kind = ViewerKind.ALIVE_HUMAN if participant.alive else ViewerKind.DEAD_SPECTATOR
    return ViewerContext(participant.participant_id, kind)

def project_finished_report(state: GameState) -> dict[str, object]:
    viewer = ViewerContext("finished-report", ViewerKind.FINISHED_REPLAY)
    return {
        "winner_faction": state.winner_faction.value if state.winner_faction else None,
        "participants": project_state(state, viewer)["participants"],
        "events": project_events(state.events, viewer, state),
    }
```

Add an authenticated report handler in `rooms.py`. It returns HTTP 409 while running. It uses `_safe_payload()` and excludes `Visibility.SERVER`; it does not feed report data into `_state_view()` or the WebSocket route.

- [ ] **Step 4: Run focused tests and the backend projection/API suite**

Run: `cd backend; uv run pytest tests/domain/test_projection.py tests/api/test_rooms.py tests/api/test_events.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/api/dependencies.py backend/src/werewolf_arena/api/routes/rooms.py backend/src/werewolf_arena/domain/projection.py backend/tests/domain/test_projection.py backend/tests/api/test_rooms.py
git commit -m "feat: add finished room reports"
```

### Task 2: Verify deletion and spectator lifecycle contracts

**Files:**
- Modify: `backend/src/werewolf_arena/persistence/repository.py`
- Modify: `backend/src/werewolf_arena/api/routes/rooms.py`
- Modify: `backend/tests/persistence/test_repository.py`
- Modify: `backend/tests/api/test_rooms.py`
- Modify: `backend/tests/api/test_events.py`

**Interfaces:**
- Consumes: `SQLiteRoomRepository.delete_room()`, `RoomRuntimeRegistry.remove()`, and `ViewerKind.DEAD_SPECTATOR`.
- Produces: `room_exists(room_id: UUID) -> bool` and a safe `RoomSnapshot.view_mode`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
async def scenario() -> None:
    await repository.delete_room(room_id)
    assert await repository.room_exists(room_id) is False
    assert await repository.events_after(room_id, 0) == ()
    assert await repository.agent_runs_for(room_id) == ()

def test_dead_spectator_snapshot_has_no_private_action_or_state(tmp_path) -> None:
    response = authenticated_dead_human_room(client)
    state = response.json()["state"]
    assert state["view_mode"] == "spectating"
    assert state["human_actions"] == []
    assert state["legal_target_ids"] == []
    assert "private_state" not in state["participants"]["human"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend; uv run pytest tests/persistence/test_repository.py tests/api/test_rooms.py tests/api/test_events.py -q`  
Expected: FAIL because the safe `view_mode`, deterministic delete assertion, or room-existence helper is absent.

- [ ] **Step 3: Implement only the tested lifecycle behavior**

Add `room_exists()` using `select(RoomRow.room_id)`. In `_state_view()`, set `view_mode` to `"finished"` when the game is finished, `"spectating"` for `DEAD_SPECTATOR`, otherwise `"active"`; force empty waiting/actions/targets outside active play. Preserve the existing delete endpoint, repository transaction, and registry removal.

- [ ] **Step 4: Run focused tests and all backend tests**

Run: `cd backend; uv run pytest -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/api/routes/rooms.py backend/src/werewolf_arena/persistence/repository.py backend/tests/persistence/test_repository.py backend/tests/api/test_rooms.py backend/tests/api/test_events.py
git commit -m "feat: harden spectator and room deletion lifecycle"
```

### Task 3: Add browser-safe history storage and report API support

**Files:**
- Create: `frontend/src/features/history/room-history.ts`
- Create: `frontend/src/features/history/room-history.test.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/api-client.test.ts`

**Interfaces:**
- Consumes: `RoomPayload`, `RoomSnapshot`, and browser `localStorage`.
- Produces: `RoomHistoryEntry`, `loadRoomHistory()`, `rememberRoom()`, `removeRoom()`, `ApiClient.getReport()`, and `ApiClient.deleteRoom()`.

- [ ] **Step 1: Write failing storage and API-client tests**

```ts
it("stores only non-sensitive room history metadata", () => {
  rememberRoom({ roomId: "room-1", openedAt: "2026-08-26T00:00:00.000Z" });
  expect(loadRoomHistory()).toEqual([{ roomId: "room-1", openedAt: "2026-08-26T00:00:00.000Z" }]);
  expect(localStorage.getItem("werewolf-arena-room-history")).not.toContain("session_token");
});

it("requests a finished report and deletes with cookies", async () => {
  await api.getReport("room-1");
  await api.deleteRoom("room-1");
  expect(fetch).toHaveBeenNthCalledWith(1, "/api/rooms/room-1/report", expect.objectContaining({ credentials: "include" }));
  expect(fetch).toHaveBeenNthCalledWith(2, "/api/rooms/room-1", expect.objectContaining({ method: "DELETE" }));
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd frontend; npm run test -- --run src/features/history/room-history.test.ts src/lib/api-client.test.ts`  
Expected: FAIL because storage functions and report/delete methods do not exist.

- [ ] **Step 3: Implement typed client and history primitives**

```ts
export type RoomHistoryEntry = { roomId: string; openedAt: string };
const storageKey = "werewolf-arena-room-history";

function persist(entries: RoomHistoryEntry[]): void {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

export function rememberRoom(entry: RoomHistoryEntry): void {
  persist([entry, ...loadRoomHistory().filter((item) => item.roomId !== entry.roomId)]);
}

export function loadRoomHistory(): RoomHistoryEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isRoomHistoryEntry) : [];
  } catch { return []; }
}

export function removeRoom(roomId: string): void {
  persist(loadRoomHistory().filter((item) => item.roomId !== roomId));
}
```

Extend `RoomSnapshot` with `view_mode: "active" | "spectating" | "finished"`, add a `RoomReport` type, add a no-content request helper, and retain `credentials: "include"` on every request.

- [ ] **Step 4: Run focused tests and type checking**

Run: `cd frontend; npm run test -- --run src/features/history/room-history.test.ts src/lib/api-client.test.ts; npm run typecheck`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/features/history/room-history.ts frontend/src/features/history/room-history.test.ts frontend/src/lib/types.ts frontend/src/lib/api-client.ts frontend/src/lib/api-client.test.ts
git commit -m "feat: add local room history primitives"
```

### Task 4: Build the home history and deletion experience

**Files:**
- Create: `frontend/src/features/history/RoomHistoryList.tsx`
- Create: `frontend/src/features/history/room-history-list.test.tsx`
- Modify: `frontend/src/features/home/HomePage.tsx`
- Modify: `frontend/src/features/home/home-page.test.tsx`
- Modify: `frontend/src/styles/global.css`

**Interfaces:**
- Consumes: `loadRoomHistory()`, `removeRoom()`, `ApiClient.getRoom()`, `ApiClient.deleteRoom()`.
- Produces: authorized active/finished history cards and a confirmed delete flow.

- [ ] **Step 1: Write failing UI tests**

```tsx
it("shows only successfully authorized historical room details", async () => {
  api.getRoom.mockResolvedValueOnce(activePayload).mockRejectedValueOnce(new ApiRequestError("Invalid room session"));
  render(<HomePage apiClient={api} />);
  expect(await screen.findByText("继续对局")).toBeVisible();
  expect(screen.queryByText("Invalid room session")).not.toBeInTheDocument();
});

it("confirms deletion before removing the server room and local entry", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  await user.click(screen.getByRole("button", { name: "删除对局" }));
  expect(api.deleteRoom).toHaveBeenCalledWith("room-1");
  expect(loadRoomHistory()).toEqual([]);
});
```

- [ ] **Step 2: Run focused UI tests and verify RED**

Run: `cd frontend; npm run test -- --run src/features/home/home-page.test.tsx src/features/history/room-history-list.test.tsx`  
Expected: FAIL because no history list or confirmed deletion behavior exists.

- [ ] **Step 3: Implement authorized room cards**

Use `useEffect` to refresh only locally indexed room IDs. Render active rooms under “继续对局”, finished rooms under “历史对局”, and inaccessible records as a generic removable card without state/role/event data. Creating a room must call `rememberRoom({ roomId, openedAt: new Date().toISOString() })`; remove the legacy single-room storage key. Call `window.confirm("确定删除这局对局吗？")` before invoking `deleteRoom`.

- [ ] **Step 4: Run focused UI tests and all frontend unit tests**

Run: `cd frontend; npm run test -- --run`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/features/history/RoomHistoryList.tsx frontend/src/features/history/room-history-list.test.tsx frontend/src/features/home/HomePage.tsx frontend/src/features/home/home-page.test.tsx frontend/src/styles/global.css
git commit -m "feat: add local room history management"
```

### Task 5: Render spectator state and finished reports in the room

**Files:**
- Create: `frontend/src/features/room/SpectatorPanel.tsx`
- Create: `frontend/src/features/room/FinishedReport.tsx`
- Modify: `frontend/src/features/room/GameRoomPage.tsx`
- Modify: `frontend/src/features/room/PrivatePanel.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`
- Modify: `frontend/src/features/room/room.css`

**Interfaces:**
- Consumes: `RoomSnapshot.view_mode`, `ApiClient.getReport()`, `RoomReport`, and `useRoomSession()`.
- Produces: no private/action UI in spectator mode and an authorized finished-only replay panel.

- [ ] **Step 1: Write failing room UI tests**

```tsx
it("renders a public-only spectator panel without private role or actions", () => {
  render(<GameRoomPage roomId="room-1" apiClient={apiFor(spectatingPayload)} />);
  expect(screen.getByText("你已出局，正在旁观公开对局。")).toBeVisible();
  expect(screen.queryByText("你的身份")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /确认|投票|跳过/ })).not.toBeInTheDocument();
});

it("loads all identities only after the room is finished", async () => {
  render(<GameRoomPage roomId="room-1" apiClient={apiFor(finishedPayload, report)} />);
  expect(await screen.findByText("完整复盘")).toBeVisible();
  expect(api.getReport).toHaveBeenCalledWith("room-1");
});
```

- [ ] **Step 2: Run focused room tests and verify RED**

Run: `cd frontend; npm run test -- --run src/features/room/game-room-page.test.tsx`  
Expected: FAIL because spectator and report components do not exist.

- [ ] **Step 3: Implement view-mode gated panels**

Render `PrivatePanel` and `ActionPanel` only for `view_mode === "active"`. Render `SpectatorPanel` for `"spectating"`. When `status === "finished"`, fetch `getReport(roomId)` once, render `FinishedReport`, and show retryable non-sensitive errors if the report request fails. `FinishedReport` renders only the safe report response, including final role IDs and event text; it never stringifies unknown payloads.

- [ ] **Step 4: Run room tests, all frontend unit tests, typecheck, and build**

Run: `cd frontend; npm run test -- --run; npm run typecheck; npm run build`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/features/room/SpectatorPanel.tsx frontend/src/features/room/FinishedReport.tsx frontend/src/features/room/GameRoomPage.tsx frontend/src/features/room/PrivatePanel.tsx frontend/src/features/room/game-room-page.test.tsx frontend/src/features/room/room.css
git commit -m "feat: add spectator and finished replay views"
```

### Task 6: Add lifecycle browser coverage and update local usage docs

**Files:**
- Modify: `frontend/e2e/game-room.spec.ts`
- Modify: `frontend/scripts/start-e2e-backend.py`
- Modify: `README.md`
- Modify: `backend/README.md`

**Interfaces:**
- Consumes: offline scripted AI server, history UI, completed report, delete endpoint.
- Produces: a deterministic browser lifecycle test and accurate Phase 5 local instructions.

- [ ] **Step 1: Write the failing browser scenario**

```ts
test("a completed local room can be replayed and deleted without private AI data", async ({ page }) => {
  await page.goto("/");
  await createDeterministicRoomThatFinishes(page);
  await expect(page.getByText("完整复盘")).toBeVisible();
  await expect(page.getByText("AI 玩家 1")).toBeVisible();
  await page.getByRole("button", { name: "返回历史" }).click();
  await page.getByRole("button", { name: "删除对局" }).click();
  await expect(page.getByText("暂无本地对局记录")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("agent_memory");
});
```

- [ ] **Step 2: Run the Playwright test and verify RED**

Run: `cd frontend; npm run test:e2e -- --grep "replayed and deleted"`  
Expected: FAIL because the lifecycle UI and deterministic completion script are not implemented.

- [ ] **Step 3: Add deterministic completion support and document it**

Make `ScriptedRoomClient` choose valid non-human targets, complete discussion/votes, and avoid external LLM calls. Update the root README to mark Phase 4 as complete and Phase 5 as lifecycle work; document local history, report, and delete behavior in the backend README.

- [ ] **Step 4: Run browser coverage and all project verification**

```powershell
cd frontend
npm run test -- --run
npm run typecheck
npm run build
npm run test:e2e
cd ../backend
uv run pytest -q
uv run ruff check .
uv run mypy src
```

Expected: every command passes; browser output has no private-field warning and local test servers are stopped afterward.

- [ ] **Step 5: Commit**

```powershell
git add frontend/e2e/game-room.spec.ts frontend/scripts/start-e2e-backend.py README.md backend/README.md
git commit -m "test: cover room lifecycle in browser"
```

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 enforce report-only finished visibility, safe spectator projection, and transactional deletion; Tasks 3–4 implement browser-local history and confirmed deletion; Task 5 renders spectator and replay experiences; Task 6 provides browser coverage and updates documentation.
- **Completeness scan:** Every task names exact files, public interfaces, failing-test commands, minimal implementation direction, verification, and commit scope.
- **Type consistency:** `RoomSnapshot.view_mode` originates in `_state_view()`, flows through `RoomPayload`, and gates `GameRoomPage`. `RoomReport` originates at the report endpoint and is consumed solely by `ApiClient.getReport()` and `FinishedReport`.
