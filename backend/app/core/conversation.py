"""对话管理模块"""

import uuid
import time
from typing import Dict, List, Optional, Any

from app.memory import memory_manager, SessionState
from app.llm import router as llm_router
from app.rag import knowledge_base
from app.guardrails import input_filter, output_validator


class ConversationManager:
    """对话管理器"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self, user_id: str, tenant_id: str) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
        
        Returns:
            str: 会话 ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created_at": time.time(),
            "last_active": time.time(),
            "messages": []
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        获取会话信息
        
        Args:
            session_id: 会话 ID
        
        Returns:
            Optional[Dict]: 会话信息
        """
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str):
        """
        添加消息到会话
        
        Args:
            session_id: 会话 ID
            role: 角色 (user, assistant)
            content: 消息内容
        """
        session = self.get_session(session_id)
        if session:
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": time.time()
            })
            session["last_active"] = time.time()

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            limit: 限制条数
        
        Returns:
            List[Dict]: 历史消息
        """
        session = self.get_session(session_id)
        if not session:
            return []
        return session["messages"][-limit:]

    async def process_message(self, session_id: str, user_id: str, tenant_id: str, message: str) -> Dict:
        """
        处理用户消息并生成回复
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            tenant_id: 租户 ID
            message: 用户消息
        
        Returns:
            Dict: 回复信息
        """
        # 1. 输入过滤
        filtered_message = input_filter.filter_input(message)
        if not filtered_message:
            return {
                "reply": "您的消息包含不适当内容，请重新输入。",
                "intent": "filtered",
                "confidence": 1.0
            }

        # 2. 获取记忆上下文
        context = memory_manager.get_context(session_id, user_id, tenant_id)
        relevant_context = memory_manager.get_relevant_context(user_id, tenant_id, message)

        # 3. 检索相关知识
        knowledge_results = knowledge_base.retrieve(tenant_id, message, top_k=3)

        # 4. 构建提示词
        prompt = self._build_prompt(
            message=filtered_message,
            context=context,
            relevant_context=relevant_context,
            knowledge_results=knowledge_results
        )

        # 5. 调用 LLM
        llm_response = await llm_router.generate(
            tenant_id=tenant_id,
            prompt=prompt,
            model="deepseek-chat",
            temperature=0.3
        )

        # 6. 输出验证
        validated_response = output_validator.validate_output(llm_response)

        # 7. 更新记忆
        self._update_memory(user_id, tenant_id, message, validated_response)

        # 8. 添加消息到会话
        self.add_message(session_id, "user", message)
        self.add_message(session_id, "assistant", validated_response)

        return {
            "reply": validated_response,
            "intent": "general_query",  # TODO: 实现意图识别
            "confidence": 0.8,
            "quick_replies": self._generate_quick_replies(validated_response)
        }

    def _build_prompt(self, message: str, context: Dict, relevant_context: Dict, knowledge_results: List) -> str:
        """
        构建提示词
        
        Args:
            message: 用户消息
            context: 记忆上下文
            relevant_context: 相关上下文
            knowledge_results: 知识检索结果
        
        Returns:
            str: 提示词
        """
        prompt = f"""
你是一个智能客服助手，需要根据用户的问题提供准确、友好的回答。

# 用户信息
{self._format_user_info(context.get('user_profile'))}

# 最近咨询
{self._format_recent_consultations(context.get('recent_consultations', []))}

# 相关记忆
{self._format_related_episodes(relevant_context.get('related_episodes', []))}

# 相关知识
{self._format_knowledge_results(knowledge_results)}

# 用户问题
{message}

请根据以上信息，提供一个准确、友好的回答。
        """
        return prompt

    def _format_user_info(self, user_profile: Optional[Dict]) -> str:
        """
        格式化用户信息
        
        Args:
            user_profile: 用户画像
        
        Returns:
            str: 格式化后的用户信息
        """
        if not user_profile:
            return "无"
        info = []
        if user_profile.get('name'):
            info.append(f"姓名: {user_profile['name']}")
        if user_profile.get('birthday'):
            info.append(f"生日: {user_profile['birthday']}")
        if user_profile.get('gender'):
            info.append(f"性别: {user_profile['gender']}")
        if user_profile.get('occupation'):
            info.append(f"职业: {user_profile['occupation']}")
        return "\n".join(info) if info else "无"

    def _format_recent_consultations(self, consultations: List) -> str:
        """
        格式化最近咨询
        
        Args:
            consultations: 最近咨询列表
        
        Returns:
            str: 格式化后的最近咨询
        """
        if not consultations:
            return "无"
        formatted = []
        for consult in consultations[:3]:
            content = consult.get('content', '')[:100]
            formatted.append(f"- {content}...")
        return "\n".join(formatted)

    def _format_related_episodes(self, episodes: List) -> str:
        """
        格式化相关情景记忆
        
        Args:
            episodes: 相关情景记忆列表
        
        Returns:
            str: 格式化后的相关情景记忆
        """
        if not episodes:
            return "无"
        formatted = []
        for episode in episodes[:2]:
            content = episode.get('content', '')[:100]
            formatted.append(f"- {content}...")
        return "\n".join(formatted)

    def _format_knowledge_results(self, knowledge_results: List) -> str:
        """
        格式化知识检索结果
        
        Args:
            knowledge_results: 知识检索结果
        
        Returns:
            str: 格式化后的知识检索结果
        """
        if not knowledge_results:
            return "无"
        formatted = []
        for result in knowledge_results[:3]:
            content = result.get('content', '')[:100]
            formatted.append(f"- {content}...")
        return "\n".join(formatted)

    def _update_memory(self, user_id: str, tenant_id: str, user_message: str, assistant_response: str):
        """
        更新记忆
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            user_message: 用户消息
            assistant_response: 助手回复
        """
        # 存储对话到长期记忆
        memory_manager.store_memory(
            user_id,
            tenant_id,
            {
                "type": "long_term",
                "data": {
                    "content": f"用户: {user_message}\n助手: {assistant_response}",
                    "type": "conversation",
                    "metadata": {
                        "timestamp": time.time(),
                        "interaction_type": "chat"
                    }
                }
            }
        )

    def _generate_quick_replies(self, response: str) -> List[str]:
        """
        生成快速回复选项
        
        Args:
            response: 助手回复
        
        Returns:
            List[str]: 快速回复选项
        """
        # 简单实现，实际应用中可以根据回复内容动态生成
        return [
            "还有其他问题吗？",
            "我需要更多信息",
            "谢谢，问题已解决"
        ]


# 全局对话管理器实例
conversation_manager = ConversationManager()