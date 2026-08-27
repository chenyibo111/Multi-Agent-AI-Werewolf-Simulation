"""Tests for automatic AI turns that stop precisely at a human decision point."""

from __future__ import annotations

import asyncio
from uuid import UUID

from werewolf_arena.agents.budget import AgentBudget
from werewolf_arena.agents.models import AgentDecision
from werewolf_arena.agents.orchestrator import GameOrchestrator
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand
from werewolf_arena.domain.projection import ViewerContext, ViewerKind, project_events
from werewolf_arena.persistence.repository import SQLiteRoomRepository
from werewolf_arena.roles.standard import standard_role_registry
from werewolf_arena.runtime.room_runtime import RoomRuntime


def test_orchestrator_drives_ai_wolves_then_waits_for_human_seer() -> None:
    """Only AI acts automatically; the next human ability produces a durable wait state."""

    class WolfPolicy:
        async def decide(self, observation):
            return AgentDecision(kind=CommandKind.WOLF_KILL, target_id="human")

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="seer")
        policies = {
            participant.participant_id: WolfPolicy()
            for participant in state.participants
            if participant.role_id == "wolf"
        }

        result = await GameOrchestrator(engine, policies).advance(state)

        assert result.state.phase is Phase.NIGHT_SEER
        assert result.waiting_for_human is True
        assert result.human_actions == (CommandKind.INSPECT, CommandKind.NOOP)
        assert result.state.agent_usage.model_calls == 1

    asyncio.run(scenario())


def test_runtime_persists_automatic_progression_before_returning_human_wait(tmp_path) -> None:
    """A restart resumes the persisted human wait state without re-running the wolf policy."""

    class CountingWolfPolicy:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, observation):
            self.calls += 1
            return AgentDecision(kind=CommandKind.WOLF_KILL, target_id="human")

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="seer")
        policy = CountingWolfPolicy()
        policies = {
            participant.participant_id: policy
            for participant in state.participants
            if participant.role_id == "wolf"
        }
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        await repository.save_state(state)
        orchestrator = GameOrchestrator(engine, policies)
        runtime = RoomRuntime(engine, repository, state, orchestrator=orchestrator)

        result = await runtime.advance_until_waiting()
        resumed = await RoomRuntime.resume(engine, repository, state.game_id, orchestrator=orchestrator)

        assert result.waiting_for_human is True
        assert (await resumed.get_state()).phase is Phase.NIGHT_SEER
        assert policy.calls == 1

    asyncio.run(scenario())


def test_runtime_enforces_budget_and_persists_redacted_agent_run_metrics(tmp_path) -> None:
    """An exhausted room budget skips later policies while completed calls get durable metrics."""

    class CountingPolicy:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, observation):
            self.calls += 1
            if observation.phase is Phase.NIGHT_WOLF:
                return AgentDecision(kind=CommandKind.WOLF_KILL, target_id="human")
            return AgentDecision(kind=CommandKind.NOOP)

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager")
        policy = CountingPolicy()
        policies = {
            participant.participant_id: policy for participant in state.participants if not participant.is_human
        }
        repository = SQLiteRoomRepository(tmp_path / "werewolf.db")
        await repository.initialize()
        await repository.create_room(state)
        await repository.save_state(state)
        runtime = RoomRuntime(
            engine,
            repository,
            state,
            orchestrator=GameOrchestrator(engine, policies, budget=AgentBudget(max_model_calls=1)),
        )

        result = await runtime.advance_until_waiting()
        records = await repository.agent_runs_for(state.game_id)

        assert result.state.agent_usage.model_calls == 1
        assert policy.calls == 1
        assert len(records) == 1
        assert records[0].status == "success"
        assert records[0].participant_id != "human"

    asyncio.run(scenario())


def test_submitted_human_vote_starts_ai_votes_without_a_duplicate_command() -> None:
    """A human's accepted vote is a completed turn, not another vote prompt."""

    class AbstainPolicy:
        async def decide(self, observation):
            assert observation.phase is Phase.DAY_VOTE
            return AgentDecision(kind=CommandKind.ABSTAIN)

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"phase": Phase.DAY_VOTE}
        )
        state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.VOTE, target_id="ai-1"))
        policies = {
            participant.participant_id: AbstainPolicy()
            for participant in state.participants
            if not participant.is_human
        }
        orchestrator = GameOrchestrator(engine, policies)

        assert orchestrator.wait_status(state).waiting_for_human is False
        advanced = await orchestrator._run_individual_phase(
            state, orchestrator._actors_for_phase(state), []
        )

        assert {command.actor_id for command in advanced.pending_commands} == {
            participant.participant_id for participant in state.participants
        }
        assert not any(event.event_type == "command_rejected" for event in advanced.events)

    asyncio.run(scenario())


def test_ai_vote_reason_is_public_after_the_vote_is_accepted() -> None:
    """A safe AI vote reason is visible to another live player as a public event."""

    class VotingPolicy:
        async def decide(self, observation):
            return AgentDecision(
                kind=CommandKind.VOTE,
                target_id=observation.legal_target_ids[0],
                public_reason="票型和发言前后矛盾。",
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"phase": Phase.DAY_VOTE}
        )
        policies = {
            participant.participant_id: VotingPolicy()
            for participant in state.participants
            if not participant.is_human
        }
        orchestrator = GameOrchestrator(engine, policies)

        advanced = await orchestrator._run_individual_phase(
            state, orchestrator._actors_for_phase(state), []
        )
        reasons = [event for event in advanced.events if event.event_type == "agent_public_reason"]
        viewer_events = project_events(
            advanced.events,
            ViewerContext("human", ViewerKind.ALIVE_HUMAN),
            advanced,
        )

        assert len(reasons) == len(policies)
        assert reasons[0].visibility is Visibility.PUBLIC
        assert reasons[0].payload["action_kind"] == CommandKind.VOTE.value
        assert reasons[0].payload["reason"] == "票型和发言前后矛盾。"
        assert any(event["event_type"] == "agent_public_reason" for event in viewer_events)

    asyncio.run(scenario())


