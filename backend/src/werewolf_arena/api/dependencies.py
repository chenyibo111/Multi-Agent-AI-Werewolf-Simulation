"""Shared authorization dependencies for HTTP and WebSocket transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer session token")

    repository = request.app.state.repository
    try:
        participant_id = await repository.authorize_session(room_id, credentials.credentials)
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
    viewer_kind = (
        ViewerKind.FINISHED_REPLAY
        if state.status.value == "finished"
        else ViewerKind.ALIVE_HUMAN
        if participant.alive
        else ViewerKind.DEAD_SPECTATOR
    )
    return AuthorizedRoom(participant_id, ViewerContext(participant_id, viewer_kind), runtime)
