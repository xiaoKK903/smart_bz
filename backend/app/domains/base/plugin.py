"""领域插件基类 - 所有行业插件必须实现这些接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any


@dataclass
class Intent:
    id: str
    name: str
    description: str

    @classmethod
    def from_yaml(cls, data: dict) -> "Intent":
        return cls(id=data["id"], name=data["name"], description=data["description"])


@dataclass
class Slot:
    id: str
    type: str
    prompt: str
    required: bool = True
    pattern: Optional[str] = None
    values: Optional[list[str]] = None
    extract_hint: Optional[str] = None

    @classmethod
    def from_yaml(cls, data: dict, required: bool = True) -> "Slot":
        return cls(
            id=data["id"],
            type=data["type"],
            prompt=data["prompt"],
            required=required,
            pattern=data.get("pattern"),
            values=data.get("values"),
            extract_hint=data.get("extract_hint"),
        )


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    requires_confirmation: bool = False


@dataclass
class Session:
    session_id: str
    tenant_id: str
    user_id: str
    current_intent: Optional[str] = None
    slots: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)
    user_profile: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    quick_replies: list = field(default_factory=list)

    def get_slot(self, slot_id: str) -> Optional[Any]:
        return self.slots.get(slot_id)

    def set_slot(self, slot_id: str, value: Any):
        self.slots[slot_id] = value

    def set_quick_replies(self, replies: list[str]):
        self.quick_replies = replies

    def save_summary(self, summary: str):
        self.cache["summary"] = summary


class BaseDomainPlugin(ABC):
    """领域插件基类"""

    def __init__(self, config: dict):
        self.config = config

    def _find_intent(self, intent_id: str) -> dict:
        for intent in self.config.get("intents", []):
            if intent["id"] == intent_id:
                return intent
        raise ValueError(f"Intent not found: {intent_id}")

    @abstractmethod
    def get_intents(self) -> list[Intent]:
        """声明本插件处理的意图列表"""
        pass

    @abstractmethod
    def get_slots(self, intent: str) -> list[Slot]:
        """声明完成某意图需要的槽位"""
        pass

    @abstractmethod
    def build_context(self, session: Session) -> str:
        """构建领域特定的上下文（注入到 Prompt）"""
        pass

    @abstractmethod
    def get_system_prompt(self, intent: str) -> str:
        """返回领域 System Prompt"""
        pass

    @abstractmethod
    def post_process(self, response: str, session: Session) -> str:
        """领域特定的后处理"""
        pass

    def get_tools(self) -> list[Tool]:
        """可选：声明领域工具（Function Calling）"""
        return []

    def on_session_start(self, session: Session):
        """可选：会话开始时的初始化"""
        pass

    def on_session_end(self, session: Session):
        """可选：会话结束时的清理/总结"""
        pass
