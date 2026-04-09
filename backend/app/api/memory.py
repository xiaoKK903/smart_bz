"""记忆管理 API"""

from fastapi import APIRouter, HTTPException

from app.memory import memory_manager

router = APIRouter()


@router.get("/get")
def get_memory(user_id: str, tenant_id: str, query: str = None, memory_type: str = None):
    """
    获取记忆
    
    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        query: 查询文本（用于长期记忆检索）
        memory_type: 记忆类型（short_term, user_profile, long_term）
    """
    try:
        result = memory_manager.get_memory(user_id, tenant_id, query, memory_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆失败: {e}")


@router.post("/store")
def store_memory(user_id: str, tenant_id: str, memory: dict):
    """
    存储记忆
    
    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        memory: 记忆数据，包含 type 和 data 字段
    """
    try:
        result = memory_manager.store_memory(user_id, tenant_id, memory)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"存储记忆失败: {e}")


@router.delete("/delete")
def delete_memory(user_id: str, tenant_id: str, memory_id: str = None,
                  memory_type: str = None, field: str = None,
                  slot_keys: list = None, sub_type: str = None,
                  operator_id: str = None, reason: str = ""):
    """
    删除记忆
    
    Args:
        user_id: 目标用户 ID
        tenant_id: 租户 ID
        memory_id: 具体记忆 ID（长期记忆的 ep_/consult_/fb_ ID）
        memory_type: 记忆层级 — "short_term" | "user_profile" | "long_term"
        field: 指定字段/子项
        slot_keys: 短期记忆：要删除的槽位键列表
        sub_type: 长期记忆子类型 — "episode" | "consultation" | "feedback"
        operator_id: 操作者 ID（默认 = user_id，即自助删除）
        reason: 删除原因（记入日志）
    """
    try:
        result = memory_manager.delete_memory(
            user_id, tenant_id, memory_id, memory_type,
            field=field, slot_keys=slot_keys, sub_type=sub_type,
            operator_id=operator_id, reason=reason
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除记忆失败: {e}")


@router.get("/consistency")
def check_memory_consistency(user_id: str, tenant_id: str):
    """
    检查记忆一致性
    
    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
    """
    try:
        result = memory_manager.check_memory_consistency(user_id, tenant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查记忆一致性失败: {e}")


@router.get("/relevant")
def get_relevant_memory(user_id: str, tenant_id: str, query: str, max_tokens: int = 1000):
    """
    获取与查询相关的记忆
    
    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        query: 查询文本
        max_tokens: 最大 token 数（控制返回内容长度）
    """
    try:
        result = memory_manager.get_relevant_memory(user_id, tenant_id, query, max_tokens)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相关记忆失败: {e}")


@router.get("/logs")
def get_deletion_logs(user_id: str = None, tenant_id: str = None, limit: int = 50):
    """
    查询记忆删除操作日志
    
    Args:
        user_id: 按用户过滤（None = 全部）
        tenant_id: 按租户过滤（None = 全部）
        limit: 最多返回条数
    """
    try:
        result = memory_manager.get_deletion_logs(user_id, tenant_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询删除日志失败: {e}")


@router.get("/health")
def health_check(tenant_id: str = "test"):
    """
    记忆系统健康检查
    
    Args:
        tenant_id: 租户 ID（用于测试）
    """
    try:
        result = memory_manager.health(tenant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {e}")