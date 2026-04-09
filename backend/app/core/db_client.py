"""PostgreSQL 客户端"""

import psycopg2
from app.config import settings


# 全局数据库连接池
_db_pool = None


def get_db():
    """
    获取 PostgreSQL 连接
    
    Returns:
        psycopg2.connection: PostgreSQL 连接对象
    """
    global _db_pool
    if _db_pool is None:
        # 从 URL 中提取连接参数
        import urllib.parse
        url = urllib.parse.urlparse(settings.database_url)
        _db_pool = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username or "postgres",
            password=url.password or "",
            database=url.path.lstrip("/"),
        )
    return _db_pool


def close_db():
    """
    关闭数据库连接
    """
    global _db_pool
    if _db_pool:
        _db_pool.close()
        _db_pool = None