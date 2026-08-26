"""Start an offline, deterministic arena API for browser integration tests."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import uvicorn

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend" / "src"))

from werewolf_arena.agents.model_client import ModelCompletion  # noqa: E402
from werewolf_arena.api.app import create_app  # noqa: E402


class ScriptedRoomClient:
    """Deterministic AI replacement that advances a room to each human decision."""

    async def complete(self, system_prompt: str, user_prompt: str, max_output_tokens: int) -> ModelCompletion:
        del system_prompt, max_output_tokens
        observation = json.loads(user_prompt)
        if observation["phase"] == "night_wolf":
            target = next(player_id for player_id in observation["legal_target_ids"] if player_id != "human")
            return ModelCompletion(json.dumps({"kind": "wolf_kill", "target_id": target}))
        if observation["phase"] == "day_vote":
            return ModelCompletion(json.dumps({"kind": "abstain"}))
        return ModelCompletion(json.dumps({"kind": "noop"}))


def main() -> None:
    """Keep the temporary database alive for the lifetime of the test server."""
    with tempfile.TemporaryDirectory(prefix="werewolf-arena-e2e-") as directory:
        app = create_app(
            database_path=Path(directory) / "werewolf-arena.db",
            model_client=ScriptedRoomClient(),
        )
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
