"""Tests for room-scoped model-call budget decisions."""

from werewolf_arena.agents.budget import MODEL_COMPLETION_MAX_TOKENS, AgentBudget
from werewolf_arena.domain.models import AgentUsage


def test_budget_refuses_a_call_after_the_room_call_limit() -> None:
    """A room that has consumed its permitted calls cannot start another remote request."""
    budget = AgentBudget(max_model_calls=2, max_total_tokens=100)
    usage = AgentUsage(model_calls=2, input_tokens=20, output_tokens=10)

    reservation = budget.reserve(usage, estimated_output_tokens=20)

    assert reservation.allowed is False
    assert reservation.reason == "model_call_limit"


def test_budget_reserves_the_full_model_completion_allowance_by_default() -> None:
    """A reasoning model cannot start when its configured completion allowance exceeds room budget."""
    budget = AgentBudget(max_total_tokens=MODEL_COMPLETION_MAX_TOKENS - 1)

    reservation = budget.reserve(AgentUsage())

    assert reservation.allowed is False
    assert reservation.reason == "token_limit"
