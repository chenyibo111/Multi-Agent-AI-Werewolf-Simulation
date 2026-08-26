"""Constrained model policy that converts safe observations into server decisions."""

from __future__ import annotations

import json

from pydantic import ValidationError

from werewolf_arena.domain.enums import CommandKind

from .model_client import AsyncModelClient, ModelCompletion
from .models import AgentDecision, AgentObservation


class AgentPolicy:
    """Bind a single model policy to one participant and its allowlisted observation."""

    def __init__(self, participant_id: str, model_client: AsyncModelClient) -> None:
        self._participant_id = participant_id
        self._model_client = model_client

    async def decide(self, observation: AgentObservation) -> AgentDecision:
        """Return an allowlisted decision or a safe no-op when the model is unusable."""
        if observation.participant_id != self._participant_id:
            raise ValueError("Agent policy received an observation for another participant")
        try:
            completion = await self._model_client.complete(
                "You are a Werewolf Arena player. Return only one JSON decision allowed by the observation.",
                observation.model_dump_json(),
                max_output_tokens=256,
            )
            decision = AgentDecision.model_validate(json.loads(completion.text)).model_copy(
                update={
                    "input_tokens": completion.input_tokens,
                    "output_tokens": completion.output_tokens,
                    "cost_usd": completion.cost_usd,
                    "latency_ms": completion.latency_ms,
                }
            )
        except (json.JSONDecodeError, TypeError, ValidationError):
            return self._fallback("invalid_model_output")
        except Exception:  # noqa: BLE001 - provider exceptions must not leave a room unable to progress.
            return self._fallback("model_error")
        if not self._is_allowed(decision, observation):
            return self._fallback("invalid_model_output")
        return decision

    @staticmethod
    def _is_allowed(decision: AgentDecision, observation: AgentObservation) -> bool:
        if decision.kind not in observation.legal_kinds:
            return False
        needs_target = decision.kind in {
            CommandKind.WOLF_KILL,
            CommandKind.INSPECT,
            CommandKind.WITCH_SAVE,
            CommandKind.WITCH_POISON,
            CommandKind.VOTE,
        }
        if needs_target and decision.target_id not in observation.legal_target_ids:
            return False
        return not decision.speech or len(decision.speech) <= 500

    @staticmethod
    def _fallback(failure_kind: str) -> AgentDecision:
        return AgentDecision(kind=CommandKind.NOOP, failure_kind=failure_kind)


def completion_metrics(decision: AgentDecision) -> ModelCompletion:
    """Expose normalized metrics for the later durable agent-run recorder."""
    return ModelCompletion(
        text="",
        input_tokens=decision.input_tokens,
        output_tokens=decision.output_tokens,
        cost_usd=decision.cost_usd,
        latency_ms=decision.latency_ms,
    )
