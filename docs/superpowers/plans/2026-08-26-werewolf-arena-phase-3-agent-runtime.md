# Werewolf Arena Phase 3 Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one human and five real OpenAI-compatible AI players complete a standard six-player game through the existing REST/WebSocket server, with strict information isolation, durable recovery, budgets, and safe degradation.

**Architecture:** A new `agents/` layer turns a per-player authorized observation into a constrained decision using an asynchronous OpenAI-compatible client. `GameOrchestrator` converts only valid AI decisions to existing domain commands, while `RoomRuntime` serializes human input and automatic steps under its existing lock. Domain remains the authoritative rule layer, and SQLite stores snapshots, append-only events, and redacted model-call records.

**Tech Stack:** Python `>=3.12,<3.15`, Pydantic v2, `openai.AsyncOpenAI`, `python-dotenv`, FastAPI, SQLAlchemy 2 / aiosqlite, pytest, httpx2, uvicorn.

**Spec:** `docs/superpowers/specs/2026-08-26-werewolf-arena-phase-3-agent-runtime-design.md`

## Global Constraints

- Read `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` from `backend/.env`; never print, persist, or return `LLM_API_KEY`.
- Tests must inject scripted clients and never call a network model endpoint.
- `GameEngine` remains the only component that can modify authority state from a command.
- Browser/API/WebSocket messages must use `project_state` or `project_events`, never serialize raw `GameState`, Agent memory, prompt, or raw model content.
- Persist accepted AI/human steps before publish; resuming cannot replay a persisted model decision or consume budget twice.
- Retain local SQLite and current bearer authorization; add a room-path HttpOnly cookie without removing bearer support.
- Run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`, and `git diff --check` before every commit.

---

### Task 1: Add OpenAI-compatible configuration and asynchronous model boundary

**Files:**
- Modify: `backend/pyproject.toml`, `backend/.env.example`, `backend/uv.lock`
- Create: `backend/src/werewolf_arena/agents/__init__.py`, `backend/src/werewolf_arena/agents/config.py`, `backend/src/werewolf_arena/agents/model_client.py`
- Test: `backend/tests/agents/test_config_and_model_client.py`

**Interfaces:**
- Produces `LLMSettings.from_environment() -> LLMSettings`.
- Produces `ModelCompletion(text: str, input_tokens: int, output_tokens: int, cost_usd: float, latency_ms: int)`.
- Produces `AsyncModelClient.complete(system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion`.
- Later tasks depend only on `AsyncModelClient`, not `AsyncOpenAI`.

- [ ] **Step 1: Write failing configuration and client-contract tests**

```python
def test_settings_loads_dotenv_without_echoing_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret-value")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    assert LLMSettings.from_environment().model == "test-model"

def test_missing_settings_raise_configuration_error_without_key(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        LLMSettings.from_environment()
```

- [ ] **Step 2: Run the focused test and confirm import failure**

Run: `uv run pytest -q tests/agents/test_config_and_model_client.py`  
Expected: FAIL because `werewolf_arena.agents` does not exist.

- [ ] **Step 3: Add dependencies and implement the minimal model boundary**

```python
@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> Self: ...

class OpenAICompatibleClient:
    async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion: ...
```

Load `backend/.env` with `load_dotenv`, instantiate `AsyncOpenAI` lazily, call `chat.completions.create`, normalize string/list content, and collect `usage`. Add `openai` and `python-dotenv` runtime dependencies and document only blank/example values in `.env.example`.

- [ ] **Step 4: Run focused tests and static checks**

Run: `uv run pytest -q tests/agents/test_config_and_model_client.py; uv run ruff check .; uv run mypy src`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/pyproject.toml backend/uv.lock backend/.env.example backend/src/werewolf_arena/agents backend/tests/agents/test_config_and_model_client.py
git commit -m "feat: add async openai compatible client"
```

### Task 2: Define safe observations, decisions, memory, and deterministic policy tests

**Files:**
- Create: `backend/src/werewolf_arena/agents/models.py`, `backend/src/werewolf_arena/agents/observation.py`, `backend/src/werewolf_arena/agents/policy.py`
- Test: `backend/tests/agents/test_observation_and_policy.py`

**Interfaces:**
- Consumes `AsyncModelClient`, `GameState`, `Participant`, and `GameEvent`.
- Produces `AgentObservation`, `AgentDecision`, `AgentMemory`, `AgentPolicy.decide(observation)`, and `build_observation(state, participant_id)`.
- Later tasks use `AgentDecision.to_command(actor_id)`; actor ID is never supplied by the model.

- [ ] **Step 1: Write failing isolation and parser tests**

```python
async def test_observation_hides_other_roles_and_private_events() -> None:
    observation = build_observation(state_with_seer_secret, "ai-wolf")
    assert "seer" not in observation.model_dump_json()
    assert "inspection_result" not in observation.model_dump_json()

async def test_policy_rewrites_actor_and_falls_back_after_invalid_json() -> None:
    policy = AgentPolicy("ai-1", ScriptedAsyncClient(["not-json", '{"kind":"vote","target_id":"human"}']))
    decision = await policy.decide(observation)
    assert decision.kind is CommandKind.NOOP
    assert decision.failure_kind == "invalid_model_output"
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `uv run pytest -q tests/agents/test_observation_and_policy.py`  
Expected: FAIL because observation/policy interfaces are absent.

- [ ] **Step 3: Implement Pydantic contracts and a scripted client**

```python
class AgentObservation(BaseModel):
    participant_id: str
    phase: Phase
    public_events: tuple[dict[str, object], ...]
    private_facts: dict[str, object]
    legal_kinds: tuple[CommandKind, ...]
    legal_target_ids: tuple[str, ...]
    memory: AgentMemory

class AgentDecision(BaseModel):
    kind: CommandKind
    target_id: str | None = None
    speech: str = ""
    public_reason: str = ""
    failure_kind: str | None = None
```

Build observations from public events plus only recipient-matching private events. Store AI memory under `Participant.private_state["agent_memory"]`; exclude it from all projection output. Parse model JSON once, enforce allowed command/target lists before returning a decision, and return a phase-appropriate `NOOP` decision when parsing fails. Provide `ScriptedAsyncClient` only in test support or the test module.

- [ ] **Step 4: Run focused tests and all existing domain tests**

Run: `uv run pytest -q tests/agents/test_observation_and_policy.py tests/domain`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/agents backend/tests/agents/test_observation_and_policy.py
git commit -m "feat: add isolated agent observation and policy"
```

### Task 3: Complete domain commands for discussion, abstention, and safe skips

**Files:**
- Modify: `backend/src/werewolf_arena/domain/enums.py`, `backend/src/werewolf_arena/domain/engine.py`, `backend/src/werewolf_arena/domain/projection.py`
- Test: `backend/tests/domain/test_discussion_and_safe_commands.py`

**Interfaces:**
- Produces valid `CommandKind.SPEAK`, `CommandKind.END_DISCUSSION`, `CommandKind.ABSTAIN`, and `CommandKind.NOOP` transitions.
- `GameEngine.submit` emits `public_speech`, `discussion_ended`, and safe action events.
- `GameEngine.advance_automatic` resolves a no-op night ability and no-effective-vote day without getting stuck.

- [ ] **Step 1: Write failing full-phase domain tests**

```python
def test_speech_is_public_and_human_ends_discussion_into_vote() -> None:
    state = state.model_copy(update={"phase": Phase.DAY_DISCUSSION})
    state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.SPEAK, text="我怀疑 ai-1"))
    state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.END_DISCUSSION))
    assert state.phase is Phase.DAY_VOTE

def test_abstentions_resolve_without_executing_an_empty_target() -> None:
    result = submit_all_alive(state_in_vote, CommandKind.ABSTAIN)
    assert engine.advance_automatic(result).events[-1].event_type == "vote_no_execution"
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `uv run pytest -q tests/domain/test_discussion_and_safe_commands.py`  
Expected: FAIL because `END_DISCUSSION` and day/no-op handling are absent.

- [ ] **Step 3: Extend the authority engine without bypasses**

Add `END_DISCUSSION` to `CommandKind`; allow `SPEAK` only in `DAY_DISCUSSION` with non-empty bounded text; allow only human/authorized callers to end discussion at the runtime layer while engine validates phase. Let `ABSTAIN` count as a completed day command but not as a target vote. Let `NOOP` complete eligible night-player turns and resolve an unsaved victim normally. Append public events for speech, discussion closure, abstention/no-execution, and existing phase changes. Preserve self-target and duplicate-command rejection.

- [ ] **Step 4: Run domain and projection suites**

Run: `uv run pytest -q tests/domain; uv run ruff check .; uv run mypy src`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/domain backend/tests/domain/test_discussion_and_safe_commands.py
git commit -m "feat: complete discussion and safe game commands"
```

### Task 4: Persist redacted agent-run accounting and durable budget state

**Files:**
- Modify: `backend/src/werewolf_arena/domain/models.py`, `backend/src/werewolf_arena/persistence/models.py`, `backend/src/werewolf_arena/persistence/repository.py`
- Create: `backend/src/werewolf_arena/agents/budget.py`
- Test: `backend/tests/persistence/test_agent_runs.py`, `backend/tests/agents/test_budget.py`

**Interfaces:**
- Produces `AgentBudget`, `AgentUsage`, and `BudgetExceeded`.
- Produces `SQLiteRoomRepository.record_agent_run(room_id, record)` and `agent_runs_for(room_id)`.
- `GameState.agent_usage` is snapshot-persisted, so recovery resumes exact budget totals.

- [ ] **Step 1: Write failing accounting and no-secret persistence tests**

```python
async def test_agent_run_records_metrics_without_prompt_or_raw_response(tmp_path) -> None:
    await repository.record_agent_run(room_id, AgentRunRecord(model="test", status="success", input_tokens=12, output_tokens=4))
    row = (await repository.agent_runs_for(room_id))[0]
    assert row.model == "test"
    assert "raw_prompt" not in row.model_dump_json()

def test_budget_rejects_call_that_exceeds_room_limit() -> None:
    assert budget.reserve(usage, estimated_output_tokens=30).allowed is False
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest -q tests/persistence/test_agent_runs.py tests/agents/test_budget.py`  
Expected: FAIL because accounting and budget models are absent.

- [ ] **Step 3: Add models and repository methods**

```python
class AgentUsage(DomainModel):
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

class AgentRunRecord(BaseModel):
    participant_id: str
    model: str
    status: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    failure_kind: str | None = None
```

Add `AgentRunRow` with room ID, sequence/attempt ID, participant ID, metrics, status, and failure kind only. Add `agent_usage: AgentUsage` to `GameState`. Budget reservation occurs before a remote call; usage update and `AgentRunRecord` persistence happen in the same runtime lock after each attempt. Do not add prompt/raw-response columns.

- [ ] **Step 4: Run persistence, agent, and full state serialization tests**

Run: `uv run pytest -q tests/persistence tests/agents tests/domain/test_models.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/domain/models.py backend/src/werewolf_arena/persistence backend/src/werewolf_arena/agents/budget.py backend/tests/persistence/test_agent_runs.py backend/tests/agents/test_budget.py
git commit -m "feat: persist agent usage and run metrics"
```

### Task 5: Implement orchestrated AI turns and room-level automatic progression

**Files:**
- Create: `backend/src/werewolf_arena/agents/orchestrator.py`
- Modify: `backend/src/werewolf_arena/runtime/room_runtime.py`, `backend/src/werewolf_arena/runtime/registry.py`, `backend/src/werewolf_arena/api/app.py`
- Test: `backend/tests/runtime/test_agent_orchestration.py`

**Interfaces:**
- Consumes `AgentPolicy`, `AgentBudget`, `SQLiteRoomRepository`, and `GameEngine`.
- Produces `GameOrchestrator.advance(state: GameState) -> OrchestrationResult` where `OrchestrationResult` has `state`, `waiting_for_human`, and `human_actions`.
- Produces `RoomRuntime.advance_until_waiting()` and changes `RoomRuntime.submit()` to return `RuntimeResult` with `state`, `new_events`, and wait metadata.

- [ ] **Step 1: Write failing runtime flow tests**

```python
async def test_orchestrator_drives_ai_until_the_human_is_the_seer() -> None:
    result = await runtime.advance_until_waiting()
    assert result.waiting_for_human is True
    assert result.human_actions == (CommandKind.INSPECT, CommandKind.NOOP)

async def test_restart_does_not_repeat_a_persisted_ai_model_call() -> None:
    await runtime.advance_until_waiting()
    resumed = await RoomRuntime.resume(engine, repository, room_id, orchestrator)
    await resumed.advance_until_waiting()
    assert scripted_client.call_count == 1
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest -q tests/runtime/test_agent_orchestration.py`  
Expected: FAIL because no orchestrator or runtime advance interface exists.

- [ ] **Step 3: Implement phase dispatch and failure-safe decisions**

`GameOrchestrator` determines alive actors for the current phase. It pauses if the human is required; otherwise it calls the matching AI policy sequentially, records usage, converts a decision to a command, submits it to `GameEngine`, and advances automatic rules. For AI wolves, choose one living AI wolf as coordinator and mirror its target for the second wolf; if human is a wolf, add the AI suggestion as a private event and pause until the human target is received. In discussion, emit one speech per alive AI in seat order; after human speech, emit at most one AI reply. Use safe decisions when model/budget validation fails. Persist and publish after each applied command, never after an uncommitted in-memory step.

- [ ] **Step 4: Run runtime and full automated suites**

Run: `uv run pytest -q tests/runtime tests/domain tests/persistence; uv run ruff check .; uv run mypy src`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/agents/orchestrator.py backend/src/werewolf_arena/runtime backend/src/werewolf_arena/api/app.py backend/tests/runtime/test_agent_orchestration.py
git commit -m "feat: orchestrate automated agent turns"
```

### Task 6: Expose safe human wait states, automatic continuation, and browser-ready session cookies

**Files:**
- Modify: `backend/src/werewolf_arena/domain/projection.py`, `backend/src/werewolf_arena/api/schemas.py`, `backend/src/werewolf_arena/api/dependencies.py`, `backend/src/werewolf_arena/api/routes/rooms.py`, `backend/src/werewolf_arena/api/routes/events.py`
- Test: `backend/tests/api/test_agent_rooms.py`, `backend/tests/api/test_events.py`

**Interfaces:**
- `project_state(state, viewer, runtime_status)` adds only `waiting_for_human`, `human_actions`, `legal_target_ids`, and safe phase text.
- `POST /api/rooms/{room_id}/continue` returns the same safe result shape as command submission.
- `create_room` sets `werewolf_room_session` cookie with `httponly=True`, `samesite="lax"`, and `path=f"/api/rooms/{room_id}"`.

- [ ] **Step 1: Write failing API security and auto-advance tests**

```python
def test_create_room_auto_advances_and_sets_room_scoped_cookie(client) -> None:
    response = client.post("/api/rooms", json={"requested_role_id": "seer"})
    assert response.cookies["werewolf_room_session"]
    assert response.json()["state"]["waiting_for_human"] is True
    assert "agent_memory" not in response.text

def test_continue_accepts_cookie_but_foreign_cookie_is_forbidden(client) -> None:
    assert client.post(f"/api/rooms/{room_id}/continue").status_code == 200
    assert foreign_client.post(f"/api/rooms/{room_id}/continue").status_code == 403
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest -q tests/api/test_agent_rooms.py tests/api/test_events.py`  
Expected: FAIL because continuation, wait metadata, and cookie authentication do not exist.

- [ ] **Step 3: Implement response projection and endpoints**

Add a cookie fallback to `require_room_session` and WebSocket `_bearer_token` without accepting raw tokens in query parameters. Make creation call `advance_until_waiting`; make command submission call it after a valid human command; add `continue` for explicit restart recovery. Compute legal human command kinds/targets from current authority state and viewer role, but never include AI role/resource/memory fields. Return rejected human commands as 422 without losing their already-audited rejection event.

- [ ] **Step 4: Run API, runtime, and security tests**

Run: `uv run pytest -q tests/api tests/runtime; uv run ruff check .; uv run mypy src`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/werewolf_arena/domain/projection.py backend/src/werewolf_arena/api backend/tests/api
git commit -m "feat: expose automated room continuation api"
```

### Task 7: Add a real-model smoke entry point and Phase 3 operational documentation

**Files:**
- Create: `backend/scripts/smoke_real_game.py`
- Modify: `backend/README.md`, `backend/.env.example`, `README.md`, `docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md`
- Test: `backend/tests/agents/test_smoke_configuration.py`

**Interfaces:**
- `python scripts/smoke_real_game.py --requested-role villager --max-agent-calls 8` requires complete `.env` and creates no browser-visible raw model artifact.
- Documentation states that this smoke command is opt-in and may incur provider charges.

- [ ] **Step 1: Write failing no-network-by-default smoke tests**

```python
def test_smoke_command_refuses_missing_configuration_without_network(monkeypatch) -> None:
    result = run_smoke_subprocess_without_llm_environment()
    assert result.returncode != 0
    assert "LLM_API_KEY" in result.stderr
    assert "secret" not in result.stderr
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `uv run pytest -q tests/agents/test_smoke_configuration.py`  
Expected: FAIL because the smoke entry point is absent.

- [ ] **Step 3: Implement only an explicit opt-in smoke command**

Create an app/runtime with a temporary SQLite path, fail fast on incomplete settings, execute `advance_until_waiting`, and print only room ID, phase, wait status, total agent calls, token usage, and redacted failures. Do not execute this script in normal CI. Document `uv sync --all-groups`, server startup, `.env` setup, optional smoke command, budget/cost warning, and Phase 3 completion status.

- [ ] **Step 4: Run the entire verification gate**

Run: `uv sync --all-groups; uv run pytest -q; uv run ruff check .; uv run mypy src; git diff --check`  
Expected: PASS with all normal tests offline.

- [ ] **Step 5: Commit**

```powershell
git add backend/scripts/smoke_real_game.py backend/README.md backend/.env.example README.md docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md backend/tests/agents/test_smoke_configuration.py
git commit -m "docs: describe phase three agent runtime"
```

## Plan Self-Review

- **Spec coverage:** Tasks 1-2 cover configuration, client, JSON contracts, memory, and information isolation. Task 3 supplies the missing game commands required for a full loop. Task 4 provides durable budgets and redacted accounting. Task 5 provides AI orchestration, human pauses, persistence, restart safety, and wolf coordination. Task 6 provides safe REST/WebSocket state and browser-compatible room cookies. Task 7 supplies opt-in real-model smoke verification and operational documentation.
- **Placeholder scan:** This plan contains no deferred implementation markers; every task names files, interfaces, test command, implementation requirement, and commit.
- **Type consistency:** `AsyncModelClient` flows from Task 1 to `AgentPolicy` in Task 2 and into `GameOrchestrator` in Task 5. `AgentDecision` is converted to `GameCommand` only within the orchestrator. `RuntimeResult` created in Task 5 is consumed by Task 6.

## Execution Mode

The user previously selected inline execution for this project. Execute the tasks in this session using `superpowers:executing-plans`, with a fresh test/verification/commit cycle for each task.
