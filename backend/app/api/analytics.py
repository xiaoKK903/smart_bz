"""数据分析 API"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard():
    """获取数据看板"""
    return {"status": "not implemented"}
