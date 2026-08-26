"""Tests for durable, redacted model-call metrics."""

from __future__ import annotations

import asyncio

from werewolf_arena.agents.budget import AgentRunRecord
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import AgentUsage
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry


def test_agent_runs_store_metrics_without_prompt_or_raw_response(tmp_path) -> None:
    """The audit table keeps operational metrics but no model secret material."""

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"agent_usage": AgentUsage(model_calls=1, input_tokens=12, output_tokens=4)}
        )
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        await repository.save_state(state)
        await repository.record_agent_run(
            state.game_id,
            AgentRunRecord(
                participant_id="ai-1",
                model="test-model",
                status="success",
                input_tokens=12,
                output_tokens=4,
                latency_ms=25,
            ),
        )

        restored = await repository.load_state(state.game_id)
        records = await repository.agent_runs_for(state.game_id)

        assert restored.agent_usage == state.agent_usage
        assert records[0].model == "test-model"
        assert "raw_prompt" not in records[0].model_dump_json()
        assert "raw_model_response" not in records[0].model_dump_json()

    asyncio.run(scenario())
