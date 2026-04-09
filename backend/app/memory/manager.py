#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆管理器
统一调度三层记忆：短期记忆（Redis）、用户画像（PostgreSQL）、长期情景记忆（ChromaDB）

支持三层记忆的增/查/删，含权限验证与操作日志。
"""

import json
import os
import time
from datetime import datetime

from app.memory.short_term import SessionState, Phase
from app.memory.user_profile import get_user_profile, update_user_profile, delete_user_profile, clear_user_profile_field
from app.memory.long_term import long_term_memory


# ================================================================
#  操作日志记录器
# ================================================================

_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'logs')


class _DeletionLogger:
    """记忆删除操作日志 — JSON Lines 格式"""

    def __init__(self, log_dir: str = _LOG_DIR):
        self._log_dir = log_dir
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_file = os.path.join(self._log_dir, 'memory_deletion.jsonl')

    def log(self, *, operator_id: str, user_id: str, tenant_id: str, memory_type: str,
            action: str, target: str, success: bool,
            reason: str = "", detail: str = ""):
        """写入一条删除操作日志"""
        entry = {
            "ts": datetime.now().isoformat(),
            "operator": operator_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "memory_type": memory_type,
            "action": action,
            "target": target,
            "success": success,
            "reason": reason,
            "detail": detail,
        }
        try:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[DeletionLogger] 日志写入失败: {e}")

    def query(self, user_id: str = None, tenant_id: str = None, limit: int = 50) -> list:
        """查询删除日志（最近 N 条，可按 user_id 过滤）"""
        entries = []
        try:
            if not os.path.exists(self._log_file):
                return entries
            with open(self._log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if user_id and record.get("user_id") != user_id:
                            continue
                        if tenant_id and record.get("tenant_id") != tenant_id:
                            continue
                        entries.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        # 返回最近的 limit 条
        return entries[-limit:]


_deletion_logger = _DeletionLogger()


class MemoryManager:
    """记忆管理器"""

    def __init__(self):
        self.long_term = long_term_memory

    # ================================================================
    #  核心接口：get_context（conversation.py 调用）
    # ================================================================

    def get_context(self, session_id: str, user_id: str, tenant_id: str) -> dict:
        """
        为当前对话构建记忆上下文，供 system prompt 注入。

        返回:
            {
                "slots": {k: v, ...},         # 画像中的槽位数据
                "user_profile": {...} | None,  # 用户画像
                "recent_consultations": [...],  # 最近咨询结论
                "related_episodes": [...],      # 相关情景记忆
            }
        """
        ctx = {
            "slots": {},
            "user_profile": None,
            "recent_consultations": [],
            "related_episodes": [],
        }

        # ---------- 用户画像 ----------
        profile = get_user_profile(user_id, tenant_id)
        if profile:
            ctx["user_profile"] = profile
            # 从画像提取槽位
            slot_mapping = {
                "birth_year": "birthday",
                "gender": "gender",
                "name": "name",
                "occupation": "occupation",
            }
            for slot_key, profile_key in slot_mapping.items():
                v = profile.get(profile_key)
                if v:
                    if slot_key == "birth_year" and v:
                        # birthday 可能是 "1990-03-15"
                        parts = str(v).split("-")
                        if len(parts) >= 1 and parts[0].isdigit():
                            ctx["slots"]["birth_year"] = parts[0]
                        if len(parts) >= 2:
                            ctx["slots"]["birth_month"] = parts[1]
                        if len(parts) >= 3:
                            ctx["slots"]["birth_day"] = parts[2]
                    else:
                        ctx["slots"][slot_key] = str(v)

        # ---------- 短期记忆（Session 槽位）补充 ----------
        try:
            ss = SessionState(session_id, tenant_id)
            session_slots = ss.get_slots()
            if session_slots:
                # 短期记忆的槽位优先级高于画像
                ctx["slots"].update(session_slots)
        except Exception as e:
            print(f"[MemoryManager] 短期记忆读取异常: {e}")

        # ---------- 长期记忆：最近咨询 ----------
        try:
            recent = self.long_term.recall_consultations(user_id, tenant_id, "最近咨询", top_k=3)
            if recent:
                ctx["recent_consultations"] = recent
        except Exception as e:
            print(f"[MemoryManager] 咨询记忆检索异常: {e}")

        return ctx

    # ================================================================
    #  按查询检索相关长期记忆（每轮对话时调用）
    # ================================================================

    def get_relevant_context(self, user_id: str, tenant_id: str, query: str) -> dict:
        """
        根据用户当前消息，检索相关的长期记忆。

        Returns:
            {
                "related_episodes": [...],
                "past_consultations": [...],
            }
        """
        extra = {
            "related_episodes": [],
            "past_consultations": [],
        }
        try:
            episodes = self.long_term.recall_episodes(user_id, tenant_id, query, top_k=3)
            if episodes:
                extra["related_episodes"] = episodes
        except Exception:
            pass
        try:
            consults = self.long_term.recall_consultations(user_id, tenant_id, query, top_k=2)
            if consults:
                extra["past_consultations"] = consults
        except Exception:
            pass
        return extra

    # ================================================================
    #  通用读写接口
    # ================================================================

    def get_memory(self, user_id, tenant_id, query=None, memory_type=None):
        """获取记忆"""
        memories = {}

        if memory_type in (None, "short_term"):
            session_state = SessionState(user_id, tenant_id)
            session_data = session_state.get_state()
            slots = session_state.get_slots()
            memories["short_term"] = {
                "session_state": session_data,
                "slots": slots,
            }

        if memory_type in (None, "user_profile"):
            user_info = get_user_profile(user_id, tenant_id)
            memories["user_profile"] = {
                "user_info": user_info,
            }

        if memory_type in (None, "long_term") and query:
            long_term_memories = self.long_term.retrieve_memory(user_id, tenant_id, query)
            memories["long_term"] = long_term_memories
        elif memory_type in (None, "long_term"):
            long_term_memories = self.long_term.get_user_memories(user_id, tenant_id)
            memories["long_term"] = long_term_memories

        return {"success": True, "memories": memories}

    def store_memory(self, user_id, tenant_id, memory):
        """存储记忆"""
        memory_type = memory.get("type")
        data = memory.get("data", {})

        if memory_type == "short_term":
            session_state = SessionState(user_id, tenant_id)
            if "session_state" in data:
                if "phase" in data["session_state"]:
                    session_state.transition(data["session_state"]["phase"])
                if "intent" in data["session_state"]:
                    session_state.set_intent(data["session_state"]["intent"])
            if "slots" in data:
                session_state.fill_slots(data["slots"])
            return {"success": True, "message": "短期记忆存储成功"}

        elif memory_type == "user_profile":
            if "user_info" in data:
                update_user_profile(user_id, tenant_id, **data["user_info"])
            return {"success": True, "message": "用户画像存储成功"}

        elif memory_type == "long_term":
            result = self.long_term.store_memory(user_id, tenant_id, data)
            return result
        
        return {"success": False, "message": "无效的记忆类型"}

    # ================================================================
    #  记忆删除（含权限验证 + 操作日志）
    # ================================================================

    def delete_memory(self, user_id: str, tenant_id: str, memory_id: str = None,
                      memory_type: str = None, *,
                      field: str = None,
                      slot_keys: list = None,
                      sub_type: str = None,
                      operator_id: str = None,
                      reason: str = "") -> dict:
        """
        删除指定类型的记忆数据。

        Args:
            user_id:      目标用户 ID
            tenant_id:    租户 ID
            memory_id:    具体记忆 ID（长期记忆的 ep_/consult_/fb_ ID）
            memory_type:  记忆层级 — "short_term" | "user_profile" | "long_term"
            field:        指定字段/子项（见下方说明）
            slot_keys:    短期记忆：要删除的槽位键列表
            sub_type:     长期记忆子类型 — "episode" | "consultation" | "feedback"
            operator_id:  操作者 ID（默认 = user_id，即自助删除）
            reason:       删除原因（记入日志）

        支持的组合:

        短期记忆 (short_term):
            memory_type="short_term"                         → 重置整个会话
            memory_type="short_term", slot_keys=["birth_year", ...] → 删除指定槽位
            memory_type="short_term", field="slots"          → 清除所有槽位

        用户画像 (user_profile):
            memory_type="user_profile"                       → 删除整个画像
            memory_type="user_profile", field="name"         → 清除姓名 (name/birthday/gender/occupation)

        长期记忆 (long_term):
            memory_type="long_term", memory_id="ep_xxx"      → 删除指定记忆
            memory_type="long_term", sub_type="episode"      → 删除该用户所有情景记忆
            memory_type="long_term"                          → 删除该用户全部长期记忆

        Returns:
            {"success": bool, "message": str, "deleted_count": int}
        """
        if not user_id:
            return {"success": False, "message": "缺少 user_id"}
        if not tenant_id:
            return {"success": False, "message": "缺少 tenant_id"}
        if not memory_type:
            return {"success": False, "message": "缺少 memory_type"}

        # ---- 权限验证 ----
        effective_operator = operator_id or user_id
        perm = self._check_permission(effective_operator, user_id, tenant_id, memory_type)
        if not perm["allowed"]:
            _deletion_logger.log(
                operator_id=effective_operator, user_id=user_id, tenant_id=tenant_id,
                memory_type=memory_type, action="delete",
                target=memory_id or field or sub_type or "all",
                success=False, reason=reason,
                detail=f"权限拒绝: {perm['reason']}")
            return {"success": False, "message": perm["reason"]}

        # ---- 分发到具体处理器 ----
        if memory_type == "short_term":
            return self._delete_short_term(
                user_id, tenant_id, field=field, slot_keys=slot_keys,
                operator_id=effective_operator, reason=reason)
        elif memory_type == "user_profile":
            return self._delete_user_profile(
                user_id, tenant_id, field=field, memory_id=memory_id,
                operator_id=effective_operator, reason=reason)
        elif memory_type == "long_term":
            return self._delete_long_term(
                user_id, tenant_id, memory_id=memory_id, sub_type=sub_type,
                operator_id=effective_operator, reason=reason)
        else:
            return {"success": False, "message": f"不支持的记忆类型: {memory_type}"}

    # ---------- 权限验证 ----------

    @staticmethod
    def _check_permission(operator_id: str, user_id: str, tenant_id: str,
                          memory_type: str) -> dict:
        """
        基础权限验证：用户只能删除自己的记忆。

        Returns:
            {"allowed": bool, "reason": str}
        """
        if not operator_id:
            return {"allowed": False, "reason": "缺少操作者身份"}
        if operator_id != user_id:
            return {"allowed": False,
                    "reason": f"操作者 {operator_id} 无权删除用户 {user_id} 的记忆"}
        if memory_type not in ("short_term", "user_profile", "long_term"):
            return {"allowed": False,
                    "reason": f"无效的记忆类型: {memory_type}"}
        return {"allowed": True, "reason": ""}

    # ---------- 短期记忆删除 ----------

    def _delete_short_term(self, user_id: str, tenant_id: str, *,
                           field: str = None,
                           slot_keys: list = None,
                           operator_id: str, reason: str) -> dict:
        """短期记忆删除（Redis）"""
        try:
            ss = SessionState(user_id, tenant_id)

            if slot_keys:
                # 删除指定槽位
                ss.delete_slots(slot_keys)
                target_desc = f"slots: {slot_keys}"
                msg = f"已删除槽位: {', '.join(slot_keys)}"
                count = len(slot_keys)

            elif field == "slots":
                # 清除所有槽位
                ss.clear_all_slots()
                target_desc = "all_slots"
                msg = "已清除所有槽位"
                count = 1

            else:
                # 重置整个会话
                ss.reset()
                target_desc = "entire_session"
                msg = "短期记忆已全部清除"
                count = 1

            _deletion_logger.log(
                operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                memory_type="short_term", action="delete",
                target=target_desc, success=True,
                reason=reason)
            return {"success": True, "message": msg, "deleted_count": count}

        except Exception as e:
            _deletion_logger.log(
                operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                memory_type="short_term", action="delete",
                target=field or "session", success=False,
                reason=reason, detail=str(e))
            return {"success": False, "message": f"短期记忆删除失败: {e}",
                    "deleted_count": 0}

    # ---------- 用户画像删除 ----------

    def _delete_user_profile(self, user_id: str, tenant_id: str, *,
                             field: str = None,
                             memory_id: str = None,
                             operator_id: str, reason: str) -> dict:
        """用户画像删除（PostgreSQL）"""
        try:
            profile = get_user_profile(user_id, tenant_id)

            if field in ("name", "birthday", "gender", "occupation"):
                # 清除指定画像字段
                ok = clear_user_profile_field(user_id, tenant_id, field)
                msg = f"已清除 {field} 字段" if ok else \
                      f"清除 {field} 失败（用户不存在或字段已为空）"
                _deletion_logger.log(
                    operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                    memory_type="user_profile", action="clear_field",
                    target=field, success=ok, reason=reason)
                return {"success": ok, "message": msg,
                        "deleted_count": 1 if ok else 0}

            elif field:
                return {"success": False,
                        "message": f"不支持清除的字段: {field}",
                        "deleted_count": 0}

            else:
                # 删除整个用户画像
                ok = delete_user_profile(user_id, tenant_id)
                msg = "已删除完整用户画像" if ok else "用户画像不存在"
                _deletion_logger.log(
                    operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                    memory_type="user_profile", action="delete_full_profile",
                    target="entire_profile", success=ok, reason=reason)
                return {"success": ok, "message": msg,
                        "deleted_count": 1 if ok else 0}

        except Exception as e:
            _deletion_logger.log(
                operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                memory_type="user_profile", action="delete",
                target=field or memory_id or "profile", success=False,
                reason=reason, detail=str(e))
            return {"success": False, "message": f"用户画像删除失败: {e}",
                    "deleted_count": 0}

    # ---------- 长期记忆删除 ----------

    def _delete_long_term(self, user_id: str, tenant_id: str, *,
                          memory_id: str = None,
                          sub_type: str = None,
                          operator_id: str, reason: str) -> dict:
        """长期记忆删除（ChromaDB）"""
        try:
            if memory_id:
                # 删除单条记忆
                result = self.long_term.delete_memory(memory_id)
                ok = result.get("success", False)
                _deletion_logger.log(
                    operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                    memory_type="long_term", action="delete_single",
                    target=memory_id, success=ok, reason=reason,
                    detail=result.get("message", ""))
                return {"success": ok,
                        "message": f"已删除记忆 {memory_id}" if ok else
                                   result.get("message", "删除失败"),
                        "deleted_count": 1 if ok else 0}

            # 批量删除 — 按 sub_type 或全部
            if sub_type:
                # 删除指定子类型的全部记忆
                deleted = self.long_term.delete_user_memories(user_id, tenant_id, sub_type)
            else:
                # 删除该用户的全部长期记忆
                deleted = self.long_term.delete_user_memories(user_id, tenant_id)

            target_desc = sub_type or "all"
            _deletion_logger.log(
                operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                memory_type="long_term", action="delete_bulk",
                target=target_desc, success=True, reason=reason,
                detail=f"共删除 {deleted} 条")
            return {
                "success": True,
                "message": f"已删除长期记忆 {deleted} 条",
                "deleted_count": deleted,
            }

        except Exception as e:
            _deletion_logger.log(
                operator_id=operator_id, user_id=user_id, tenant_id=tenant_id,
                memory_type="long_term", action="delete",
                target=memory_id or sub_type or "all", success=False,
                reason=reason, detail=str(e))
            return {"success": False, "message": f"长期记忆删除失败: {e}",
                    "deleted_count": 0}

    # ---------- 删除日志查询 ----------

    def get_deletion_logs(self, user_id: str = None, tenant_id: str = None,
                          limit: int = 50) -> dict:
        """
        查询记忆删除操作日志。

        Args:
            user_id: 按用户过滤（None = 全部）
            tenant_id: 按租户过滤（None = 全部）
            limit:   最多返回条数

        Returns:
            {"success": True, "logs": [...]}
        """
        logs = _deletion_logger.query(user_id=user_id, tenant_id=tenant_id, limit=limit)
        return {"success": True, "logs": logs}

    def get_relevant_memory(self, user_id, tenant_id, query, max_tokens=1000):
        """获取与查询相关的记忆（控制 token 使用）"""
        session_state = SessionState(user_id, tenant_id)
        session_data = session_state.get_state()
        slots = session_state.get_slots()

        user_info = get_user_profile(user_id, tenant_id)

        long_term_memories = self.long_term.retrieve_memory(user_id, tenant_id, query, top_k=3)

        return {
            "success": True,
            "relevant_memory": {
                "short_term": {"session_state": session_data, "slots": slots},
                "user_profile": {"user_info": user_info},
                "long_term": long_term_memories.get("memories", [])[:2],
            },
        }

    def check_memory_consistency(self, user_id, tenant_id):
        """检查记忆一致性"""
        user_info = get_user_profile(user_id, tenant_id)
        if not user_info:
            return {"success": False, "message": "用户不存在"}

        session_state = SessionState(user_id, tenant_id)
        session_data = session_state.get_state()
        long_term_count = len(self.long_term.get_user_memories(user_id, tenant_id).get("memories", []))

        return {
            "success": True,
            "consistency": {
                "user_exists": True,
                "session_active": session_data is not None,
                "long_term_count": long_term_count,
            },
        }

    def health(self, tenant_id: str = "test"):
        """健康检查"""
        try:
            test_session = SessionState("test_health", tenant_id)
            test_session.set_intent("test")
            test_session.fill_slots({"test": "value"})
            test_session.reset()

            test_memory = {
                "content": "健康检查测试",
                "metadata": {"type": "test", "timestamp": time.time()},
            }
            store_result = self.long_term.store_memory("test_health", tenant_id, test_memory)
            if store_result.get("success"):
                memory_id = store_result.get("memory_id")
                if memory_id:
                    self.long_term.delete_memory(memory_id)

            return {"status": "ok", "short_term": "connected", "long_term": "connected"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# 全局实例
memory_manager = MemoryManager()