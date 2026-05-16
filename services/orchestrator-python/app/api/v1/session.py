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

    # TODO: 从数据库分页查询
    # 当前返回模拟数据
    session_store = get_session_store()

    # 模拟数据
    now = datetime.utcnow()
    mock_sessions = [
        SessionInfo(
            id=f"sess_mock_{i}",
            type=session_type or SessionType.CHAT,
            title=f"会话 {i + 1}",
            status=status or SessionStatus.ACTIVE,
            message_count=i * 5 + 3,
            created_at=now - timedelta(days=i),
            updated_at=now - timedelta(hours=i),
        )
        for i in range(min(page_size, 5))
    ]

    return SessionList(
        sessions=mock_sessions,
        total=42,  # 模拟总数
        page=page,
        page_size=page_size,
        has_more=page * page_size < 42,
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

    logger.info(
        "session_updated",
        session_id=session_id,
        request_id=request_id,
        updates=request.model_dump(exclude_none=True),
    )

    session_store = get_session_store()
    info = await session_store.get_session_info(session_id)

    if not info:
        raise HTTPException(status_code=404, detail="会话不存在")

    # TODO: 实现更新逻辑
    # 当前返回模拟数据

    return SessionInfo(
        id=session_id,
        type=SessionType(info.get("type", "chat")),
        title=request.title or info.get("title"),
        status=request.status or SessionStatus(info.get("status", "active")),
        message_count=info.get("message_count", 0),
        created_at=info.get("created_at", datetime.utcnow()),
        updated_at=datetime.utcnow(),
        metadata=request.metadata or info.get("metadata"),
    )