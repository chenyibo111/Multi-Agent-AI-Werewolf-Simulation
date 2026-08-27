"""Fixed, role-aware strategy cards for constrained AI decisions."""

from __future__ import annotations

_ROLE_STRATEGIES = {
    "wolf": "你的身份是狼人。优先伪装成可信好人，与同伴协作并结合公开发言选择击杀和投票目标。",
    "seer": "你的身份是预言家。谨慎规划查验，基于查验结果和公开发言建立可信身份判断。",
    "witch": "你的身份是女巫。审慎使用药剂：结合夜间受害者与公开局势，独立决定救人、用毒或保留药剂。",
    "villager": "你的身份是平民。关注发言矛盾、行为动机和票型变化，用公开信息作出判断。",
}
_DEFAULT_STRATEGY = "基于你被允许看到的事实、当前合法行动和公开信息作出谨慎判断。"


def strategy_for(role_id: str) -> str:
    """Return a fixed Chinese strategy instruction without granting extra authority."""
    return _ROLE_STRATEGIES.get(role_id, _DEFAULT_STRATEGY)
