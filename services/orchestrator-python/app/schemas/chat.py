"""Chat 相关的 Pydantic 模型

定义对话请求和响应的数据结构。

【核心概念】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chat 模型用于：
1. 接收用户对话请求（ChatRequest）
2. 返回对话响应（ChatResponse）
3. 支持流式输出（ChatChunk）
4. 记录对话历史（ChatMessage）

【流式响应设计】
使用 SSE (Server-Sent Events) 实现流式输出：
- 每个 ChatChunk 是一个独立的 SSE 事件
- 客户端通过 EventSource 或 fetch + ReadableStream 接收
- 最后一个 chunk 的 is_final=True 表示流结束
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class FinishReason(str, Enum):
    """结束原因"""

    STOP = "stop"  # 正常结束
    PENDING_APPROVAL = "pending_approval"  # 等待审批
    TOOL_CALL = "tool_call"  # 调用工具
    ERROR = "error"  # 发生错误
    LENGTH = "length"  # 达到最大长度
    CONTENT_FILTER = "content_filter"  # 内容过滤


class ChatMessage(BaseModel):
    """对话消息

    用于记录对话历史和构建 Agent 输入。

    Attributes:
        role: 消息角色（user/assistant/system/tool）
        content: 消息内容
        timestamp: 消息时间戳
    """

    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="消息时间戳")

    model_config = {"json_schema_extra": {"examples": [{"role": "user", "content": "帮我查询订单状态", "timestamp": "2024-01-01T00:00:00Z"}]}}


class ChatOptions(BaseModel):
    """对话选项

    可选的对话配置参数。

    Attributes:
        model: 指定模型名称
        temperature: 温度参数（0-2），越高越随机
        max_tokens: 最大生成 token 数
        enable_rag: 是否启用 RAG 检索
        enable_tools: 是否启用工具调用
        stream: 是否流式输出
    """

    model: str | None = Field(default=None, description="指定模型名称")
    temperature: float | None = Field(default=None, ge=0, le=2, description="温度参数")
    max_tokens: int | None = Field(default=None, ge=1, le=8000, description="最大 token 数")
    enable_rag: bool = Field(default=True, description="是否启用 RAG")
    enable_tools: bool = Field(default=True, description="是否启用工具")
    stream: bool = Field(default=False, description="是否流式输出")


class ChatRequest(BaseModel):
    """对话请求

    接收用户输入并启动 Agent 执行。

    Attributes:
        message: 用户输入消息
        history: 对话历史（可选）
        session_id: 会话 ID（可选，用于多轮对话）
        options: 对话选项（可选）

    Example:
        ```json
        {
            "message": "帮我查询订单 ORD-123 的状态",
            "session_id": "sess_abc123",
            "options": {
                "model": "qwen-max",
                "enable_tools": true
            }
        }
        ```
    """

    message: str = Field(..., min_length=1, max_length=8000, description="用户输入消息")
    history: list[ChatMessage] | None = Field(default=None, description="对话历史")
    session_id: str | None = Field(default=None, description="会话 ID")
    options: ChatOptions | None = Field(default=None, description="对话选项")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "帮我查询订单 ORD-123 的状态",
                    "session_id": "sess_abc123",
                    "options": {"model": "qwen-max", "enable_tools": True},
                }
            ]
        }
    }


class ToolCallInfo(BaseModel):
    """工具调用信息

    记录 Agent 调用的工具详情。

    Attributes:
        tool_id: 工具调用唯一标识
        tool_name: 工具名称
        arguments: 工具参数
        result: 工具返回结果（执行后填充）
    """

    tool_id: str = Field(..., description="工具调用 ID")
    tool_name: str = Field(..., description="工具名称")
    arguments: dict = Field(default_factory=dict, description="工具参数")
    result: dict | None = Field(default=None, description="工具返回结果")


class TokenUsage(BaseModel):
    """Token 使用统计

    记录本次对话的 token 消耗。

    Attributes:
        prompt_tokens: 提示词 token 数
        completion_tokens: 补全 token 数
        total_tokens: 总 token 数
    """

    prompt_tokens: int = Field(default=0, ge=0, description="提示词 token 数")
    completion_tokens: int = Field(default=0, ge=0, description="补全 token 数")
    total_tokens: int = Field(default=0, ge=0, description="总 token 数")


class ChatResponse(BaseModel):
    """对话响应

    返回 Agent 执行结果。

    Attributes:
        request_id: 请求追踪 ID
        session_id: 会话 ID
        response: Agent 生成的响应内容
        model_used: 使用的模型名称
        tokens: Token 使用统计
        tool_calls: 工具调用列表（如有）
        approval_id: 审批 ID（如需审批）
        finish_reason: 结束原因
        latency_ms: 响应延迟（毫秒）
    """

    request_id: str = Field(..., description="请求追踪 ID")
    session_id: str = Field(..., description="会话 ID")
    response: str = Field(default="", description="Agent 生成的响应")
    model_used: str = Field(default="qwen-max", description="使用的模型")
    tokens: TokenUsage = Field(default_factory=TokenUsage, description="Token 统计")
    tool_calls: list[ToolCallInfo] | None = Field(default=None, description="工具调用列表")
    approval_id: str | None = Field(default=None, description="审批 ID（如需审批）")
    finish_reason: FinishReason = Field(default=FinishReason.STOP, description="结束原因")
    latency_ms: int = Field(default=0, ge=0, description="响应延迟（毫秒）")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "req_abc123",
                    "session_id": "sess_xyz789",
                    "response": "订单 ORD-123 的当前状态是：已发货",
                    "model_used": "qwen-max",
                    "tokens": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                    "finish_reason": "stop",
                    "latency_ms": 1500,
                }
            ]
        }
    }


class ChatChunk(BaseModel):
    """对话流式响应块

    用于 SSE 流式输出的单个数据块。

    【流式输出流程】
    1. 客户端发起 POST 请求，stream=true
    2. 服务端返回 text/event-stream 响应
    3. 每个 ChatChunk 作为一个 SSE 事件发送
    4. 最后一个 chunk 的 is_final=True，包含完整统计信息

    Attributes:
        chunk_id: 数据块序号
        delta_content: 增量内容
        is_final: 是否为最后一个数据块
        finish_reason: 结束原因（仅 final 块有值）
        tokens: Token 统计（仅 final 块有值）
    """

    chunk_id: int = Field(..., ge=0, description="数据块序号")
    delta_content: str = Field(default="", description="增量内容")
    is_final: bool = Field(default=False, description="是否为最后一个数据块")
    finish_reason: FinishReason | None = Field(default=None, description="结束原因")
    tokens: TokenUsage | None = Field(default=None, description="Token 统计")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"chunk_id": 0, "delta_content": "订单", "is_final": False},
                {"chunk_id": 1, "delta_content": " ORD-123", "is_final": False},
                {
                    "chunk_id": 2,
                    "delta_content": " 已发货",
                    "is_final": True,
                    "finish_reason": "stop",
                    "tokens": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                },
            ]
        }
    }
