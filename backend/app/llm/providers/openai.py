"""OpenAI 提供商（延迟导入，未安装 openai 包时不会崩溃）"""

from app.config import settings


async def generate(prompt: str, model: str = "gpt-3.5-turbo",
                   temperature: float = 0.3, max_tokens: int = 800) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 包未安装，无法使用 OpenAI provider")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个智能客服助手。"},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
