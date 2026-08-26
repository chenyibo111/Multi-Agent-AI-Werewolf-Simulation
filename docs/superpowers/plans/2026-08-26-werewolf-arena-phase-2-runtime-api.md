# Werewolf Arena Phase 2 Runtime and API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task with red-green-refactor and a commit after each task.

**Goal:** Persist local rooms in SQLite and expose a server-authoritative FastAPI/ WebSocket interface that creates, resumes and safely projects a single human player's game.

**Architecture:** SQLAlchemy repositories persist authority-only snapshots and append-only events. A per-room `GameRuntime` serializes commands behind an `asyncio.Lock`, saves after accepted work, and emits permission-filtered event envelopes. FastAPI authenticates a random local session token before invoking the runtime; REST loads state and submits commands, while WebSocket reconnects from a public event sequence.

**Tech Stack:** Python `>=3.12,<3.15`, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, aiosqlite, pytest, httpx, pytest-asyncio, uvicorn.

**Spec:** `docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md`

## Global constraints

- Implement only local SQLite and local session tokens; do not add accounts, cloud deployment, real LLM calls or React.
- `domain/` remains independent of FastAPI and SQLAlchemy.
- Complete snapshots/events are never returned from HTTP or WebSocket; always call `project_state` and `project_events`.
- Store the session token only as a SHA-256 hash; return its raw value once at room creation.
- A room runtime serializes every command and snapshots state after an accepted command or phase advancement.
- WebSocket reconnect requires `after_sequence`; only events authorized for that session may be replayed.

## Files and responsibilities

```text
backend/src/werewolf_arena/
  persistence/database.py       # engine/session factory and schema initialization
  persistence/models.py         # SQLAlchemy room, snapshot, event and session tables
  persistence/repository.py     # RoomRepository interface and SQLite implementation
  runtime/room_runtime.py       # lock, load/save, command dispatch and event subscribers
  api/app.py                    # FastAPI factory, lifespan and CORS
  api/schemas.py                # request/response models without authority fields
  api/dependencies.py           # bearer-token/session authorization
  api/routes/rooms.py           # create/get/submit/delete endpoints
  api/routes/events.py          # WebSocket subscription endpoint
backend/tests/
  persistence/test_repository.py
  runtime/test_room_runtime.py
  api/test_rooms.py
  api/test_events.py
```

### Task 1: Add persistence dependencies and schema-tested SQLite repository

**Files:** modify `backend/pyproject.toml`; create the three `persistence/` modules and `tests/persistence/test_repository.py`.

- [ ] Write a failing test that saves a room snapshot plus two authority events, reloads by room ID, and asserts snapshot fields, event sequence and plugin/mode versions match.
- [ ] Run `uv run pytest tests/persistence/test_repository.py -q`; expect import failure.
- [ ] Add SQLAlchemy/Alembic/aiosqlite dependencies, create tables `rooms`, `game_snapshots`, `game_events`, `player_sessions`, and implement `SQLiteRoomRepository.create_room`, `save_state`, `load_state`, `events_after`, `delete_room`.
- [ ] Serialize `GameState` through explicit JSON codecs; do not pickle domain objects.
- [ ] Run focused and full test/lint/type commands; commit `feat: add sqlite room repository`.

### Task 2: Add local session issuance and room ownership checks

**Files:** modify `persistence/models.py` and `repository.py`; create `tests/persistence/test_sessions.py`.

- [ ] Write failing tests that creation returns one raw token, database stores only its hash, and another token cannot read the room.
- [ ] Run focused test and confirm failure.
- [ ] Implement `issue_session`, `authorize_session`, `revoke_room_sessions` using `secrets.token_urlsafe` and SHA-256 digest comparison.
- [ ] Run all persistence tests/lint/types; commit `feat: add local room session authorization`.

### Task 3: Add serialized room runtime, snapshots and resume

**Files:** create `runtime/room_runtime.py`, `tests/runtime/test_room_runtime.py`.

- [ ] Write failing async tests that concurrent submissions are serialized, an accepted command saves a snapshot, and a new runtime instance reloads the same state without duplicating events.
- [ ] Run focused test and confirm failure.
- [ ] Implement `RoomRuntime.submit`, `get_state`, `resume`, `subscribe`, and per-room `asyncio.Lock`; reject unknown/dead/invalid commands through existing domain events.
- [ ] Emit runtime envelopes only after projection; raw `GameState` never enters subscriber queues.
- [ ] Run all tests/lint/types; commit `feat: add serialized room runtime`.

### Task 4: Add FastAPI room REST endpoints

**Files:** create `api/app.py`, `api/schemas.py`, `api/dependencies.py`, `api/routes/rooms.py`, `tests/api/test_rooms.py`.

- [ ] Write failing API tests for `POST /api/rooms`, `GET /api/rooms/{id}`, `POST /api/rooms/{id}/commands`, and delete; assert responses omit other identities and reject missing/foreign bearer tokens with 401/403.
- [ ] Run focused test and confirm failure.
- [ ] Implement an app factory receiving a repository/runtime registry, strict localhost CORS, Pydantic request schemas, bearer authorization and status mapping for rejected commands.
- [ ] Use `project_state`/`project_events` for every success payload.
- [ ] Run all tests/lint/types; commit `feat: add local room REST api`.

### Task 5: Add WebSocket reconnect and permission-filtered event streaming

**Files:** create `api/routes/events.py`, modify `api/app.py`, create `tests/api/test_events.py`.

- [ ] Write failing tests that a connected human receives only projected public/own-private events, reconnect with `after_sequence` receives missing allowed events, and a foreign token is closed with 1008.
- [ ] Run focused test and confirm failure.
- [ ] Implement `/api/rooms/{room_id}/events?after_sequence=N`, authorization before accept, catch-up from `events_after`, then runtime subscriber streaming with monotonically increasing sequence.
- [ ] Run all tests/lint/types; commit `feat: add room websocket event stream`.

### Task 6: Document and verify Phase 2 local server

**Files:** modify `README.md`, `backend/README.md`, specification status; add `.env.example` without secrets.

- [ ] Document `uv run uvicorn werewolf_arena.api.app:create_app --factory --reload` and a curl-free browser/API verification flow.
- [ ] Run `uv sync --all-groups`, `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`, `git diff --check`.
- [ ] Commit `docs: describe phase two local runtime api`.

## Acceptance gate

Phase 2 is complete when a local client can create a room, receive a one-time session token, load only its authorized view, submit a command, reconnect to a permission-filtered WebSocket event stream, restart the server and resume from SQLite without duplicate events. No raw authority snapshot, secret, other-player identity or private event may cross the API boundary.
