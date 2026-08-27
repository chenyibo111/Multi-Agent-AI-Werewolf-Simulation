# Role Strategy and Explainable UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every standard role an explicit AI strategy, expose safe action reasons, and make game progress easier to follow.

**Architecture:** Keep the server as the only rules authority. A pure role-strategy module contributes Chinese role instructions to `AgentPolicy`; new reason events are written only after a constrained model decision is accepted and projected with existing visibility rules. The frontend consumes those events and current server phase without predicting game state.

**Tech Stack:** Python, FastAPI, Pydantic, React, TypeScript, pytest, Vitest.

---

### Task 1: Role strategy cards and model decision contract

**Files:**
- Create: `backend/src/werewolf_arena/agents/role_strategy.py`
- Modify: `backend/src/werewolf_arena/agents/policy.py`
- Modify: `backend/src/werewolf_arena/agents/models.py`
- Test: `backend/tests/agents/test_observation_and_policy.py`

- [x] Write failing tests asserting each of `wolf`, `seer`, `witch`, and `villager` gets a distinct strategy instruction and that a valid `public_reason` is preserved.
- [x] Run `env LLM_BASE_URL='' LLM_API_KEY='' LLM_MODEL='' ./.venv/bin/pytest -q tests/agents/test_observation_and_policy.py` and confirm failure.
- [x] Add `strategy_for(role_id)` returning a fixed Chinese instruction; include it in the system prompt. Validate `public_reason` to 300 characters, replace internal IDs with names, and reject reasons for unrecognized model payloads.
- [x] Remove the deterministic witch-save branch so the model supplies a legal save/poison/noop action.
- [x] Re-run the focused test and confirm success.

### Task 2: Safe explanation events

**Files:**
- Modify: `backend/src/werewolf_arena/agents/orchestrator.py`
- Modify: `backend/src/werewolf_arena/domain/projection.py`
- Test: `backend/tests/runtime/test_agent_orchestration.py`
- Test: `backend/tests/domain/test_projection.py`

- [x] Write failing tests for a public vote reason event, a private night-action reason event, and their isolation from an unrelated live player.
- [x] Run the focused backend tests and confirm failure.
- [x] After a valid AI decision, append `agent_public_reason` for speech/vote decisions and `agent_private_reason` for night actions. Recipients for private reasons are only the acting player; preserve the existing death-global and finished-replay filtering.
- [x] Re-run the focused tests and confirm success.

### Task 3: Phase and reason feedback UI

**Files:**
- Modify: `frontend/src/features/room/RoomTimeline.tsx`
- Modify: `frontend/src/features/room/PrivatePanel.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`
- Test: `frontend/src/features/room/game-room-page.test.tsx`

- [x] Write failing component tests for public vote reasons, private night reasons, and a visible current-phase feedback label.
- [x] Run `/Users/yibo.chen/.nvm/versions/node/v22.22.1/bin/node node_modules/vitest/vitest.mjs run src/features/room/game-room-page.test.tsx` and confirm failure.
- [x] Render only recognized reason payloads using player names; add a phase-feedback line based on the server-supplied `phase_text`; do not display raw payloads or unrecognized reason fields.
- [x] Re-run the focused component test and confirm success.

### Task 4: Full verification and commit

- [x] Run backend pytest, Ruff and mypy; run frontend Vitest and TypeScript checks.
- [x] Run `git diff --check`, mark the plan complete, and commit with `feat: add role-aware AI explanations`.
