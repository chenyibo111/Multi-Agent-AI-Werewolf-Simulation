"""Server-side automatic turn scheduling for AI-controlled participants."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase, Visibility
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
                if state.phase is Phase.NIGHT_WOLF and human.role_id == "wolf":
                    state = await self._suggest_target_to_human_wolf(state, actors, agent_runs)
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
            coordinator = None
            decision = None
        elif submitted_commands:
            target_id = None
            coordinator = None
            decision = None
        else:
            coordinator = actors[0]
            decision, state = await self._decision(state, coordinator, agent_runs)
            target_id = decision.target_id if decision.kind is CommandKind.WOLF_KILL else self._first_non_wolf_target(state)
        for actor in actors:
            if self._has_submitted_command(state, actor.participant_id):
                continue
            if target_id is None:
                state = self._submit_with_reason(
                    state,
                    actor,
                    GameCommand(actor_id=actor.participant_id, kind=CommandKind.NOOP),
                    decision if actor is coordinator else None,
                )
                continue
            state = self._submit_with_reason(
                state,
                actor,
                GameCommand(actor_id=actor.participant_id, kind=CommandKind.WOLF_KILL, target_id=target_id),
                decision if actor is coordinator else None,
            )
        return state

    async def _suggest_target_to_human_wolf(
        self,
        state: GameState,
        actors: tuple[Participant, ...],
        agent_runs: list[AgentRunRecord],
    ) -> GameState:
        """Ask one AI wolf for a private recommendation before a human wolf commits."""
        if self._has_current_wolf_suggestion(state):
            return state
        advisor = next((actor for actor in actors if not actor.is_human), None)
        if advisor is None:
            return state
        decision, state = await self._decision(state, advisor, agent_runs)
        if decision.kind is not CommandKind.WOLF_KILL or decision.target_id is None:
            return state
        recipients = frozenset(actor.participant_id for actor in actors if actor.alive)
        return state.append_event(
            "wolf_team_suggestion",
            {
                "actor_id": advisor.participant_id,
                "target_id": decision.target_id,
                "message": decision.team_message or "我建议优先击杀这个目标。",
            },
            visibility=Visibility.PRIVATE,
            recipient_ids=recipients,
        )

    @staticmethod
    def _has_current_wolf_suggestion(state: GameState) -> bool:
        """Only one advice event belongs to each night-wolf phase, including after reloads."""
        phase_start = max(
            (
                event.sequence
                for event in state.events
                if event.event_type == "phase_changed" and event.payload.get("phase") == Phase.NIGHT_WOLF.value
            ),
            default=0,
        )
        return any(
            event.event_type == "wolf_team_suggestion" and event.sequence > phase_start
            for event in state.events
        )

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
            state = self._submit_with_reason(state, actor, decision.to_command(actor.participant_id), decision)
        return state

    async def _run_discussion(
        self,
        state: GameState,
        agent_runs: list[AgentRunRecord],
    ) -> tuple[GameState, bool]:
        spoken_ids = self._spoken_ids(state)
        ai_players = [item for item in state.participants if item.alive and not item.is_human]
        random.Random(f"{state.game_id}:{state.round_number}:day_discussion").shuffle(ai_players)
        for actor in ai_players:
            if actor.participant_id in spoken_ids:
                continue
            decision, state = await self._decision(state, actor, agent_runs)
            text = decision.speech or "我暂时没有更多信息。"
            state = self._submit_with_reason(
                state,
                actor,
                GameCommand(actor_id=actor.participant_id, kind=CommandKind.SPEAK, text=text),
                decision,
            )
        human = self._human(state)
        return state, human.alive

    @staticmethod
    def _spoken_ids(state: GameState) -> set[str]:
        spoken_ids: set[str] = set()
        discussion_started_at = max(
            (
                event.sequence
                for event in state.events
                if event.event_type == "phase_changed" and event.payload.get("phase") == Phase.DAY_DISCUSSION.value
            ),
            default=0,
        )
        for event in state.events:
            actor_id = event.payload.get("actor_id")
            if event.sequence > discussion_started_at and event.event_type == "public_speech" and isinstance(actor_id, str):
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

    def _submit_with_reason(
        self,
        state: GameState,
        actor: Participant,
        command: GameCommand,
        decision: AgentDecision | None,
    ) -> GameState:
        """Persist a safe reason only after the engine accepts the corresponding AI command."""
        accepted_state = self._engine.submit(state, command)
        if decision is None or decision.kind is not command.kind or not self._command_was_accepted(accepted_state, command):
            return accepted_state
        return self._record_reason(accepted_state, actor, decision)

    @staticmethod
    def _command_was_accepted(state: GameState, command: GameCommand) -> bool:
        if command.kind is CommandKind.SPEAK:
            return bool(state.events) and state.events[-1].event_type == "public_speech"
        return command in state.pending_commands

    @staticmethod
    def _record_reason(state: GameState, actor: Participant, decision: AgentDecision) -> GameState:
        reason = decision.public_reason.strip()
        if not reason or decision.failure_kind is not None:
            return state
        if decision.kind in {CommandKind.SPEAK, CommandKind.VOTE, CommandKind.ABSTAIN}:
            return state.append_event(
                "agent_public_reason",
                {
                    "actor_id": actor.participant_id,
                    "action_kind": decision.kind.value,
                    "reason": reason,
                },
                Visibility.PUBLIC,
            )
        if decision.kind in {
            CommandKind.WOLF_KILL,
            CommandKind.INSPECT,
            CommandKind.WITCH_SAVE,
            CommandKind.WITCH_POISON,
        }:
            return state.append_event(
                "agent_private_reason",
                {
                    "actor_id": actor.participant_id,
                    "action_kind": decision.kind.value,
                    "target_id": decision.target_id,
                    "reason": reason,
                },
                Visibility.PRIVATE,
                frozenset({actor.participant_id}),
            )
        return state

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
