"""API tests for automatic AI progression and browser-safe room continuation."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from werewolf_arena.agents.model_client import ModelCompletion
from werewolf_arena.api.app import create_app


class ScriptedRoomClient:
    """Offline model substitute that lets API tests exercise the real orchestration path."""

    async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
        del system_prompt, max_output_tokens
        observation = json.loads(user_prompt)
        phase = observation["phase"]
        if phase == "night_wolf":
            target = next(item for item in observation["legal_target_ids"] if item != "human")
            return ModelCompletion(json.dumps({"kind": "wolf_kill", "target_id": target}))
        if phase == "night_seer":
            return ModelCompletion(json.dumps({"kind": "noop"}))
        if phase == "night_witch":
            return ModelCompletion(json.dumps({"kind": "noop"}))
        if phase == "day_vote":
            return ModelCompletion(json.dumps({"kind": "abstain"}))
        return ModelCompletion(json.dumps({"kind": "noop"}))


def test_create_room_auto_advances_and_sets_a_room_scoped_session_cookie(tmp_path) -> None:
    """Creation runs AI turns until the human needs to act and gives browsers a safe credential."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=ScriptedRoomClient())
    with TestClient(app) as client:
        response = client.post("/api/rooms", json={"requested_role_id": "seer"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["state"]["phase"] == "night_seer"
    assert payload["state"]["waiting_for_human"] is True
    assert payload["state"]["human_actions"] == ["inspect", "noop"]
    assert payload["state"]["legal_target_ids"]
    assert payload["state"]["phase_text"] == "预言家查验"
    assert "werewolf_room_session" in response.cookies
    assert "agent_memory" not in response.text


def test_continue_uses_the_room_cookie_after_a_restart_safe_wait(tmp_path) -> None:
    """A browser can request continuation with its room cookie rather than a custom WS header."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=ScriptedRoomClient())
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "seer"}).json()

        continued = client.post(f"/api/rooms/{created['room_id']}/continue")

    assert continued.status_code == 200
    assert continued.json()["state"]["waiting_for_human"] is True


def test_room_snapshot_preserves_the_current_human_wait_status(tmp_path) -> None:
    """A page refresh must not hide an already persisted human turn boundary."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=ScriptedRoomClient())
    with TestClient(app) as client:
        created = client.post("/api/rooms", json={"requested_role_id": "seer"}).json()
        loaded = client.get(f"/api/rooms/{created['room_id']}")

    assert loaded.status_code == 200
    assert loaded.json()["state"]["waiting_for_human"] is True


def test_witch_room_exposes_only_the_fixed_antidote_target(tmp_path) -> None:
    """A human witch receives the server-selected rescue target but may still choose poison targets."""
    app = create_app(database_path=tmp_path / "werewolf.db", model_client=ScriptedRoomClient())
    with TestClient(app) as client:
        response = client.post("/api/rooms", json={"requested_role_id": "witch"})

    assert response.status_code == 201
    state = response.json()["state"]
    assert state["phase"] == "night_witch"
    assert set(state["fixed_target_ids"]) == {"witch_save"}
    assert state["fixed_target_ids"]["witch_save"] in state["legal_target_ids"]
