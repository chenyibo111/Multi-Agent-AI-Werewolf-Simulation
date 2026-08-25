from uuid import UUID

import pytest

from werewolf_arena.domain.enums import Visibility
from werewolf_arena.domain.errors import DomainValidationError
from werewolf_arena.domain.models import GameState


def test_package_exposes_version() -> None:
    import werewolf_arena

    assert werewolf_arena.__version__ == "0.1.0"


def test_append_event_assigns_monotonic_sequence() -> None:
    state = GameState.empty(game_id=UUID("00000000-0000-0000-0000-000000000001"))

    state = state.append_event("game_created", {}, Visibility.SERVER)
    state = state.append_event("phase_changed", {"phase": "night_wolf"}, Visibility.PUBLIC)

    assert [event.sequence for event in state.events] == [1, 2]
    assert state.events[1].visibility is Visibility.PUBLIC


def test_private_event_requires_recipient() -> None:
    state = GameState.empty()

    with pytest.raises(DomainValidationError, match="recipient"):
        state.append_event("inspection", {}, Visibility.PRIVATE)
