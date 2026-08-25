"""服务端权威的对局创建与命令入口。"""

from __future__ import annotations

import random

from werewolf_arena.roles.registry import RoleRegistry

from .enums import CommandKind, Phase, Visibility
from .mode import GameMode
from .models import GameCommand, GameState, Participant


class GameEngine:
    """验证角色、创建确定性阵容，并接收后续阶段命令。"""

    def __init__(self, registry: RoleRegistry, mode: GameMode, seed: int = 7) -> None:
        mode.validate(registry)
        self._registry = registry
        self._mode = mode
        self._seed = seed

    def create_game(self, human_participant_id: str, requested_role_id: str | None) -> GameState:
        """创建标准阵容，并保证被请求的人类身份占用一个合法槽位。"""

        role_slots = list(self._mode.role_slots)
        if requested_role_id is not None:
            if requested_role_id not in role_slots:
                raise ValueError("requested role is not available in this mode")
            role_slots.remove(requested_role_id)
            human_role = requested_role_id
        else:
            randomizer = random.Random(self._seed)
            randomizer.shuffle(role_slots)
            human_role = role_slots.pop()
        randomizer = random.Random(self._seed)
        randomizer.shuffle(role_slots)

        participants = [self._participant(human_participant_id, "你", human_role, is_human=True)]
        participants.extend(
            self._participant(f"ai-{index}", f"AI 玩家 {index}", role_id)
            for index, role_id in enumerate(role_slots, start=1)
        )
        state = GameState.empty().model_copy(update={"participants": tuple(participants), "phase": Phase.NIGHT_WOLF})
        state = state.append_event("game_created", {}, Visibility.SERVER)
        return state.append_event("phase_changed", {"phase": Phase.NIGHT_WOLF.value}, Visibility.PUBLIC)

    def submit(self, state: GameState, command: GameCommand) -> GameState:
        """验证命令入口；非法命令只生成公开拒绝事件。"""

        actor = next((item for item in state.participants if item.participant_id == command.actor_id), None)
        if actor is None:
            return self._reject(state, command, "unknown_actor")
        if not actor.alive:
            return self._reject(state, command, "dead_actor")
        if command.kind is CommandKind.VOTE and state.phase is not Phase.DAY_VOTE:
            return self._reject(state, command, "wrong_phase")
        if any(item.actor_id == command.actor_id for item in state.pending_commands):
            return self._reject(state, command, "duplicate_command")
        return state.model_copy(update={"pending_commands": (*state.pending_commands, command)})

    def _participant(self, participant_id: str, display_name: str, role_id: str, is_human: bool = False) -> Participant:
        plugin = self._registry.get(role_id, "1.0.0")
        return Participant(
            participant_id=participant_id,
            display_name=display_name,
            role_id=role_id,
            role_version=plugin.definition.version,
            faction=plugin.definition.faction,
            is_human=is_human,
            private_state=plugin.initial_private_state(participant_id),
        )

    @staticmethod
    def _reject(state: GameState, command: GameCommand, reason: str) -> GameState:
        return state.append_event(
            "command_rejected", {"actor_id": command.actor_id, "reason": reason}, Visibility.PUBLIC
        )
