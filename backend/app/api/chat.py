"""对话 API"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.conversation import conversation_manager

router = APIRouter()


class ChatRequest(BaseModel):
    tenant_id: str
    session_id: Optional[str] = None
    user_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    quick_replies: Optional[list[str]] = None


@router.post("/send", response_model=ChatResponse)
async def send_message(req: ChatRequest):
    """发送消息并获取回复"""
    # 如果没有会话ID，创建新会话
    if not req.session_id:
        req.session_id = conversation_manager.create_session(req.user_id, req.tenant_id)
    
    # 处理消息
    result = await conversation_manager.process_message(
        req.session_id, req.user_id, req.tenant_id, req.message
    )
    
    # 构建响应
    return ChatResponse(
        session_id=req.session_id,
        reply=result["reply"],
        intent=result.get("intent"),
        confidence=result.get("confidence"),
        quick_replies=result.get("quick_replies")
    )


@router.post("/message", response_model=ChatResponse)
async def send_message_alias(req: ChatRequest):
    """发送消息并获取回复（别名端点）"""
    return await send_message(req)


@router.get("/history/{session_id}")
async def get_history(session_id: str, limit: int = 50):
    """获取会话历史"""
    history = conversation_manager.get_history(session_id, limit)
    return {"messages": history}
