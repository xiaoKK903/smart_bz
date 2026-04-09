"""插件注册表 - 管理已加载的领域插件"""

from typing import Optional
from .plugin import BaseDomainPlugin


class PluginRegistry:
    """单例注册表，管理所有已加载的插件"""

    _instance: Optional["PluginRegistry"] = None
    _plugins: dict[str, BaseDomainPlugin] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._plugins = {}
        return cls._instance

    def register(self, name: str, plugin: BaseDomainPlugin):
        self._plugins[name] = plugin

    def get(self, name: str) -> Optional[BaseDomainPlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        return list(self._plugins.keys())

    def unregister(self, name: str):
        self._plugins.pop(name, None)
