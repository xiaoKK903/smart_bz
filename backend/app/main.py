"""智能客服平台 - FastAPI 入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, tenant, knowledge, analytics, admin, memory

app = FastAPI(
    title="智能客服平台",
    description="通用智能客服平台 API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(tenant.router, prefix="/api/tenant", tags=["租户"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])
app.include_router(admin.router, prefix="/api/admin", tags=["管理"])
app.include_router(memory.router, prefix="/api/memory", tags=["记忆管理"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
