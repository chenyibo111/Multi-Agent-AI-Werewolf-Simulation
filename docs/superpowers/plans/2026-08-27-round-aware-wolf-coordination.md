# Round-Aware Wolf Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Randomize each room's roles, seats, and daily AI order while giving agents complete relevant public context and human wolves private AI teammate suggestions.

**Architecture:** Add deterministic per-game/round derivations around persisted `game_id`, not mutable process RNG, so restarting a room preserves order. Extend safe projections and `AgentObservation` with explicitly allowlisted player metadata; retain only public event types useful for reasoning. Add a private wolf-team suggestion event and a `team_message` decision field, then change orchestration so an AI wolf advises a human wolf before the human chooses the final kill.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, React, TypeScript, pytest, Vitest.

---

### Task 1: Per-room random role and seat assignment

**Files:**
- Modify: `backend/src/werewolf_arena/domain/models.py`
- Modify: `backend/src/werewolf_arena/domain/engine.py`
- Modify: `backend/src/werewolf_arena/api/app.py`
- Modify: `backend/src/werewolf_arena/domain/projection.py`
- Modify: `backend/tests/domain/test_standard_game_engine.py`
- Modify: `backend/tests/domain/test_projection.py`

- [x] **Step 1: Write failing tests**

Create deterministic engines with distinct seeds and assert random-role creation produces differing valid rosters; assert a requested human role remains fixed. Assert every participant has unique public `seat_number` and the projection exposes it without exposing other roles.

- [x] **Step 2: Run the focused tests to verify failure**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/domain/test_standard_game_engine.py tests/domain/test_projection.py`

Expected: FAIL because `Participant` has no seat and application construction uses seed `7`.

- [x] **Step 3: Implement minimal random assignment**

Add `seat_number: int` to `Participant`. Let `GameEngine(seed: int | None)` use `secrets.randbits(64)` when no seed is supplied; preserve supplied seeds for tests. Shuffle all created participants once, assign consecutive seat numbers in that shuffled order, and instantiate the application engine with `seed=None`. Project only `seat_number`, `display_name`, and alive state publicly.

- [x] **Step 4: Re-run focused tests**

Run the command from Step 2. Expected: PASS.

### Task 2: Give agents named, complete public context

**Files:**
- Modify: `backend/src/werewolf_arena/agents/models.py`
- Modify: `backend/src/werewolf_arena/agents/observation.py`
- Modify: `backend/src/werewolf_arena/agents/policy.py`
- Modify: `backend/tests/agents/test_observation_and_policy.py`

- [x] **Step 1: Write failing tests**

Build a state containing an early public speech and more than twenty later relevant public events. Assert the observation retains the early speech, includes `{participant_id, display_name, seat_number, alive}` for every player, excludes private/server events, and keeps internal role IDs out of public roster entries. Assert the policy prompt requires natural-language references to display names rather than `ai-*` IDs.

- [x] **Step 2: Run focused tests to verify failure**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/agents/test_observation_and_policy.py`

Expected: FAIL because observations truncate to twenty events and contain no named roster.

- [x] **Step 3: Implement minimal context contract**

Add `public_players` to `AgentObservation`. Replace the fixed history cap with a whitelist of meaningful public event types (`public_speech`, `night_announcement`, `vote_result`, `execution`, `vote_tied`, `vote_no_execution`, `game_finished`). Populate the named public roster and change the Chinese system prompt to require display names in `speech`, `public_reason`, and `team_message`; preserve JSON/allowlist rules.

- [x] **Step 4: Re-run focused tests**

Run the command from Step 2. Expected: PASS.

### Task 3: Private wolf teammate visibility and recommendation

**Files:**
- Modify: `backend/src/werewolf_arena/agents/models.py`
- Modify: `backend/src/werewolf_arena/agents/orchestrator.py`
- Modify: `backend/src/werewolf_arena/api/routes/rooms.py`
- Modify: `backend/src/werewolf_arena/domain/projection.py`
- Modify: `backend/tests/api/test_rooms.py`
- Modify: `backend/tests/runtime/test_agent_orchestration.py`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/features/room/PrivatePanel.tsx`
- Modify: `frontend/src/features/room/RoomTimeline.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`

- [x] **Step 1: Write failing backend and frontend tests**

For a human wolf, assert the active room state contains only living wolf teammates’ public identity fields; assert a dead spectator has neither that field nor private wolf events. Use a scripted AI wolf decision with `team_message`, call the orchestrator at `NIGHT_WOLF`, and assert it pauses for the human after adding a private `wolf_team_suggestion` event. Render the private panel/timeline and assert teammate name and private suggestion are visible only in the active wolf state.

- [x] **Step 2: Run focused tests to verify failure**

Run backend: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/api/test_rooms.py tests/runtime/test_agent_orchestration.py`

Run frontend: `/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run src/features/room/game-room-page.test.tsx`

Expected: FAIL because neither the private state field nor event exists and orchestration pauses before consulting an AI wolf.

- [x] **Step 3: Implement minimal coordination**

Add `team_message: str = ""` to `AgentDecision` and cap it at 300 characters in policy validation. For an active human wolf, `_run_wolf_team` calls one AI teammate before returning the human action; append `wolf_team_suggestion` as a `Visibility.PRIVATE` event addressed only to alive wolves with the suggested target and message. Expose an allowlisted `wolf_teammates` state field only for alive human wolves; render it in `PrivatePanel` and render the private suggestion with names in `RoomTimeline`. Once the human submits a target, preserve the existing team-target mirroring path.

- [x] **Step 4: Re-run focused tests**

Run both commands from Step 2. Expected: PASS.

### Task 4: Reset and randomize daily AI discussion order

**Files:**
- Modify: `backend/src/werewolf_arena/agents/orchestrator.py`
- Modify: `backend/tests/runtime/test_agent_orchestration.py`

- [x] **Step 1: Write failing tests**

Create a state with one completed prior `day_discussion`, then append a new `phase_changed` to `day_discussion`. Assert every currently alive AI speaks again. Construct two copies of a state with the same game ID and round and assert their ordered AI speech IDs match; use a different round and assert the ordering key differs.

- [x] **Step 2: Run the focused test to verify failure**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/runtime/test_agent_orchestration.py`

Expected: FAIL because `_spoken_ids` scans all game events and actor order follows the fixed participant tuple.

- [x] **Step 3: Implement the minimal daily order**

Locate the latest public `phase_changed` event whose phase is `day_discussion`; only speeches after its sequence count as spoken. Build the AI actor sequence with `random.Random(f"{state.game_id}:{state.round_number}:day_discussion")`, shuffle it, and use it for this round. Preserve death filtering and automatic transition after a dead human’s AI discussion completes.

- [x] **Step 4: Re-run focused test**

Run the command from Step 2. Expected: PASS.

### Task 5: Full verification and commit

**Files:**
- Verify only

- [x] **Step 1: Run backend checks**

```zsh
env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/mypy src
```

- [x] **Step 2: Run frontend checks**

```zsh
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/typescript/bin/tsc -b --pretty false
```

- [x] **Step 3: Review and commit**

Run `git diff --check`, review the intended files, and commit with `feat: add round-aware AI coordination`.
