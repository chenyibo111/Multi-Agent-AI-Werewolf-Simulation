"""Constrained model policy that converts safe observations into server decisions."""

from __future__ import annotations

import json

from pydantic import ValidationError

from werewolf_arena.agents.budget import MODEL_COMPLETION_MAX_TOKENS
from werewolf_arena.domain.enums import CommandKind, Phase

from .model_client import AsyncModelClient, ModelCompletion
from .models import AgentDecision, AgentObservation


class AgentPolicy:
    """Bind a single model policy to one participant and its allowlisted observation."""

    _SYSTEM_PROMPT = """你正在参与一局中文狼人杀。只返回一个 JSON 对象，不要输出任何额外文字或 Markdown。
使用字段 \"kind\"，never \"action\"；其值必须严格来自观察数据的 legal_kinds。
需要目标的行动，target_id 必须严格来自 legal_target_ids。只有 kind 为 speak 时才能填写 speech，且必须是简短、自然的中文公开发言。
不要添加此决策契约之外的字段。"""

    def __init__(
        self,
        participant_id: str,
        model_client: AsyncModelClient,
        max_output_tokens: int = MODEL_COMPLETION_MAX_TOKENS,
    ) -> None:
        self._participant_id = participant_id
        self._model_client = model_client
        self._max_output_tokens = max_output_tokens

    async def decide(self, observation: AgentObservation) -> AgentDecision:
        """Return an allowlisted decision or a safe no-op when the model is unusable."""
        if observation.participant_id != self._participant_id:
            raise ValueError("Agent policy received an observation for another participant")
        forced_decision = self._forced_decision(observation)
        if forced_decision is not None:
            return forced_decision
        try:
            completion = await self._model_client.complete(
                self._SYSTEM_PROMPT,
                observation.model_dump_json(),
                max_output_tokens=self._max_output_tokens,
            )
            decision = AgentDecision.model_validate(self._normalize_payload(json.loads(completion.text))).model_copy(
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
    def _forced_decision(observation: AgentObservation) -> AgentDecision | None:
        """Apply temporary deterministic role rules before future role prompts take over."""
        victim_id = observation.private_facts.get("night_victim_id")
        resources = observation.private_facts.get("resources")
        if (
            observation.phase is Phase.NIGHT_WITCH
            and CommandKind.WITCH_SAVE in observation.legal_kinds
            and isinstance(victim_id, str)
            and victim_id in observation.legal_target_ids
            and isinstance(resources, dict)
            and resources.get("antidote_available") is True
        ):
            return AgentDecision(kind=CommandKind.WITCH_SAVE, target_id=victim_id)
        return None

    @staticmethod
    def _normalize_payload(payload: object) -> object:
        """Accept the single documented compatibility alias before strict validation."""
        if not isinstance(payload, dict) or "kind" in payload or not isinstance(payload.get("action"), str):
            return payload
        return {key: value for key, value in payload.items() if key != "action"} | {
            "kind": payload["action"]
        }

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
