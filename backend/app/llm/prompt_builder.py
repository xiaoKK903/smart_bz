"""Prompt 构建器 — 统一组装 system prompt 和 user message"""

from typing import Dict, List, Optional
from app.llm.token_counter import count_tokens, truncate_to_tokens


def build_system_prompt(
    domain_prompt: str,
    slot_info: str = "",
    memory_context: str = "",
    rag_results: str = "",
    max_tokens: int = 3000,
) -> str:
    """
    组装完整的 system prompt

    Args:
        domain_prompt: 领域插件提供的 system prompt
        slot_info: 槽位收集状态提示
        memory_context: 记忆上下文
        rag_results: RAG 检索结果
        max_tokens: 最大 token 数

    Returns:
        组装好的 system prompt
    """
    sections = [domain_prompt]

    if slot_info:
        sections.append(f"\n\n{slot_info}")

    if memory_context:
        sections.append(f"\n\n# 用户上下文\n{memory_context}")

    if rag_results:
        sections.append(f"\n\n# 参考知识\n{rag_results}")

    full_prompt = "".join(sections)

    # 如果超长，截断 RAG 和记忆部分
    if count_tokens(full_prompt) > max_tokens:
        full_prompt = truncate_to_tokens(full_prompt, max_tokens)

    return full_prompt


def build_user_message(user_input: str, additional_context: str = "") -> str:
    """构建 user message"""
    if additional_context:
        return f"{additional_context}\n\n用户说：{user_input}"
    return user_input


def format_memory_context(context: Dict) -> str:
    """将记忆系统返回的 context 格式化为文本"""
    parts = []

    profile = context.get("user_profile")
    if profile:
        info = []
        for k in ["name", "birthday", "gender", "occupation"]:
            v = profile.get(k)
            if v:
                info.append(f"{k}: {v}")
        if info:
            parts.append("用户画像: " + ", ".join(info))

    consultations = context.get("recent_consultations", [])
    if consultations:
        parts.append("最近咨询:")
        for c in consultations[:3]:
            content = c.get("content", "")[:100]
            parts.append(f"  - {content}")

    episodes = context.get("related_episodes", [])
    if episodes:
        parts.append("相关记忆:")
        for e in episodes[:2]:
            content = e.get("content", "")[:100]
            parts.append(f"  - {content}")

    return "\n".join(parts) if parts else ""


def format_rag_results(results: List[Dict]) -> str:
    """将 RAG 检索结果格式化为文本"""
    if not results:
        return ""
    parts = []
    for r in results[:3]:
        content = r.get("content", "")[:300]
        parts.append(f"- {content}")
    return "\n".join(parts)
