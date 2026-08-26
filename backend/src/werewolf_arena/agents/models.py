"""Stable, server-side contracts for agent observations and decisions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from werewolf_arena.domain.enums import CommandKind, Phase
from werewolf_arena.domain.models import GameCommand


class AgentMemory(BaseModel):
    """Compressed private memory that may be restored without replaying model calls."""

    model_config = ConfigDict(frozen=True)

    summary: str = ""
    through_sequence: int = 0


class AgentObservation(BaseModel):
    """The complete and intentionally limited context available to one AI player."""

    model_config = ConfigDict(frozen=True)

    participant_id: str
    phase: Phase
    public_events: tuple[dict[str, object], ...] = ()
    private_events: tuple[dict[str, object], ...] = ()
    private_facts: dict[str, object] = Field(default_factory=dict)
    legal_kinds: tuple[CommandKind, ...] = ()
    legal_target_ids: tuple[str, ...] = ()
    memory: AgentMemory = Field(default_factory=AgentMemory)


class AgentDecision(BaseModel):
    """A model proposal that is still constrained by the server's allowlist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CommandKind
    target_id: str | None = None
    speech: str = ""
    public_reason: str = ""
    failure_kind: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0

    def to_command(self, actor_id: str) -> GameCommand:
        """Bind the command actor on the server rather than trusting model data."""
        return GameCommand(
            actor_id=actor_id,
            kind=self.kind,
            target_id=self.target_id,
            text=self.speech,
            metadata={"public_reason": self.public_reason},
        )
