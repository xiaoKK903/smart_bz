"""会话状态机"""

from enum import Enum
from typing import Optional, Dict
import time


class SessionPhase(str, Enum):
    """会话阶段"""
    INIT = "init"                          # 初始状态
    INTENT_IDENTIFIED = "intent_identified" # 已识别意图
    SLOT_FILLING = "slot_filling"          # 槽位填充中
    PROCESSING = "processing"              # 处理中（构建上下文+调LLM）
    RESPONDING = "responding"              # 回复中
    COMPLETED = "completed"                # 已完成
    HUMAN_HANDOFF = "human_handoff"        # 已转人工


# 合法的状态转移
VALID_TRANSITIONS = {
    SessionPhase.INIT: [SessionPhase.INTENT_IDENTIFIED, SessionPhase.RESPONDING],
    SessionPhase.INTENT_IDENTIFIED: [SessionPhase.SLOT_FILLING, SessionPhase.PROCESSING, SessionPhase.HUMAN_HANDOFF],
    SessionPhase.SLOT_FILLING: [SessionPhase.SLOT_FILLING, SessionPhase.PROCESSING, SessionPhase.HUMAN_HANDOFF, SessionPhase.INIT],
    SessionPhase.PROCESSING: [SessionPhase.RESPONDING, SessionPhase.HUMAN_HANDOFF],
    SessionPhase.RESPONDING: [SessionPhase.COMPLETED, SessionPhase.INIT],
    SessionPhase.COMPLETED: [SessionPhase.INIT],
    SessionPhase.HUMAN_HANDOFF: [SessionPhase.INIT],
}

# 超时时间（秒）
SESSION_TIMEOUT = 1800  # 30分钟


class SessionState:
    """单个会话的状态"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.phase = SessionPhase.INIT
        self.intent: Optional[str] = None
        self.domain: Optional[str] = None
        self.slots: Dict[str, str] = {}
        self.slot_attempts: int = 0           # 追问次数
        self.max_slot_attempts: int = 5       # 最多追问5轮
        self.created_at: float = time.time()
        self.updated_at: float = time.time()

    def transition(self, new_phase: SessionPhase) -> bool:
        """
        状态转移

        Args:
            new_phase: 目标状态

        Returns:
            是否转移成功
        """
        valid = VALID_TRANSITIONS.get(self.phase, [])
        if new_phase in valid:
            self.phase = new_phase
            self.updated_at = time.time()
            return True
        # 允许任何状态回到 INIT（超时重置等场景）
        if new_phase == SessionPhase.INIT:
            self.phase = SessionPhase.INIT
            self.intent = None
            self.domain = None
            self.slots = {}
            self.slot_attempts = 0
            self.updated_at = time.time()
            return True
        return False

    def is_timed_out(self) -> bool:
        """检查会话是否超时"""
        return (time.time() - self.updated_at) > SESSION_TIMEOUT

    def set_intent(self, intent: str, domain: str):
        """设置识别到的意图"""
        self.intent = intent
        self.domain = domain
        self.updated_at = time.time()

    def fill_slot(self, key: str, value: str):
        """填充一个槽位"""
        self.slots[key] = value
        self.updated_at = time.time()

    def fill_slots(self, slots: Dict[str, str]):
        """批量填充槽位"""
        self.slots.update(slots)
        self.updated_at = time.time()

    def increment_attempt(self):
        """增加追问次数"""
        self.slot_attempts += 1

    def exceeded_max_attempts(self) -> bool:
        """是否超出最大追问次数"""
        return self.slot_attempts >= self.max_slot_attempts

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "intent": self.intent,
            "domain": self.domain,
            "slots": self.slots,
            "slot_attempts": self.slot_attempts,
        }


class StateManager:
    """全局状态管理器"""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        """获取或创建会话状态"""
        state = self._sessions.get(session_id)
        if state is None or state.is_timed_out():
            state = SessionState(session_id)
            self._sessions[session_id] = state
        return state

    def remove(self, session_id: str):
        """移除会话状态"""
        self._sessions.pop(session_id, None)

    def cleanup_expired(self):
        """清理过期会话"""
        expired = [sid for sid, s in self._sessions.items() if s.is_timed_out()]
        for sid in expired:
            del self._sessions[sid]


# 全局实例
state_manager = StateManager()
