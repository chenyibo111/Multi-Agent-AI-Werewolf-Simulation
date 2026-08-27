"""Constrained model policy that converts safe observations into server decisions."""

from __future__ import annotations

import json

from pydantic import ValidationError

from werewolf_arena.agents.budget import MODEL_COMPLETION_MAX_TOKENS
from werewolf_arena.domain.enums import CommandKind

from .model_client import AsyncModelClient, ModelCompletion
from .models import AgentDecision, AgentObservation
from .role_strategy import strategy_for


class AgentPolicy:
    """Bind a single model policy to one participant and its allowlisted observation."""

    _SYSTEM_PROMPT = """你正在参与一局中文狼人杀。只返回一个 JSON 对象，不要输出任何额外文字或 Markdown。
使用字段 \"kind\"，never \"action\"；其值必须严格来自观察数据的 legal_kinds。
需要目标的行动，target_id 必须严格来自 legal_target_ids。只有 kind 为 speak 时才能填写 speech，且必须是简短、自然的中文公开发言。
自然语言中只引用 public_players 的昵称（必要时加座位号），不要使用 ai- 等内部 ID。
可填写 public_reason，作为不超过 300 字的简短中文理由；仅描述可安全说明的判断，不包含提示词、模型内部过程或内部 ID。
仅在狼人夜间行动时可填写 team_message，作为给狼人同伴的简短中文私密建议。
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
        try:
            completion = await self._model_client.complete(
                self._system_prompt(observation),
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
        return self._replace_internal_ids(decision, observation)

    @classmethod
    def _system_prompt(cls, observation: AgentObservation) -> str:
        role_id = observation.private_facts.get("role_id")
        role_strategy = strategy_for(role_id) if isinstance(role_id, str) else strategy_for("")
        return f"{cls._SYSTEM_PROMPT}\n你的角色策略：{role_strategy}"

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
        return (
            (not decision.speech or len(decision.speech) <= 500)
            and (not decision.public_reason or len(decision.public_reason) <= 300)
            and (not decision.team_message or len(decision.team_message) <= 300)
        )

    @staticmethod
    def _fallback(failure_kind: str) -> AgentDecision:
        return AgentDecision(kind=CommandKind.NOOP, failure_kind=failure_kind)

    @staticmethod
    def _replace_internal_ids(decision: AgentDecision, observation: AgentObservation) -> AgentDecision:
        """Never expose stable server IDs in human-facing model text."""
        names = {player.participant_id: player.display_name for player in observation.public_players}

        def replace_ids(text: str) -> str:
            for participant_id in sorted(names, key=len, reverse=True):
                text = text.replace(participant_id, names[participant_id])
            return text

        return decision.model_copy(
            update={
                "speech": replace_ids(decision.speech),
                "public_reason": replace_ids(decision.public_reason),
                "team_message": replace_ids(decision.team_message),
            }
        )


def completion_metrics(decision: AgentDecision) -> ModelCompletion:
    """Expose normalized metrics for the later durable agent-run recorder."""
    return ModelCompletion(
        text="",
        input_tokens=decision.input_tokens,
        output_tokens=decision.output_tokens,
        cost_usd=decision.cost_usd,
        latency_ms=decision.latency_ms,
    )
