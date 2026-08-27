"""Tests for commands that let a human and AI finish every game phase safely."""

from __future__ import annotations

from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand
from werewolf_arena.roles.standard import standard_role_registry


def _engine() -> GameEngine:
    return GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)


def test_public_speech_and_discussion_end_transition_to_day_vote() -> None:
    """Discussion accepts a bounded public speech and the human can close it for voting."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="villager").model_copy(
        update={"phase": Phase.DAY_DISCUSSION}
    )

    state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.SPEAK, text="我怀疑 ai-1。"))
    state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.END_DISCUSSION))

    assert state.phase is Phase.DAY_VOTE
    speech = next(event for event in state.events if event.event_type == "public_speech")
    assert speech.visibility is Visibility.PUBLIC
    assert speech.payload["text"] == "我怀疑 ai-1。"
    assert state.events[-1].event_type == "discussion_ended"


def test_discussion_automatically_ends_when_the_human_has_died() -> None:
    """A dead human cannot be required to close discussion before the AI vote."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="seer")
    state = state.model_copy(
        update={
            "phase": Phase.DAY_DISCUSSION,
            "participants": tuple(
                participant.model_copy(update={"alive": False})
                if participant.participant_id == "human"
                else participant
                for participant in state.participants
            ),
        }
    )

    state = engine.advance_automatic(state)

    assert state.phase is Phase.DAY_VOTE
    assert state.events[-1].event_type == "discussion_ended"
    assert state.events[-1].payload == {"actor_id": "system"}


def test_all_abstentions_resolve_without_executing_an_empty_target() -> None:
    """Abstentions complete the vote phase and never create an empty-player execution."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="villager").model_copy(
        update={"phase": Phase.DAY_VOTE}
    )

    for participant in state.participants:
        state = engine.submit(state, GameCommand(actor_id=participant.participant_id, kind=CommandKind.ABSTAIN))
    state = engine.advance_automatic(state)

    assert state.phase is Phase.NIGHT_WOLF
    assert state.pending_commands == ()
    assert state.events[-2].event_type == "vote_no_execution"
    assert state.events[-1].event_type == "phase_changed"
    vote_result = next(event for event in state.events if event.event_type == "vote_result")
    assert vote_result.payload == {
        "votes": [{"actor_id": participant.participant_id, "target_id": None} for participant in state.participants]
    }


def test_vote_result_publicly_records_each_vote_and_abstention() -> None:
    """Day-vote resolution retains the complete public ballot before clearing commands."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="villager").model_copy(
        update={"phase": Phase.DAY_VOTE}
    )
    voters = iter(state.participants)
    first = next(voters)
    second = next(voters)
    state = engine.submit(state, GameCommand(actor_id=first.participant_id, kind=CommandKind.VOTE, target_id=second.participant_id))
    state = engine.submit(
        state,
        GameCommand(actor_id=second.participant_id, kind=CommandKind.ABSTAIN, target_id=first.participant_id),
    )
    for participant in voters:
        state = engine.submit(state, GameCommand(actor_id=participant.participant_id, kind=CommandKind.ABSTAIN))

    state = engine.advance_automatic(state)

    result = next(event for event in state.events if event.event_type == "vote_result")
    assert result.visibility is Visibility.PUBLIC
    assert result.payload == {
        "votes": [
            {"actor_id": first.participant_id, "target_id": second.participant_id},
            {"actor_id": second.participant_id, "target_id": None},
            *({"actor_id": participant.participant_id, "target_id": None} for participant in tuple(state.participants)[2:]),
        ]
    }


def test_noop_completes_a_night_ability_turn_without_a_target() -> None:
    """A skipped skill is a valid command so a failed agent cannot deadlock the night."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="seer").model_copy(
        update={"phase": Phase.NIGHT_SEER}
    )

    state = engine.submit(state, GameCommand(actor_id="human", kind=CommandKind.NOOP))
    state = engine.advance_automatic(state)

    assert state.phase is Phase.NIGHT_WITCH
    assert state.pending_commands == ()


def test_wolves_cannot_submit_a_kill_against_their_teammate() -> None:
    """The authority engine enforces the same team-safety rule exposed to wolf policies."""
    engine = _engine()
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [participant for participant in state.participants if participant.role_id == "wolf"]

    state = engine.submit(
        state,
        GameCommand(actor_id=wolves[0].participant_id, kind=CommandKind.WOLF_KILL, target_id=wolves[1].participant_id),
    )

    assert state.events[-1].event_type == "command_rejected"
    assert state.events[-1].payload["reason"] == "wolf_teammate_forbidden"
