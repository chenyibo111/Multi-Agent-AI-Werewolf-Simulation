"""Tests for per-agent information isolation and constrained model decisions."""

from __future__ import annotations

import asyncio

from werewolf_arena.agents.model_client import ModelCompletion
from werewolf_arena.agents.observation import build_observation
from werewolf_arena.agents.policy import AgentPolicy
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.roles.standard import standard_role_registry


def test_observation_excludes_another_agents_private_event() -> None:
    """A player receives public facts plus only private events addressed to that player."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    state = state.append_event("night_note", {"secret": "ai-2-only"}, Visibility.PRIVATE, frozenset({"ai-2"}))

    observation = build_observation(state, "ai-1")

    assert "ai-2-only" not in observation.model_dump_json()
    assert observation.participant_id == "ai-1"
    assert "ai-1" not in observation.legal_target_ids


def test_policy_rejects_model_actor_override_and_returns_safe_noop() -> None:
    """The model cannot choose a different actor or a command outside the observation allowlist."""

    class ScriptedClient:
        async def complete(self, *args: object, **kwargs: object) -> ModelCompletion:
            return ModelCompletion('{"actor_id":"human","kind":"wolf_kill","target_id":"human"}')

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        observation = build_observation(state, "ai-1")

        decision = await AgentPolicy("ai-1", ScriptedClient()).decide(observation)

        assert decision.kind is CommandKind.NOOP
        assert decision.failure_kind == "invalid_model_output"

    asyncio.run(scenario())
