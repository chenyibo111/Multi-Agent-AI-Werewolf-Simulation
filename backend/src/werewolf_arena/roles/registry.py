"""可信角色插件的启动时注册表。"""

from werewolf_arena.domain.errors import DomainValidationError

from .base import RolePlugin


class RoleRegistry:
    """按稳定角色 ID 和版本检索插件。"""

    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str], RolePlugin] = {}

    def register(self, plugin: RolePlugin) -> None:
        """注册一个唯一版本；重复注册被拒绝。"""

        key = (plugin.definition.role_id, plugin.definition.version)
        if key in self._plugins:
            raise DomainValidationError("role version already registered")
        self._plugins[key] = plugin

    def get(self, role_id: str, version: str) -> RolePlugin:
        """读取已注册插件，未注册角色不能进入游戏模式。"""

        try:
            return self._plugins[(role_id, version)]
        except KeyError as error:
            raise DomainValidationError(f"role plugin is not registered: {role_id}@{version}") from error
