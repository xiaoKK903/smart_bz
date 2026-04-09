"""八字解读 API"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio

from app.llm import router as llm_router

router = APIRouter()


class InterpretRequest(BaseModel):
    clientId: str
    sessionId: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    fullBazi: Optional[str] = None
    details: Optional[Dict] = None
    lunar: Optional[Dict] = None
    solarTerms: Optional[Dict] = None
    today: Optional[Dict] = None
    config: Optional[Dict] = None
    prompt: Optional[str] = None
    stream: Optional[bool] = False


@router.post("/interpret")
async def interpret_bazi(req: InterpretRequest):
    """解读八字"""
    # 构建提示词
    if not req.prompt:
        prompt = f"请根据以下八字信息，提供简洁的命理解读：\n\n八字：{req.fullBazi}\n\n请从以下几个方面进行简要解读：\n1. 性格特点\n2. 优势特长\n3. 发展建议\n4. 注意事项\n\n请用简洁、实用的语言，控制在200字以内。"
    else:
        prompt = req.prompt
    
    # 调用LLM生成解读
    llm_response = await llm_router.generate(
        tenant_id="bazi",
        prompt=prompt,
        model="deepseek-chat",
        temperature=0.3
    )
    
    # 检查是否需要流式响应
    if req.stream:
        # 模拟流式响应
        response_text = llm_response["text"]
        
        async def stream_response():
            for char in response_text:
                yield char
                await asyncio.sleep(0.01)  # 模拟流式效果
        
        return StreamingResponse(stream_response(), media_type="text/plain")
    else:
        # 非流式响应
        return {
            "text": llm_response["text"]
        }
