"""知识库管理 API"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_knowledge_bases():
    """列出知识库"""
    return {"knowledge_bases": []}


@router.post("/upload")
async def upload_document():
    """上传知识文档"""
    return {"status": "not implemented"}
