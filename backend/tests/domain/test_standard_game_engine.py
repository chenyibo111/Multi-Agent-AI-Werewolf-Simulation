from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Faction, GameStatus, Phase
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.domain.models import GameCommand
from werewolf_arena.roles.standard import standard_role_registry


def standard_engine(seed: int = 7) -> GameEngine:
    return GameEngine(standard_role_registry(), standard_six_player_mode(), seed)


def test_requested_human_role_is_reserved_and_roster_is_valid() -> None:
    engine = standard_engine(seed=7)

    state = engine.create_game("human", requested_role_id="seer")

    human = next(player for player in state.participants if player.participant_id == "human")
    assert human.role_id == "seer"
    assert len(state.participants) == 6
    assert sum(player.role_id == "wolf" for player in state.participants) == 2


def test_dead_participant_command_is_rejected_without_state_change() -> None:
    engine = standard_engine()
    state = engine.create_game("human", requested_role_id="villager")
    dead_human = next(player for player in state.participants if player.participant_id == "human")
    state = state.model_copy(
        update={
            "phase": Phase.DAY_VOTE,
            "participants": tuple(
                player.model_copy(update={"alive": False})
                if player.participant_id == "human"
                else player
                for player in state.participants
            ),
        }
    )
    command = GameCommand(actor_id=dead_human.participant_id, kind=CommandKind.VOTE, target_id="ai-1")

    result = engine.submit(state, command)

    assert result.events[-1].event_type == "command_rejected"
    assert result.pending_commands == state.pending_commands


def test_matched_wolf_attack_can_be_saved_by_witch() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="wolf")
    wolves = [player for player in state.participants if player.role_id == "wolf"]
    victim = next(player for player in state.participants if player.role_id == "villager")
    seer = next(player for player in state.participants if player.role_id == "seer")
    witch = next(player for player in state.participants if player.role_id == "witch")

    for wolf in wolves:
        state = engine.submit(
            state, GameCommand(actor_id=wolf.participant_id, kind=CommandKind.WOLF_KILL, target_id=victim.participant_id)
        )
    state = engine.advance_automatic(state)
    state = engine.submit(
        state, GameCommand(actor_id=seer.participant_id, kind=CommandKind.INSPECT, target_id=wolves[0].participant_id)
    )
    state = engine.advance_automatic(state)
    state = engine.submit(
        state, GameCommand(actor_id=witch.participant_id, kind=CommandKind.WITCH_SAVE, target_id=victim.participant_id)
    )
    state = engine.advance_automatic(state)

    assert state.phase is Phase.DAY_DISCUSSION
    assert next(player for player in state.participants if player.participant_id == victim.participant_id).alive
    assert any(event.event_type == "inspection_result" for event in state.events)
    assert any(event.event_type == "night_announcement" for event in state.events)


def test_tied_day_votes_do_not_execute_any_player() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="villager").model_copy(update={"phase": Phase.DAY_VOTE})
    target_left, target_right = "ai-1", "ai-2"
    actors_for_left = [player.participant_id for player in state.participants if player.participant_id != target_left][:3]
    actors_for_right = [player.participant_id for player in state.participants if player.participant_id not in actors_for_left and player.participant_id != target_right]

    for actor_id in actors_for_left:
        state = engine.submit(state, GameCommand(actor_id=actor_id, kind=CommandKind.VOTE, target_id=target_left))
    for actor_id in actors_for_right:
        state = engine.submit(state, GameCommand(actor_id=actor_id, kind=CommandKind.VOTE, target_id=target_right))
    state = engine.advance_automatic(state)

    assert all(player.alive for player in state.participants)
    assert state.events[-1].event_type == "vote_tied"


def test_witch_can_only_save_the_pending_night_victim() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="wolf")
    wolves = [player for player in state.participants if player.role_id == "wolf"]
    victim = next(player for player in state.participants if player.role_id == "villager")
    seer = next(player for player in state.participants if player.role_id == "seer")
    witch = next(player for player in state.participants if player.role_id == "witch")
    for wolf in wolves:
        state = engine.submit(
            state,
            GameCommand(actor_id=wolf.participant_id, kind=CommandKind.WOLF_KILL, target_id=victim.participant_id),
        )
    state = engine.advance_automatic(state)
    state = engine.submit(
        state,
        GameCommand(actor_id=seer.participant_id, kind=CommandKind.INSPECT, target_id=wolves[0].participant_id),
    )
    state = engine.advance_automatic(state)

    result = engine.submit(
        state,
        GameCommand(actor_id=witch.participant_id, kind=CommandKind.WITCH_SAVE, target_id=seer.participant_id),
    )

    assert result.events[-1].event_type == "command_rejected"
    assert result.pending_commands == ()


