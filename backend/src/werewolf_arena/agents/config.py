"""Server-only OpenAI-compatible model configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

DEFAULT_LLM_MAX_OUTPUT_TOKENS = 4_096


class LLMConfigurationError(RuntimeError):
    """Raised for incomplete model settings without revealing secret values."""


@dataclass(frozen=True)
class LLMSettings:
    """Settings required by an OpenAI Chat Completions compatible endpoint."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0
    max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS
    thinking_enabled: bool = False

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
        raw_max_output_tokens = values.get("LLM_MAX_OUTPUT_TOKENS", str(DEFAULT_LLM_MAX_OUTPUT_TOKENS)).strip()
        try:
            max_output_tokens = int(raw_max_output_tokens)
        except ValueError as error:
            raise LLMConfigurationError("LLM_MAX_OUTPUT_TOKENS must be a positive integer") from error
        if max_output_tokens < 1:
            raise LLMConfigurationError("LLM_MAX_OUTPUT_TOKENS must be a positive integer")
        raw_thinking_enabled = values.get("LLM_THINKING_ENABLED", "false").strip().lower()
        if raw_thinking_enabled not in {"true", "false"}:
            raise LLMConfigurationError("LLM_THINKING_ENABLED must be true or false")
        return cls(
            base_url=required["LLM_BASE_URL"],
            api_key=required["LLM_API_KEY"],
            model=required["LLM_MODEL"],
            max_output_tokens=max_output_tokens,
            thinking_enabled=raw_thinking_enabled == "true",
        )
