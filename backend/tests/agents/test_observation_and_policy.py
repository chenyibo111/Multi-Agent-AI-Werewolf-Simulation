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


def test_wolf_observation_contains_only_its_team_and_never_allows_team_kills() -> None:
    """Wolf coordination is private, while the server excludes wolf teammates from kill candidates."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [participant for participant in state.participants if participant.role_id == "wolf"]

    observation = build_observation(state, wolves[0].participant_id)

    assert observation.private_facts["wolf_teammates"] == [wolves[1].participant_id]
    assert wolves[1].participant_id not in observation.legal_target_ids
