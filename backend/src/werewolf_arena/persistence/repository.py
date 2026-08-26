"""异步 SQLite 房间仓储。"""

from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from werewolf_arena.domain.models import GameState

from .models import Base, EventRow, RoomRow, SnapshotRow


class SQLiteRoomRepository:
    """保存房间完整快照与可审计事件序列。"""

    def __init__(self, database_path: Path) -> None:
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def create_room(self, state: GameState) -> None:
        async with self._sessions() as session:
            session.add(RoomRow(room_id=str(state.game_id)))
            await session.commit()

    async def save_state(self, state: GameState) -> None:
        room_id = str(state.game_id)
        async with self._sessions() as session:
            await self._save(session, room_id, state)
            await session.commit()

    async def load_state(self, room_id: UUID) -> GameState:
        async with self._sessions() as session:
            snapshot = await session.get(SnapshotRow, str(room_id))
            if snapshot is None:
                raise KeyError(f"room snapshot not found: {room_id}")
            return GameState.model_validate_json(snapshot.state_json)

    async def _save(self, session: AsyncSession, room_id: str, state: GameState) -> None:
        await session.merge(SnapshotRow(room_id=room_id, state_json=state.model_dump_json()))
        await session.execute(delete(EventRow).where(EventRow.room_id == room_id))
        session.add_all(
            EventRow(room_id=room_id, sequence=event.sequence, event_json=event.model_dump_json())
            for event in state.events
        )
