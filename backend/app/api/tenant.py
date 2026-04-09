"""租户管理 API"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_tenants():
    """列出所有租户"""
    return {"tenants": []}


@router.post("/")
async def create_tenant():
    """创建租户"""
    return {"status": "not implemented"}
