"""DeepSeek 提供商"""

import httpx
from app.config import settings


async def generate(prompt: str, model: str = "deepseek-chat", 
                  temperature: float = 0.3, max_tokens: int = 800) -> str:
    """
    调用 DeepSeek API 生成文本
    
    Args:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数
    
    Returns:
        str: 生成的文本
    """
    url = f"{settings.deepseek_base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个智能客服助手，需要根据用户的问题提供准确、友好的回答。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]