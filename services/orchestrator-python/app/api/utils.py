"""API 层共享工具函数

避免在多个 API 模块中重复定义相同的辅助函数。
"""

from __future__ import annotations

import uuid


def get_or_create_session_id(session_id: str | None, tenant_id: str, user_id: str) -> str:
    """获取或创建会话 ID

    若已有 session_id 直接返回，否则生成新会话 ID。
    格式：sess_{uuid_hex[:16]}_{tenant_id}

    Args:
        session_id: 可选的已有会话 ID
        tenant_id: 租户 ID（用于会话隔离）
        user_id: 用户 ID（预留，当前未使用）

    Returns:
        会话 ID 字符串
    """
    if session_id:
        return session_id
    return f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"
