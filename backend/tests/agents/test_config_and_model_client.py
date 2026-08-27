"""Tests for the OpenAI-compatible configuration and async client boundary."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from werewolf_arena.agents.config import LLMConfigurationError, LLMSettings
from werewolf_arena.agents.model_client import OpenAICompatibleClient


def test_settings_load_required_environment_values_without_echoing_the_key() -> None:
    """Missing model configuration is actionable but never exposes the supplied secret."""
    settings = LLMSettings.from_mapping(
        {
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "secret-value",
            "LLM_MODEL": "test-model",
        }
    )

    assert settings.base_url == "https://example.test/v1"
    assert settings.model == "test-model"
    assert settings.max_output_tokens == 4_096
    assert settings.thinking_enabled is False

    configured = LLMSettings.from_mapping(
        {
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "secret-value",
            "LLM_MODEL": "test-model",
            "LLM_MAX_OUTPUT_TOKENS": "4096",
        }
    )
    assert configured.max_output_tokens == 4_096

    thinking_enabled = LLMSettings.from_mapping(
        {
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "secret-value",
            "LLM_MODEL": "test-model",
            "LLM_THINKING_ENABLED": "true",
        }
    )
    assert thinking_enabled.thinking_enabled is True

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY") as error:
        LLMSettings.from_mapping(
            {
                "LLM_BASE_URL": "https://example.test/v1",
                "LLM_MODEL": "test-model",
            }
        )
    assert "secret-value" not in str(error.value)

    with pytest.raises(LLMConfigurationError, match="LLM_MAX_OUTPUT_TOKENS"):
        LLMSettings.from_mapping(
            {
                "LLM_BASE_URL": "https://example.test/v1",
                "LLM_API_KEY": "secret-value",
                "LLM_MODEL": "test-model",
                "LLM_MAX_OUTPUT_TOKENS": "0",
            }
        )


def test_client_normalizes_response_content_and_usage_without_a_network_call() -> None:
    """The SDK adapter produces the stable response contract used by every policy."""

    class FakeCompletions:
        async def create(self, **kwargs: object) -> object:
            assert kwargs["model"] == "test-model"
            assert kwargs["max_tokens"] == 32
            assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{\"kind\": \"noop\"}"))],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
            )

    class FakeSDK:
        chat = SimpleNamespace(completions=FakeCompletions())

    async def scenario() -> None:
        settings = LLMSettings("https://example.test/v1", "secret-value", "test-model")
        client = OpenAICompatibleClient(settings, sdk_client=FakeSDK())

        completion = await client.complete("system", "user", max_output_tokens=32)

        assert completion.text == '{"kind": "noop"}'
        assert completion.input_tokens == 12
        assert completion.output_tokens == 4

    asyncio.run(scenario())
