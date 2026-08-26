"""狼人杀领域使用的稳定字符串枚举。"""

from enum import Enum


class Faction(str, Enum):
    """标准局的阵营。"""

    GOOD = "good"
    WOLF = "wolf"


class Phase(str, Enum):
    """标准局可推进的阶段。"""

    SETUP = "setup"
    NIGHT_WOLF = "night_wolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    FINISHED = "finished"


class GameStatus(str, Enum):
    """对局生命周期状态。"""

    RUNNING = "running"
    FINISHED = "finished"


class Visibility(str, Enum):
    """权威事件的可见范围。"""

    SERVER = "server"
    PUBLIC = "public"
    PRIVATE = "private"


class CommandKind(str, Enum):
    """玩家或策略可以提出的命令种类。"""

    WOLF_KILL = "wolf_kill"
    INSPECT = "inspect"
    WITCH_SAVE = "witch_save"
    WITCH_POISON = "witch_poison"
    SPEAK = "speak"
    END_DISCUSSION = "end_discussion"
    VOTE = "vote"
    ABSTAIN = "abstain"
    NOOP = "noop"


class EffectKind(str, Enum):
    """角色插件可以建议、但不能自行应用的效果种类。"""

    KILL = "kill"
    INSPECT = "inspect"
    SAVE = "save"
    POISON = "poison"
    SPEECH = "speech"
    VOTE = "vote"
