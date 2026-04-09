"""Prompt 版本管理"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PromptVersion:
    id: str
    version: str          # "1.0.0"
    template: str
    variables: list[str]  # 模板变量
    is_active: bool = True
    ab_group: Optional[str] = None  # A/B 测试分组


class PromptManager:
    """
    Prompt 模板管理：
    - 版本化：每次修改生成新版本，可回滚
    - A/B 测试：同一意图可配多个版本，按比例分流
    - 变量注入：{context}, {user_name}, {order_info} 等动态替换
    """

    def __init__(self, prompts_dir: str = "./prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._versions: dict[str, list[PromptVersion]] = {}

    def get_active(self, intent: str, ab_group: str = None) -> Optional[PromptVersion]:
        """获取当前生效的 prompt 版本"""
        versions = self._versions.get(intent, [])
        for v in versions:
            if v.is_active:
                if ab_group and v.ab_group and v.ab_group != ab_group:
                    continue
                return v
        return None

    def render(self, prompt: PromptVersion, **kwargs) -> str:
        """渲染模板，注入变量"""
        result = prompt.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def rollback(self, intent: str, target_version: str):
        """回滚到指定版本"""
        versions = self._versions.get(intent, [])
        for v in versions:
            v.is_active = (v.version == target_version)
