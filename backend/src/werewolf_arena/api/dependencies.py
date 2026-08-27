"""Shared authorization dependencies for HTTP and WebSocket transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from werewolf_arena.domain.models import GameState, Participant
from werewolf_arena.domain.projection import ViewerContext, ViewerKind
from werewolf_arena.runtime.registry import RoomRuntimeRegistry
from werewolf_arena.runtime.room_runtime import RoomRuntime

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthorizedRoom:
    """The participant, projection capability, and runtime for a verified session."""

    participant_id: str
    viewer: ViewerContext
    runtime: RoomRuntime


async def require_room_session(
    room_id: UUID,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> AuthorizedRoom:
    """Authenticate a bearer credential before exposing a room or accepting intent."""
    raw_token = (
        credentials.credentials
        if credentials is not None and credentials.scheme.lower() == "bearer"
        else request.cookies.get("werewolf_room_session")
    )
    if raw_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing room session token")

    repository = request.app.state.repository
    try:
        participant_id = await repository.authorize_session(room_id, raw_token)
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid room session") from error

    registry: RoomRuntimeRegistry = request.app.state.runtime_registry
    try:
        runtime = await registry.get(room_id)
        state = await runtime.get_state()
    except KeyError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found") from error
    participant = next((item for item in state.participants if item.participant_id == participant_id), None)
    if participant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid room participant")
    return AuthorizedRoom(participant_id, viewer_for_participant(state, participant), runtime)


def viewer_for_participant(state: GameState, participant: Participant) -> ViewerContext:
    """Derive exactly the safe projection capability for a known room participant."""
    del state
    viewer_kind = ViewerKind.ALIVE_HUMAN if participant.alive else ViewerKind.DEAD_GLOBAL
    return ViewerContext(participant.participant_id, viewer_kind)
