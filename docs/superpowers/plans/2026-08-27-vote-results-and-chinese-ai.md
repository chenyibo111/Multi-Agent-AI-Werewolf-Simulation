# Vote Results and Chinese AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish complete vote results, render them with player names, and make AI players use Chinese speech and human-friendly names.

**Architecture:** The domain engine snapshots accepted vote commands into a public event before it clears transient commands. The frontend resolves only the event’s actor and target IDs through the already-projected participant map. The agent policy keeps the existing JSON contract but states its natural-language speech requirement in Chinese; game construction changes only display names, preserving stable AI IDs.

**Tech Stack:** Python 3.14, FastAPI domain model, Pydantic, React, TypeScript, Vitest, pytest.

---

### Task 1: Publish a complete vote-result event

**Files:**
- Modify: `backend/src/werewolf_arena/domain/engine.py`
- Modify: `backend/tests/domain/test_discussion_and_safe_commands.py`

- [x] **Step 1: Write the failing domain tests**

Add a parametrized or focused test that submits votes from every living participant, advances the day-vote phase, and asserts the public `vote_result` event has one entry per alive actor, preserving a vote target and an abstention as `None`. Add assertions that the event also exists in the tied and all-abstain paths.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/domain/test_discussion_and_safe_commands.py`

Expected: FAIL because no `vote_result` event exists.

- [x] **Step 3: Add the minimal domain event**

Before each `DAY_VOTE` branch clears `pending_commands`, append a public event:

```python
state = state.append_event(
    "vote_result",
    {"votes": [{"actor_id": command.actor_id, "target_id": command.target_id} for command in commands]},
    Visibility.PUBLIC,
)
```

Use the validated `commands` list, so the event contains only accepted commands and no private information.

- [x] **Step 4: Re-run the focused test**

Run the command from Step 2. Expected: PASS.

### Task 2: Localize agent instructions and display names

**Files:**
- Modify: `backend/src/werewolf_arena/agents/policy.py`
- Modify: `backend/src/werewolf_arena/domain/engine.py`
- Modify: `backend/tests/agents/test_observation_and_policy.py`
- Modify: `backend/tests/domain/test_standard_game_engine.py`

- [x] **Step 1: Write failing tests**

Extend the policy prompt test to assert Chinese speech guidance is present while `"kind"`, `legal_kinds`, `legal_target_ids`, and `never "action"` remain required. Add a game-creation assertion that participant IDs remain `ai-1` through `ai-5` while their display names are `林小雨`、`周子墨`、`陈星河`、`苏晚`、`顾言`.

- [x] **Step 2: Run the focused tests to verify they fail**

Run: `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/agents/test_observation_and_policy.py tests/domain/test_standard_game_engine.py`

Expected: FAIL because the prompt is English and AI names are generic.

- [x] **Step 3: Implement the minimal behavior**

Replace the prompt’s natural-language instructions with Chinese wording that requires concise natural Chinese in `speech` for a speak action, and preserves the exact JSON constraints. Define a fixed tuple of five display names in `GameEngine` and use it when creating `ai-1` through `ai-5`.

- [x] **Step 4: Re-run the focused tests**

Run the command from Step 2. Expected: PASS.

### Task 3: Render vote results by display name

**Files:**
- Modify: `frontend/src/features/room/RoomTimeline.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`

- [x] **Step 1: Write failing component tests**

Render `RoomTimeline` with participants and a `vote_result` event. Assert it displays `林小雨 → 周子墨` and `陈星河 → 弃权`. Add an unknown-ID case that falls back to the ID without rendering unexpected payload fields.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run src/features/room/game-room-page.test.tsx`

Expected: FAIL because the timeline does not receive participants and does not know `vote_result`.

- [x] **Step 3: Implement the minimal rendering path**

Pass `state.participants` from the game-room page to `RoomTimeline`. For a valid `vote_result.votes` array, resolve every `actor_id` and non-null `target_id` through participant display names, join lines with `；`, and safely fall back to the ID. Keep unknown events on the generic safe line.

- [x] **Step 4: Re-run the focused test and type-check**

Run the Vitest command from Step 2, then:

```zsh
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/typescript/bin/tsc -b --pretty false
```

Expected: PASS and exit 0.

### Task 4: Run the full verification suite

**Files:**
- Verify only

- [x] **Step 1: Run backend quality gates**

```zsh
env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/mypy src
```

Expected: all checks pass.

- [x] **Step 2: Run frontend quality gates**

```zsh
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run
/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/typescript/bin/tsc -b --pretty false
```

Expected: all checks pass.

- [x] **Step 3: Review and commit**

Run `git diff --check`, inspect only the intended files, then commit all implementation and test changes with `feat: show vote breakdowns and localize AI`.
