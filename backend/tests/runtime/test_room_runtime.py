"""Behaviour tests for the serialized, persistent room runtime."""

from __future__ import annotations

import asyncio

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind
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
