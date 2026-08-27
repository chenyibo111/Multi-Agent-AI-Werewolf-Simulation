# Disable Thinking and Trim Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable DeepSeek thinking mode by default and reduce AI prompt noise without removing authorized, decision-relevant private facts.

**Architecture:** `LLMSettings` owns a boolean thinking setting. `OpenAICompatibleClient` maps the disabled setting to DeepSeek's official OpenAI-SDK extension, `extra_body={"thinking": {"type": "disabled"}}`. `build_observation` filters lifecycle/rejection events and bounds only the public event history; private events remain intact.

**Tech Stack:** Python 3.12+, OpenAI Python SDK, Pydantic v2, pytest.

---

### Task 1: Add a default-off DeepSeek thinking setting

**Files:**
- Modify: `backend/src/werewolf_arena/agents/config.py`
- Modify: `backend/src/werewolf_arena/agents/model_client.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/agents/test_config_and_model_client.py`

- [ ] **Step 1: Write failing tests**

Assert configuration defaults `thinking_enabled` to false, accepts `LLM_THINKING_ENABLED=true`, and a fake SDK receives `extra_body={"thinking": {"type": "disabled"}}` when disabled.

- [ ] **Step 2: Verify RED**

Run `cd backend && uv run pytest tests/agents/test_config_and_model_client.py -q` and expect missing `thinking_enabled` or missing `extra_body` assertions.

- [ ] **Step 3: Implement the setting and request mapping**

Parse only case-insensitive `true` and `false`; reject other values with `LLMConfigurationError`. Add `LLM_THINKING_ENABLED=false` to the example environment file. When false, pass the official DeepSeek `extra_body` object; when true, omit it.

- [ ] **Step 4: Verify GREEN**

Run `cd backend && uv run pytest tests/agents/test_config_and_model_client.py -q` and expect all tests to pass.

### Task 2: Bound non-private prompt history

**Files:**
- Modify: `backend/src/werewolf_arena/agents/observation.py`
- Test: `backend/tests/agents/test_observation_and_policy.py`

- [ ] **Step 1: Write failing observation test**

Append `phase_changed`, `command_rejected`, and more than twenty `public_speech` events. Assert the AI observation excludes the two noise event types, retains the newest twenty meaningful public events in sequence order, and still includes recipient private events.

- [ ] **Step 2: Verify RED**

Run `cd backend && uv run pytest tests/agents/test_observation_and_policy.py -q` and expect the unbounded current observation to fail.

- [ ] **Step 3: Implement the minimal event filter**

Filter only public `phase_changed` and `command_rejected` events, then retain the newest twenty allowed public events. Do not filter, truncate, or broaden private event visibility.

- [ ] **Step 4: Run full verification and live smoke**

Run `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy src` from `backend`. Then run `uv run python scripts/smoke_real_game.py --requested-role villager --max-agent-calls 8` and verify that the redacted result contains no `invalid_model_output` failures.
