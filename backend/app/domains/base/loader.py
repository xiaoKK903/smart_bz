"""插件加载器 - 动态发现和加载领域插件"""

import importlib
import yaml
from pathlib import Path
from typing import Optional

from .plugin import BaseDomainPlugin
from .registry import PluginRegistry


class PluginLoader:
    """从 domains/ 目录动态加载插件"""

    def __init__(self, domains_dir: str = None):
        self.domains_dir = Path(domains_dir or Path(__file__).parent.parent / "domains")
        self.registry = PluginRegistry()

    def discover(self) -> list[str]:
        """发现所有可用插件（含 config.yaml 的目录）"""
        plugins = []
        for path in self.domains_dir.iterdir():
            if path.is_dir() and (path / "config.yaml").exists():
                if path.name not in ("base", "template", "__pycache__"):
                    plugins.append(path.name)
        return plugins

    def load(self, plugin_name: str) -> BaseDomainPlugin:
        """加载指定插件"""
        plugin_dir = self.domains_dir / plugin_name

        # 读取配置
        config_path = plugin_dir / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 动态导入插件模块
        module = importlib.import_module(f"app.domains.{plugin_name}.plugin")

        # 查找插件类（BaseDomainPlugin 的子类）
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseDomainPlugin)
                and attr is not BaseDomainPlugin
            ):
                plugin_class = attr
                break

        if not plugin_class:
            raise ValueError(f"No plugin class found in {plugin_name}/plugin.py")

        instance = plugin_class(config)
        self.registry.register(plugin_name, instance)
        return instance

    def load_all(self) -> dict[str, BaseDomainPlugin]:
        """加载所有发现的插件"""
        plugins = {}
        for name in self.discover():
            try:
                plugins[name] = self.load(name)
            except Exception as e:
                print(f"[PluginLoader] Failed to load '{name}': {e}")
        return plugins
