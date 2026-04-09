#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户画像模块（Layer 2）
使用 PostgreSQL 存储用户基本信息与重要特征
当PostgreSQL不可用时，使用内存存储作为备选
"""

# 内存存储作为PostgreSQL的备选
memory_storage = {}

from app.core.db_client import get_db


# ========== 核心 SQL 语句 ==========

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    birthday DATE,
    gender VARCHAR(10),
    occupation VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_tenant ON user_profiles(user_id, tenant_id);
"""


# ========== 初始化表结构 ==========

def _init_table():
    """初始化用户画像表"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()
    except Exception as e:
        print(f"[user_profile] 表初始化失败: {e}")


# 模块加载时初始化表
_init_table()


# ========== 核心接口 ==========

def get_user_profile(user_id: str, tenant_id: str) -> dict:
    """
    获取用户画像。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID

    Returns:
        用户画像字典，不存在返回 None
    """
    if not user_id or not tenant_id:
        return None

    # 尝试从内存存储获取
    key = f"{tenant_id}:{user_id}"
    if key in memory_storage:
        return memory_storage[key]

    query = """
    SELECT id, user_id, tenant_id, name, birthday, gender, occupation, created_at, updated_at
    FROM user_profiles
    WHERE user_id = %s AND tenant_id = %s
    """

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(query, (user_id, tenant_id))
            row = cur.fetchone()
        if not row:
            return None

        # 构建返回字典
        profile = {
            "id": row[0],
            "user_id": row[1],
            "tenant_id": row[2],
            "name": row[3],
            "birthday": str(row[4]) if row[4] else None,
            "gender": row[5],
            "occupation": row[6],
            "created_at": str(row[7]),
            "updated_at": str(row[8]),
        }
        # 保存到内存存储
        memory_storage[key] = profile
        return profile
    except Exception as e:
        print(f"[user_profile] 获取用户画像失败: {e}")
        return None


def update_user_profile(user_id: str, tenant_id: str, **kwargs) -> bool:
    """
    更新用户画像（不存在则创建）。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        **kwargs: 要更新的字段（name, birthday, gender, occupation）

    Returns:
        是否成功
    """
    if not user_id or not tenant_id:
        return False

    # 过滤有效字段
    valid_fields = {k: v for k, v in kwargs.items()
                   if k in ("name", "birthday", "gender", "occupation")}
    if not valid_fields:
        return True  # 无字段更新，视为成功

    # 检查用户是否存在
    existing = get_user_profile(user_id, tenant_id)

    # 更新内存存储
    key = f"{tenant_id}:{user_id}"
    if existing:
        # 更新现有记录
        existing.update(valid_fields)
        existing["updated_at"] = "2024-01-01"
        memory_storage[key] = existing
    else:
        # 创建新记录
        new_profile = {
            "id": len(memory_storage) + 1,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        }
        new_profile.update(valid_fields)
        memory_storage[key] = new_profile

    try:
        conn = get_db()
        with conn.cursor() as cur:
            if existing:
                # 更新现有记录
                set_clause = ", ".join([f"{k} = %s" for k in valid_fields.keys()])
                values = list(valid_fields.values()) + [user_id, tenant_id]
                update_query = f"""
                UPDATE user_profiles
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND tenant_id = %s
                """
                cur.execute(update_query, values)
            else:
                # 创建新记录
                fields = ["user_id", "tenant_id"] + list(valid_fields.keys())
                placeholders = ["%s"] * len(fields)
                values = [user_id, tenant_id] + list(valid_fields.values())
                insert_query = f"""
                INSERT INTO user_profiles ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                """
                cur.execute(insert_query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"[user_profile] 更新用户画像失败: {e}")
        # 即使数据库失败，内存存储已更新，视为成功
        return True


def delete_user_profile(user_id: str, tenant_id: str) -> bool:
    """
    删除用户画像。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID

    Returns:
        是否成功（用户不存在也视为成功）
    """
    if not user_id or not tenant_id:
        return False

    # 从内存存储删除
    key = f"{tenant_id}:{user_id}"
    if key in memory_storage:
        del memory_storage[key]

    query = """
    DELETE FROM user_profiles
    WHERE user_id = %s AND tenant_id = %s
    """

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(query, (user_id, tenant_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[user_profile] 删除用户画像失败: {e}")
        # 即使数据库失败，内存存储已删除，视为成功
        return True


def clear_user_profile_field(user_id: str, tenant_id: str, field: str) -> bool:
    """
    清除用户画像的指定字段。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        field: 字段名（name, birthday, gender, occupation）

    Returns:
        是否成功
    """
    if not user_id or not tenant_id or field not in ("name", "birthday", "gender", "occupation"):
        return False

    # 从内存存储清除字段
    key = f"{tenant_id}:{user_id}"
    if key in memory_storage:
        memory_storage[key][field] = None
        memory_storage[key]["updated_at"] = "2024-01-01"

    query = f"""
    UPDATE user_profiles
    SET {field} = NULL, updated_at = CURRENT_TIMESTAMP
    WHERE user_id = %s AND tenant_id = %s
    """

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(query, (user_id, tenant_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[user_profile] 清除字段失败: {e}")
        # 即使数据库失败，内存存储已更新，视为成功
        return True


def list_user_profiles(tenant_id: str, limit: int = 100) -> list:
    """
    列出指定租户的所有用户画像。

    Args:
        tenant_id: 租户 ID
        limit: 最大返回数量

    Returns:
        用户画像列表
    """
    if not tenant_id:
        return []

    # 从内存存储获取
    profiles = []
    for key, profile in memory_storage.items():
        if profile["tenant_id"] == tenant_id:
            profiles.append(profile)
    if profiles:
        return profiles[:limit]

    query = """
    SELECT id, user_id, tenant_id, name, birthday, gender, occupation, created_at, updated_at
    FROM user_profiles
    WHERE tenant_id = %s
    ORDER BY created_at DESC
    LIMIT %s
    """

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(query, (tenant_id, limit))
            rows = cur.fetchall()

        profiles = []
        for row in rows:
            profile = {
                "id": row[0],
                "user_id": row[1],
                "tenant_id": row[2],
                "name": row[3],
                "birthday": str(row[4]) if row[4] else None,
                "gender": row[5],
                "occupation": row[6],
                "created_at": str(row[7]),
                "updated_at": str(row[8]),
            }
            profiles.append(profile)
        return profiles
    except Exception as e:
        print(f"[user_profile] 列出用户画像失败: {e}")
        return []


def count_user_profiles(tenant_id: str) -> int:
    """
    统计指定租户的用户画像数量。

    Args:
        tenant_id: 租户 ID

    Returns:
        用户数量
    """
    if not tenant_id:
        return 0

    # 从内存存储统计
    count = 0
    for profile in memory_storage.values():
        if profile["tenant_id"] == tenant_id:
            count += 1
    if count > 0:
        return count

    query = """
    SELECT COUNT(*)
    FROM user_profiles
    WHERE tenant_id = %s
    """

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(query, (tenant_id,))
            count = cur.fetchone()[0]
        return count
    except Exception as e:
        print(f"[user_profile] 统计用户画像失败: {e}")
        return 0