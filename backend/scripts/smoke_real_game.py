"""Explicit, paid smoke test for a real OpenAI-compatible Werewolf Arena model."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from werewolf_arena.agents.budget import AgentBudget
from werewolf_arena.agents.config import LLMConfigurationError, LLMSettings
from werewolf_arena.agents.model_client import OpenAICompatibleClient
from werewolf_arena.agents.orchestrator import GameOrchestrator
from werewolf_arena.agents.policy import AgentPolicy
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry
from werewolf_arena.runtime.room_runtime import RoomRuntime


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one opt-in real-model Werewolf Arena smoke step.")
    parser.add_argument("--requested-role", default="villager")
    parser.add_argument("--max-agent-calls", type=int, default=8)
    return parser.parse_args()


async def _run(requested_role: str, max_agent_calls: int) -> dict[str, object]:
    settings = LLMSettings.from_environment()
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role)
    client = OpenAICompatibleClient(settings)
    policies = {
        participant.participant_id: AgentPolicy(
            participant.participant_id,
            client,
            max_output_tokens=settings.max_output_tokens,
        )
        for participant in state.participants
        if not participant.is_human
    }
    orchestrator = GameOrchestrator(
        engine,
        policies,
        budget=AgentBudget(max_model_calls=max_agent_calls),
        max_output_tokens=settings.max_output_tokens,
    )
    with TemporaryDirectory(prefix="werewolf-arena-smoke-") as directory:
        repository = SQLiteRoomRepository(Path(directory) / "smoke.db")
        await repository.initialize()
        await repository.create_room(state)
        await repository.save_state(state)
        runtime = RoomRuntime(engine, repository, state, orchestrator)
        result = await runtime.advance_until_waiting()
    usage = result.state.agent_usage
    return {
        "room_id": str(result.state.game_id),
        "phase": result.state.phase.value,
        "waiting_for_human": result.waiting_for_human,
        "agent_calls": usage.model_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": usage.cost_usd,
        "failures": [record.failure_kind for record in result.agent_runs if record.failure_kind is not None],
    }


def main() -> int:
    """Fail safely without a configured provider; otherwise print only redacted operational data."""
    arguments = _arguments()
    if arguments.max_agent_calls < 1:
        print("--max-agent-calls must be at least 1", file=sys.stderr)
        return 2
    try:
        output = asyncio.run(_run(arguments.requested_role, arguments.max_agent_calls))
    except LLMConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
