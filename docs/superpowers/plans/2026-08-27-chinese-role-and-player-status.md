# Chinese Role Labels and Player Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Render authorized role and faction values in Chinese and replace player status dots with explicit text badges.

**Architecture:** Add pure frontend label functions for role and faction values, then use them in player and result components. Keep role visibility entirely server-driven: components format a role only when the existing projection includes it.

### Task 1: Label helpers and player rail

**Files:**
- Create: `frontend/src/lib/game-labels.ts`
- Modify: `frontend/src/features/room/PlayerRail.tsx`
- Modify: `frontend/src/features/room/game-room-page.test.tsx`

- [x] Write failing tests for “存活/已出局” labels and “女巫” role text, while asserting an absent `role_id` stays absent.
- [x] Run the focused Vitest file and verify failure.
- [x] Add `roleLabel` and `factionLabel`; render text status badges and authorized Chinese role labels.
- [x] Re-run the focused test and verify success.

### Task 2: Reuse Chinese labels in private and finished views

**Files:**
- Modify: `frontend/src/features/room/PrivatePanel.tsx`
- Modify: `frontend/src/features/room/FinishedReport.tsx`
- Modify: `frontend/src/features/room/room-lifecycle-panels.test.tsx`

- [x] Write failing tests for a Chinese private identity and Chinese finished winner/roles.
- [x] Run the focused Vitest file and verify failure.
- [x] Reuse the label helpers without changing role visibility.
- [x] Re-run the focused test and verify success.

### Task 3: Verify and commit

- [x] Run full frontend Vitest and TypeScript checks, plus `git diff --check`.
- [x] Mark this plan complete and commit with `feat: localize player role labels`.
