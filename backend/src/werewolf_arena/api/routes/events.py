"""Permission-filtered WebSocket event stream for a local room."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket, status
from starlette.websockets import WebSocketDisconnect

from werewolf_arena.domain.projection import project_events

from ..dependencies import viewer_for_participant

router = APIRouter(tags=["events"])


@router.websocket("/api/rooms/{room_id}/events")
async def room_events(websocket: WebSocket, room_id: UUID, after_sequence: int = 0) -> None:
    """Replay authorized events, then stream future projected event envelopes."""
    raw_token = _bearer_token(websocket)
    repository = websocket.app.state.repository
    if raw_token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        participant_id = await repository.authorize_session(room_id, raw_token)
        runtime = await websocket.app.state.runtime_registry.get(room_id)
        state = await runtime.get_state()
    except (KeyError, PermissionError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    participant = next((item for item in state.participants if item.participant_id == participant_id), None)
    if participant is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    viewer = viewer_for_participant(state, participant)
    await websocket.accept()
    queue = runtime.subscribe(viewer)
    try:
        missed_events = await repository.events_after(room_id, after_sequence)
        projected = project_events(missed_events, viewer, state)
        if projected:
            await websocket.send_json({"type": "events", "events": projected})
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        return
    finally:
        runtime.unsubscribe(queue)


def _bearer_token(websocket: WebSocket) -> str | None:
    """Prefer a bearer header, then use the room-scoped browser session cookie."""
    authorization = websocket.headers.get("authorization")
    if authorization is not None:
        scheme, separator, token = authorization.partition(" ")
        if separator != "" and scheme.lower() == "bearer" and token:
            return token
    return websocket.cookies.get("werewolf_room_session")
