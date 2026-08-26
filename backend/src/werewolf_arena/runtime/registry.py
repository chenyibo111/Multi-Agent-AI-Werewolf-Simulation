"""In-process lookup and restart recovery for per-room runtimes."""

from __future__ import annotations

import asyncio
from uuid import UUID

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.models import GameState
from werewolf_arena.persistence.repository import SQLiteRoomRepository

from .room_runtime import RoomRuntime


class RoomRuntimeRegistry:
    """Keep active rooms in memory and lazily rebuild them from SQLite after restart."""

    def __init__(self, engine: GameEngine, repository: SQLiteRoomRepository) -> None:
        self._engine = engine
        self._repository = repository
        self._runtimes: dict[UUID, RoomRuntime] = {}
        self._lock = asyncio.Lock()

    async def create(self, state: GameState) -> RoomRuntime:
        """Register the runtime belonging to a newly persisted room."""
        runtime = RoomRuntime(self._engine, self._repository, state)
        async with self._lock:
            self._runtimes[state.game_id] = runtime
        return runtime

    async def get(self, room_id: UUID) -> RoomRuntime:
        """Return an active runtime or lazily resume it from the latest snapshot."""
        async with self._lock:
            runtime = self._runtimes.get(room_id)
            if runtime is None:
                runtime = await RoomRuntime.resume(self._engine, self._repository, room_id)
                self._runtimes[room_id] = runtime
            return runtime

    async def remove(self, room_id: UUID) -> None:
        """Forget a deleted room so its runtime cannot be reused."""
        async with self._lock:
            self._runtimes.pop(room_id, None)
