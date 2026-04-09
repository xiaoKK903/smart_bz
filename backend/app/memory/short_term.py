#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短期记忆模块（Layer 1）
基于 Redis Hash 跟踪对话阶段与槽位填充
"""

import json
import time
from typing import Optional

from app.core.redis_client import get_redis, make_key


# ========== 状态常量 ==========

class Phase:
    """对话阶段枚举"""
    GREETING        = "greeting"          # 初始问候
    COLLECTING_INFO  = "collecting_info"   # 收集信息（槽位填充）
    ANALYZING       = "analyzing"         # 分析中
    ADVISING        = "advising"          # 给出建议
    FOLLOW_UP       = "follow_up"         # 追问 / 深入讨论

    ALL = (GREETING, COLLECTING_INFO, ANALYZING, ADVISING, FOLLOW_UP)


# ========== 合法转换表 ==========
# key: 当前状态 → value: 允许跳转到的目标状态集合

VALID_TRANSITIONS = {
    Phase.GREETING: {
        Phase.COLLECTING_INFO,   # 用户开始对话，进入信息收集
        Phase.ADVISING,          # 老用户，已有信息，直接进入建议
    },
    Phase.COLLECTING_INFO: {
        Phase.ANALYZING,         # 槽位填满，进入分析
        Phase.GREETING,          # 用户中途跑题 / 重新开始
    },
    Phase.ANALYZING: {
        Phase.ADVISING,          # 分析完成，开始给建议
        Phase.COLLECTING_INFO,   # 分析发现信息不足，回去补充
    },
    Phase.ADVISING: {
        Phase.FOLLOW_UP,         # 用户追问
        Phase.COLLECTING_INFO,   # 用户换了一个主题来问
        Phase.GREETING,          # 结束本次咨询
    },
    Phase.FOLLOW_UP: {
        Phase.ADVISING,          # 继续给建议
        Phase.COLLECTING_INFO,   # 用户换主题
        Phase.GREETING,          # 结束
    },
}


# ========== TTL 配置 ==========

TTL_SESSION = 7200      # 会话状态: 2 小时
TTL_SLOTS   = 7200      # 槽位: 2 小时
TTL_CALC    = 86400     # 计算结果缓存: 24 小时

# 通用必填槽位
REQUIRED_SLOTS = ("name", "email", "phone")


# ========== 会话状态机 ==========

class SessionState:
    """
    Redis-backed 会话状态机。

    每个会话 (session_id) 对应一组 Redis key：
      {tenant}:session:{sid}:state  — Hash  (phase / intent / turn_count / ...)
      {tenant}:session:{sid}:slots  — Hash  (name / email / phone / ...)
      {tenant}:session:{sid}:calc   — String (计算结果 JSON)

    用法:
        ss = SessionState(session_id, tenant_id)
        state = ss.get_state()           # 读取当前状态
        ss.transition(Phase.COLLECTING_INFO)  # 安全跳转
        ss.fill_slot("name", "张三")
        missing = ss.get_missing_slots()
    """

    def __init__(self, session_id: str, tenant_id: str):
        self.sid = session_id
        self.tenant = tenant_id
        self.r = get_redis()
        self._state_key = make_key(f"{tenant_id}:session:{session_id}:state")
        self._slots_key = make_key(f"{tenant_id}:session:{session_id}:slots")
        self._calc_key  = make_key(f"{tenant_id}:session:{session_id}:calc")

    # ---------- 状态读写 ----------

    def get_state(self) -> dict:
        """
        获取当前会话状态。
        如果 Redis 中无记录，返回初始 greeting 状态。
        """
        data = self.r.hgetall(self._state_key)
        if not data:
            return self._init_state()
        # turn_count 等数值字段转型
        data["turn_count"] = int(data.get("turn_count", 0))
        data["created_at"] = float(data.get("created_at", 0))
        data["last_active"] = float(data.get("last_active", 0))
        return data

    def _init_state(self) -> dict:
        """初始化新会话状态并写入 Redis"""
        now = time.time()
        state = {
            "phase": Phase.GREETING,
            "intent": "",
            "sub_intent": "",
            "turn_count": 0,
            "created_at": now,
            "last_active": now,
        }
        self.r.hset(self._state_key, mapping={
            k: str(v) if isinstance(v, (int, float)) else v
            for k, v in state.items()
        })
        self.r.expire(self._state_key, TTL_SESSION)
        return state

    def _update_fields(self, **fields):
        """批量更新状态字段"""
        mapping = {}
        for k, v in fields.items():
            mapping[k] = str(v) if isinstance(v, (int, float)) else v
        mapping["last_active"] = str(time.time())
        self.r.hset(self._state_key, mapping=mapping)
        self.r.expire(self._state_key, TTL_SESSION)

    # ---------- 状态转换 ----------

    def transition(self, target_phase: str, force: bool = False) -> dict:
        """
        将会话转换到 target_phase。

        Args:
            target_phase: 目标阶段（Phase 常量）
            force: True 则跳过合法性检查（慎用，仅测试/重置）

        Returns:
            转换后的完整状态 dict

        Raises:
            ValueError: 目标状态不合法 / 转换不合法
        """
        if target_phase not in Phase.ALL:
            raise ValueError(f"未知阶段: {target_phase}")

        current = self.get_state()
        current_phase = current["phase"]

        if not force and current_phase == target_phase:
            # 同状态不报错，刷新 last_active
            self._update_fields()
            return self.get_state()

        if not force:
            allowed = VALID_TRANSITIONS.get(current_phase, set())
            if target_phase not in allowed:
                raise ValueError(
                    f"非法状态转换: {current_phase} → {target_phase}  "
                    f"(允许: {', '.join(sorted(allowed))})"
                )

        self._update_fields(phase=target_phase)
        return self.get_state()

    def get_phase(self) -> str:
        """快捷读取当前阶段"""
        return self.r.hget(self._state_key, "phase") or Phase.GREETING

    # ---------- 意图 ----------

    def set_intent(self, intent: str, sub_intent: str = ""):
        """设置当前意图"""
        fields = {"intent": intent}
        if sub_intent:
            fields["sub_intent"] = sub_intent
        self._update_fields(**fields)

    # ---------- 轮次计数 ----------

    def increment_turn(self) -> int:
        """对话轮次 +1，返回新值"""
        new_count = self.r.hincrby(self._state_key, "turn_count", 1)
        self._update_fields()  # 刷新 last_active
        return new_count

    # ---------- 槽位管理 ----------

    def fill_slot(self, key: str, value: str):
        """填充单个槽位"""
        self.r.hset(self._slots_key, key, value)
        self.r.expire(self._slots_key, TTL_SLOTS)

    def fill_slots(self, data: dict):
        """批量填充槽位"""
        if not data:
            return
        self.r.hset(self._slots_key, mapping=data)
        self.r.expire(self._slots_key, TTL_SLOTS)

    def get_slots(self) -> dict:
        """获取所有已填槽位"""
        return self.r.hgetall(self._slots_key) or {}

    def get_slot(self, key: str) -> Optional[str]:
        """获取单个槽位值"""
        return self.r.hget(self._slots_key, key)

    def get_missing_slots(self) -> list:
        """返回尚未填充的必填槽位列表"""
        filled = self.get_slots()
        return [s for s in REQUIRED_SLOTS if s not in filled or not filled[s]]

    def slots_complete(self) -> bool:
        """必填槽位是否全部填充"""
        return len(self.get_missing_slots()) == 0

    # ---------- 计算缓存 ----------

    def cache_calculation(self, calc: dict):
        """缓存计算结果（JSON）"""
        self.r.setex(
            self._calc_key,
            TTL_CALC,
            json.dumps(calc, ensure_ascii=False),
        )

    def get_calculation(self) -> Optional[dict]:
        """读取缓存的计算结果"""
        raw = self.r.get(self._calc_key)
        return json.loads(raw) if raw else None

    # ---------- 槽位删除 ----------

    def delete_slot(self, key: str):
        """删除单个槽位"""
        self.r.hdel(self._slots_key, key)

    def delete_slots(self, keys: list):
        """批量删除指定槽位"""
        if keys:
            self.r.hdel(self._slots_key, *keys)

    def clear_all_slots(self):
        """清除所有槽位（保留会话状态）"""
        self.r.delete(self._slots_key)

    def clear_calculation(self):
        """清除计算缓存"""
        self.r.delete(self._calc_key)

    # ---------- 会话重置 ----------

    def reset(self):
        """清除该会话的全部 Redis 数据并回到 greeting"""
        pipe = self.r.pipeline()
        pipe.delete(self._state_key)
        pipe.delete(self._slots_key)
        pipe.delete(self._calc_key)
        pipe.execute()
        self._init_state()

    # ---------- 自动状态推进 ----------

    def auto_advance(self, intent: str) -> str:
        """
        根据意图和当前槽位自动推进状态。
        供 server.py 的 _handle_interpret 调用，替代硬编码 if/else。

        逻辑:
          1. greeting + 业务相关意图 → collecting_info
          2. collecting_info + 槽位全满 → analyzing
          3. analyzing → advising (分析完成后由外部调用)
          4. advising + 新问题 → follow_up

        Args:
            intent: 意图分类器返回的意图字符串

        Returns:
            推进后的当前阶段
        """
        phase = self.get_phase()

        # 业务相关意图列表
        business_intents = {
            "bazi_query", "career_advice", "investment_advice",
            "relationship_advice", "health_advice",
            "location_advice", "risk_tips",
            "general_query", "customer_service",
        }

        # --- 规则 1: greeting → collecting_info ---
        if phase == Phase.GREETING and intent in business_intents:
            self.transition(Phase.COLLECTING_INFO)
            self.set_intent(intent)
            return Phase.COLLECTING_INFO

        # --- 规则 2: collecting_info + 槽位全满 → analyzing ---
        if phase == Phase.COLLECTING_INFO and self.slots_complete():
            self.transition(Phase.ANALYZING)
            return Phase.ANALYZING

        # --- 规则 3: advising + 继续追问 → follow_up ---
        if phase == Phase.ADVISING and intent in business_intents:
            self.transition(Phase.FOLLOW_UP)
            self.set_intent(intent)
            return Phase.FOLLOW_UP

        # --- 规则 4: follow_up 继续追问保持 follow_up ---
        if phase == Phase.FOLLOW_UP and intent in business_intents:
            self.set_intent(intent)
            return Phase.FOLLOW_UP

        # --- 规则 5: 任何阶段 + greeting/farewell → greeting ---
        if intent in ("greeting", "farewell") and phase != Phase.GREETING:
            self.transition(Phase.GREETING, force=True)
            return Phase.GREETING

        # 其他情况：保持当前阶段
        self.set_intent(intent)
        return phase

    # ---------- 调试 ----------

    def dump(self) -> dict:
        """一次性读取全部会话数据（调试用）"""
        return {
            "state": self.get_state(),
            "slots": self.get_slots(),
            "calc": self.get_calculation(),
            "missing_slots": self.get_missing_slots(),
        }

    def __repr__(self):
        return f"<SessionState sid={self.sid} phase={self.get_phase()}>"