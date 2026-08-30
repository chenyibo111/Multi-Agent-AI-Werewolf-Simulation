"""Browser-safe aggregate health derived from redacted agent-run records."""

from __future__ import annotations

from typing import Literal, TypedDict

from werewolf_arena.agents.budget import AgentRunRecord


class AgentHealth(TypedDict):
    """Safe room-level operational metrics with no model or participant identity."""

    status: Literal["idle", "healthy", "degraded"]
    total_calls: int
    successful_calls: int
    fallback_calls: int
    input_tokens: int
    output_tokens: int
    average_latency_ms: int
    latest_failure_kind: str | None


def project_agent_health(runs: tuple[AgentRunRecord, ...]) -> AgentHealth:
    """Return aggregate operational health suitable for the room owner's browser."""
    fallback_runs = tuple(run for run in runs if run.status == "fallback")
    successful_calls = sum(run.status == "success" for run in runs)
    total_calls = len(runs)
    return {
        "status": "idle" if not runs else "degraded" if fallback_runs else "healthy",
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "fallback_calls": len(fallback_runs),
        "input_tokens": sum(run.input_tokens for run in runs),
        "output_tokens": sum(run.output_tokens for run in runs),
        "average_latency_ms": round(sum(run.latency_ms for run in runs) / total_calls) if runs else 0,
        "latest_failure_kind": fallback_runs[-1].failure_kind if fallback_runs else None,
    }
