# Werewolf Arena Phase 4 Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a local, browser-playable React interface for one human and five AI Werewolf Arena players.

**Architecture:** `frontend/` is a Vite React TypeScript application. It reads only the projected FastAPI REST/WebSocket payloads through an `ApiClient` and a `useRoomSession` coordinator, which owns sequence deduplication and reconnect state. FastAPI continues to own rules and session cookies, and serves a built SPA when `frontend/dist` exists.

**Tech Stack:** React 19, TypeScript, Vite, React Router, Vitest, Testing Library, Playwright, FastAPI, pytest, uvicorn.

**Spec:** `docs/superpowers/specs/2026-08-26-werewolf-arena-phase-4-web-ui-design.md`

## Global Constraints

- All browser requests use `credentials: "include"`; never read or store `session_token`.
- Render only projected REST and WebSocket fields; never reconstruct rules or expose Agent memory, raw prompts, raw output, API keys, or authority state.
- `waiting_for_human`, `human_actions`, `legal_target_ids`, and `phase_text` are the sole sources for player controls.
- REST and WebSocket events are deduplicated by monotonic `sequence` before rendering.
- The WebSocket reconnect URL must include only `after_sequence`; credentials are supplied by the room-scoped HttpOnly cookie.
- Keep the chosen A layout: central narrative timeline plus a persistent right-side private/action panel, with moonlit dark visual styling.
- FastAPI must start normally when no `frontend/dist` directory exists.
- Frontend unit/e2e tests use local mocks and never call a real LLM endpoint.
- Before every commit run the task’s focused tests; before the final commit run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`, `npm run test`, `npm run build`, and `git diff --check`.

---

### Task 1: Scaffold the typed React application and safe REST client

**Files:**
- Create: `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/global.css`
- Create: `frontend/src/lib/types.ts`, `frontend/src/lib/api-client.ts`
- Create: `frontend/src/lib/api-client.test.ts`, `frontend/src/test/setup.ts`

**Interfaces:**
- Produces `ApiClient(baseUrl?: string)` with `createRoom(requestedRoleId?: string)`, `getRoom(roomId: string)`, `submitCommand(roomId: string, command: HumanCommand)`, and `continueRoom(roomId: string)`.
- Produces `RoomSnapshot`, `RoomEvent`, `RoomPayload`, `ProjectedParticipant`, and `HumanCommand` types with no authority-only fields.
- Consumes the existing `/api/rooms` contracts and returns parsed `RoomPayload` data with `credentials: "include"`.

- [ ] **Step 1: Write failing client tests**

```ts
it("creates a room with cookies but never reads session_token", async () => {
  global.fetch = vi.fn().mockResolvedValue(jsonResponse(createdRoomPayload));
  const payload = await new ApiClient("http://api.test").createRoom("seer");
  expect(fetch).toHaveBeenCalledWith(
    "http://api.test/api/rooms",
    expect.objectContaining({ credentials: "include", method: "POST" }),
  );
  expect(payload.state.phase).toBe("night_seer");
  expect(payload).not.toHaveProperty("session_token");
});

it("turns an API 422 into a user-safe request error", async () => {
  global.fetch = vi.fn().mockResolvedValue(jsonResponse({ detail: "wrong_phase" }, 422));
  await expect(new ApiClient().continueRoom("room-1")).rejects.toMatchObject({ message: "wrong_phase" });
});
```

- [ ] **Step 2: Run the focused test to confirm the missing frontend boundary**

Run: `npm run test -- --run src/lib/api-client.test.ts` from `frontend/`  
Expected: FAIL because the package and client modules do not yet exist.

- [ ] **Step 3: Add Vite/Vitest configuration, exact projected types, and the REST client**

```ts
export type RoomPayload = { state: RoomSnapshot; events: RoomEvent[] };

