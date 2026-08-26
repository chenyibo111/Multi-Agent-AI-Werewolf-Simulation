"""角色插件的受限声明式契约。"""

from __future__ import annotations

from typing import Protocol

from werewolf_arena.domain.enums import CommandKind, Faction, Phase
from werewolf_arena.domain.models import DomainModel, EffectProposal, GameCommand, GameState


class RoleDefinition(DomainModel):
    """可版本化的角色元数据。"""

    role_id: str
    version: str
    faction: Faction
    display_name: str
    ability_ids: tuple[str, ...] = ()


class AbilityDefinition(DomainModel):
    """角色在一个固定阶段可提出的能力。"""

    ability_id: str
    phase: Phase
    command_kind: CommandKind
    max_uses: int
    allow_self_target: bool = False


class RolePlugin(Protocol):
    """插件只能提议效果，不能直接修改全局对局状态。"""

    @property
    def definition(self) -> RoleDefinition: ...

    @property
    def abilities(self) -> tuple[AbilityDefinition, ...]: ...

    def initial_private_state(self, participant_id: str) -> dict[str, object]: ...

    def propose_effects(
        self, state: GameState, command: GameCommand
    ) -> tuple[EffectProposal, ...]: ...
