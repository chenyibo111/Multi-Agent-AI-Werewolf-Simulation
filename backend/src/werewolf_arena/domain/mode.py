"""游戏模式及其角色配额校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .enums import Faction, Phase
from .errors import DomainValidationError

if TYPE_CHECKING:
    from werewolf_arena.roles.registry import RoleRegistry


@dataclass(frozen=True)
class GameMode:
    """定义一局游戏的人数、角色槽位和阶段顺序。"""

    mode_id: str
    version: str
    player_count: int
    role_slots: tuple[str, ...]
    phase_order: tuple[Phase, ...]

    def validate(self, registry: RoleRegistry) -> None:
        """确认模式引用的角色可用且同时包含两个标准阵营。"""

        if len(self.role_slots) != self.player_count:
            raise DomainValidationError("role slot count must match player count")
        factions: set[Faction] = set()
        for role_id in self.role_slots:
            if not role_id:
                raise DomainValidationError("role id cannot be empty")
            factions.add(registry.get(role_id, "1.0.0").definition.faction)
        if {Faction.GOOD, Faction.WOLF} - factions:
            raise DomainValidationError("mode must include good and wolf factions")


def standard_six_player_mode() -> GameMode:
    """返回首期内置的六人标准局模式。"""

    return GameMode(
        mode_id="standard_six",
        version="1.0.0",
        player_count=6,
        role_slots=("wolf", "wolf", "seer", "witch", "villager", "villager"),
        phase_order=(
            Phase.NIGHT_WOLF,
            Phase.NIGHT_SEER,
            Phase.NIGHT_WITCH,
            Phase.DAY_DISCUSSION,
            Phase.DAY_VOTE,
        ),
    )
