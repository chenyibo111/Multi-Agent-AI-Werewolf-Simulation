# Agent JSON Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow OpenAI-compatible models that emit the common `action` JSON field to make valid Werewolf Arena decisions without weakening server-side action or target authorization.

**Architecture:** `AgentPolicy` remains the only boundary that converts a model completion into an `AgentDecision`. It will normalize precisely one alias (`action` to `kind`) before Pydantic validation, then retain the existing per-phase command and target allowlists. The system prompt will state the required output contract explicitly so compliant models use `kind` directly.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, OpenAI-compatible Chat Completions.

---

## File structure

- Modify: `backend/src/werewolf_arena/agents/policy.py` — describe the output schema and normalize the single safe alias before validation.
- Modify: `backend/tests/agents/test_observation_and_policy.py` — cover the DeepSeek-style alias and retain rejection of unsafe output.

### Task 1: Normalize the `action` alias without relaxing authorization

**Files:**
- Modify: `backend/tests/agents/test_observation_and_policy.py`
- Modify: `backend/src/werewolf_arena/agents/policy.py`

- [ ] **Step 1: Write failing policy tests**

Add a scripted client that returns a JSON object using `action` with a legal `wolf_kill` target. Assert that `AgentPolicy.decide` returns `CommandKind.WOLF_KILL`, the same target, and no failure kind. Capture the system prompt and assert that it contains `\"kind\"`, `legal_kinds`, `legal_target_ids`, and `never \"action\"`.

```python
assert decision.kind is CommandKind.WOLF_KILL
assert decision.target_id in observation.legal_target_ids
assert decision.failure_kind is None
assert '"kind"' in client.system_prompt
assert "legal_kinds" in client.system_prompt
assert "legal_target_ids" in client.system_prompt
assert 'never "action"' in client.system_prompt
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
cd backend && uv run pytest tests/agents/test_observation_and_policy.py -q
```

Expected: the new alias test fails because `AgentDecision` requires `kind`, and the prompt assertion fails because the current one-line prompt does not define the contract.

- [ ] **Step 3: Implement the smallest compatibility boundary**

In `AgentPolicy`, add a private prompt constant that requires exactly one JSON object, names the `kind` field, points to `legal_kinds`/`legal_target_ids`, forbids Markdown and says never to use `action`. Add a private payload normalizer that accepts a mapping with `action` only when `kind` is absent, removes `action`, and sets `kind` to its string value. Parse with `json.loads`, normalize, then call `AgentDecision.model_validate` as today.

```python
if "kind" not in payload and isinstance(payload.get("action"), str):
    return {key: value for key, value in payload.items() if key != "action"} | {
        "kind": payload["action"]
    }
```

Do not map other aliases, tolerate unknown keys, retain raw completions, or bypass `_is_allowed`.

- [ ] **Step 4: Run focused and full backend checks**

Run:

```bash
cd backend && uv run pytest tests/agents/test_observation_and_policy.py -q
uv run pytest -q
uv run ruff check .
uv run mypy src
```

Expected: all commands exit with status 0.

- [ ] **Step 5: Run the capped real-model smoke**

Run after automated checks:

```bash
cd backend && uv run python scripts/smoke_real_game.py --requested-role villager --max-agent-calls 8
```

Expected: `failures` does not contain `invalid_model_output` for the documented `action` alias; output remains redacted and the call cap is unchanged.

- [ ] **Step 6: Commit the focused fix**

```bash
git add backend/src/werewolf_arena/agents/policy.py backend/tests/agents/test_observation_and_policy.py docs/superpowers/plans/2026-08-27-agent-json-compatibility.md
git commit -m "fix: accept action alias in agent JSON decisions"
```

## Plan self-review

- The sole compatibility alias is `action` to `kind`; Pydantic still forbids every remaining unknown key.
- Existing command and target authorization remains mandatory after normalization.
- Automated tests prove the alias is accepted and the explicit Prompt contract is sent.
- The final smoke verifies the exact real-provider behavior observed during diagnosis.
