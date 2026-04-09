"""Redis 客户端"""

import redis
from app.config import settings


# 全局 Redis 连接池
_redis_pool = None


def get_redis():
    """
    获取 Redis 连接
    
    Returns:
        redis.Redis: Redis 连接对象
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(settings.redis_url)
    return redis.Redis(connection_pool=_redis_pool)


def make_key(key: str) -> str:
    """
    生成 Redis key
    
    Args:
        key: 原始 key
    
    Returns:
        str: 格式化后的 key
    """
    return f"smartcs:{key}"