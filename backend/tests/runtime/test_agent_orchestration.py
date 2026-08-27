"""Tests for automatic AI turns that stop precisely at a human decision point."""

from __future__ import annotations

import asyncio

from werewolf_arena.agents.budget import AgentBudget
from werewolf_arena.agents.models import AgentDecision
from werewolf_arena.agents.orchestrator import GameOrchestrator
from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand
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
