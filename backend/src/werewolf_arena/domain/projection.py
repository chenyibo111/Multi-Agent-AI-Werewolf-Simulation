"""将权威状态裁剪为某个浏览器会话可以安全读取的视图。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .enums import Visibility
from .models import GameEvent, GameState


class ViewerKind(str, Enum):
    """决定玩家在对局中可见信息的身份状态。"""

    ALIVE_HUMAN = "alive_human"
    DEAD_SPECTATOR = "dead_spectator"
    FINISHED_REPLAY = "finished_replay"


@dataclass(frozen=True)
class ViewerContext:
    """当前会话所属座位与其授权级别。"""

    participant_id: str
    kind: ViewerKind


def project_state(state: GameState, viewer: ViewerContext) -> dict[str, object]:
    """构造允许前端读取的状态字段，绝不返回完整 GameState。"""

    participants: dict[str, dict[str, object]] = {}
    for participant in state.participants:
        item: dict[str, object] = {
            "participant_id": participant.participant_id,
            "display_name": participant.display_name,
            "alive": participant.alive,
        }
        if viewer.kind is ViewerKind.FINISHED_REPLAY or participant.participant_id == viewer.participant_id:
            item["role_id"] = participant.role_id
        if participant.participant_id == viewer.participant_id and viewer.kind is ViewerKind.ALIVE_HUMAN:
            item["private_state"] = _safe_payload(participant.private_state)
        participants[participant.participant_id] = item
    return {
        "game_id": str(state.game_id),
        "phase": state.phase.value,
        "status": state.status.value,
        "round_number": state.round_number,
        "participants": participants,
    }


def project_events(
    events: tuple[GameEvent, ...], viewer: ViewerContext, state: GameState
) -> tuple[dict[str, object], ...]:
    """按会话可见性过滤权威事件，并转换为浏览器安全字典。"""

    del state
    visible = []
    for event in events:
        if not _can_view(event, viewer):
            continue
        visible.append(
            {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "payload": _safe_payload(event.payload),
                "visibility": event.visibility.value,
            }
        )
    return tuple(visible)


def project_finished_report(state: GameState) -> dict[str, object]:
    """Return the completed game's safe final replay without changing live projections."""
    viewer = ViewerContext("finished-report", ViewerKind.FINISHED_REPLAY)
    state_view = project_state(state, viewer)
    return {
        "winner_faction": state.winner_faction.value if state.winner_faction is not None else None,
        "participants": state_view["participants"],
        "events": project_events(state.events, viewer, state),
    }


def _can_view(event: GameEvent, viewer: ViewerContext) -> bool:
    if viewer.kind is ViewerKind.FINISHED_REPLAY:
        return event.visibility is not Visibility.SERVER
    if event.visibility is Visibility.PUBLIC:
        return True
    return viewer.kind is ViewerKind.ALIVE_HUMAN and viewer.participant_id in event.recipient_ids


def _safe_payload(value: object) -> object:
    forbidden = {"raw_prompt", "raw_model_response", "secret", "api_key", "chain_of_thought"}
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items() if key not in forbidden}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_safe_payload(item) for item in value)
    return value
