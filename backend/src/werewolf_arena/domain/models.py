"""不可变的对局状态、命令、效果建议与权威事件。"""

from __future__ import annotations

from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import CommandKind, EffectKind, Faction, GameStatus, Phase, Visibility
from .errors import DomainValidationError


class DomainModel(BaseModel):
    """领域对象共享的冻结配置。"""

    model_config = ConfigDict(frozen=True)


class Participant(DomainModel):
    """一个座位的服务端权威信息。"""

    participant_id: str
    display_name: str
    role_id: str
    role_version: str = "1.0.0"
    faction: Faction
    seat_number: int | None = None
    is_human: bool = False
    alive: bool = True
    private_state: dict[str, object] = Field(default_factory=dict)


class GameCommand(DomainModel):
    """人类或策略向裁判提交的结构化意图。"""

    command_id: UUID = Field(default_factory=uuid4)
    actor_id: str
    kind: CommandKind
    target_id: str | None = None
    text: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class EffectProposal(DomainModel):
    """插件提出、等待裁判统一验证的领域效果。"""

    effect_kind: EffectKind
    source_id: str
    target_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class GameEvent(DomainModel):
    """追加式权威事件；可见性由投影层进一步执行。"""

    event_id: UUID = Field(default_factory=uuid4)
    sequence: int
    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)
    visibility: Visibility
    recipient_ids: frozenset[str] = Field(default_factory=frozenset)


class AgentUsage(DomainModel):
    """Durable room-level accounting used to stop model spending safely."""

    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class GameState(DomainModel):
    """一局游戏的完整服务端状态。"""

    game_id: UUID
    mode_id: str = "standard_six"
    mode_version: str = "1.0.0"
    phase: Phase = Phase.SETUP
    status: GameStatus = GameStatus.RUNNING
    round_number: int = 1
    participants: tuple[Participant, ...] = ()
    events: tuple[GameEvent, ...] = ()
    pending_commands: tuple[GameCommand, ...] = ()
    winner_faction: Faction | None = None
    agent_usage: AgentUsage = Field(default_factory=AgentUsage)

    @classmethod
    def empty(cls, game_id: UUID | None = None) -> Self:
        """创建不含玩家和事件的初始状态，供引擎创建对局使用。"""

        return cls(game_id=game_id or uuid4())

    def append_event(
        self,
        event_type: str,
        payload: dict[str, object],
        visibility: Visibility,
        recipient_ids: frozenset[str] = frozenset(),
    ) -> Self:
        """返回追加单个新事件后的新状态，原状态保持不变。"""

        if visibility is Visibility.PRIVATE and not recipient_ids:
            raise DomainValidationError("private event requires at least one recipient")
        if visibility is not Visibility.PRIVATE and recipient_ids:
            raise DomainValidationError("only private events may have recipients")
        event = GameEvent(
            sequence=len(self.events) + 1,
            event_type=event_type,
            payload=payload,
            visibility=visibility,
            recipient_ids=recipient_ids,
        )
        return self.model_copy(update={"events": (*self.events, event)})
