# Werewolf Arena Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, server-authoritative and plugin-extensible six-player Werewolf domain core that can create and advance a complete standard game without a Web API, database, browser or real LLM.

**Architecture:** This phase creates the backend package boundary and the pure domain layer. `GameEngine` owns `GameState` and emits append-only `GameEvent` values; policies only submit typed `GameCommand` values. `RolePlugin` instances declare roles and abilities, while the engine validates every command and applies only validated effect proposals. An in-memory event list proves the contract that later SQLite repositories, FastAPI endpoints and WebSocket projections will persist and expose.

**Tech Stack:** Python `>=3.12,<3.15` (Python 3.14.3 is available locally), uv, FastAPI, Pydantic v2, pytest, ruff, mypy. This phase uses no network model call and no frontend dependency.

**Spec:** `docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md`

## Global Constraints

- Keep source under `backend/src/werewolf_arena/`; tests under `backend/tests/`.
- Python domain code must not import FastAPI, SQLAlchemy, React, environment variables or model SDKs.
- The browser/API boundary is not implemented in this phase; no domain type may serialize a complete state as a player view.
- Model output and plugins can only produce commands or effect proposals; only `GameEngine` changes a `GameState`.
- Standard mode has exactly six seats: 2 wolves, 1 seer, 1 witch and 2 villagers.
- Use `UUID` game IDs and event IDs; event sequence numbers start at `1` and strictly increase by one.
- Store all role IDs, mode IDs and plugin versions as stable strings; never use Python class names as persistence identifiers.
- User-visible fields and docstrings are Chinese; internal identifiers remain English and type-annotated.
- Every task follows red-green-refactor: add a focused failing pytest, run it, add the smallest implementation, rerun focused tests and then the phase suite.
- Each task ends with the exact commit shown in that task. Do not mix unrelated files into a commit.

---

## Delivery map

| Phase | Deliverable | Depends on | Exit evidence |
|---|---|---|---|
| 1 (this plan) | Pure rules core, standard roles, plugin registry, event log and viewer projection | None | `pytest` proves complete deterministic standard games and information isolation. |
| 2 | SQLite repositories, snapshots, local sessions, FastAPI REST/WebSocket room runtime | Phase 1 | Restart/reconnect tests preserve event sequence and viewer permissions. |
| 3 | OpenAI-compatible Agent Runtime, private memory, wolf consultation, budgets and safe fallback | Phase 2 | Scripted and optional live-model games complete without secret or private-memory leakage. |
| 4 | React/TypeScript monthlight UI: lobby, game, death spectator, result and replay | Phase 2 event API | Browser end-to-end tests prove a human can finish a game. |
| 5 | Integration hardening, visual polish, docs and local one-command run | Phases 1-4 | Full test suite, smoke-test report and manual acceptance checklist pass. |

## Phase 1 file structure

```text
backend/
  pyproject.toml
  src/werewolf_arena/
    __init__.py
    domain/
      __init__.py
      enums.py              # Faction, Phase, GameStatus, visibility and command kinds
      models.py             # immutable state, participants, commands, events and effects
      errors.py             # domain-specific validation errors
      mode.py               # GameMode plus roster validation
      engine.py             # creation, validation, phase resolution and winner calculation
      projection.py         # safe viewer projections; never exposes GameState directly
    roles/
      __init__.py
      base.py               # RolePlugin protocol and declarative ability contract
      registry.py           # trusted startup registry and version validation
      standard.py           # wolf, seer, witch and villager built-in plugins
  tests/
    conftest.py
    domain/
      test_models.py
      test_mode_and_registry.py
      test_standard_game_engine.py
      test_projection.py
```

The `backend/` directory deliberately has its own Python package and dependency manifest. A future `frontend/` directory will be a separate Node workspace; neither is created in this phase because the domain core needs no JavaScript to be independently testable.

### Task 1: Establish the backend package and quality gates

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/werewolf_arena/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/domain/test_models.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces an importable `werewolf_arena` package.
- Produces the commands `uv run pytest`, `uv run ruff check .`, `uv run mypy src` when executed from `backend/`.

