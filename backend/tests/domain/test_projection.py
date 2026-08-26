from werewolf_arena.domain.engine import GameEngine, replay
from werewolf_arena.domain.enums import CommandKind, GameStatus, Phase, Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand
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

    assert "role_id" not in view["participants"][wolf.participant_id]
    assert all(event["event_type"] != "inspection_result" for event in events)


def test_dead_human_sees_only_public_events_until_finished() -> None:
    engine = GameEngine(standard_role_registry(), standard_six_player_mode(), seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    seer = next(player for player in state.participants if player.role_id == "seer")
    state = state.model_copy(
        update={
            "participants": tuple(
                player.model_copy(update={"alive": False}) if player.participant_id == "human" else player
                for player in state.participants
            )
        }
    ).append_event("inspection_result", {}, Visibility.PRIVATE, frozenset({seer.participant_id}))
    viewer = ViewerContext("human", ViewerKind.DEAD_SPECTATOR)

    events = project_events(state.events, viewer, state)

    assert all(event["visibility"] == Visibility.PUBLIC.value for event in events)


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
