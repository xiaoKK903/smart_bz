"""管理后台 API"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def system_status():
    """系统状态"""
    return {"status": "ok"}
