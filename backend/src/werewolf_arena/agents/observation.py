"""Build strict per-player views for AI decision policies."""

from __future__ import annotations

from werewolf_arena.domain.enums import CommandKind, Phase, Visibility
from werewolf_arena.domain.models import GameEvent, GameState, Participant

from .models import AgentMemory, AgentObservation, PublicPlayer

_PUBLIC_REASONING_EVENT_TYPES = frozenset(
    {
        "agent_public_reason",
        "public_speech",
        "night_announcement",
        "vote_result",
        "execution",
        "vote_tied",
        "vote_no_execution",
        "game_finished",
    }
)


def build_observation(state: GameState, participant_id: str) -> AgentObservation:
    """Return only the state facts that the specified AI is authorized to use."""
    participant = _participant(state, participant_id)
    memory_data = participant.private_state.get("agent_memory", {})
    memory = AgentMemory.model_validate(memory_data) if isinstance(memory_data, dict) else AgentMemory()
    private_facts: dict[str, object] = {
        "role_id": participant.role_id,
        "faction": participant.faction.value,
        "resources": {
            key: value for key, value in participant.private_state.items() if key != "agent_memory"
        },
    }
    if participant.role_id == "wolf":
        private_facts["wolf_teammates"] = [
            item.participant_id
            for item in state.participants
            if item.alive and item.role_id == "wolf" and item.participant_id != participant_id
        ]
    if participant.role_id == "witch":
        night_victim_id = _night_victim_id(state.events)
        if night_victim_id is not None:
            private_facts["night_victim_id"] = night_victim_id
    return AgentObservation(
        participant_id=participant_id,
        phase=state.phase,
        public_events=_public_context_events(state.events),
        public_players=tuple(
            PublicPlayer(
                participant_id=item.participant_id,
                display_name=item.display_name,
                seat_number=item.seat_number,
                alive=item.alive,
            )
            for item in state.participants
        ),
        private_events=tuple(
            _event_view(event)
            for event in state.events
            if event.visibility is Visibility.PRIVATE and participant_id in event.recipient_ids
        ),
        private_facts=private_facts,
        legal_kinds=_legal_kinds(state, participant),
        legal_target_ids=tuple(
            item.participant_id
            for item in state.participants
            if item.alive
            and item.participant_id != participant_id
            and not (state.phase is Phase.NIGHT_WOLF and participant.role_id == "wolf" and item.role_id == "wolf")
        ),
        memory=memory,
    )


def _public_context_events(events: tuple[GameEvent, ...]) -> tuple[dict[str, object], ...]:
    """Keep the complete, compact public facts needed to reason across rounds."""
    relevant_events = tuple(
        event
        for event in events
        if event.visibility is Visibility.PUBLIC and event.event_type in _PUBLIC_REASONING_EVENT_TYPES
    )
    return tuple(_event_view(event) for event in relevant_events)


def _participant(state: GameState, participant_id: str) -> Participant:
    participant = next((item for item in state.participants if item.participant_id == participant_id), None)
    if participant is None:
        raise ValueError(f"Unknown participant: {participant_id}")
    return participant


def _legal_kinds(state: GameState, participant: Participant) -> tuple[CommandKind, ...]:
    phase = state.phase
    if phase is Phase.NIGHT_WOLF and participant.role_id == "wolf":
        return (CommandKind.WOLF_KILL, CommandKind.NOOP)
    if phase is Phase.NIGHT_SEER and participant.role_id == "seer":
        return (CommandKind.INSPECT, CommandKind.NOOP)
    if phase is Phase.NIGHT_WITCH and participant.role_id == "witch":
        night_victim_id = _night_victim_id(state.events)
        legal_kinds: list[CommandKind] = []
        if (
            bool(participant.private_state.get("antidote_available"))
            and night_victim_id is not None
            and night_victim_id != participant.participant_id
        ):
            legal_kinds.append(CommandKind.WITCH_SAVE)
        if bool(participant.private_state.get("poison_available")):
            legal_kinds.append(CommandKind.WITCH_POISON)
        return (*legal_kinds, CommandKind.NOOP)
    if phase is Phase.DAY_DISCUSSION:
        return (CommandKind.SPEAK, CommandKind.NOOP)
    if phase is Phase.DAY_VOTE:
        return (CommandKind.VOTE, CommandKind.ABSTAIN)
    return (CommandKind.NOOP,)


def _night_victim_id(events: tuple[GameEvent, ...]) -> str | None:
    """Return the still-pending wolf target for the witch's private view."""
    for event in reversed(events):
        if event.event_type != "night_victim":
            continue
        target_id = event.payload.get("target_id")
        return target_id if isinstance(target_id, str) else None
    return None


def _event_view(event: GameEvent) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "event_type": event.event_type,
        "payload": _safe_payload(event.payload),
    }


def _safe_payload(value: object) -> object:
    forbidden = {"raw_prompt", "raw_model_response", "secret", "api_key", "chain_of_thought"}
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items() if key not in forbidden}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_safe_payload(item) for item in value)
    return value
