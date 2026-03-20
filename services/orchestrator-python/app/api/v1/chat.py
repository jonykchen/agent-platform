"""Chat API - 对话补全"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

import structlog

from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
from app.core.config import config

logger = structlog.get_logger()
router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., min_length=1, max_length=8000, description="用户输入消息")
    session_id: str | None = Field(None, description="会话 ID")
    model: str | None = Field(None, description="指定模型")
    temperature: float | None = Field(None, ge=0, le=2, description="温度参数")
    max_tokens: int | None = Field(None, ge=1, le=8000, description="最大 token 数")
    stream: bool = Field(False, description="是否流式输出")
    enable_rag: bool = Field(True, description="是否启用 RAG")
    enable_tools: bool = Field(True, description="是否启用工具")


class ChatResponse(BaseModel):
    """对话响应"""

    request_id: str
    response: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    finish_reason: str


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest, req: Request):
    """对话补全"""
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    logger.info(
        "Chat request",
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        message_length=len(request.message),
        stream=request.stream,
    )

    # TODO: 实现 Agent 编排逻辑
    # 当前返回 Mock 响应

    return ChatResponse(
        request_id=request_id,
        response=f"收到您的消息：{request.message[:100]}\n\n（Agent 编排引擎待实现）",
        model_used="mock",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.0,
        latency_ms=50,
        finish_reason="stop",
    )