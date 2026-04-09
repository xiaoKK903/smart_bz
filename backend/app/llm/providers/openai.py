"""OpenAI 提供商"""

from openai import OpenAI
from app.config import settings


async def generate(prompt: str, model: str = "gpt-3.5-turbo", 
                  temperature: float = 0.3, max_tokens: int = 800) -> str:
    """
    调用 OpenAI API 生成文本
    
    Args:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数
    
    Returns:
        str: 生成的文本
    """
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个智能客服助手，需要根据用户的问题提供准确、友好的回答。"},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content