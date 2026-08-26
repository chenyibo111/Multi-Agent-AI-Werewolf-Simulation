"""Public HTTP request contracts that exclude authority-only fields."""

from __future__ import annotations

from pydantic import BaseModel, Field

from werewolf_arena.domain.enums import CommandKind


class CreateRoomRequest(BaseModel):
    """Optional human role selection for a standard local room."""

    requested_role_id: str | None = None


class SubmitCommandRequest(BaseModel):
    """A browser command whose actor identity is supplied by the session token."""

    kind: CommandKind
    target_id: str | None = None
    text: str = Field(default="", max_length=1_000)
    metadata: dict[str, object] = Field(default_factory=dict)