- [ ] **Step 1: Write the failing package-import test**

```python
# backend/tests/domain/test_models.py
def test_package_exposes_version() -> None:
    import werewolf_arena

    assert werewolf_arena.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the test and verify collection fails**

Run: `cd backend; uv run pytest tests/domain/test_models.py::test_package_exposes_version -q`

Expected: FAIL because the package and project manifest do not exist.

- [ ] **Step 3: Add the minimal backend manifest and package marker**

```toml
# backend/pyproject.toml
[project]
name = "werewolf-arena"
version = "0.1.0"
requires-python = ">=3.12,<3.15"
dependencies = ["fastapi>=0.115,<1", "pydantic>=2.10,<3"]

[dependency-groups]
dev = ["mypy>=1.13,<2", "pytest>=8.3,<9", "ruff>=0.8,<1"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
packages = ["werewolf_arena"]
```

```python
# backend/src/werewolf_arena/__init__.py
"""Werewolf Arena server-authoritative game package."""

__version__ = "0.1.0"
```

Add `.pytest_cache/`, `.mypy_cache/` and `.ruff_cache/` to `.gitignore`.

- [ ] **Step 4: Run package and quality checks**

Run: `cd backend; uv sync --all-groups; uv run pytest -q; uv run ruff check .; uv run mypy src`

Expected: all commands exit with code `0`.

- [ ] **Step 5: Commit the package boundary**

```bash
git add .gitignore backend/pyproject.toml backend/src/werewolf_arena/__init__.py backend/tests
git commit -m "build: initialize backend domain package"
```

### Task 2: Define immutable domain values and the append-only event contract

**Files:**
- Create: `backend/src/werewolf_arena/domain/__init__.py`
- Create: `backend/src/werewolf_arena/domain/enums.py`
- Create: `backend/src/werewolf_arena/domain/models.py`
- Create: `backend/src/werewolf_arena/domain/errors.py`
- Modify: `backend/tests/domain/test_models.py`

**Interfaces:**
- Produces `Faction`, `Phase`, `GameStatus`, `Visibility`, `CommandKind` and `EffectKind` string enums.
- Produces frozen Pydantic models `Participant`, `GameCommand`, `EffectProposal`, `GameEvent` and `GameState`.
- `GameState.append_event(event_type: str, payload: dict[str, object], visibility: Visibility, recipient_ids: frozenset[str] = frozenset()) -> GameState` returns a copied state whose new event sequence is exactly prior count plus one.

- [ ] **Step 1: Write focused failing event tests**

```python
def test_append_event_assigns_monotonic_sequence() -> None:
    state = GameState.empty(game_id=UUID("00000000-0000-0000-0000-000000000001"))

    state = state.append_event("game_created", {}, Visibility.SERVER)
    state = state.append_event("phase_changed", {"phase": "night_wolf"}, Visibility.PUBLIC)

    assert [event.sequence for event in state.events] == [1, 2]
    assert state.events[1].visibility is Visibility.PUBLIC


def test_private_event_requires_recipient() -> None:
    state = GameState.empty()

    with pytest.raises(DomainValidationError, match="recipient"):
        state.append_event("inspection", {}, Visibility.PRIVATE)
```

- [ ] **Step 2: Run the focused tests and verify imports fail**

Run: `cd backend; uv run pytest tests/domain/test_models.py -q`

Expected: FAIL because `GameState`, `Visibility` and `DomainValidationError` are unavailable.

- [ ] **Step 3: Implement typed immutable values**

Implement enums as `class X(str, Enum)`. Use Pydantic `ConfigDict(frozen=True)` for domain models. `GameEvent` must include `event_id: UUID`, `sequence: int`, `event_type: str`, `payload: dict[str, object]`, `visibility: Visibility`, and `recipient_ids: frozenset[str]`. `GameState` must include `game_id`, `mode_id`, `mode_version`, `phase`, `status`, `round_number`, `participants`, `events`, `pending_commands`, and `winner_faction`.

`append_event` must reject a private visibility event with an empty recipient set and must allocate sequence as `len(self.events) + 1`; it must not mutate the original state.

- [ ] **Step 4: Run domain model checks**

Run: `cd backend; uv run pytest tests/domain/test_models.py -q; uv run ruff check src tests; uv run mypy src`

Expected: all commands exit with code `0`.

- [ ] **Step 5: Commit the event contract**

```bash
git add backend/src/werewolf_arena/domain backend/tests/domain/test_models.py
git commit -m "feat: add immutable game event domain models"
```

### Task 3: Add the trusted role plugin registry and standard game mode validation

**Files:**
- Create: `backend/src/werewolf_arena/domain/mode.py`
- Create: `backend/src/werewolf_arena/roles/__init__.py`
- Create: `backend/src/werewolf_arena/roles/base.py`
- Create: `backend/src/werewolf_arena/roles/registry.py`
- Create: `backend/src/werewolf_arena/roles/standard.py`
- Create: `backend/tests/domain/test_mode_and_registry.py`

**Interfaces:**
- `RoleDefinition(role_id: str, version: str, faction: Faction, display_name: str, ability_ids: tuple[str, ...])`.
- `AbilityDefinition(ability_id: str, phase: Phase, command_kind: CommandKind, max_uses: int, allow_self_target: bool)`.
- `RolePlugin` protocol: `definition`, `abilities`, `initial_private_state(participant_id: str) -> dict[str, object]`, `propose_effects(state: GameState, command: GameCommand) -> tuple[EffectProposal, ...]`.
- `RoleRegistry.register(plugin: RolePlugin) -> None`, `get(role_id: str, version: str) -> RolePlugin`.
- `GameMode.validate(registry: RoleRegistry) -> None`; `standard_six_player_mode() -> GameMode`.

- [ ] **Step 1: Write failing registry and roster-validation tests**

```python
def test_standard_mode_has_exact_six_valid_role_slots() -> None:
    registry = standard_role_registry()
    mode = standard_six_player_mode()

    mode.validate(registry)

    assert mode.player_count == 6
    assert Counter(mode.role_slots) == Counter(
        {"wolf": 2, "seer": 1, "witch": 1, "villager": 2}
    )


def test_registry_rejects_replacing_same_role_version() -> None:
    registry = RoleRegistry()
    registry.register(VillagerPlugin())

    with pytest.raises(DomainValidationError, match="already registered"):
        registry.register(VillagerPlugin())
```

- [ ] **Step 2: Run registry tests and verify they fail**

Run: `cd backend; uv run pytest tests/domain/test_mode_and_registry.py -q`

Expected: FAIL because the roles and mode modules do not exist.

- [ ] **Step 3: Implement declarative plugins and validation**

`RoleRegistry` must be an in-memory trusted startup registry keyed by `(role_id, version)` and reject duplicate keys. `GameMode.validate` must reject an empty role ID, a role-slot count that differs from `player_count`, missing registered plugin versions, and a roster lacking both the `good` and `wolf` factions. Repeated role IDs are valid because the standard roster intentionally contains two wolves and two villagers.

Implement built-ins with stable IDs and version `"1.0.0"`: `wolf` (night kill), `seer` (night inspect), `witch` (night save and night poison, one use each) and `villager` (no ability). Do not put winner logic in a plugin.

- [ ] **Step 4: Run plugin tests and the phase suite**

Run: `cd backend; uv run pytest -q; uv run ruff check .; uv run mypy src`

Expected: all commands exit with code `0`.

- [ ] **Step 5: Commit plugin infrastructure**

```bash
git add backend/src/werewolf_arena/domain/mode.py backend/src/werewolf_arena/roles backend/tests/domain/test_mode_and_registry.py
git commit -m "feat: add versioned role plugin registry"
```

### Task 4: Implement authoritative game creation, command validation and phase resolution

**Files:**
- Create: `backend/src/werewolf_arena/domain/engine.py`
- Create: `backend/tests/domain/test_standard_game_engine.py`
- Modify: `backend/src/werewolf_arena/domain/models.py`
- Modify: `backend/src/werewolf_arena/roles/standard.py`

**Interfaces:**
- `GameEngine(registry: RoleRegistry, mode: GameMode, seed: int)`.
- `GameEngine.create_game(human_participant_id: str, requested_role_id: str | None) -> GameState`.
- `GameEngine.submit(state: GameState, command: GameCommand) -> GameState`.
- `GameEngine.advance_automatic(state: GameState) -> GameState` advances only phases that do not await the human participant.
- `GameEngine.legal_commands(state: GameState, participant_id: str) -> tuple[CommandKind, ...]`.

- [ ] **Step 1: Write failing end-to-end domain tests**

```python
def test_requested_human_role_is_reserved_and_roster_is_valid() -> None:
    engine = standard_engine(seed=7)

    state = engine.create_game("human", requested_role_id="seer")

    human = next(player for player in state.participants if player.participant_id == "human")
    assert human.role_id == "seer"
    assert len(state.participants) == 6
    assert sum(player.role_id == "wolf" for player in state.participants) == 2


def test_dead_participant_command_is_rejected_without_state_change() -> None:
    state = state_with_dead_participant("human")
    command = GameCommand(actor_id="human", kind=CommandKind.VOTE, target_id="ai-1")

    result = standard_engine().submit(state, command)

    assert result.events[-1].event_type == "command_rejected"
    assert result.pending_commands == state.pending_commands
```

- [ ] **Step 2: Run engine tests and verify they fail**

Run: `cd backend; uv run pytest tests/domain/test_standard_game_engine.py -q`

Expected: FAIL because `GameEngine` is unavailable.

- [ ] **Step 3: Implement creation and validation before effects**

`create_game` must use `random.Random(seed)` and reserve `requested_role_id` for the human only if that role exists in the mode roster. When role is `None`, shuffle the complete roster deterministically. It must emit `game_created` as server-only and `phase_changed` as public events.

`submit` must append `command_rejected` rather than raise for client/model-invalid commands. Validation must reject unknown actors, dead actors, wrong phase, wrong role, unavailable ability, duplicate command, invalid target, self-target when prohibited and exhausted resource. Rejected commands must not alter participants, private resources or accepted pending commands.

- [ ] **Step 4: Implement deterministic phase resolution and winner checks**

Implement these standard phases: `NIGHT_WOLF`, `NIGHT_SEER`, `NIGHT_WITCH`, `DAY_DISCUSSION`, `DAY_VOTE`, `FINISHED`. Wolves each submit a kill intent; a kill succeeds only when both living wolves choose the same living non-wolf target. The seer receives a private inspection result. The witch may save the pending victim or poison one legal target; each potion is single-use and both cannot be used on the same night. Day vote executes the unique highest target; a tie executes nobody.

After night and vote resolution, apply deaths and call `check_winner`: good wins when no wolves remain; wolves win when living wolves are at least living good players; otherwise continue. Every resolution writes explicit event types and correct visibility.

- [ ] **Step 5: Run complete core tests**

Run: `cd backend; uv run pytest tests/domain/test_standard_game_engine.py -q; uv run pytest -q; uv run ruff check .; uv run mypy src`

Expected: all commands exit with code `0`.

- [ ] **Step 6: Commit the standard authoritative game**

```bash
git add backend/src/werewolf_arena/domain/engine.py backend/src/werewolf_arena/domain/models.py backend/src/werewolf_arena/roles/standard.py backend/tests/domain/test_standard_game_engine.py
git commit -m "feat: implement authoritative standard game engine"
```

### Task 5: Add permission-safe viewer projection and deterministic replay verification

**Files:**
- Create: `backend/src/werewolf_arena/domain/projection.py`
- Create: `backend/tests/domain/test_projection.py`
- Modify: `backend/src/werewolf_arena/domain/engine.py`
- Modify: `backend/tests/domain/test_standard_game_engine.py`

**Interfaces:**
- `ViewerKind` enum values: `ALIVE_HUMAN`, `DEAD_SPECTATOR`, `FINISHED_REPLAY`.
- `ViewerContext(participant_id: str, kind: ViewerKind)`.
- `project_state(state: GameState, viewer: ViewerContext) -> dict[str, object]`.
- `project_events(events: tuple[GameEvent, ...], viewer: ViewerContext, state: GameState) -> tuple[dict[str, object], ...]`.
- `replay(initial_state: GameState, accepted_commands: tuple[GameCommand, ...], engine: GameEngine) -> GameState` for deterministic test verification only.

- [ ] **Step 1: Write failing privacy and replay tests**

```python
def test_alive_villager_cannot_receive_wolf_identity_or_private_seer_event() -> None:
    state = state_after_private_seer_inspection()
    view = project_state(state, ViewerContext("villager-human", ViewerKind.ALIVE_HUMAN))
    events = project_events(state.events, ViewerContext("villager-human", ViewerKind.ALIVE_HUMAN), state)

    assert "role_id" not in view["participants"]["wolf-ai"]
    assert all(event["event_type"] != "inspection_result" for event in events)


def test_dead_human_sees_only_public_events_until_finished() -> None:
    state = state_after_human_death()
    events = project_events(state.events, ViewerContext("human", ViewerKind.DEAD_SPECTATOR), state)

    assert all(event["visibility"] == "public" for event in events)
```

- [ ] **Step 2: Run projection tests and verify they fail**

Run: `cd backend; uv run pytest tests/domain/test_projection.py -q`

Expected: FAIL because projection interfaces do not exist.

- [ ] **Step 3: Implement field allow-lists, not field deny-lists**

Construct projection dictionaries explicitly. For an alive player, include each participant's public ID, display name, alive status and public vote; include the viewer's own role and permitted private resources only. Include wolf teammate identity only when the viewer is a living wolf. A dead spectator receives public participant fields and public events only. A finished replay receives complete role identities and event payloads, but removes `raw_prompt`, `raw_model_response`, `secret`, `api_key` and `chain_of_thought` keys recursively if present.

Never return a Pydantic `model_dump()` of `GameState`, `Participant` or a private event directly.

- [ ] **Step 4: Add deterministic complete-game replay test**

Drive a complete standard game with scripted legal commands, collect accepted commands, replay them from a seed-equivalent initial state, and assert equal phase, status, winner faction, participant alive flags and event type/sequence pairs. This test guarantees later persistence can recover without a new model call.

- [ ] **Step 5: Run security and full phase checks**

Run: `cd backend; uv run pytest -q; uv run ruff check .; uv run mypy src`

Expected: all commands exit with code `0`.

- [ ] **Step 6: Commit projection and replay contracts**

```bash
git add backend/src/werewolf_arena/domain/projection.py backend/src/werewolf_arena/domain/engine.py backend/tests/domain/test_projection.py backend/tests/domain/test_standard_game_engine.py
git commit -m "feat: add permission-safe game projections"
```

### Task 6: Document the phase-one executable and run the final gate

**Files:**
- Modify: `README.md`
- Create: `backend/README.md`
- Modify: `docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md`

**Interfaces:**
- Documents the Phase 1 core as an internal deterministic library, not yet a browser application.
- Documents exact verification commands and explicitly identifies Phase 2 as the point where API, SQLite and WebSocket work begins.

- [ ] **Step 1: Add documentation assertions as a smoke-test command list**

In `backend/README.md`, include exactly these commands:

```powershell
cd backend
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run mypy src
```

State that a passing Phase 1 build has no HTTP server, no browser UI, no database and no real model call by design.

- [ ] **Step 2: Run the final Phase 1 gate**

Run: `cd backend; uv run pytest -q; uv run ruff check .; uv run mypy src`

Expected: all commands exit with code `0`; record the command outputs in the implementation handoff message, not in source files.

- [ ] **Step 3: Commit final Phase 1 documentation**

```bash
git add README.md backend/README.md docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md
git commit -m "docs: describe phase one domain core"
```

## Phase 1 acceptance gate

Phase 1 is complete only when all six task commits exist and the final command suite passes. The resulting code must create a deterministic six-player game, reserve or randomly assign the human role, reject illegal commands as events, resolve all standard role actions, determine a winner, support a versioned role registry, and project data without leaking other players' private information. It intentionally stops before SQLite, FastAPI, WebSocket, real LLMs and React; those are the independently reviewable deliverables of Phases 2 through 5.
