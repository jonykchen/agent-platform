"""Session API - 会话管理

提供会话生命周期管理的 API 端点。

【核心概念】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Session API 用于：
1. 创建新会话
2. 获取会话详情
3. 列出用户的会话（分页）
4. 删除会话

【会话作用】
- 保持多轮对话上下文
- 关联 Agent 执行历史
- 支持会话级别的元数据

【会话生命周期】
┌─────────────────────────────────────────────────────────────────────────┐
│                      POST /api/v1/sessions                               │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                   │
│                    │  创建会话       │                                    │
│                    │  session_id     │                                    │
│                    │  status=active  │                                    │
│                    └─────────────────┘                                   │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                   │
│                    │  添加消息       │                                    │
│                    │  更新 updated_at│                                    │
│                    └─────────────────┘                                   │
│                              │                                          │
│               ┌──────────────┴──────────────┐                           │
│               │                             │                           │
│          [继续对话]                    [删除会话]                        │
│               │                             │                           │
│               ▼                             ▼                           │
│         更新消息列表                DELETE /sessions/{id}               │
│                                        │                                │
│                                        ▼                                │
│                                 status=deleted                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

【分页设计】
使用游标分页而非偏移分页的原因：
- 大数据集时偏移分页性能差
- 游标分页避免数据重复/遗漏
- 适合实时更新的列表

当前实现使用简单的页码分页，后续可升级为游标分页。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

import structlog

from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
from app.memory.session_store import get_session_store
from app.schemas.session import (
    SessionCreate,
    SessionDeleteResponse,
    SessionInfo,
    SessionList,
    SessionStatus,
    SessionType,
    SessionUpdate,
)

logger = structlog.get_logger()
router = APIRouter()


@router.post("/sessions", response_model=SessionInfo)
async def create_session(request: SessionCreate, req: Request):
    """创建会话

    创建一个新的对话会话。

    Args:
        request: SessionCreate 创建请求
            - session_type: 会话类型
            - title: 会话标题
            - metadata: 元数据
        req: FastAPI Request 对象

    Returns:
        SessionInfo 会话信息

    Example:
        ```json
        POST /api/v1/sessions
        {
            "session_type": "chat",
            "title": "销售数据分析"
        }
        ```
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    session_id = f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"
    now = datetime.utcnow()

    logger.info(
        "session_created",
        session_id=session_id,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        session_type=request.session_type.value,
    )

    # 创建会话信息
    session_info = SessionInfo(
        id=session_id,
        type=request.session_type,
        title=request.title or f"新会话 - {now.strftime('%Y-%m-%d %H:%M')}",
        status=SessionStatus.ACTIVE,
        message_count=0,
        created_at=now,
        updated_at=now,
        metadata=request.metadata,
    )

    # 保存到存储
    session_store = get_session_store()
    await session_store.create_session(
        session_id=session_id,
        session_type=request.session_type.value,
        title=session_info.title,
        metadata=request.metadata,
    )

    return session_info


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str, req: Request):
    """获取会话详情

    查询指定会话的详细信息。

    Args:
        session_id: 会话唯一标识

    Returns:
        SessionInfo 会话详情

    Raises:
        HTTPException: 会话不存在 (404)
    """
    request_id = get_request_id()

    logger.debug(
        "session_queried",
        session_id=session_id,
        request_id=request_id,
    )

    # 从存储获取会话信息
    session_store = get_session_store()
    info = await session_store.get_session_info(session_id)

    if not info:
        logger.warning(
            "session_not_found",
            session_id=session_id,
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取消息数量
    history = await session_store.get_history(session_id)

    return SessionInfo(
        id=session_id,
        type=SessionType(info.get("type", "chat")),
        title=info.get("title"),
        status=SessionStatus(info.get("status", "active")),
        message_count=len(history),
        created_at=info.get("created_at", datetime.utcnow()),
        updated_at=info.get("updated_at"),
        last_message_at=history[-1].get("timestamp") if history else None,
        metadata=info.get("metadata"),
    )


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(session_id: str, req: Request):
    """删除会话

    软删除会话及其历史消息。

    Args:
        session_id: 会话唯一标识

    Returns:
        SessionDeleteResponse 删除结果

    Note:
        这是软删除，数据仍保留用于审计。
        实际删除需要管理员权限或等待自动清理。
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()

    logger.info(
        "session_deleted",
        session_id=session_id,
        request_id=request_id,
        tenant_id=tenant_id,
    )

    # 清空会话
    session_store = get_session_store()
    await session_store.clear(session_id)

    return SessionDeleteResponse(
        id=session_id,
        status=SessionStatus.DELETED,
        message="会话已删除",
    )


@router.get("/sessions", response_model=SessionList)
async def list_sessions(
    req: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    session_type: SessionType | None = Query(default=None, description="会话类型过滤"),
    status: SessionStatus | None = Query(default=None, description="状态过滤"),
):
    """列出会话

    分页查询当前用户的会话列表。
    使用 Redis 实现会话索引，支持分页和过滤。

    Args:
        page: 页码（从 1 开始）
        page_size: 每页数量（1-100）
        session_type: 可选的会话类型过滤
        status: 可选的状态过滤

    Returns:
        SessionList 会话列表

    Example:
        ```
        GET /api/v1/sessions?page=1&page_size=20&session_type=chat
        ```
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    logger.debug(
        "sessions_listed",
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
        session_type=session_type,
    )

    session_store = get_session_store()

    # 使用 Redis Sorted Set 实现分页
    # Key: session:index:{tenant_id}:{user_id}
    # Score: updated_at timestamp
    index_key = f"session:index:{tenant_id}:{user_id}"

    # 计算分页
    offset = (page - 1) * page_size

    # 从 Redis 获取会话 ID 列表（按更新时间倒序）
    redis_client = session_store._client if hasattr(session_store, '_client') else None
    if redis_client is None:
        redis_client = await session_store._get_client()

    # 获取总数
    total = await redis_client.zcard(index_key)

    # 获取分页数据
    session_ids = await redis_client.zrange(
        index_key,
        -offset - page_size,
        -offset - 1 if offset > 0 else -1,
        desc=True,
    )

    # 如果索引为空，返回空列表
    if not session_ids:
        return SessionList(
            sessions=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
        )

    # 批量获取会话详情
    sessions = []
    for sid in session_ids:
        sid_str = sid.decode() if isinstance(sid, bytes) else sid
        info = await session_store.get_session_info(sid_str)
        if info and info.get("exists"):
            # 过滤
            if session_type and info.get("type") != session_type.value:
                continue
            if status and info.get("status") != status.value:
                continue

            sessions.append(SessionInfo(
                id=sid_str,
                type=SessionType(info.get("type", "chat")),
                title=info.get("title", "未命名会话"),
                status=SessionStatus(info.get("status", "active")),
                message_count=info.get("message_count", 0),
                created_at=info.get("created_at", datetime.utcnow()),
                updated_at=info.get("updated_at", datetime.utcnow()),
                metadata=info.get("metadata"),
            ))

    return SessionList(
        sessions=sessions,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + page_size < total,
    )


@router.patch("/sessions/{session_id}", response_model=SessionInfo)
async def update_session(session_id: str, request: SessionUpdate, req: Request):
    """更新会话

    更新会话的标题或状态。

    Args:
        session_id: 会话唯一标识
        request: SessionUpdate 更新请求
            - title: 新标题
            - status: 新状态
            - metadata: 更新元数据

    Returns:
        SessionInfo 更新后的会话信息

    Raises:
        HTTPException: 会话不存在 (404)
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    logger.info(
        "session_updated",
        session_id=session_id,
        request_id=request_id,
        tenant_id=tenant_id,
        updates=request.model_dump(exclude_none=True),
    )

    session_store = get_session_store()
    info = await session_store.get_session_info(session_id)

    if not info or not info.get("exists"):
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取 Redis 客户端
    redis_client = await session_store._get_client()
    now = datetime.utcnow()

    # 更新会话元数据
    meta_key = f"session:{session_id}:meta"

    # 构建更新数据
    updates = {}
    if request.title:
        updates["title"] = request.title
    if request.status:
        updates["status"] = request.status.value
    if request.metadata:
        updates["metadata"] = json.dumps(request.metadata)
    updates["updated_at"] = now.isoformat()

    # 写入更新
    if updates:
        import json
        await redis_client.hset(meta_key, mapping={
            k: v if isinstance(v, str) else json.dumps(v)
            for k, v in updates.items()
        })
        await redis_client.expire(meta_key, 86400)  # 保持 TTL

        # 更新索引中的 score（按更新时间排序）
        index_key = f"session:index:{tenant_id}:{user_id}"
        await redis_client.zadd(index_key, {session_id: now.timestamp()})

    # 返回更新后的信息
    updated_info = await session_store.get_session_info(session_id)

    return SessionInfo(
        id=session_id,
        type=SessionType(updated_info.get("type", "chat")),
        title=request.title or updated_info.get("title", "未命名会话"),
        status=request.status or SessionStatus(updated_info.get("status", "active")),
        message_count=updated_info.get("message_count", 0),
        created_at=updated_info.get("created_at", now),
        updated_at=now,
        metadata=request.metadata or updated_info.get("metadata"),
    )