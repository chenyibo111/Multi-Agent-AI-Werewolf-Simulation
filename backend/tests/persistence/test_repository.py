import asyncio

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
