"""Serialized command handling and permission-filtered room event delivery."""

from __future__ import annotations

import asyncio
from typing import Self
from uuid import UUID

from werewolf_arena.agents.orchestrator import GameOrchestrator, OrchestrationResult
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.models import GameCommand, GameEvent, GameState
from werewolf_arena.domain.projection import ViewerContext, project_events
from werewolf_arena.persistence.repository import SQLiteRoomRepository

RuntimeEnvelope = dict[str, object]


class RoomRuntime:
    """Own the mutable in-memory snapshot for one room behind an async lock."""

    def __init__(
        self,
        engine: GameEngine,
        repository: SQLiteRoomRepository,
        state: GameState,
        orchestrator: GameOrchestrator | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._state = state
        self._orchestrator = orchestrator
        self._lock = asyncio.Lock()
        self._subscribers: dict[asyncio.Queue[RuntimeEnvelope], ViewerContext] = {}

    @classmethod
    async def resume(
        cls,
        engine: GameEngine,
        repository: SQLiteRoomRepository,
        room_id: UUID,
        orchestrator: GameOrchestrator | None = None,
    ) -> Self:
        """Reconstruct a room runtime from its latest authoritative snapshot."""
        return cls(engine, repository, await repository.load_state(room_id), orchestrator=orchestrator)

    async def get_state(self) -> GameState:
        """Return the current authority state for an already-authorized server caller."""
        async with self._lock:
            return self._state

    async def submit(self, command: GameCommand) -> GameState:
        """Apply one intent, persist the changed snapshot, then publish safe new events."""
        async with self._lock:
            before = self._state
            submitted = self._engine.submit(before, command)
            next_state = self._engine.advance_automatic(submitted)
            if next_state == before:
                return before

            self._state = next_state
            await self._repository.save_state(next_state)
            new_events = next_state.events[len(before.events) :]
            self._publish(new_events, next_state)
            return next_state

    async def advance_until_waiting(self) -> OrchestrationResult:
        """Persist all automatic AI work, then return the next human wait boundary."""
        if self._orchestrator is None:
            raise RuntimeError("Room runtime has no agent orchestrator")
        async with self._lock:
            before = self._state
            result = await self._orchestrator.advance(before)
            if result.state != before:
                self._state = result.state
                await self._repository.save_state(result.state)
                self._publish(result.state.events[len(before.events) :], result.state)
            return result

    def subscribe(self, viewer: ViewerContext) -> asyncio.Queue[RuntimeEnvelope]:
        """Register a queue that receives only events projected for one viewer."""
        queue: asyncio.Queue[RuntimeEnvelope] = asyncio.Queue()
        self._subscribers[queue] = viewer
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RuntimeEnvelope]) -> None:
        """Release a disconnected subscriber queue."""
        self._subscribers.pop(queue, None)

    def _publish(self, events: tuple[GameEvent, ...], state: GameState) -> None:
        if not events:
            return
        for queue, viewer in tuple(self._subscribers.items()):
            projected = project_events(events, viewer, state)
            if projected:
                queue.put_nowait({"type": "events", "events": projected})
