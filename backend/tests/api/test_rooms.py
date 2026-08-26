"""Contract tests for the local single-player room REST API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from werewolf_arena.api.app import create_app


def test_room_rest_lifecycle_requires_its_own_bearer_token(tmp_path) -> None:
    """The client can create, view, command, and delete only its own room."""
    app = create_app(database_path=tmp_path / "werewolf.db")
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "wolf"})
        assert created.status_code == 201
        created_payload = created.json()
        room_id = created_payload["room_id"]
        token = created_payload["session_token"]
        state = created_payload["state"]
        assert state["participants"]["human"]["role_id"] == "wolf"
        assert "role_id" not in state["participants"]["ai-1"]

        assert client.get(f"/api/rooms/{room_id}").status_code == 401

        second = client.post("/api/rooms", json={"requested_role_id": "villager"})
        foreign_token = second.json()["session_token"]
        foreign_headers = {"Authorization": f"Bearer {foreign_token}"}
        assert client.get(f"/api/rooms/{room_id}", headers=foreign_headers).status_code == 403

        headers = {"Authorization": f"Bearer {token}"}
        loaded = client.get(f"/api/rooms/{room_id}", headers=headers)
        assert loaded.status_code == 200
        assert loaded.json()["state"]["participants"] == state["participants"]

        command = client.post(
            f"/api/rooms/{room_id}/commands",
            headers=headers,
            json={"kind": "wolf_kill", "target_id": "ai-1"},
        )
        assert command.status_code == 200
        assert command.json()["accepted"] is True
        assert command.json()["state"]["participants"]["ai-1"].get("role_id") is None

        deleted = client.delete(f"/api/rooms/{room_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/rooms/{room_id}", headers=headers).status_code == 403


def test_rejected_command_returns_safe_validation_response(tmp_path) -> None:
    """A domain rejection becomes a 422 response without leaking authority fields."""
    app = create_app(database_path=tmp_path / "werewolf.db")
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "villager"}).json()
        headers = {"Authorization": f"Bearer {created['session_token']}"}

        response = client.post(
            f"/api/rooms/{created['room_id']}/commands",
            headers=headers,
            json={"kind": "wolf_kill", "target_id": "ai-1"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "wrong_role"


def test_room_resumes_after_application_restart(tmp_path) -> None:
    """A fresh application instance loads the durable snapshot for its existing token."""
    database_path = tmp_path / "werewolf.db"
    with TestClient(create_app(database_path=database_path)) as first_client:
        created = first_client.post("/api/rooms", json={"requested_role_id": "wolf"}).json()

    headers = {"Authorization": f"Bearer {created['session_token']}"}
    with TestClient(create_app(database_path=database_path)) as restarted_client:
        resumed = restarted_client.get(f"/api/rooms/{created['room_id']}", headers=headers)

    assert resumed.status_code == 200
    assert resumed.json()["state"]["game_id"] == created["room_id"]
    assert [event["sequence"] for event in resumed.json()["events"]] == [2]
