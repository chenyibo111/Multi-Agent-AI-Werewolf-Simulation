from collections import Counter

import pytest

from werewolf_arena.domain.errors import DomainValidationError
from werewolf_arena.domain.mode import standard_six_player_mode
from werewolf_arena.roles.registry import RoleRegistry
from werewolf_arena.roles.standard import VillagerPlugin, standard_role_registry


def test_standard_mode_has_exact_six_valid_role_slots() -> None:
    registry = standard_role_registry()
    mode = standard_six_player_mode()

    mode.validate(registry)

    assert mode.player_count == 6
    assert Counter(mode.role_slots) == Counter(
        {"wolf": 2, "seer": 1, "witch": 1, "villager": 2}
    )


def test_registry_rejects_replacing_same_role_version() -> None:
    registry = RoleRegistry()
    registry.register(VillagerPlugin())

    with pytest.raises(DomainValidationError, match="already registered"):
        registry.register(VillagerPlugin())
