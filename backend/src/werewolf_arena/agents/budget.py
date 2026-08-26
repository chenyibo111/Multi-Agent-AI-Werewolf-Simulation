"""Room-level model-call budgets and redacted model-run records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from werewolf_arena.domain.models import AgentUsage


@dataclass(frozen=True)
class BudgetReservation:
    """The result of checking whether a new completion may start."""

    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class AgentBudget:
    """Explicit room limits that bound cost and prevent unbounded retries."""

    max_model_calls: int = 120
    max_total_tokens: int = 24_000
    max_cost_usd: float | None = None

    def reserve(self, usage: AgentUsage, estimated_output_tokens: int) -> BudgetReservation:
        """Reject a call before it starts when any configured room budget is exhausted."""
        if usage.model_calls >= self.max_model_calls:
            return BudgetReservation(False, "model_call_limit")
        if usage.input_tokens + usage.output_tokens + estimated_output_tokens > self.max_total_tokens:
            return BudgetReservation(False, "token_limit")
        if self.max_cost_usd is not None and usage.cost_usd >= self.max_cost_usd:
            return BudgetReservation(False, "cost_limit")
        return BudgetReservation(True)


class AgentRunRecord(BaseModel):
    """Persisted operational metadata that intentionally excludes prompts and raw output."""

    model_config = ConfigDict(frozen=True)

    run_id: UUID = Field(default_factory=uuid4)
    attempt_index: int = 0
    participant_id: str
    model: str
    status: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    failure_kind: str | None = None
