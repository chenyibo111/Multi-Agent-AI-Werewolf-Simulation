"""服务端权威的对局创建与命令入口。"""

from __future__ import annotations

import random
import secrets

from werewolf_arena.roles.registry import RoleRegistry

from .enums import CommandKind, Faction, GameStatus, Phase, Visibility
from .mode import GameMode
from .models import GameCommand, GameState, Participant

_AI_DISPLAY_NAMES = ("林小雨", "周子墨", "陈星河", "苏晚", "顾言")


def _ai_display_name(index: int) -> str:
    """Return a stable friendly label even for custom modes with extra seats."""
    return _AI_DISPLAY_NAMES[index] if index < len(_AI_DISPLAY_NAMES) else f"新朋友{index + 1}"


class GameEngine:
    """验证角色、创建确定性阵容，并接收后续阶段命令。"""

    def __init__(self, registry: RoleRegistry, mode: GameMode, seed: int | None = None) -> None:
        mode.validate(registry)
        self._registry = registry
        self._mode = mode
        self._seed = seed

    def create_game(self, human_participant_id: str, requested_role_id: str | None) -> GameState:
        """创建标准阵容，并保证被请求的人类身份占用一个合法槽位。"""

        randomizer = random.Random(self._seed if self._seed is not None else secrets.randbits(64))
        role_slots = list(self._mode.role_slots)
        if requested_role_id is not None:
            if requested_role_id not in role_slots:
                raise ValueError("requested role is not available in this mode")
            role_slots.remove(requested_role_id)
            human_role = requested_role_id
        else:
            randomizer.shuffle(role_slots)
            human_role = role_slots.pop()
        randomizer.shuffle(role_slots)

        participants = [self._participant(human_participant_id, "你", human_role, is_human=True)]
        participants.extend(
            self._participant(f"ai-{index + 1}", _ai_display_name(index), role_id)
            for index, role_id in enumerate(role_slots)
        )
        randomizer.shuffle(participants)
        seated_participants = tuple(
            participant.model_copy(update={"seat_number": seat_number})
            for seat_number, participant in enumerate(participants, start=1)
        )
        state = GameState.empty().model_copy(update={"participants": seated_participants, "phase": Phase.NIGHT_WOLF})
        state = state.append_event("game_created", {}, Visibility.SERVER)
        return state.append_event("phase_changed", {"phase": Phase.NIGHT_WOLF.value}, Visibility.PUBLIC)

    def submit(self, state: GameState, command: GameCommand) -> GameState:
        """验证命令入口；非法命令只生成公开拒绝事件。"""

        actor = next((item for item in state.participants if item.participant_id == command.actor_id), None)
        if actor is None:
            return self._reject(state, command, "unknown_actor")
        if not actor.alive:
            return self._reject(state, command, "dead_actor")
        allowed = {
            Phase.NIGHT_WOLF: {CommandKind.WOLF_KILL, CommandKind.NOOP},
            Phase.NIGHT_SEER: {CommandKind.INSPECT, CommandKind.NOOP},
            Phase.NIGHT_WITCH: {CommandKind.WITCH_SAVE, CommandKind.WITCH_POISON, CommandKind.NOOP},
            Phase.DAY_DISCUSSION: {CommandKind.SPEAK, CommandKind.END_DISCUSSION},
            Phase.DAY_VOTE: {CommandKind.VOTE, CommandKind.ABSTAIN},
        }
        if command.kind not in allowed.get(state.phase, set()):
            return self._reject(state, command, "wrong_phase")
        expected_role = {
            Phase.NIGHT_WOLF: "wolf",
            Phase.NIGHT_SEER: "seer",
            Phase.NIGHT_WITCH: "witch",
        }.get(state.phase)
        if expected_role is not None and actor.role_id != expected_role:
            return self._reject(state, command, "wrong_role")
        if command.kind is CommandKind.SPEAK:
            if not command.text.strip() or len(command.text) > 500:
                return self._reject(state, command, "invalid_speech")
            return state.append_event(
                "public_speech", {"actor_id": actor.participant_id, "text": command.text.strip()}, Visibility.PUBLIC
            )
        if command.kind is CommandKind.END_DISCUSSION:
            return self._change_phase(
                state, Phase.DAY_VOTE
            ).append_event("discussion_ended", {"actor_id": actor.participant_id}, Visibility.PUBLIC)
        needs_target = command.kind in {
            CommandKind.WOLF_KILL,
            CommandKind.INSPECT,
            CommandKind.WITCH_SAVE,
            CommandKind.WITCH_POISON,
            CommandKind.VOTE,
        }
        if needs_target and (
            command.target_id is None
            or not any(item.participant_id == command.target_id and item.alive for item in state.participants)
        ):
            return self._reject(state, command, "invalid_target")
        if needs_target and command.target_id == command.actor_id:
            return self._reject(state, command, "self_target_forbidden")
        if command.kind is CommandKind.WOLF_KILL:
            target = next(item for item in state.participants if item.participant_id == command.target_id)
            if target.role_id == "wolf":
                return self._reject(state, command, "wolf_teammate_forbidden")
        if any(item.actor_id == command.actor_id for item in state.pending_commands):
            return self._reject(state, command, "duplicate_command")
        if command.kind is CommandKind.WITCH_SAVE:
            victim = self._night_victim(state)
            if command.target_id != victim:
                return self._reject(state, command, "invalid_save_target")
            if not bool(actor.private_state.get("antidote_available")):
                return self._reject(state, command, "ability_exhausted")
        if command.kind is CommandKind.WITCH_POISON and not bool(actor.private_state.get("poison_available")):
            return self._reject(state, command, "ability_exhausted")
        return state.model_copy(update={"pending_commands": (*state.pending_commands, command)})

    def advance_automatic(self, state: GameState) -> GameState:
        """结算已完整提交的当前阶段，并推进到下一个等待行动的阶段。"""

        if state.phase is Phase.NIGHT_WOLF:
            wolves = [item for item in state.participants if item.alive and item.role_id == "wolf"]
            commands = [item for item in state.pending_commands if item.actor_id in {wolf.participant_id for wolf in wolves}]
            if {item.actor_id for item in commands} != {item.participant_id for item in wolves}:
                return state
            targets = {item.target_id for item in commands if item.kind is CommandKind.WOLF_KILL}
            state = state.model_copy(update={"pending_commands": ()})
            if len(targets) == 1:
                state = state.append_event("night_victim", {"target_id": targets.pop()}, Visibility.SERVER)
            else:
                state = state.append_event("wolf_attack_failed", {}, Visibility.SERVER)
            return self._change_phase(state, Phase.NIGHT_SEER)
        if state.phase is Phase.NIGHT_SEER:
            seer = next((item for item in state.participants if item.alive and item.role_id == "seer"), None)
            if seer is None:
                return self._notify_witch_of_night_target(self._change_phase(state, Phase.NIGHT_WITCH))
            command = next((item for item in state.pending_commands if item.actor_id == seer.participant_id), None)
            if command is None:
                return state
            state = state.model_copy(update={"pending_commands": ()})
            if command.kind is CommandKind.INSPECT:
                target = next(item for item in state.participants if item.participant_id == command.target_id)
                state = state.append_event(
                    "inspection_result",
                    {"target_id": target.participant_id, "is_wolf": target.role_id == "wolf"},
                    Visibility.PRIVATE,
                    frozenset({seer.participant_id}),
                )
            return self._notify_witch_of_night_target(self._change_phase(state, Phase.NIGHT_WITCH))
        if state.phase is Phase.NIGHT_WITCH:
            witch = next((item for item in state.participants if item.alive and item.role_id == "witch"), None)
            command = (
                next((item for item in state.pending_commands if item.actor_id == witch.participant_id), None)
                if witch is not None
                else GameCommand(actor_id="system", kind=CommandKind.NOOP)
            )
            if command is None:
                return state
            victim = self._night_victim(state)
            saved = command.kind is CommandKind.WITCH_SAVE and command.target_id == victim
            poisoned = command.target_id if command.kind is CommandKind.WITCH_POISON else None
            dead_ids = {item for item in (victim, poisoned) if item is not None}
            if saved and victim is not None:
                dead_ids.discard(victim)
            resource_key = (
                "antidote_available"
                if command.kind is CommandKind.WITCH_SAVE
                else "poison_available"
                if command.kind is CommandKind.WITCH_POISON
                else None
            )
            updated_private_state = (
                {**witch.private_state, resource_key: False}
                if witch is not None and resource_key is not None
                else dict(witch.private_state)
                if witch is not None
                else {}
            )
            participants = tuple(
                item.model_copy(update={"alive": False})
                if item.participant_id in dead_ids
                else item.model_copy(update={"private_state": updated_private_state})
                if witch is not None and item.participant_id == witch.participant_id and resource_key is not None
                else item
                for item in state.participants
            )
            state = state.model_copy(update={"participants": participants, "pending_commands": ()})
            if witch is not None:
                state = state.append_event(
                    "witch_action_result",
                    {
                        "saved_target_id": victim if saved else None,
                        "poisoned_target_id": poisoned,
                        "antidote_available": bool(updated_private_state.get("antidote_available")),
                        "poison_available": bool(updated_private_state.get("poison_available")),
                    },
                    Visibility.PRIVATE,
                    frozenset({witch.participant_id}),
                )
            state = state.append_event(
                "night_announcement",
                {"death_count": len(dead_ids), "death_ids": sorted(dead_ids)},
                Visibility.PUBLIC,
            )
            return self._finish_if_winner(self._change_phase(state, Phase.DAY_DISCUSSION))
        if state.phase is Phase.DAY_DISCUSSION:
            if not any(participant.is_human and participant.alive for participant in state.participants):
                return self._change_phase(state, Phase.DAY_VOTE).append_event(
                    "discussion_ended", {"actor_id": "system"}, Visibility.PUBLIC
                )
            return state
        if state.phase is Phase.DAY_VOTE:
            alive = [item for item in state.participants if item.alive]
            commands = [item for item in state.pending_commands if item.kind in {CommandKind.VOTE, CommandKind.ABSTAIN}]
            if {item.actor_id for item in commands} != {item.participant_id for item in alive}:
                return state
            state = state.append_event(
                "vote_result",
                {
                    "votes": [
                        {
                            "actor_id": command.actor_id,
                            "target_id": command.target_id if command.kind is CommandKind.VOTE else None,
                        }
                        for command in commands
                    ]
                },
                Visibility.PUBLIC,
            )
            counts: dict[str, int] = {}
            for command in commands:
                if command.kind is CommandKind.VOTE and command.target_id is not None:
                    counts[command.target_id] = counts.get(command.target_id, 0) + 1
            if not counts:
                state = state.model_copy(update={"pending_commands": ()}).append_event(
                    "vote_no_execution", {}, Visibility.PUBLIC
                )
                return self._finish_if_winner(self._change_phase(state, Phase.NIGHT_WOLF))
            highest = max(counts.values())
            winning_targets = [target for target, count in counts.items() if count == highest]
            state = state.model_copy(update={"pending_commands": ()})
            if len(winning_targets) > 1:
                state = self._finish_if_winner(self._change_phase(state, Phase.NIGHT_WOLF))
                return state.append_event("vote_tied", {"targets": winning_targets}, Visibility.PUBLIC)
            executed = winning_targets[0]
            participants = tuple(
                item.model_copy(update={"alive": False}) if item.participant_id == executed else item
                for item in state.participants
            )
            state = state.model_copy(update={"participants": participants})
            state = state.append_event("execution", {"target_id": executed}, Visibility.PUBLIC)
            return self._finish_if_winner(self._change_phase(state, Phase.NIGHT_WOLF))
        return state

    @staticmethod
    def _night_victim(state: GameState) -> str | None:
        for event in reversed(state.events):
            if event.event_type == "night_victim":
                target_id = event.payload.get("target_id")
                return target_id if isinstance(target_id, str) else None
        return None

    @staticmethod
    def _notify_witch_of_night_target(state: GameState) -> GameState:
        witch = next((item for item in state.participants if item.alive and item.role_id == "witch"), None)
        victim = GameEngine._night_victim(state)
        if witch is None or victim is None:
            return state
        return state.append_event(
            "witch_night_target",
            {"target_id": victim},
            Visibility.PRIVATE,
            frozenset({witch.participant_id}),
        )

    @staticmethod
    def _finish_if_winner(state: GameState) -> GameState:
        wolves = [item for item in state.participants if item.alive and item.faction is Faction.WOLF]
        good = [item for item in state.participants if item.alive and item.faction is Faction.GOOD]
        winner = Faction.GOOD if not wolves else Faction.WOLF if len(wolves) >= len(good) else None
        if winner is None:
            return state
        state = state.model_copy(
            update={"status": GameStatus.FINISHED, "phase": Phase.FINISHED, "winner_faction": winner}
        )
        return state.append_event("game_finished", {"winner_faction": winner.value}, Visibility.PUBLIC)

    @staticmethod
    def _change_phase(state: GameState, phase: Phase) -> GameState:
        round_number = state.round_number + 1 if phase is Phase.NIGHT_WOLF and state.phase is not Phase.NIGHT_WOLF else state.round_number
        return state.model_copy(update={"phase": phase, "round_number": round_number}).append_event(
            "phase_changed", {"phase": phase.value}, Visibility.PUBLIC
        )

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


def replay(initial_state: GameState, accepted_commands: tuple[GameCommand, ...], engine: GameEngine) -> GameState:
    """从指定初始状态重放已接受命令，用于确定性恢复验证。"""

    state = initial_state
    for command in accepted_commands:
        state = engine.submit(state, command)
        state = engine.advance_automatic(state)
    return state
