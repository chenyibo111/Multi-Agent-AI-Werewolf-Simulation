"""Server-only OpenAI-compatible model configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self


class LLMConfigurationError(RuntimeError):
    """Raised for incomplete model settings without revealing secret values."""


@dataclass(frozen=True)
class LLMSettings:
    """Settings required by an OpenAI Chat Completions compatible endpoint."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> Self:
        """Load the backend-local dotenv file and then validate environment values."""
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Self:
        """Validate required settings from a supplied mapping without logging values."""
        required = {
            "LLM_BASE_URL": values.get("LLM_BASE_URL", "").strip(),
            "LLM_API_KEY": values.get("LLM_API_KEY", "").strip(),
            "LLM_MODEL": values.get("LLM_MODEL", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise LLMConfigurationError("Missing model configuration: " + ", ".join(missing))
        return cls(
            base_url=required["LLM_BASE_URL"],
            api_key=required["LLM_API_KEY"],
            model=required["LLM_MODEL"],
        )
