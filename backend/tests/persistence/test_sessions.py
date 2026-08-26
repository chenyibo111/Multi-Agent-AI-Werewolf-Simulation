"""Tests for locally issued room-session credentials."""

from __future__ import annotations

import asyncio
import sqlite3

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry


def test_room_session_stores_only_token_hash_and_authorizes_owner(tmp_path) -> None:
    """A raw browser token is never persisted and only unlocks its own room."""
    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", "villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)

        raw_token = await repository.issue_session(state.game_id, "human")

        assert await repository.authorize_session(state.game_id, raw_token) == "human"
        try:
            await repository.authorize_session(state.game_id, "a-different-token")
        except PermissionError as error:
            assert str(error) == "Invalid room session"
        else:
            raise AssertionError("An unrelated token must not authorize the room")

        connection = sqlite3.connect(tmp_path / "werewolf.db")
        try:
            stored_token = connection.execute(
                "SELECT token_hash FROM player_sessions WHERE room_id = ?",
                (str(state.game_id),),
            ).fetchone()[0]
        finally:
            connection.close()

        assert stored_token != raw_token
        assert len(stored_token) == 64

    asyncio.run(scenario())


def test_revoking_room_sessions_invalidates_existing_tokens(tmp_path) -> None:
    """Starting over or closing a room can invalidate every local credential."""
    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", "villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        raw_token = await repository.issue_session(state.game_id, "human")

        await repository.revoke_room_sessions(state.game_id)

        try:
            await repository.authorize_session(state.game_id, raw_token)
        except PermissionError as error:
            assert str(error) == "Invalid room session"
        else:
            raise AssertionError("A revoked token must not authorize the room")

    asyncio.run(scenario())
