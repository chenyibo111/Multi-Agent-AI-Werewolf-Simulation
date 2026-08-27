"""Tests for per-agent information isolation and constrained model decisions."""

from __future__ import annotations

import asyncio
import json

from werewolf_arena.agents.budget import MODEL_COMPLETION_MAX_TOKENS
from werewolf_arena.agents.model_client import ModelCompletion
from werewolf_arena.agents.observation import build_observation
from werewolf_arena.agents.policy import AgentPolicy
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase, Visibility
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


def test_observation_removes_noise_and_bounds_public_history() -> None:
    """Long games keep only the latest meaningful public context while retaining private facts."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    state = state.append_event("command_rejected", {"reason": "wrong_phase"}, Visibility.PUBLIC)
    state = state.append_event("inspection_result", {"target_id": "ai-1"}, Visibility.PRIVATE, frozenset({"ai-1"}))
    for index in range(22):
        state = state.append_event(
            "public_speech",
            {"actor_id": "human", "text": f"speech-{index}"},
            Visibility.PUBLIC,
        )

    observation = build_observation(state, "ai-1")

    assert [event["event_type"] for event in observation.public_events] == ["public_speech"] * 20
    assert [event["payload"]["text"] for event in observation.public_events] == [
        f"speech-{index}" for index in range(2, 22)
    ]
    assert observation.private_events == (
        {"sequence": 4, "event_type": "inspection_result", "payload": {"target_id": "ai-1"}},
    )


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


def test_policy_accepts_action_alias_and_sends_explicit_json_contract() -> None:
    """A common OpenAI-compatible action alias is normalized before allowlist validation."""

    class CapturingClient:
        system_prompt = ""
        max_output_tokens = 0

        async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
            self.system_prompt = system_prompt
            self.max_output_tokens = max_output_tokens
            observation = json.loads(user_prompt)
            return ModelCompletion(
                json.dumps(
                    {
                        "action": "wolf_kill",
                        "target_id": observation["legal_target_ids"][0],
                    }
                )
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        wolf = next(item for item in state.participants if item.role_id == "wolf")
        observation = build_observation(state, wolf.participant_id)
        client = CapturingClient()

        decision = await AgentPolicy(wolf.participant_id, client).decide(observation)

        assert decision.kind is CommandKind.WOLF_KILL
        assert decision.target_id in observation.legal_target_ids
        assert decision.failure_kind is None
        assert '"kind"' in client.system_prompt
        assert "legal_kinds" in client.system_prompt
        assert "legal_target_ids" in client.system_prompt
        assert 'never "action"' in client.system_prompt
        assert client.max_output_tokens == MODEL_COMPLETION_MAX_TOKENS

    asyncio.run(scenario())


def test_wolf_observation_contains_only_its_team_and_never_allows_team_kills() -> None:
    """Wolf coordination is private, while the server excludes wolf teammates from kill candidates."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [participant for participant in state.participants if participant.role_id == "wolf"]

    observation = build_observation(state, wolves[0].participant_id)

    assert observation.private_facts["wolf_teammates"] == [wolves[1].participant_id]
    assert wolves[1].participant_id not in observation.legal_target_ids


def test_witch_observation_exposes_the_pending_victim_and_forces_an_available_save() -> None:
    """The temporary witch policy saves the server-known victim without a model call."""

    class NeverCalledClient:
        async def complete(self, *args: object, **kwargs: object) -> ModelCompletion:
            raise AssertionError("An available witch save must not call the model")

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        witch = next(participant for participant in state.participants if participant.role_id == "witch")
        victim = next(participant for participant in state.participants if participant.role_id == "seer")
        state = state.model_copy(update={"phase": Phase.NIGHT_WITCH}).append_event(
            "night_victim", {"target_id": victim.participant_id}, Visibility.SERVER
        )

        observation = build_observation(state, witch.participant_id)
        decision = await AgentPolicy(witch.participant_id, NeverCalledClient()).decide(observation)

        assert observation.private_facts["night_victim_id"] == victim.participant_id
        assert decision.kind is CommandKind.WITCH_SAVE
        assert decision.target_id == victim.participant_id

    asyncio.run(scenario())
