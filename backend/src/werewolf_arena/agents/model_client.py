"""Asynchronous OpenAI-compatible model boundary used by agent policies."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from .config import LLMSettings


@dataclass(frozen=True)
class ModelCompletion:
    """Normalized model result with safe usage metadata only."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class AsyncModelClient(Protocol):
    """Small boundary that lets policies use real or scripted model clients."""

    async def complete(
        self, system_prompt: str, user_prompt: str, max_output_tokens: int
    ) -> ModelCompletion:
        """Return one normalized completion for a constrained agent request."""


class OpenAICompatibleClient:
    """Call Chat Completions without leaking credentials outside this adapter."""

    def __init__(self, settings: LLMSettings, sdk_client: Any | None = None) -> None:
        self._settings = settings
        if sdk_client is None:
            from openai import AsyncOpenAI

            sdk_client = AsyncOpenAI(
                api_key=settings.api_key,
                base_url=settings.base_url,
                timeout=settings.timeout_seconds,
            )
        self._sdk_client = sdk_client

    async def complete(
        self, system_prompt: str, user_prompt: str, max_output_tokens: int
    ) -> ModelCompletion:
        """Request a JSON object and normalize provider-specific response shapes."""
        started_at = perf_counter()
        response = await self._sdk_client.chat.completions.create(
            model=self._settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
        choices = getattr(response, "choices", ())
        if not choices:
            raise RuntimeError("Model response contained no choices")
        content = getattr(choices[0].message, "content", "")
        usage = getattr(response, "usage", None)
        return ModelCompletion(
            text=self._normalize_content(content),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=round((perf_counter() - started_at) * 1_000),
        )

    @staticmethod
    def _normalize_content(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            )
        return ""
