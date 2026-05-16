"""会话相关的 Pydantic 模型

定义会话管理的数据结构。

【核心概念】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Session API 用于：
1. 创建新会话（SessionCreate）
2. 查询会话信息（SessionInfo）
3. 列出用户的会话（SessionList）
4. 删除/归档会话

【会话生命周期】
active -> archived -> deleted

【会话类型】
- chat: 普通对话
- task: 任务执行
- analysis: 分析任务
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionType(str, Enum):
    """会话类型"""

    CHAT = "chat"  # 普通对话
    TASK = "task"  # 任务执行
    ANALYSIS = "analysis"  # 分析任务


class SessionStatus(str, Enum):
    """会话状态"""

    ACTIVE = "active"  # 活跃
    ARCHIVED = "archived"  # 已归档
    DELETED = "deleted"  # 已删除


class SessionCreate(BaseModel):
    """创建会话请求

    Attributes:
        session_type: 会话类型
        title: 会话标题（可选）
        metadata: 元数据（可选）

    Example:
        ```json
        {
            "session_type": "chat",
            "title": "销售数据分析",
            "metadata": {"project_id": "proj_123"}
        }
        ```
    """

    session_type: SessionType = Field(default=SessionType.CHAT, description="会话类型")
    title: str | None = Field(default=None, max_length=200, description="会话标题")
    metadata: dict | None = Field(default=None, description="元数据")

    model_config = {
        "json_schema_extra": {
            "examples": [{"session_type": "chat", "title": "销售数据分析", "metadata": {"project_id": "proj_123"}}]
        }
    }


class SessionInfo(BaseModel):
    """会话信息

    查询会话时返回的详细信息。

    Attributes:
        id: 会话唯一标识
        type: 会话类型
        title: 会话标题
        status: 会话状态
        message_count: 消息数量
        created_at: 创建时间
        updated_at: 最后更新时间
        last_message_at: 最后一条消息时间
        metadata: 元数据
    """

    id: str = Field(..., description="会话 ID")
    type: SessionType = Field(..., description="会话类型")
    title: str | None = Field(default=None, description="会话标题")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="会话状态")
    message_count: int = Field(default=0, ge=0, description="消息数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最后更新时间")
    last_message_at: datetime | None = Field(default=None, description="最后消息时间")
    metadata: dict | None = Field(default=None, description="元数据")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "sess_abc123",
                    "type": "chat",
                    "title": "销售数据分析",
                    "status": "active",
                    "message_count": 15,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T01:30:00Z",
                }
            ]
        }
    }


class SessionList(BaseModel):
    """会话列表

    分页查询会话时的响应。

    Attributes:
        sessions: 会话列表
        total: 总数
        page: 当前页码
        page_size: 每页数量
        has_more: 是否有更多
    """

    sessions: list[SessionInfo] = Field(default_factory=list, description="会话列表")
    total: int = Field(default=0, ge=0, description="总数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    has_more: bool = Field(default=False, description="是否有更多")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sessions": [
                        {
                            "id": "sess_abc123",
                            "type": "chat",
                            "title": "销售数据分析",
                            "status": "active",
                            "message_count": 15,
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    ],
                    "total": 42,
                    "page": 1,
                    "page_size": 20,
                    "has_more": True,
                }
            ]
        }
    }


class SessionDeleteResponse(BaseModel):
    """删除会话响应

    Attributes:
        id: 会话 ID
        status: 删除后状态
        message: 操作结果消息
    """

    id: str = Field(..., description="会话 ID")
    status: SessionStatus = Field(default=SessionStatus.DELETED, description="删除后状态")
    message: str = Field(default="会话已删除", description="操作结果消息")

    model_config = {"json_schema_extra": {"examples": [{"id": "sess_abc123", "status": "deleted", "message": "会话已删除"}]}}


class SessionUpdate(BaseModel):
    """更新会话请求

    Attributes:
        title: 新标题
        status: 新状态
        metadata: 更新元数据
    """

    title: str | None = Field(default=None, max_length=200, description="新标题")
    status: SessionStatus | None = Field(default=None, description="新状态")
    metadata: dict | None = Field(default=None, description="更新元数据")

    model_config = {"json_schema_extra": {"examples": [{"title": "新的会话标题", "status": "active"}]}}