def test_ai_night_reason_is_private_to_the_acting_player() -> None:
    """A live non-recipient cannot project a wolf's night-action reason."""

    class WolfPolicy:
        async def decide(self, observation):
            return AgentDecision(
                kind=CommandKind.WOLF_KILL,
                target_id=observation.legal_target_ids[0],
                public_reason="优先处理发言最少的目标。",
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="seer")
        wolves = [participant for participant in state.participants if participant.role_id == "wolf"]
        orchestrator = GameOrchestrator(engine, {wolf.participant_id: WolfPolicy() for wolf in wolves})

        advanced = await orchestrator._run_wolf_team(state, tuple(wolves), [])
        reason = next(event for event in advanced.events if event.event_type == "agent_private_reason")
        actor_events = project_events(
            advanced.events,
            ViewerContext(wolves[0].participant_id, ViewerKind.ALIVE_HUMAN),
            advanced,
        )
        unrelated_events = project_events(
            advanced.events,
            ViewerContext("human", ViewerKind.ALIVE_HUMAN),
            advanced,
        )

        assert reason.visibility is Visibility.PRIVATE
        assert reason.recipient_ids == frozenset({wolves[0].participant_id})
        assert reason.payload["action_kind"] == CommandKind.WOLF_KILL.value
        assert reason.payload["target_id"] in {
            participant.participant_id for participant in state.participants if participant.role_id != "wolf"
        }
        assert any(event["event_type"] == "agent_private_reason" for event in actor_events)
        assert all(event["event_type"] != "agent_private_reason" for event in unrelated_events)

    asyncio.run(scenario())


def test_human_wolf_receives_a_private_ai_teammate_suggestion_before_killing() -> None:
    class WolfAdvisor:
        calls = 0

        async def decide(self, observation):
            self.calls += 1
            return AgentDecision(
                kind=CommandKind.WOLF_KILL,
                target_id=observation.legal_target_ids[0],
                team_message="今晚先从发言最少的人开始。",
            )

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="wolf")
        teammate = next(participant for participant in state.participants if participant.role_id == "wolf" and not participant.is_human)
        advisor = WolfAdvisor()

        result = await GameOrchestrator(engine, {teammate.participant_id: advisor}).advance(state)

        assert result.waiting_for_human is True
        assert result.human_actions == (CommandKind.WOLF_KILL, CommandKind.NOOP)
        assert advisor.calls == 1
        suggestion = next(event for event in result.state.events if event.event_type == "wolf_team_suggestion")
        assert suggestion.recipient_ids == frozenset({"human", teammate.participant_id})
        assert suggestion.payload["actor_id"] == teammate.participant_id
        assert suggestion.payload["message"] == "今晚先从发言最少的人开始。"

    asyncio.run(scenario())


def test_ai_players_speak_again_after_a_new_day_discussion_begins() -> None:
    class SpeakingPolicy:
        async def decide(self, observation):
            return AgentDecision(kind=CommandKind.SPEAK, speech="我会根据公开信息继续判断。")

    async def scenario() -> None:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"phase": Phase.DAY_DISCUSSION}
        ).append_event("phase_changed", {"phase": Phase.DAY_DISCUSSION.value}, Visibility.PUBLIC)
        ai_players = [participant for participant in state.participants if not participant.is_human]
        for participant in ai_players:
            state = state.append_event(
                "public_speech",
                {"actor_id": participant.participant_id, "text": "上一轮发言。"},
                Visibility.PUBLIC,
            )
        state = state.append_event("phase_changed", {"phase": Phase.DAY_DISCUSSION.value}, Visibility.PUBLIC)
        policies = {participant.participant_id: SpeakingPolicy() for participant in ai_players}

        discussed, waiting = await GameOrchestrator(engine, policies)._run_discussion(state, [])

        assert waiting is True
        current_day_speeches = [
            event for event in discussed.events if event.event_type == "public_speech" and event.payload["text"] != "上一轮发言。"
        ]
        assert {event.payload["actor_id"] for event in current_day_speeches} == {
            participant.participant_id for participant in ai_players
        }

    asyncio.run(scenario())


def test_daily_ai_discussion_order_is_deterministic_per_round_and_changes_next_round() -> None:
    class SpeakingPolicy:
        async def decide(self, observation):
            return AgentDecision(kind=CommandKind.SPEAK, speech="根据公开信息继续判断。")

    async def order_for(round_number: int) -> list[str]:
        engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
        state = engine.create_game("human", requested_role_id="villager").model_copy(
            update={"game_id": UUID(int=1), "phase": Phase.DAY_DISCUSSION, "round_number": round_number}
        ).append_event("phase_changed", {"phase": Phase.DAY_DISCUSSION.value}, Visibility.PUBLIC)
        policies = {
            participant.participant_id: SpeakingPolicy()
            for participant in state.participants
            if not participant.is_human
        }
        discussed, _ = await GameOrchestrator(engine, policies)._run_discussion(state, [])
        return [
            event.payload["actor_id"]
            for event in discussed.events
            if event.event_type == "public_speech"
        ]

    async def scenario() -> None:
        first_order = await order_for(1)
        assert first_order == await order_for(1)
        assert first_order != await order_for(2)

    asyncio.run(scenario())