def test_executing_last_wolf_finishes_game_for_good_faction() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [player for player in state.participants if player.role_id == "wolf"]
    last_wolf = wolves[1]
    state = state.model_copy(
        update={
            "phase": Phase.DAY_VOTE,
            "participants": tuple(
                player.model_copy(update={"alive": False}) if player.participant_id == wolves[0].participant_id else player
                for player in state.participants
            ),
        }
    )
    for player in (player for player in state.participants if player.alive):
        target_id = next(
            candidate.participant_id
            for candidate in state.participants
            if candidate.alive and candidate.faction is Faction.GOOD
        ) if player.participant_id == last_wolf.participant_id else last_wolf.participant_id
        state = engine.submit(
            state,
            GameCommand(actor_id=player.participant_id, kind=CommandKind.VOTE, target_id=target_id),
        )

    state = engine.advance_automatic(state)

    assert state.status is GameStatus.FINISHED
    assert state.phase is Phase.FINISHED
    assert state.winner_faction is Faction.GOOD


def test_witch_poison_consumes_the_single_use_resource() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="wolf")
    wolves = [player for player in state.participants if player.role_id == "wolf"]
    targets = [player for player in state.participants if player.role_id == "villager"]
    seer = next(player for player in state.participants if player.role_id == "seer")
    witch = next(player for player in state.participants if player.role_id == "witch")
    state = engine.submit(
        state, GameCommand(actor_id=wolves[0].participant_id, kind=CommandKind.WOLF_KILL, target_id=targets[0].participant_id)
    )
    state = engine.submit(
        state, GameCommand(actor_id=wolves[1].participant_id, kind=CommandKind.WOLF_KILL, target_id=targets[1].participant_id)
    )
    state = engine.advance_automatic(state)
    state = engine.submit(
        state, GameCommand(actor_id=seer.participant_id, kind=CommandKind.INSPECT, target_id=wolves[0].participant_id)
    )
    state = engine.advance_automatic(state)
    state = engine.submit(
        state, GameCommand(actor_id=witch.participant_id, kind=CommandKind.WITCH_POISON, target_id=targets[0].participant_id)
    )
    state = engine.advance_automatic(state)

    updated_witch = next(player for player in state.participants if player.participant_id == witch.participant_id)
    assert updated_witch.private_state["poison_available"] is False


def test_executing_good_player_at_wolf_parity_finishes_game_for_wolves() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    wolves = [player for player in state.participants if player.role_id == "wolf"]
    good = next(player for player in state.participants if player.role_id == "villager")
    state = state.model_copy(
        update={
            "phase": Phase.DAY_VOTE,
            "participants": tuple(
                player
                if player.participant_id in {wolves[0].participant_id, wolves[1].participant_id, good.participant_id}
                else player.model_copy(update={"alive": False})
                for player in state.participants
            ),
        }
    )
    for wolf in wolves:
        state = engine.submit(
            state, GameCommand(actor_id=wolf.participant_id, kind=CommandKind.VOTE, target_id=good.participant_id)
        )
    state = engine.submit(
        state, GameCommand(actor_id=good.participant_id, kind=CommandKind.VOTE, target_id=wolves[0].participant_id)
    )

    state = engine.advance_automatic(state)

    assert state.status is GameStatus.FINISHED
    assert state.winner_faction is Faction.WOLF


def test_self_targeted_wolf_attack_is_rejected() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="wolf")

    result = engine.submit(
        state, GameCommand(actor_id="human", kind=CommandKind.WOLF_KILL, target_id="human")
    )

    assert result.events[-1].payload["reason"] == "self_target_forbidden"
    assert result.pending_commands == ()


def test_exhausted_witch_poison_is_rejected() -> None:
    engine = standard_engine(seed=7)
    state = engine.create_game("human", requested_role_id="villager")
    witch = next(player for player in state.participants if player.role_id == "witch")
    target = next(player for player in state.participants if player.role_id == "wolf")
    exhausted_witch = witch.model_copy(
        update={"private_state": {**witch.private_state, "poison_available": False}}
    )
    state = state.model_copy(
        update={
            "phase": Phase.NIGHT_WITCH,
            "participants": tuple(
                exhausted_witch if player.participant_id == witch.participant_id else player
                for player in state.participants
            ),
        }
    )

    result = engine.submit(
        state, GameCommand(actor_id=witch.participant_id, kind=CommandKind.WITCH_POISON, target_id=target.participant_id)
    )

    assert result.events[-1].payload["reason"] == "ability_exhausted"
    assert result.pending_commands == ()
