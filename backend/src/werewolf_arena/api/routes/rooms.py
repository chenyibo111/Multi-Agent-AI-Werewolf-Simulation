"""Room lifecycle and human-command REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from werewolf_arena.agents.observation import build_observation
from werewolf_arena.domain.enums import CommandKind
from werewolf_arena.domain.models import GameCommand, GameState
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
async def create_room(payload: CreateRoomRequest, request: Request) -> JSONResponse:
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
    runtime = await registry.create(state)
    result = await runtime.advance_until_waiting()
    session_token = await repository.issue_session(state.game_id, "human")
    viewer = ViewerContext("human", ViewerKind.ALIVE_HUMAN)
    response = JSONResponse(status_code=status.HTTP_201_CREATED, content={
        "room_id": str(state.game_id),
        "session_token": session_token,
        "state": _state_view(result.state, viewer, result.waiting_for_human, result.human_actions),
        "events": project_events(result.state.events, viewer, result.state),
    })
    response.set_cookie(
        "werewolf_room_session",
        session_token,
        httponly=True,
        samesite="lax",
        path=f"/api/rooms/{state.game_id}",
    )
    return response


@router.get("/{room_id}")
async def get_room(
    authorized: Annotated[AuthorizedRoom, Depends(require_room_session)],
) -> dict[str, object]:
    """Return the authenticated player's permission-filtered room snapshot."""
    state = await authorized.runtime.get_state()
    current = await authorized.runtime.current_wait_status()
    return {
        "state": _state_view(state, authorized.viewer, current.waiting_for_human, current.human_actions),
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
    await authorized.runtime.submit(command)
    result = await authorized.runtime.advance_until_waiting()
    new_events = result.state.events[len(before.events) :]
    rejection = next((event for event in new_events if event.event_type == "command_rejected"), None)
    if rejection is not None:
        detail = rejection.payload.get("reason", "command_rejected")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
    return {
        "accepted": True,
        "state": _state_view(result.state, authorized.viewer, result.waiting_for_human, result.human_actions),
        "events": project_events(new_events, authorized.viewer, result.state),
    }


@router.post("/{room_id}/continue")
async def continue_room(
    authorized: Annotated[AuthorizedRoom, Depends(require_room_session)],
) -> dict[str, object]:
    """Resume automatic AI work after an authorized reconnect or server restart."""
    result = await authorized.runtime.advance_until_waiting()
    return {
        "state": _state_view(result.state, authorized.viewer, result.waiting_for_human, result.human_actions),
        "events": project_events(result.state.events, authorized.viewer, result.state),
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


def _state_view(
    state: GameState,
    viewer: ViewerContext,
    waiting_for_human: bool,
    human_actions: tuple[CommandKind, ...],
) -> dict[str, object]:
    view = project_state(state, viewer)
    view["waiting_for_human"] = waiting_for_human
    view["human_actions"] = [getattr(action, "value", str(action)) for action in human_actions]
    target_actions = {
        CommandKind.WOLF_KILL,
        CommandKind.INSPECT,
        CommandKind.WITCH_SAVE,
        CommandKind.WITCH_POISON,
        CommandKind.VOTE,
    }
    observation = build_observation(state, viewer.participant_id)
    view["legal_target_ids"] = list(observation.legal_target_ids) if any(
        action in target_actions for action in human_actions
    ) else []
    view["phase_text"] = {
        "night_wolf": "狼人行动",
        "night_seer": "预言家查验",
        "night_witch": "女巫行动",
        "day_discussion": "白天讨论",
        "day_vote": "白天投票",
        "finished": "对局结束",
    }.get(state.phase.value, "准备中")
    return view
