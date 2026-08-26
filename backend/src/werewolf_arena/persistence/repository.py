"""异步 SQLite 房间仓储。"""

from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from werewolf_arena.domain.models import GameEvent, GameState

from .models import Base, EventRow, PlayerSessionRow, RoomRow, SnapshotRow


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

    async def events_after(self, room_id: UUID, after_sequence: int) -> tuple[GameEvent, ...]:
        """Load authoritative events newer than a browser's acknowledged sequence."""
        statement = (
            select(EventRow)
            .where(EventRow.room_id == str(room_id), EventRow.sequence > after_sequence)
            .order_by(EventRow.sequence)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return tuple(GameEvent.model_validate_json(row.event_json) for row in rows)

    async def issue_session(self, room_id: UUID, participant_id: str) -> str:
        """Return a new browser credential while persisting only its hash."""
        raw_token = token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        async with self._sessions() as session:
            session.add(
                PlayerSessionRow(
                    token_hash=token_hash,
                    room_id=str(room_id),
                    participant_id=participant_id,
                )
            )
            await session.commit()
        return raw_token

    async def authorize_session(self, room_id: UUID, raw_token: str) -> str:
        """Return the authenticated participant or reject an unknown room token."""
        statement = select(PlayerSessionRow.participant_id).where(
            PlayerSessionRow.room_id == str(room_id),
            PlayerSessionRow.token_hash == self._hash_token(raw_token),
        )
        async with self._sessions() as session:
            participant_id = (await session.execute(statement)).scalar_one_or_none()
        if participant_id is None:
            raise PermissionError("Invalid room session")
        return participant_id

    async def revoke_room_sessions(self, room_id: UUID) -> None:
        """Invalidate every browser credential associated with one room."""
        async with self._sessions() as session:
            await session.execute(delete(PlayerSessionRow).where(PlayerSessionRow.room_id == str(room_id)))
            await session.commit()

    async def delete_room(self, room_id: UUID) -> None:
        """Delete all authority records and local credentials for one room."""
        room_key = str(room_id)
        async with self._sessions() as session:
            await session.execute(delete(PlayerSessionRow).where(PlayerSessionRow.room_id == room_key))
            await session.execute(delete(EventRow).where(EventRow.room_id == room_key))
            await session.execute(delete(SnapshotRow).where(SnapshotRow.room_id == room_key))
            await session.execute(delete(RoomRow).where(RoomRow.room_id == room_key))
            await session.commit()

    async def _save(self, session: AsyncSession, room_id: str, state: GameState) -> None:
        await session.merge(SnapshotRow(room_id=room_id, state_json=state.model_dump_json()))
        await session.execute(delete(EventRow).where(EventRow.room_id == room_id))
        session.add_all(
            EventRow(room_id=room_id, sequence=event.sequence, event_json=event.model_dump_json())
            for event in state.events
        )

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return sha256(raw_token.encode("utf-8")).hexdigest()
