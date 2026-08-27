"""Server-side automatic turn scheduling for AI-controlled participants."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase
from werewolf_arena.domain.models import AgentUsage, GameCommand, GameState, Participant

from .budget import MODEL_COMPLETION_MAX_TOKENS, AgentBudget, AgentRunRecord
from .models import AgentDecision, AgentMemory, AgentObservation
from .observation import build_observation


class DecisionPolicy(Protocol):
    """The small policy contract required by the scheduler and test doubles."""

    async def decide(self, observation: AgentObservation) -> AgentDecision:
        """Propose a server-constrained decision for its bound participant."""


@dataclass(frozen=True)
class OrchestrationResult:
    """A settled state plus the exact point at which human input is required."""

    state: GameState
    waiting_for_human: bool
    human_actions: tuple[CommandKind, ...] = ()
    agent_runs: tuple[AgentRunRecord, ...] = ()


class GameOrchestrator:
    """Advance AI turns deterministically and pause whenever the human must choose."""

    def __init__(
        self,
        engine: GameEngine,
        policies: Mapping[str, DecisionPolicy],
        budget: AgentBudget | None = None,
        max_output_tokens: int = MODEL_COMPLETION_MAX_TOKENS,
    ) -> None:
        self._engine = engine
        self._policies = policies
        self._budget = budget or AgentBudget()
        self._max_output_tokens = max_output_tokens

    async def advance(self, state: GameState) -> OrchestrationResult:
        """Run all safe automatic work until a live human action or terminal state."""
        agent_runs: list[AgentRunRecord] = []
        while state.phase is not Phase.FINISHED:
            actors = self._actors_for_phase(state)
            human = next((item for item in actors if item.is_human), None)
            if human is not None and not self._has_submitted_command(state, human.participant_id):
                return OrchestrationResult(state, True, self._human_actions(state, human), tuple(agent_runs))
            if state.phase is Phase.NIGHT_WOLF:
                state = await self._run_wolf_team(state, actors, agent_runs)
            elif state.phase in {Phase.NIGHT_SEER, Phase.NIGHT_WITCH, Phase.DAY_VOTE}:
                state = await self._run_individual_phase(state, actors, agent_runs)
            elif state.phase is Phase.DAY_DISCUSSION:
                state, waiting = await self._run_discussion(state, agent_runs)
                if waiting:
                    return OrchestrationResult(
                        state,
                        True,
                        self._human_actions(state, self._human(state)),
                        tuple(agent_runs),
                    )
            else:
                return OrchestrationResult(state, False, agent_runs=tuple(agent_runs))
            advanced = self._engine.advance_automatic(state)
            if advanced == state:
                return OrchestrationResult(state, False, agent_runs=tuple(agent_runs))
            state = advanced
        return OrchestrationResult(state, False, agent_runs=tuple(agent_runs))

    def wait_status(self, state: GameState) -> OrchestrationResult:
        """Report whether the persisted state is already waiting for the human."""
        if state.phase is Phase.FINISHED:
            return OrchestrationResult(state, False)
        actors = self._actors_for_phase(state)
        human = next((item for item in actors if item.is_human), None)
        if human is not None and not self._has_submitted_command(state, human.participant_id):
            return OrchestrationResult(state, True, self._human_actions(state, human))
        if state.phase is Phase.DAY_DISCUSSION:
            human = self._human(state)
            if human.alive and self._all_ai_players_spoke(state):
                return OrchestrationResult(state, True, self._human_actions(state, human))
        return OrchestrationResult(state, False)

    async def _run_wolf_team(
        self,
        state: GameState,
        actors: tuple[Participant, ...],
        agent_runs: list[AgentRunRecord],
    ) -> GameState:
        if not actors:
            return state
        submitted_commands = tuple(
            command for command in state.pending_commands if command.actor_id in {actor.participant_id for actor in actors}
        )
        submitted_kill = next(
            (command for command in submitted_commands if command.kind is CommandKind.WOLF_KILL), None
        )
        if submitted_kill is not None:
            target_id = submitted_kill.target_id
        elif submitted_commands:
            target_id = None
        else:
            coordinator = actors[0]
            decision, state = await self._decision(state, coordinator, agent_runs)
            target_id = decision.target_id if decision.kind is CommandKind.WOLF_KILL else self._first_non_wolf_target(state)
        for actor in actors:
            if self._has_submitted_command(state, actor.participant_id):
                continue
            if target_id is None:
                state = self._engine.submit(
                    state, GameCommand(actor_id=actor.participant_id, kind=CommandKind.NOOP)
                )
                continue
            state = self._engine.submit(
                state,
                GameCommand(actor_id=actor.participant_id, kind=CommandKind.WOLF_KILL, target_id=target_id),
            )
        return state

    async def _run_individual_phase(
        self,
        state: GameState,
        actors: tuple[Participant, ...],
        agent_runs: list[AgentRunRecord],
    ) -> GameState:
        for actor in actors:
            if self._has_submitted_command(state, actor.participant_id):
                continue
            decision, state = await self._decision(state, actor, agent_runs)
            if state.phase is Phase.DAY_VOTE and decision.kind not in {CommandKind.VOTE, CommandKind.ABSTAIN}:
                decision = AgentDecision(kind=CommandKind.ABSTAIN, failure_kind=decision.failure_kind)
            state = self._engine.submit(state, decision.to_command(actor.participant_id))
        return state

    async def _run_discussion(
        self,
        state: GameState,
        agent_runs: list[AgentRunRecord],
    ) -> tuple[GameState, bool]:
        spoken_ids = self._spoken_ids(state)
        ai_players = tuple(item for item in state.participants if item.alive and not item.is_human)
        for actor in ai_players:
            if actor.participant_id in spoken_ids:
                continue
            decision, state = await self._decision(state, actor, agent_runs)
            text = decision.speech or "我暂时没有更多信息。"
            state = self._engine.submit(
                state,
                GameCommand(actor_id=actor.participant_id, kind=CommandKind.SPEAK, text=text),
            )
        human = self._human(state)
        return state, human.alive

    @staticmethod
    def _spoken_ids(state: GameState) -> set[str]:
        spoken_ids: set[str] = set()
        for event in state.events:
            actor_id = event.payload.get("actor_id")
            if event.event_type == "public_speech" and isinstance(actor_id, str):
                spoken_ids.add(actor_id)
        return spoken_ids

    def _all_ai_players_spoke(self, state: GameState) -> bool:
        spoken_ids = self._spoken_ids(state)
        return all(
            participant.participant_id in spoken_ids
            for participant in state.participants
            if participant.alive and not participant.is_human
        )

    @staticmethod
    def _has_submitted_command(state: GameState, participant_id: str) -> bool:
        """An accepted command completes that participant's turn for the active phase."""
        return any(command.actor_id == participant_id for command in state.pending_commands)

    async def _decision(
        self,
        state: GameState,
        actor: Participant,
        agent_runs: list[AgentRunRecord],
    ) -> tuple[AgentDecision, GameState]:
        policy = self._policies.get(actor.participant_id)
        reservation = self._budget.reserve(state.agent_usage, self._max_output_tokens)
        if not reservation.allowed:
            return AgentDecision(kind=CommandKind.NOOP, failure_kind=reservation.reason), state
        decision = (
            await policy.decide(build_observation(state, actor.participant_id))
            if policy is not None
            else AgentDecision(kind=CommandKind.NOOP, failure_kind="missing_policy")
        )
        if policy is not None:
            agent_runs.append(
                AgentRunRecord(
                    participant_id=actor.participant_id,
                    model="configured",
                    status="success" if decision.failure_kind is None else "fallback",
                    input_tokens=decision.input_tokens,
                    output_tokens=decision.output_tokens,
                    cost_usd=decision.cost_usd,
                    latency_ms=decision.latency_ms,
                    failure_kind=decision.failure_kind,
                )
            )
        usage = state.agent_usage
        updated_usage = AgentUsage(
            model_calls=usage.model_calls + (1 if policy is not None else 0),
            input_tokens=usage.input_tokens + decision.input_tokens,
            output_tokens=usage.output_tokens + decision.output_tokens,
            cost_usd=usage.cost_usd + decision.cost_usd,
        )
        return decision, self._remember(state, actor, decision, updated_usage)

    @staticmethod
    def _remember(
        state: GameState,
        actor: Participant,
        decision: AgentDecision,
        updated_usage: AgentUsage,
    ) -> GameState:
        """Keep a compact private checkpoint without storing model prompt or raw response."""
        summary = f"{state.phase.value}: {decision.kind.value}"
        if decision.failure_kind is not None:
            summary += f" ({decision.failure_kind})"
        updated_actor = actor.model_copy(
            update={
                "private_state": {
                    **actor.private_state,
                    "agent_memory": AgentMemory(summary=summary, through_sequence=len(state.events)).model_dump(),
                }
            }
        )
        participants = tuple(
            updated_actor if participant.participant_id == actor.participant_id else participant
            for participant in state.participants
        )
        return state.model_copy(update={"participants": participants, "agent_usage": updated_usage})

    @staticmethod
    def _actors_for_phase(state: GameState) -> tuple[Participant, ...]:
        role_for_phase = {
            Phase.NIGHT_WOLF: "wolf",
            Phase.NIGHT_SEER: "seer",
            Phase.NIGHT_WITCH: "witch",
        }.get(state.phase)
        if role_for_phase is not None:
            return tuple(item for item in state.participants if item.alive and item.role_id == role_for_phase)
        if state.phase is Phase.DAY_VOTE:
            return tuple(item for item in state.participants if item.alive)
        return ()

    @staticmethod
    def _human_actions(state: GameState, human: Participant) -> tuple[CommandKind, ...]:
        if state.phase is Phase.DAY_DISCUSSION:
            return (CommandKind.SPEAK, CommandKind.END_DISCUSSION)
        return build_observation(state, human.participant_id).legal_kinds

    @staticmethod
    def _first_non_wolf_target(state: GameState) -> str | None:
        return next(
            (item.participant_id for item in state.participants if item.alive and item.role_id != "wolf"),
            None,
        )

    @staticmethod
    def _human(state: GameState) -> Participant:
        return next(item for item in state.participants if item.is_human)
