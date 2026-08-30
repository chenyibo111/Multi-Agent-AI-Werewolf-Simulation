# Model Health and Gameplay Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the room owner a safe, actionable view of real model-call health and make one minimal strategy adjustment only if observed data warrants it.

**Architecture:** Aggregate existing redacted `AgentRunRecord` rows into a compact room-health projection. Add that projection to every authenticated room state payload so REST and WebSocket refreshes share one contract. Render it in the fixed right sidebar without revealing prompts, raw completions, player identities, or private role reasoning.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, SQLAlchemy/SQLite, React, TypeScript, Vitest.

**Spec:** User-approved P0/P1 priority after master analysis on 2026-08-30.

## Global Constraints

- Health payload contains only aggregate counts, token totals, latency, a health state, and the latest redacted fallback kind.
- Do not return prompts, raw model output, API configuration, secret material, or per-agent private context.
- Keep the existing bearer/cookie room authorization boundary.
- Preserve the desktop fixed viewport and independent panel scrolling.

---

### Task 1: Safe model-health projection

**Files:**
- Create: `backend/src/werewolf_arena/agents/health.py`
- Test: `backend/tests/agents/test_health.py`

**Interfaces:**
- Consumes: `tuple[AgentRunRecord, ...]`
- Produces: `project_agent_health(runs) -> dict[str, object]` with `status`, call counts, token totals, average latency, and `latest_failure_kind`.

- [ ] Write a failing test for idle, healthy, and fallback cases.
- [ ] Run the focused test and observe the missing projection failure.
- [ ] Implement the minimal aggregate projection.
- [ ] Run the focused test and observe success.

### Task 2: Authenticated state-payload contract

**Files:**
- Modify: `backend/src/werewolf_arena/api/routes/rooms.py`
- Modify: `backend/tests/api/test_agent_rooms.py`

**Interfaces:**
- Consumes: `request.app.state.repository.agent_runs_for(room_id)`
- Produces: `state.agent_health` on create, load, command, and continue responses.

- [ ] Write a failing API contract test for the redacted health projection.
- [ ] Run the focused test and observe the absent `agent_health` field.
- [ ] Pass repository audit rows through the shared state-view helper.
- [ ] Run the focused test and observe success.

### Task 3: Fixed-sidebar health card

**Files:**
- Create: `frontend/src/features/room/ModelHealthPanel.tsx`
- Modify: `frontend/src/features/room/GameRoomPage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: optional `RoomSnapshot.agent_health` from the API.
- Produces: a compact card that distinguishes waiting, healthy, and degraded status, showing aggregate call/latency details only.

- [ ] Write a failing page test that expects the degraded safety message and fallback reason.
- [ ] Run the focused test and observe failure.
- [ ] Implement the typed panel and sidebar styles.
- [ ] Run the focused test and observe success.

### Task 4: Evidence-based gameplay tuning and verification

**Files:**
- Modify only the smallest strategy source and regression test justified by current audit/gameplay evidence.
- Test: matching backend test.

- [ ] Inspect live audit records and current prompts/decision path.
- [ ] Add a failing regression test only if a reproducible weak behavior is found.
- [ ] Implement the smallest correction, or explicitly defer P1 when no reproducible defect exists.
- [ ] Run backend tests, frontend tests/typecheck/build, and review the full diff.
- [ ] Commit and push the feature branch.
