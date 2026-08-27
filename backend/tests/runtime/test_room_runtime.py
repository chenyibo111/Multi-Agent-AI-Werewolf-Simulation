"""Behaviour tests for the serialized, persistent room runtime."""

from __future__ import annotations

import asyncio

import pytest

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand, GameState
from werewolf_arena.domain.projection import ViewerContext, ViewerKind
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry
from werewolf_arena.runtime.room_runtime import RoomRuntime


def test_runtime_serializes_commands_persists_snapshot_and_resumes(tmp_path) -> None:
    """Concurrent commands are serialized, durable, and do not replay events twice."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        initial_state = engine.create_game("human", requested_role_id="wolf")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(initial_state)
        runtime = RoomRuntime(engine, repository, initial_state)

        first = GameCommand(actor_id="human", kind=CommandKind.WOLF_KILL, target_id="ai-1")
        second = GameCommand(actor_id="human", kind=CommandKind.WOLF_KILL, target_id="ai-2")
        await asyncio.gather(runtime.submit(first), runtime.submit(second))

        persisted = await repository.load_state(initial_state.game_id)
        assert len(persisted.pending_commands) == 1
        assert persisted.events[-1].event_type == "command_rejected"

        resumed = await RoomRuntime.resume(engine, repository, initial_state.game_id)
        resumed_state = await resumed.get_state()
        assert resumed_state == persisted
        assert len(resumed_state.events) == len(persisted.events)

    asyncio.run(scenario())


def test_runtime_subscribers_receive_only_projected_event_envelopes(tmp_path) -> None:
    """Subscriber queues never expose an authority GameState or server-only event."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        runtime = RoomRuntime(engine, repository, state)
        viewer = ViewerContext("human", ViewerKind.ALIVE_HUMAN)
        queue = runtime.subscribe(viewer)

        result = await runtime.submit(
            GameCommand(actor_id="human", kind=CommandKind.WOLF_KILL, target_id="ai-1")
        )
        envelope = await queue.get()

        assert result.events[-1].event_type == "command_rejected"
        assert envelope == {
            "type": "events",
            "events": (
                {
                    "sequence": result.events[-1].sequence,
                    "event_type": "command_rejected",
                    "payload": {"actor_id": "human", "reason": "wrong_role"},
                    "visibility": "public",
                },
            ),
        }
        assert not isinstance(envelope, GameState)
        runtime.unsubscribe(queue)

    asyncio.run(scenario())


def test_runtime_updates_a_subscriber_to_global_view_after_their_death(tmp_path) -> None:
    """A connected human receives newly visible private events immediately after dying."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        runtime = RoomRuntime(engine, repository, state)
        queue = runtime.subscribe(ViewerContext("human", ViewerKind.ALIVE_HUMAN))
        dead_state = state.model_copy(
            update={
                "participants": tuple(
                    player.model_copy(update={"alive": False}) if player.participant_id == "human" else player
                    for player in state.participants
                )
            }
        ).append_event(
            "inspection_result",
            {"target_id": "ai-1", "is_wolf": True},
            Visibility.PRIVATE,
            frozenset({"ai-1"}),
        )

        runtime._state = dead_state
        runtime._publish((dead_state.events[-1],), dead_state)

        assert await asyncio.wait_for(queue.get(), timeout=0.1) == {
            "type": "events",
            "events": (
                {
                    "sequence": dead_state.events[-1].sequence,
                    "event_type": "inspection_result",
                    "payload": {"target_id": "ai-1", "is_wolf": True},
                    "visibility": "private",
                },
            ),
        }
        runtime.unsubscribe(queue)

    asyncio.run(scenario())


def test_runtime_never_promotes_a_missing_subscriber_to_global_view(tmp_path) -> None:
    """A stale queue without a matching participant must fail closed rather than leak events."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        runtime = RoomRuntime(engine, repository, state)
        queue = runtime.subscribe(ViewerContext("missing", ViewerKind.ALIVE_HUMAN))
        event_state = state.append_event(
            "inspection_result",
            {"target_id": "ai-1", "is_wolf": True},
            Visibility.PRIVATE,
            frozenset({"ai-1"}),
        )

        runtime._publish((event_state.events[-1],), event_state)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)
        runtime.unsubscribe(queue)

    asyncio.run(scenario())
