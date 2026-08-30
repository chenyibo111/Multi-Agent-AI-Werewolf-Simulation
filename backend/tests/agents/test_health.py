"""Tests for browser-safe aggregate model health."""

from werewolf_arena.agents.budget import AgentRunRecord
from werewolf_arena.agents.health import project_agent_health


def test_health_projection_marks_fallbacks_degraded_without_agent_details() -> None:
    """A fallback must be visible operationally but reveal no per-agent identity or model name."""
    health = project_agent_health(
        (
            AgentRunRecord(
                participant_id="ai-1",
                model="private-model-name",
                status="success",
                input_tokens=12,
                output_tokens=8,
                latency_ms=100,
            ),
            AgentRunRecord(
                participant_id="ai-2",
                model="private-model-name",
                status="fallback",
                input_tokens=4,
                output_tokens=0,
                latency_ms=300,
                failure_kind="model_error",
            ),
        )
    )

    assert health == {
        "status": "degraded",
        "total_calls": 2,
        "successful_calls": 1,
        "fallback_calls": 1,
        "input_tokens": 16,
        "output_tokens": 8,
        "average_latency_ms": 200,
        "latest_failure_kind": "model_error",
    }


def test_health_projection_marks_a_room_without_model_calls_idle() -> None:
    """A new room should not be reported as broken before it has used the model."""
    assert project_agent_health(()) == {
        "status": "idle",
        "total_calls": 0,
        "successful_calls": 0,
        "fallback_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "average_latency_ms": 0,
        "latest_failure_kind": None,
    }
