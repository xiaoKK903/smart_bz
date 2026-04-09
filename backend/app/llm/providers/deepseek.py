"""DeepSeek 提供商

支持两种调用方式：
1. generate(prompt) — 简单文本生成（兼容旧接口）
2. chat(messages) — 完整 chat 格式（system + user + history）
"""

import httpx
from typing import Optional, List, Dict
from app.config import settings


async def generate(
    prompt: str,
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 800,
    system_prompt: Optional[str] = None,
) -> str:
    """
    调用 DeepSeek API 生成文本

    Args:
        prompt: 用户消息 / 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数
        system_prompt: 系统提示词（可选，不传则使用默认）

    Returns:
        str: 生成的文本
    """
    if system_prompt is None:
        system_prompt = "你是一个智能客服助手，需要根据用户的问题提供准确、友好的回答。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    return await chat(messages=messages, model=model,
                      temperature=temperature, max_tokens=max_tokens)


async def chat(
    messages: List[Dict[str, str]],
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> str:
    """
    使用完整 messages 列表调用 DeepSeek Chat API

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数

    Returns:
        str: 生成的文本
    """
    url = f"{settings.deepseek_base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
