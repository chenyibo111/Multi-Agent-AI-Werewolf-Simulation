"""Production-style SPA hosting contracts."""

from fastapi.testclient import TestClient

from werewolf_arena.api.app import create_app


def test_built_spa_is_served_for_client_routes(tmp_path, monkeypatch) -> None:
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setenv("WEREWOLF_ARENA_FRONTEND_DIST", str(build))

    with TestClient(create_app(database_path=tmp_path / "arena.db")) as client:
        response = client.get("/rooms/example")

    assert response.text == "<div id='root'></div>"


def test_missing_build_does_not_capture_api_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WEREWOLF_ARENA_FRONTEND_DIST", str(tmp_path / "missing"))

    with TestClient(create_app(database_path=tmp_path / "arena.db")) as client:
        response = client.get("/docs")

    assert response.status_code == 200
