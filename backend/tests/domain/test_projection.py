from werewolf_arena.domain.engine import GameEngine, replay
from werewolf_arena.domain.enums import CommandKind, GameStatus, Phase, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand, Participant
from werewolf_arena.domain.projection import (
    ViewerContext,
    ViewerKind,
    project_events,
    project_finished_report,
    project_state,
)
from werewolf_arena.roles.standard import standard_role_registry


def test_alive_villager_cannot_receive_wolf_identity_or_private_seer_event() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("villager-human", requested_role_id="villager")
    seer = next(player for player in state.participants if player.role_id == "seer")
    wolf = next(player for player in state.participants if player.role_id == "wolf")
    state = state.append_event(
        "inspection_result",
        {"target_id": wolf.participant_id, "is_wolf": True},
        Visibility.PRIVATE,
        frozenset({seer.participant_id}),
    )
    viewer = ViewerContext("villager-human", ViewerKind.ALIVE_HUMAN)

    view = project_state(state, viewer)
    events = project_events(state.events, viewer, state)

    assert view["participants"][wolf.participant_id]["seat_number"] == wolf.seat_number
    assert "role_id" not in view["participants"][wolf.participant_id]
    assert all(event["event_type"] != "inspection_result" for event in events)


def test_projection_omits_a_missing_legacy_seat_number() -> None:
    """Saved rooms from before seat assignment must not render every player as seat zero."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    legacy_human = Participant.model_validate(
        state.participants[0].model_dump(exclude={"seat_number"})
    )
    state = state.model_copy(update={"participants": (legacy_human, *state.participants[1:])})

    view = project_state(state, ViewerContext("human", ViewerKind.ALIVE_HUMAN))

    assert "seat_number" not in view["participants"][legacy_human.participant_id]


def test_dead_human_receives_all_game_events_and_roles_without_server_payloads() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    seer = next(player for player in state.participants if player.role_id == "seer")
    witch = next(player for player in state.participants if player.role_id == "witch")
    state = state.model_copy(
        update={
            "participants": tuple(
                player.model_copy(update={"alive": False}) if player.participant_id == "human" else player
                for player in state.participants
            )
        }
    ).append_event(
        "inspection_result",
        {"target_id": "ai-1", "is_wolf": True},
        Visibility.PRIVATE,
        frozenset({seer.participant_id}),
    ).append_event(
        "witch_action_result",
        {"saved_target_id": "ai-1", "raw_model_response": "never expose"},
        Visibility.PRIVATE,
        frozenset({witch.participant_id}),
    ).append_event(
        "night_victim",
        {"target_id": "ai-1"},
        Visibility.SERVER,
    )
    viewer = ViewerContext("human", ViewerKind.DEAD_GLOBAL)

    view = project_state(state, viewer)
    events = project_events(state.events, viewer, state)

    assert all("role_id" in participant for participant in view["participants"].values())
    assert {event["event_type"] for event in events} >= {"inspection_result", "witch_action_result"}
    assert all(event["event_type"] != "night_victim" for event in events)
    witch_result = next(event for event in events if event["event_type"] == "witch_action_result")
    assert witch_result["payload"] == {"saved_target_id": "ai-1"}


def test_dead_global_view_replays_private_agent_reason_without_sensitive_fields() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager").append_event(
        "agent_private_reason",
        {
            "actor_id": "ai-1",
            "action_kind": "inspect",
            "target_id": "ai-2",
            "reason": "优先核验可疑发言。",
            "raw_model_response": "never expose",
        },
        Visibility.PRIVATE,
        frozenset({"ai-1"}),
    )

    events = project_events(state.events, ViewerContext("human", ViewerKind.DEAD_GLOBAL), state)
    reason = next(event for event in events if event["event_type"] == "agent_private_reason")

    assert reason["payload"] == {
        "actor_id": "ai-1",
        "action_kind": "inspect",
        "target_id": "ai-2",
        "reason": "优先核验可疑发言。",
    }


def test_live_players_cannot_view_strategy_reasons_but_dead_global_view_can() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager").append_event(
        "agent_public_reason",
        {"actor_id": "ai-1", "action_kind": "speak", "reason": "先伪装成好人，观察局势。"},
        Visibility.PUBLIC,
    )

    live_events = project_events(state.events, ViewerContext("human", ViewerKind.ALIVE_HUMAN), state)
    dead_events = project_events(state.events, ViewerContext("human", ViewerKind.DEAD_GLOBAL), state)

    assert all(event["event_type"] != "agent_public_reason" for event in live_events)
    assert next(event for event in dead_events if event["event_type"] == "agent_public_reason")["payload"]["reason"] == (
        "先伪装成好人，观察局势。"
    )


def test_finished_report_reveals_roles_without_putting_them_in_live_snapshot() -> None:
    """Final identities belong to a report, not to the ordinary room projection."""
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    running_state = engine.create_game("human", requested_role_id="villager")
    finished_state = running_state.model_copy(update={"status": GameStatus.FINISHED})
    alive_view = ViewerContext("human", ViewerKind.ALIVE_HUMAN)
    wolf = next(player for player in finished_state.participants if player.role_id == "wolf")

    snapshot = project_state(finished_state, alive_view)
    report = project_finished_report(finished_state)

    assert "role_id" not in snapshot["participants"][wolf.participant_id]
    assert report["participants"][wolf.participant_id]["role_id"] == "wolf"
    assert all(event["visibility"] != Visibility.SERVER.value for event in report["events"])


def test_replay_reproduces_a_deterministic_vote_resolution() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    initial = engine.create_game("human", requested_role_id="villager").model_copy(
        update={"phase": Phase.DAY_VOTE}
    )
    target = next(player for player in initial.participants if player.participant_id != "human")
    commands = tuple(
        GameCommand(actor_id=player.participant_id, kind=CommandKind.VOTE, target_id=target.participant_id)
        if player.participant_id != target.participant_id
        else GameCommand(actor_id=player.participant_id, kind=CommandKind.VOTE, target_id="human")
        for player in initial.participants
    )

    direct = initial
    for command in commands:
        direct = engine.submit(direct, command)
    direct = engine.advance_automatic(direct)
    replayed = replay(initial, commands, engine)

    assert replayed.phase is direct.phase
    assert replayed.status is direct.status
    assert replayed.winner_faction is direct.winner_faction
    assert [event.event_type for event in replayed.events] == [event.event_type for event in direct.events]
