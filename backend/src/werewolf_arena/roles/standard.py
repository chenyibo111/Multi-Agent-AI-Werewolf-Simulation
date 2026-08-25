"""首期标准六人局的内置角色插件。"""

from werewolf_arena.domain.enums import CommandKind, Faction, Phase
from werewolf_arena.domain.models import EffectProposal, GameCommand, GameState

from .base import AbilityDefinition, RoleDefinition
from .registry import RoleRegistry


class BaseStandardPlugin:
    """标准角色共享的无副作用默认实现。"""

    definition: RoleDefinition
    abilities: tuple[AbilityDefinition, ...] = ()

    def initial_private_state(self, participant_id: str) -> dict[str, object]:
        """返回仅所属座位可见的初始资源。"""

        return {}

    def propose_effects(
        self, state: GameState, command: GameCommand
    ) -> tuple[EffectProposal, ...]:
        """Phase 1 仅声明技能，具体结算由权威引擎实现。"""

        return ()


class WolfPlugin(BaseStandardPlugin):
    definition = RoleDefinition(
        role_id="wolf", version="1.0.0", faction=Faction.WOLF, display_name="狼人", ability_ids=("wolf_kill",)
    )
    abilities = (AbilityDefinition(ability_id="wolf_kill", phase=Phase.NIGHT_WOLF, command_kind=CommandKind.WOLF_KILL, max_uses=1),)


class SeerPlugin(BaseStandardPlugin):
    definition = RoleDefinition(role_id="seer", version="1.0.0", faction=Faction.GOOD, display_name="预言家", ability_ids=("inspect",))
    abilities = (AbilityDefinition(ability_id="inspect", phase=Phase.NIGHT_SEER, command_kind=CommandKind.INSPECT, max_uses=1),)


class WitchPlugin(BaseStandardPlugin):
    definition = RoleDefinition(role_id="witch", version="1.0.0", faction=Faction.GOOD, display_name="女巫", ability_ids=("save", "poison"))
    abilities = (
        AbilityDefinition(ability_id="save", phase=Phase.NIGHT_WITCH, command_kind=CommandKind.WITCH_SAVE, max_uses=1),
        AbilityDefinition(ability_id="poison", phase=Phase.NIGHT_WITCH, command_kind=CommandKind.WITCH_POISON, max_uses=1),
    )

    def initial_private_state(self, participant_id: str) -> dict[str, object]:
        return {"antidote_available": True, "poison_available": True}


class VillagerPlugin(BaseStandardPlugin):
    definition = RoleDefinition(role_id="villager", version="1.0.0", faction=Faction.GOOD, display_name="村民")


def standard_role_registry() -> RoleRegistry:
    """返回包含四个内置角色的独立注册表。"""

    registry = RoleRegistry()
    for plugin in (WolfPlugin(), SeerPlugin(), WitchPlugin(), VillagerPlugin()):
        registry.register(plugin)
    return registry
