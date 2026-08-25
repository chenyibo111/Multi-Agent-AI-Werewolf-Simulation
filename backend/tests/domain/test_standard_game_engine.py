from werewolf_arena.domain.engine import GameEngine
from werewolf_arena.domain.enums import CommandKind, Phase
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
