"""对话引擎 — 串通插件系统的完整对话主链路"""

import uuid
import time
from typing import Dict, List, Optional

from app.core.intent import intent_classifier
from app.core.slot import slot_manager
from app.core.state import state_manager, SessionPhase
from app.core.router import domain_router
from app.memory import memory_manager
from app.rag import knowledge_base
from app.guardrails import input_filter, output_validator
from app.llm import router as llm_router
from app.llm.prompt_builder import (
    build_system_prompt, build_user_message,
    format_memory_context, format_rag_results,
)
from app.llm.fallback import get_fallback_reply


class ConversationManager:
    """对话管理器"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self, user_id: str, tenant_id: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created_at": time.time(),
            "last_active": time.time(),
            "messages": [],
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str):
        session = self.get_session(session_id)
        if session:
            session["messages"].append({
                "role": role, "content": content, "timestamp": time.time(),
            })
            session["last_active"] = time.time()

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session["messages"][-limit:]

    # ════════════════════════════════════════
    #  核心：处理用户消息
    # ════════════════════════════════════════

    async def process_message(
        self, session_id: str, user_id: str, tenant_id: str, message: str
    ) -> Dict:
        """
        完整的对话处理流程:
        输入过滤 → 意图识别 → 领域路由 → 槽位填充 → 上下文构建 → LLM → 输出验证 → 后处理
        """

        # ── 1. 输入过滤 ──
        filter_result = input_filter.filter_input(message)
        if not filter_result.get("is_safe", True):
            warnings = filter_result.get("warnings", [])
            # 只有真正危险的才拦截（注入），敏感词和PII只记录不拦截
            has_injection = any("注入" in w for w in warnings)
            if has_injection:
                return self._build_response(
                    session_id, message,
                    reply="您的消息包含不适当内容，请重新输入。",
                    intent="filtered", confidence=1.0,
                )
        # 使用过滤后的文本
        clean_message = filter_result.get("filtered", message)

        # ── 2. 获取会话状态 ──
        state = state_manager.get_or_create(session_id)

        # ── 3. 意图识别 ──
        intent_result = intent_classifier.classify(clean_message, active_domain=state.domain)
        intent = intent_result.intent
        domain = intent_result.domain
        confidence = intent_result.confidence

        # 更新状态
        if state.phase == SessionPhase.INIT or (
            state.phase != SessionPhase.SLOT_FILLING and intent != "general_query"
        ):
            state.set_intent(intent, domain)
            state.transition(SessionPhase.INTENT_IDENTIFIED)

        # 如果正在槽位填充中，保持原意图不变
        if state.phase == SessionPhase.SLOT_FILLING:
            intent = state.intent or intent
            domain = state.domain or domain

        # ── 4. 特殊意图快速路径 ──
        if intent == "greeting":
            return self._build_response(
                session_id, message,
                reply="您好！我是智能客服助手，请问有什么可以帮您？",
                intent="greeting", confidence=1.0,
                quick_replies=["八字排盘", "查询订单", "商品咨询"],
            )
        if intent == "farewell":
            state.transition(SessionPhase.INIT)
            return self._build_response(
                session_id, message,
                reply="感谢您的咨询，祝您生活愉快！如有需要随时找我。",
                intent="farewell", confidence=1.0,
            )
        if intent == "human_agent":
            state.transition(SessionPhase.HUMAN_HANDOFF)
            return self._build_response(
                session_id, message,
                reply="好的，正在为您转接人工客服，请稍候...",
                intent="human_agent", confidence=1.0,
            )

        # ── 5. 领域路由 ──
        plugin = domain_router.route(intent, domain_hint=domain)

        # ── 6. 槽位填充 ──
        slot_prompt = ""
        if plugin:
            # 从消息中提取槽位
            extracted = slot_manager.extract_slots(clean_message, intent)
            if extracted:
                state.fill_slots(extracted)

            # 检查缺失槽位
            missing = slot_manager.get_missing_slots(intent, state.slots)

            if missing:
                state.transition(SessionPhase.SLOT_FILLING)
                state.increment_attempt()

                # 超过最大追问次数，跳过槽位直接回复
                if not state.exceeded_max_attempts():
                    slot_prompt = slot_manager.build_slot_prompt(state.slots, missing)
                else:
                    slot_prompt = ""  # 不再追问，直接用已有信息回复
            else:
                state.transition(SessionPhase.PROCESSING)

        # ── 7. 构建上下文 ──
        # 领域上下文
        domain_context = ""
        if plugin:
            try:
                from app.domains.base.plugin import Session as PluginSession
                plugin_session = PluginSession(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    current_intent=intent,
                    slots=dict(state.slots),
                    cache={},
                    user_profile={},
                    history=self.get_history(session_id, limit=10),
                )
                domain_context = plugin.build_context(plugin_session)
            except Exception as e:
                print(f"[Conversation] 构建领域上下文失败: {e}")

        # 记忆上下文
        memory_context_raw = memory_manager.get_context(session_id, user_id, tenant_id)
        memory_text = format_memory_context(memory_context_raw)

        # 相关记忆
        try:
            relevant = memory_manager.get_relevant_context(user_id, tenant_id, clean_message)
            episodes = relevant.get("related_episodes", [])
            if episodes:
                ep_text = "\n".join(e.get("content", "")[:100] for e in episodes[:2])
                if ep_text:
                    memory_text += f"\n相关历史:\n{ep_text}"
        except Exception:
            pass

        # RAG 检索
        rag_results = []
        try:
            rag_results = knowledge_base.retrieve(tenant_id, clean_message, top_k=3)
        except Exception as e:
            print(f"[Conversation] RAG 检索失败: {e}")
        rag_text = format_rag_results(rag_results)

        # ── 8. 组装 Prompt ──
        # System prompt
        domain_prompt = ""
        if plugin:
            try:
                domain_prompt = plugin.get_system_prompt(intent)
            except Exception:
                domain_prompt = "你是一个智能客服助手，请根据用户问题提供准确友好的回答。"
        else:
            domain_prompt = "你是一个智能客服助手，请根据用户问题提供准确友好的回答。"

        system_prompt = build_system_prompt(
            domain_prompt=domain_prompt,
            slot_info=slot_prompt,
            memory_context=memory_text,
            rag_results=rag_text,
        )

        # 对话历史（最近几轮）
        history = self.get_history(session_id, limit=6)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": clean_message})

        # ── 9. 调用 LLM ──
        try:
            llm_response = await llm_router.generate(
                tenant_id=tenant_id,
                prompt=system_prompt + "\n\n用户: " + clean_message,
                model=None,
                temperature=0.3 if domain == "ecommerce" else 0.7,
                intent=intent,
            )
            reply_text = llm_response.get("text", "")
        except Exception as e:
            print(f"[Conversation] LLM 调用失败: {e}")
            reply_text = get_fallback_reply(domain or "general")

        if not reply_text:
            reply_text = get_fallback_reply(domain or "general")

        # ── 10. 输出验证 ──
        try:
            validated = output_validator.validate_output(reply_text)
            reply_text = validated.get("validated", reply_text)
        except Exception:
            pass

        # ── 11. 插件后处理 ──
        if plugin:
            try:
                from app.domains.base.plugin import Session as PluginSession
                plugin_session = PluginSession(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    current_intent=intent,
                    slots=dict(state.slots),
                )
                reply_text = plugin.post_process(reply_text, plugin_session)
            except Exception as e:
                print(f"[Conversation] 后处理失败: {e}")

        # ── 12. 更新记忆 ──
        try:
            memory_manager.store_memory(
                user_id, tenant_id, {
                    "type": "long_term",
                    "data": {
                        "content": f"用户: {message}\n助手: {reply_text}",
                        "type": "conversation",
                        "metadata": {
                            "timestamp": time.time(),
                            "intent": intent,
                            "domain": domain,
                        },
                    },
                },
            )
        except Exception as e:
            print(f"[Conversation] 记忆存储失败: {e}")

        # ── 13. 状态流转 ──
        if state.phase == SessionPhase.PROCESSING:
            state.transition(SessionPhase.RESPONDING)
            state.transition(SessionPhase.COMPLETED)
            state.transition(SessionPhase.INIT)  # 重置，准备下一轮

        # ── 14. 返回 ──
        quick_replies = None
        if plugin:
            try:
                from app.domains.base.plugin import Session as PluginSession
                ps = PluginSession(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
                plugin.on_session_start(ps)
                quick_replies = ps.quick_replies or None
            except Exception:
                pass

        return self._build_response(
            session_id, message,
            reply=reply_text, intent=intent,
            confidence=confidence, quick_replies=quick_replies,
        )

    # ════════════════════════════════════════
    #  辅助方法
    # ════════════════════════════════════════

    def _build_response(
        self, session_id: str, user_message: str,
        reply: str, intent: str, confidence: float = 0.8,
        quick_replies: Optional[List[str]] = None,
    ) -> Dict:
        """统一的响应构建 + 消息存储"""
        self.add_message(session_id, "user", user_message)
        self.add_message(session_id, "assistant", reply)
        return {
            "reply": reply,
            "intent": intent,
            "confidence": confidence,
            "quick_replies": quick_replies or [],
        }


# 全局实例
conversation_manager = ConversationManager()
