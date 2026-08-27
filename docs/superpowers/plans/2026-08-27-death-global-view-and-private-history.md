# Death Global View and Private History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give living players a durable record of their own role information and give dead players a safe, immediate full-game view.

**Architecture:** Preserve the existing event-sourced authority model. Write explicit private witch events at phase entry and resolution; extend viewer kinds so a dead player receives all non-server events and all identities; keep recursive payload redaction at the projection boundary. The UI renders only recognized event contracts and uses the global projection without client-side reconstruction.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, React, TypeScript, pytest, Vitest.

---

### Task 1: Persist witch knowledge and action results

**Files:**
- Modify: `backend/src/werewolf_arena/domain/engine.py:159-194`
- Modify: `backend/tests/domain/test_standard_game_engine.py`

- [x] **Step 1: Write failing domain tests**

```python
def test_witch_receives_private_night_target_and_save_result() -> None:
    # Advance a matched wolf attack to NIGHT_WITCH, then save the target.
    # Assert events addressed to the witch include:
    # witch_night_target {target_id: victim_id}
    # witch_action_result {saved_target_id: victim_id, poisoned_target_id: None,
    #                      antidote_available: False, poison_available: True}
    ...
```

- [x] **Step 2: Run the focused test and verify it fails**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/domain/test_standard_game_engine.py::test_witch_receives_private_night_target_and_save_result`

Expected: FAIL because no witch-specific private events exist.

- [x] **Step 3: Implement the smallest event contracts**

When wolf and seer processing have advanced to `NIGHT_WITCH`, append `witch_night_target` privately to the alive witch if a victim exists. During witch resolution, append `witch_action_result` privately to that witch with explicit saved/poisoned IDs and post-resolution ability availability. Do not write an event for a nonexistent/dead witch and do not put these facts in a public or server event.

- [x] **Step 4: Re-run the focused test**

Run the command from Step 2. Expected: PASS.

### Task 2: Authorize death global projection safely

**Files:**
- Modify: `backend/src/werewolf_arena/domain/projection.py:10-94`
- Modify: `backend/src/werewolf_arena/api/dependencies.py:58-62`
- Modify: `backend/src/werewolf_arena/api/routes/rooms.py:146-193`
- Modify: `backend/tests/domain/test_projection.py`
- Modify: `backend/tests/api/test_rooms.py`

- [x] **Step 1: Write failing projection and API-view tests**

```python
def test_dead_viewer_receives_roles_and_all_non_server_events() -> None:
    # Add private seer, witch and wolf events plus a server event to a state.
    # Assert a dead viewer sees every role and the three private events,
    # but not the server event or a raw_model_response payload key.
    ...

def test_dead_human_room_view_is_global_without_actions() -> None:
    # Assert the dead room view remains non-interactive but exposes every role.
    ...
```

- [x] **Step 2: Run focused tests and verify they fail**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/domain/test_projection.py tests/api/test_rooms.py`

Expected: FAIL because `DEAD_SPECTATOR` currently only receives public events and hides other identities.

- [x] **Step 3: Implement a distinct global viewer capability**

Rename the dead capability to `DEAD_GLOBAL` (or add it while updating every caller). For this capability, project all participant roles and every event except `Visibility.SERVER`; apply `_safe_payload` exactly as for all other views. Keep `waiting_for_human`, human actions and targets empty after death. Leave all living views unchanged. Remove the no-longer-valid assertion that a dead view excludes the human private state only if the full state contract deliberately excludes `private_state`; roles/events must be the source of global knowledge.

- [x] **Step 4: Re-run focused tests**

Run the command from Step 2. Expected: PASS.

### Task 3: Render recognized private history for active and dead views

**Files:**
- Modify: `frontend/src/features/room/RoomTimeline.tsx`
- Modify: `frontend/src/features/room/PrivatePanel.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`

- [x] **Step 1: Write failing component tests**

```tsx
it("renders witch target and action-result events with player names", () => {
  render(<RoomTimeline participants={players} events={[
    { sequence: 1, event_type: "witch_night_target", payload: { target_id: "ai-1" }, visibility: "private" },
    { sequence: 2, event_type: "witch_action_result", payload: {
      saved_target_id: "ai-1", poisoned_target_id: null,
      antidote_available: false, poison_available: true,
    }, visibility: "private" },
  ]} />);
  expect(screen.getByText("女巫得知：今晚被袭击的是林小雨。 ")).toBeVisible();
  expect(screen.getByText("女巫行动：救下林小雨；解药已用，毒药可用。 ")).toBeVisible();
});
```

- [x] **Step 2: Run the focused test and verify it fails**

Run: `/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run src/features/room/game-room-page.test.tsx`

Expected: FAIL because unrecognized events render as a generic status line.

- [x] **Step 3: Implement safe event text**

Add explicit recognizers for `witch_night_target` and `witch_action_result`. Convert only known scalar payload fields to names and fixed Chinese text; continue using the generic line for unknown events so private raw payloads cannot be serialized into the page. Keep the existing room timeline visible in `spectating` mode, which will now contain the safe global event projection.

- [x] **Step 4: Re-run the focused test**

Run the command from Step 2. Expected: PASS.

### Task 4: Full verification and commit

**Files:**
- Modify: `docs/superpowers/plans/2026-08-27-death-global-view-and-private-history.md`

- [x] **Step 1: Run backend checks**

```zsh
cd backend
env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/mypy src
```

- [x] **Step 2: Run frontend checks**

```zsh
cd frontend
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/typescript/bin/tsc -b --pretty false
```

- [x] **Step 3: Review and commit**

Run `git diff --check`, mark the completed checklist items, inspect `git status --short`, and commit with `feat: add death global view`.
