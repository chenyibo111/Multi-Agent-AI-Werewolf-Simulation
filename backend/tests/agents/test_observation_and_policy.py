"""Tests for per-agent information isolation and constrained model decisions."""

from __future__ import annotations

import asyncio
import json

from werewolf_arena.agents.budget import MODEL_COMPLETION_MAX_TOKENS
from werewolf_arena.agents.model_client import ModelCompletion
from werewolf_arena.agents.observation import build_observation
from werewolf_arena.agents.policy import AgentPolicy
from werewolf_arena.agents.role_strategy import strategy_for
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

    assert [event["event_type"] for event in observation.public_events] == ["public_speech"] * 22
    assert [event["payload"]["text"] for event in observation.public_events] == [
        f"speech-{index}" for index in range(22)
    ]
    assert observation.private_events == (
        {"sequence": 4, "event_type": "inspection_result", "payload": {"target_id": "ai-1"}},
    )


def test_observation_includes_named_public_roster_without_roles() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")

    observation = build_observation(state, "ai-1")

    assert len(observation.public_players) == len(state.participants)
    assert observation.public_players[0].display_name
    assert observation.public_players[0].seat_number >= 1
    assert "role_id" not in observation.public_players[0].model_dump()


def test_observation_excludes_another_agents_strategy_reason() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager").append_event(
        "agent_public_reason",
        {"actor_id": "ai-1", "action_kind": "vote", "reason": "票型最可疑。"},
        Visibility.PRIVATE,
        frozenset({"ai-1"}),
    )

    observation = build_observation(state, "ai-2")

    assert all(event["event_type"] != "agent_public_reason" for event in observation.public_events)
    assert all(event["event_type"] != "agent_public_reason" for event in observation.private_events)


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
        assert "中文" in client.system_prompt
        assert "昵称" in client.system_prompt
        assert "ai-" in client.system_prompt
        assert client.max_output_tokens == MODEL_COMPLETION_MAX_TOKENS

    asyncio.run(scenario())


def test_policy_replaces_internal_ids_in_public_speech_with_display_names() -> None:
    class ScriptedClient:
        async def complete(self, *args: object, **kwargs: object) -> ModelCompletion:
            return ModelCompletion('{"kind":"speak","speech":"我怀疑 ai-2 的发言。"}')

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"phase": Phase.DAY_DISCUSSION}
        )
        decision = await AgentPolicy("ai-1", ScriptedClient()).decide(build_observation(state, "ai-1"))
        expected_name = next(player.display_name for player in state.participants if player.participant_id == "ai-2")

        assert decision.speech == f"我怀疑 {expected_name} 的发言。"

    asyncio.run(scenario())


def test_standard_roles_receive_distinct_strategy_cards() -> None:
    strategies = {role_id: strategy_for(role_id) for role_id in ("wolf", "seer", "witch", "villager")}

    assert len(set(strategies.values())) == 4
    assert "伪装" in strategies["wolf"]
    assert "查验" in strategies["seer"]
    assert "药剂" in strategies["witch"]
    assert "票型" in strategies["villager"]


def test_policy_includes_role_strategy_and_preserves_safe_public_reason() -> None:
    class CapturingClient:
        system_prompt = ""

        async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
            self.system_prompt = system_prompt
            observation = json.loads(user_prompt)
            return ModelCompletion(
                json.dumps(
                    {
                        "kind": "wolf_kill",
                        "target_id": observation["legal_target_ids"][0],
                        "public_reason": "ai-2 的发言最可疑。",
                    }
                )
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        wolf = next(item for item in state.participants if item.role_id == "wolf")
        client = CapturingClient()

        decision = await AgentPolicy(wolf.participant_id, client).decide(build_observation(state, wolf.participant_id))

        expected_name = next(player.display_name for player in state.participants if player.participant_id == "ai-2")
        assert "伪装" in client.system_prompt
        assert decision.public_reason == f"{expected_name} 的发言最可疑。"

    asyncio.run(scenario())


def test_wolf_observation_contains_only_its_team_and_never_allows_team_kills() -> None:
    """Wolf coordination is private, while the server excludes wolf teammates from kill candidates."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [participant for participant in state.participants if participant.role_id == "wolf"]

    observation = build_observation(state, wolves[0].participant_id)

    assert observation.private_facts["wolf_teammates"] == [wolves[1].participant_id]
    assert wolves[1].participant_id not in observation.legal_target_ids


def test_witch_observation_exposes_the_pending_victim_and_uses_model_strategy() -> None:
    """A witch receives the victim but decides whether to spend an antidote through the model."""

    class CapturingClient:
        calls = 0

        async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
            self.calls += 1
            observation = json.loads(user_prompt)
            return ModelCompletion(
                json.dumps(
                    {
                        "kind": "witch_save",
                        "target_id": observation["private_facts"]["night_victim_id"],
                    }
                )
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        witch = next(participant for participant in state.participants if participant.role_id == "witch")
        victim = next(participant for participant in state.participants if participant.role_id == "seer")
        state = state.model_copy(update={"phase": Phase.NIGHT_WITCH}).append_event(
            "night_victim", {"target_id": victim.participant_id}, Visibility.SERVER
        )

        observation = build_observation(state, witch.participant_id)
        client = CapturingClient()
        decision = await AgentPolicy(witch.participant_id, client).decide(observation)

        assert observation.private_facts["night_victim_id"] == victim.participant_id
        assert client.calls == 1
        assert decision.kind is CommandKind.WITCH_SAVE
        assert decision.target_id == victim.participant_id

    asyncio.run(scenario())
