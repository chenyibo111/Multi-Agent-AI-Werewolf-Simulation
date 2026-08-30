"""WebSocket reconnect and projection tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from werewolf_arena.agents.model_client import ModelCompletion
from werewolf_arena.api.app import create_app


class NoopModelClient:
    """Keep WebSocket transport tests independent from the developer's live model settings."""

    async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
        del system_prompt, user_prompt, max_output_tokens
        return ModelCompletion('{"kind":"noop"}')


def test_websocket_replays_visible_events_and_streams_new_ones(tmp_path) -> None:
    """Reconnects resume at a sequence while authority-only events stay hidden."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=NoopModelClient())
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "wolf"}).json()
        room_id = created["room_id"]
        headers = {"Authorization": f"Bearer {created['session_token']}"}

        with client.websocket_connect(f"/api/rooms/{room_id}/events?after_sequence=0", headers=headers) as socket:
            catch_up = socket.receive_json()
            assert catch_up["type"] == "events"
            assert [event["event_type"] for event in catch_up["events"]] == ["phase_changed"]
            assert all(event["event_type"] != "game_created" for event in catch_up["events"])

            response = client.post(
                f"/api/rooms/{room_id}/commands",
                headers=headers,
                json={"kind": "wolf_kill", "target_id": "human"},
            )
            assert response.status_code == 422
            streamed = socket.receive_json()
            assert streamed["events"] == [
                {
                    "sequence": 3,
                    "event_type": "command_rejected",
                    "payload": {"actor_id": "human", "reason": "self_target_forbidden"},
                    "visibility": "public",
                }
            ]

        with client.websocket_connect(f"/api/rooms/{room_id}/events?after_sequence=2", headers=headers) as socket:
            replayed = socket.receive_json()
            assert [event["sequence"] for event in replayed["events"]] == [3]


def test_websocket_rejects_foreign_room_token(tmp_path) -> None:
    """A token from another room closes the connection before acceptance."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=NoopModelClient())
    with TestClient(app) as client:
        first = client.post("/api/rooms", json={}).json()
        second = client.post("/api/rooms", json={}).json()
        headers = {"Authorization": f"Bearer {second['session_token']}"}

        with (
            pytest.raises(WebSocketDisconnect) as error,
            client.websocket_connect(f"/api/rooms/{first['room_id']}/events", headers=headers),
        ):
            pass

    assert error.value.code == 1008


def test_websocket_accepts_the_room_scoped_browser_cookie(tmp_path) -> None:
    """The session cookie issued at room creation also authenticates browser WebSockets."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=NoopModelClient())
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "wolf"}).json()

        with client.websocket_connect(f"/api/rooms/{created['room_id']}/events?after_sequence=0") as socket:
            catch_up = socket.receive_json()

    assert catch_up["type"] == "events"
    assert [event["event_type"] for event in catch_up["events"]] == ["phase_changed"]
