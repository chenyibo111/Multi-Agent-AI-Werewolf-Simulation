"""Application factory for the local, server-authoritative arena API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from werewolf_arena.agents.config import LLMConfigurationError, LLMSettings
from werewolf_arena.agents.model_client import AsyncModelClient, OpenAICompatibleClient
from werewolf_arena.agents.orchestrator import GameOrchestrator
from werewolf_arena.agents.policy import AgentPolicy
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameState
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry
from werewolf_arena.runtime.registry import RoomRuntimeRegistry

from .routes.events import router as events_router
from .routes.rooms import router as rooms_router


def create_app(database_path: Path | None = None, model_client: AsyncModelClient | None = None) -> FastAPI:
    """Build a local API whose dependencies can later be replaced for deployment."""
    configured_database = Path(os.environ.get("WEREWOLF_ARENA_DATABASE_PATH", "werewolf_arena.db"))
    repository = SQLiteRoomRepository(database_path or configured_database)
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    if model_client is None:
        try:
            model_client = OpenAICompatibleClient(LLMSettings.from_environment())
        except LLMConfigurationError:
            model_client = None

    def orchestrator_factory(state: GameState) -> GameOrchestrator:
        policies = (
            {
                participant.participant_id: AgentPolicy(participant.participant_id, model_client)
                for participant in state.participants
                if not participant.is_human
            }
            if model_client is not None
            else {}
        )
        return GameOrchestrator(engine, policies)

    runtime_registry = RoomRuntimeRegistry(engine, repository, orchestrator_factory)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await repository.initialize()
        yield

    app = FastAPI(title="Werewolf Arena", lifespan=lifespan)
    app.state.repository = repository
    app.state.engine = engine
    app.state.runtime_registry = runtime_registry
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(rooms_router)
    app.include_router(events_router)
    return app
