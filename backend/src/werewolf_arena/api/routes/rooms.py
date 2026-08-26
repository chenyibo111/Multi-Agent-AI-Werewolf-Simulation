"""Room lifecycle and human-command REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from werewolf_arena.domain.models import GameCommand
from werewolf_arena.domain.projection import (
    ViewerContext,
    ViewerKind,
    project_events,
    project_state,
)

from ..dependencies import AuthorizedRoom, require_room_session
from ..schemas import CreateRoomRequest, SubmitCommandRequest

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_room(payload: CreateRoomRequest, request: Request) -> dict[str, object]:
    """Create a persisted local room and return its one-time raw session token."""
    engine = request.app.state.engine
    repository = request.app.state.repository
    registry = request.app.state.runtime_registry
    try:
        state = engine.create_game("human", payload.requested_role_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    await repository.create_room(state)
    await repository.save_state(state)
    await registry.create(state)
    session_token = await repository.issue_session(state.game_id, "human")
    viewer = ViewerContext("human", ViewerKind.ALIVE_HUMAN)
    return {
        "room_id": str(state.game_id),
        "session_token": session_token,
        "state": project_state(state, viewer),
        "events": project_events(state.events, viewer, state),
    }


@router.get("/{room_id}")
async def get_room(
    authorized: Annotated[AuthorizedRoom, Depends(require_room_session)],
) -> dict[str, object]:
    """Return the authenticated player's permission-filtered room snapshot."""
    state = await authorized.runtime.get_state()
    return {
        "state": project_state(state, authorized.viewer),
        "events": project_events(state.events, authorized.viewer, state),
    }


@router.post("/{room_id}/commands")
async def submit_command(
    payload: SubmitCommandRequest,
    authorized: Annotated[AuthorizedRoom, Depends(require_room_session)],
) -> dict[str, object]:
    """Submit a human intent; the authenticated session, never JSON, supplies its actor ID."""
    before = await authorized.runtime.get_state()
    command = GameCommand(
        actor_id=authorized.participant_id,
        kind=payload.kind,
        target_id=payload.target_id,
        text=payload.text,
        metadata=payload.metadata,
    )
    state = await authorized.runtime.submit(command)
    new_events = state.events[len(before.events) :]
    rejection = next((event for event in new_events if event.event_type == "command_rejected"), None)
    if rejection is not None:
        detail = rejection.payload.get("reason", "command_rejected")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
    return {
        "accepted": True,
        "state": project_state(state, authorized.viewer),
        "events": project_events(new_events, authorized.viewer, state),
    }


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: UUID,
    request: Request,
    authorized: Annotated[AuthorizedRoom, Depends(require_room_session)],
) -> Response:
    """Revoke local access and remove the entire room authority record."""
    del authorized
    await request.app.state.repository.delete_room(room_id)
    await request.app.state.runtime_registry.remove(room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
