from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import Visibility
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.projection import (
    ViewerContext,
    ViewerKind,
    project_events,
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
