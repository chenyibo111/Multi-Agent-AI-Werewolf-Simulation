import asyncio
import sqlite3

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry


def test_sqlite_repository_round_trips_state_and_events(tmp_path) -> None:
    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        state = state.append_event("private_note", {"value": "only-server"}, Visibility.SERVER)
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()

        await repository.create_room(state)
        await repository.save_state(state)
        loaded = await repository.load_state(state.game_id)

        assert loaded.mode_id == state.mode_id
        assert loaded.mode_version == state.mode_version
        assert [event.sequence for event in loaded.events] == [event.sequence for event in state.events]
        assert loaded.participants == state.participants

    asyncio.run(scenario())


def test_sqlite_repository_appends_new_events_without_deleting_existing_audit_rows(tmp_path) -> None:
    """Saving a newer snapshot extends the event audit trail instead of rebuilding it."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        first_state = engine.create_game("human", requested_role_id="villager")
        database_path = tmp_path / "werewolf.db"
        repository = SQLiteRoomRepository(database_path)
        await repository.initialize()
        await repository.create_room(first_state)
        await repository.save_state(first_state)

        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                "CREATE TRIGGER reject_event_deletion BEFORE DELETE ON game_events "
                "BEGIN SELECT RAISE(FAIL, 'event audit rows must be append-only'); END;"
            )
            connection.commit()
        finally:
            connection.close()

        second_state = first_state.append_event("audit_marker", {}, Visibility.SERVER)
        await repository.save_state(second_state)
        events = await repository.events_after(second_state.game_id, after_sequence=0)

        assert [event.sequence for event in events] == [1, 2, 3]
        assert events[-1].event_type == "audit_marker"

    asyncio.run(scenario())


def test_sqlite_repository_delete_removes_the_room_authority_record(tmp_path) -> None:
    """Deleting a room leaves no persisted record that can later be resumed."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        await repository.save_state(state)

        await repository.delete_room(state.game_id)

        assert await repository.room_exists(state.game_id) is False
        assert await repository.events_after(state.game_id, after_sequence=0) == ()

    asyncio.run(scenario())