export class ApiClient {
  async submitCommand(roomId: string, command: HumanCommand): Promise<RoomPayload> {
    return this.request<RoomPayload>(`/api/rooms/${roomId}/commands`, {
      method: "POST",
      body: JSON.stringify(command),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (!response.ok) throw new ApiRequestError(await safeMessage(response));
    return stripCreateToken((await response.json()) as T & { session_token?: string });
  }
}
```

Use React Router with placeholder routes only; do not build gameplay components in this task. Configure Vite’s development proxy for `/api` and `/docs` to `http://127.0.0.1:8000` while retaining browser cookies.

- [ ] **Step 4: Run frontend type, unit, and build checks**

Run: `npm run test -- --run src/lib/api-client.test.ts; npm run typecheck; npm run build` from `frontend/`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend
git commit -m "feat: scaffold typed web client"
```

### Task 2: Add room-session coordination, event deduplication, and reconnect support

**Files:**
- Create: `frontend/src/features/room/event-store.ts`, `frontend/src/features/room/event-store.test.ts`
- Create: `frontend/src/features/room/use-room-session.ts`, `frontend/src/features/room/use-room-session.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces `mergeRoomEvents(current: RoomEvent[], incoming: RoomEvent[]): RoomEvent[]`, sorted and unique by `sequence`.
- Produces `useRoomSession(roomId: string, apiClient: ApiClient)` returning `{ snapshot, events, connection, error, refresh, continueRoom, submitCommand }`.
- Consumes `WebSocket`, `RoomPayload`, and `ApiClient`; never takes an actor ID, a raw token, or arbitrary target lists.

- [ ] **Step 1: Write failing event and hook tests**

```ts
it("keeps one ordered copy when REST and socket carry the same event", () => {
  expect(mergeRoomEvents([event(4)], [event(3), event(4)])).toEqual([event(3), event(4)]);
});

it("reconnects using only the latest event sequence", async () => {
  renderHook(() => useRoomSession("room-1", api));
  await waitFor(() => expect(WebSocket).toHaveBeenCalledWith(expect.stringContaining("after_sequence=7")));
  expect(String(mockWebSocketUrl())).not.toContain("token");
});
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `npm run test -- --run src/features/room` from `frontend/`  
Expected: FAIL because the room session modules do not exist.

- [ ] **Step 3: Implement reducer-style event merging and a bounded reconnect hook**

```ts
export function mergeRoomEvents(current: RoomEvent[], incoming: RoomEvent[]): RoomEvent[] {
  return [...new Map([...current, ...incoming].map((event) => [event.sequence, event])).values()]
    .sort((left, right) => left.sequence - right.sequence);
}

const socketUrl = (roomId: string, sequence: number) =>
  `${webSocketOrigin()}/api/rooms/${roomId}/events?after_sequence=${sequence}`;
```

On initial mount fetch the snapshot, retain the highest sequence, then open a WebSocket. Handle only `{ type: "events", events: RoomEvent[] }`. On close, retry at 0.5 s, 1 s, 2 s, and 4 s; after the fourth failure expose `connection: "offline"` without looping. `refresh` calls `getRoom`; `continueRoom` calls the server then merges the response. Clean up timers and sockets on unmount.

- [ ] **Step 4: Run focused tests and the full frontend suite**

Run: `npm run test -- --run src/features/room; npm run test; npm run typecheck` from `frontend/`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/App.tsx frontend/src/features
git commit -m "feat: add resilient room session state"
```

### Task 3: Build the playable A-layout pages and safe action controls

**Files:**
- Create: `frontend/src/features/home/CreateGameForm.tsx`, `frontend/src/features/home/HomePage.tsx`, `frontend/src/features/home/home-page.test.tsx`
- Create: `frontend/src/features/room/GameRoomPage.tsx`, `frontend/src/features/room/RoomTimeline.tsx`, `frontend/src/features/room/PlayerRail.tsx`, `frontend/src/features/room/PrivatePanel.tsx`, `frontend/src/features/room/ActionPanel.tsx`, `frontend/src/features/room/ConnectionStatus.tsx`
- Create: `frontend/src/features/room/game-room-page.test.tsx`, `frontend/src/features/room/room.css`
- Modify: `frontend/src/App.tsx`, `frontend/src/styles/global.css`

**Interfaces:**
- `CreateGameForm` calls `ApiClient.createRoom(requestedRoleId)` and navigates to `/rooms/:roomId` on success.
- `ActionPanel({ state, onSubmit, pending })` maps only safe action strings to `HumanCommand` and takes target options only from `state.legal_target_ids`.
- `GameRoomPage` consumes `useRoomSession` and renders a timeline plus right-side player/private/action rail.

- [ ] **Step 1: Write failing page tests**

```tsx
it("renders only server-provided targets and disables repeat submission", async () => {
  render(<ActionPanel state={waitingSeerState} onSubmit={submit} pending={false} />);
  expect(screen.getByRole("button", { name: "AI 玩家 1" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "隐藏玩家" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "确认查验" }));
  expect(submit).toHaveBeenCalledWith({ kind: "inspect", target_id: "ai-1" });
});

it("never renders agent_memory or another player role in the room DOM", () => {
  render(<GameRoomPage roomId="room-1" apiClient={api} />);
  expect(document.body.textContent).not.toContain("agent_memory");
  expect(document.body.textContent).not.toContain("狼人");
});
```

- [ ] **Step 2: Run the focused UI tests to confirm failure**

Run: `npm run test -- --run src/features/home src/features/room/game-room-page.test.tsx` from `frontend/`  
Expected: FAIL because the gameplay components do not exist.

- [ ] **Step 3: Implement the pages and A-layout components**

Use one semantic main timeline and an `aside` for the fixed-width right rail. Map event types to concise Chinese narrative labels: phase changes, public speech, night announcements, executions, vote outcomes, and game finish. Unknown event types render a generic safe system line and never serialize payload objects wholesale.

`ActionPanel` must render:

```ts
const targetKinds = new Set(["wolf_kill", "inspect", "witch_save", "witch_poison", "vote"]);
const directKinds = new Set(["abstain", "noop", "end_discussion"]);
```

For `speak`, enforce client-side nonblank text and maximum 500 characters, then send `{ kind: "speak", text }`. For target actions require one selected `legal_target_ids` value. For a finished state show winner content and a “再开一局” link to `/`; do not add a separate result route. Store only the most recent room ID in `localStorage`, and only after room creation succeeds.

- [ ] **Step 4: Run UI tests, accessibility checks available through Testing Library, and production build**

Run: `npm run test -- --run src/features/home src/features/room; npm run typecheck; npm run build` from `frontend/`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat: add playable narrative game room ui"
```

### Task 4: Serve the production SPA from FastAPI and document local startup

**Files:**
- Modify: `backend/src/werewolf_arena/api/app.py`, `backend/tests/api/test_static_web.py`, `backend/README.md`, `README.md`
- Create: `frontend/.env.example`

**Interfaces:**
- `create_app()` serves `frontend/dist/assets/*` and returns `frontend/dist/index.html` for client routes such as `/rooms/example` when the build exists.
- API endpoints, `/docs`, and the room WebSocket route retain existing routing behavior.
- A missing `frontend/dist` leaves API startup and API tests functional.

- [ ] **Step 1: Write failing static-hosting tests**

```python
def test_built_spa_is_served_for_client_routes(tmp_path, monkeypatch) -> None:
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setenv("WEREWOLF_ARENA_FRONTEND_DIST", str(build))
    with TestClient(create_app(database_path=tmp_path / "arena.db")) as client:
        assert client.get("/rooms/example").text == "<div id='root'></div>"

def test_missing_build_does_not_capture_api_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WEREWOLF_ARENA_FRONTEND_DIST", str(tmp_path / "missing"))
    with TestClient(create_app(database_path=tmp_path / "arena.db")) as client:
        assert client.get("/docs").status_code == 200
```

- [ ] **Step 2: Run the focused backend test to confirm failure**

Run: `uv run pytest -q tests/api/test_static_web.py --basetemp 'D:\AI\.tmp\werewolf-arena-pytest-phase4-static'` from `backend/`  
Expected: FAIL because FastAPI has no SPA static mount or fallback.

- [ ] **Step 3: Add opt-in static mounting and explicit SPA fallback**

```python
frontend_dist = Path(os.environ.get("WEREWOLF_ARENA_FRONTEND_DIST", project_root / "frontend" / "dist"))
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{client_path:path}", include_in_schema=False)
    async def spa_fallback(client_path: str) -> FileResponse:
        if client_path.startswith(("api/", "docs", "openapi.json")):
            raise HTTPException(status_code=404)
        return FileResponse(frontend_dist / "index.html")
```

Place the fallback after API and WebSocket registration. Verify `assets` exists before mounting it. Document development as two terminals (`uv run uvicorn ...` and `npm run dev`) and production-like local operation as `npm run build` followed by the FastAPI command.

- [ ] **Step 4: Run focused static/API tests and frontend build**

Run: `uv run pytest -q tests/api --basetemp 'D:\AI\.tmp\werewolf-arena-pytest-phase4-api'; npm run build` from their respective directories  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/api/app.py backend/tests/api/test_static_web.py backend/README.md README.md frontend/.env.example
git commit -m "feat: serve built web application"
```

### Task 5: Add a browser-level local gameplay test and final delivery checks

**Files:**
- Create: `frontend/playwright.config.ts`, `frontend/e2e/game-room.spec.ts`, `frontend/scripts/start-e2e-backend.py`
- Modify: `frontend/package.json`, `backend/README.md`

**Interfaces:**
- `npm run test:e2e` starts an offline FastAPI test server with an injected scripted model client, serves the built SPA, and runs Playwright against it.
- The e2e fixture creates a known human seer room, waits for the AI-driven inspect action, submits a valid human command, and validates the visible state/timeline.

- [ ] **Step 1: Write the failing Playwright specification**

```ts
test("a human seer can create, inspect, and see no private AI fields", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("选择身份").selectOption("seer");
  await page.getByRole("button", { name: "开始对局" }).click();
  await expect(page.getByText("预言家查验")).toBeVisible();
  await page.getByRole("button", { name: /AI 玩家 1/ }).click();
  await page.getByRole("button", { name: "确认查验" }).click();
  await expect(page.locator("body")).not.toContainText("agent_memory");
});
```

- [ ] **Step 2: Run the focused e2e command to confirm failure**

Run: `npm run test:e2e -- --grep "human seer"` from `frontend/`  
Expected: FAIL because the Playwright runner and test backend helper do not exist.

- [ ] **Step 3: Implement isolated e2e startup and the test**

`start-e2e-backend.py` must use `create_app(database_path=temporary_path, model_client=ScriptedRoomClient())`, never environment LLM credentials, bind to a configurable loopback port, and remove its temporary database on exit. Configure Playwright `webServer` entries for the backend helper and `npm run dev -- --host 127.0.0.1`. Use the human seer flow because it deterministically stops at `night_seer`.

- [ ] **Step 4: Run browser, backend, and frontend verification**

Run: `npm run test:e2e; npm run test; npm run typecheck; npm run build; uv run pytest -q --basetemp 'D:\AI\.tmp\werewolf-arena-pytest-phase4-full'; uv run ruff check .; uv run mypy src; git diff --check`  
Expected: PASS, with no real network model call.

- [ ] **Step 5: Commit**

```powershell
git add frontend backend/README.md
git commit -m "test: cover playable web game flow"
```

## Plan Self-Review

- **Spec coverage:** Tasks 1-2 implement typed cookie-based transport, state synchronization, event deduplication and recovery. Task 3 implements the chosen narrative UI, all safe actions, spectator/finished UI and privacy assertions. Task 4 supplies production-style FastAPI static hosting and startup documentation. Task 5 covers browser gameplay with an offline model replacement.
- **Placeholder scan:** The plan has no deferred implementation markers; each task names files, contracts, failure tests, implementation shape, verification commands and commit boundary.
- **Type consistency:** `RoomPayload` is defined in Task 1, consumed by Task 2, and supplied to Task 3. `ApiClient` is the only REST boundary. `mergeRoomEvents` is the only event deduplication function. Backend static hosting remains behind `WEREWOLF_ARENA_FRONTEND_DIST` and does not change the domain/API contracts.

## Execution Mode

The user previously selected inline execution for this project and requested not to be asked again. Execute these tasks in the current session using `superpowers:executing-plans`; use a dedicated feature branch `feature/phase-4-web-ui`, preserve `master`, and push the completed Phase 4 branch to GitHub automatically.
