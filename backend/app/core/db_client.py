"""PostgreSQL 客户端（延迟导入，未安装 psycopg2 时降级为 None）"""

from app.config import settings

_db_pool = None
_db_available = None


def get_db():
    """获取 PostgreSQL 连接，未安装驱动时返回 None"""
    global _db_pool, _db_available

    if _db_available is False:
        return None

    if _db_pool is not None:
        return _db_pool

    try:
        import psycopg2
        import urllib.parse
        url = urllib.parse.urlparse(settings.database_url)
        _db_pool = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username or "postgres",
            password=url.password or "",
            database=url.path.lstrip("/"),
        )
        _db_available = True
        return _db_pool
    except Exception as e:
        print(f"[DB] PostgreSQL 不可用: {e}")
        _db_available = False
        return None


def close_db():
    global _db_pool
    if _db_pool:
        try:
            _db_pool.close()
        except Exception:
            pass
        _db_pool = None
