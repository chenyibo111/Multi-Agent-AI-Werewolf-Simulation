"""Safety checks for the opt-in real-model smoke command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_smoke_command_refuses_missing_configuration_without_network(tmp_path) -> None:
    """A missing provider configuration fails locally without echoing any secret material."""
    backend_root = Path(__file__).resolve().parents[2]
    environment = {
        **os.environ,
        "PYTHONPATH": str(backend_root / "src"),
        "LLM_BASE_URL": "",
        "LLM_API_KEY": "",
        "LLM_MODEL": "",
    }
    result = subprocess.run(
        [sys.executable, str(backend_root / "scripts" / "smoke_real_game.py")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "LLM_API_KEY" in result.stderr
    assert "secret" not in result.stderr.lower()
