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
    assert state.events[-2].event_type == "vote_no_execution"
    assert state.events[-1].event_type == "phase_changed"


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
