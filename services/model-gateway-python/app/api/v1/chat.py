"""Chat API - 对话补全

核心职责：
1. 接收 OpenAI 兼容格式的对话请求
2. 调用模型路由器选择最优模型
3. 执行模型调用并返回结果

请求处理流程：
┌─────────────────────────────────────────────────────────┐
│                HTTP POST /v1/chat/completions           │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 请求参数解析    │                     │
│                  │ messages        │                     │
│                  │ model (可选)    │                     │
│                  │ temperature     │                     │
│                  │ max_tokens      │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 调用模型路由器  │                     │
│                  │ route(request)   │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 执行模型调用    │                     │
│                  │ provider.chat() │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 构建响应        │                     │
│                  │ ChatResponse    │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                    返回 HTTP 响应                       │
└─────────────────────────────────────────────────────────┘

OpenAI 兼容接口：
- 请求格式与 OpenAI API 一致
- 支持 messages 数组格式
- 支持 model, temperature, max_tokens 参数
- 流式输出暂不支持

"""

import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.content_filter import get_content_filter
from app.core.exceptions import (
    AllProvidersDownError,
    ModelContentFilteredError,
    ModelTimeoutError,
)
from app.core.response_cache import get_response_cache
from app.providers.base import ChatCompletionRequest
from app.router.model_router import get_model_router

router = APIRouter()
logger = structlog.get_logger()


class ChatRequest(BaseModel):
    """对话请求"""

    messages: list[dict] = Field(..., min_length=1)
    model: str = "qwen-max"
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(2000, ge=1, le=8000)
    stream: bool = False


class ChatResponse(BaseModel):
    """对话响应"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict]
    usage: dict


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """对话补全 - OpenAI 兼容接口

    处理流程：
    1. 解析请求参数
    2. 调用模型路由器选择最优模型
    3. 执行模型调用
    4. 返回 OpenAI 格式的响应

    Args:
        request: ChatRequest 对话请求
            - messages: 对话消息列表
            - model: 可选的指定模型
            - temperature: 温度参数 (0-2)
            - max_tokens: 最大生成 token 数
            - stream: 是否流式输出（暂不支持）

    Returns:
        ChatResponse OpenAI 格式的对话响应
            - id: 响应唯一标识
            - model: 实际使用的模型
            - choices: 生成结果列表
            - usage: Token 使用统计
    """
    request_id = f"chat-{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    logger.info(
        "request_received",
        endpoint="/v1/chat/completions",
        request_id=request_id,
        model=request.model,
        message_count=len(request.messages),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=request.stream,
    )

    if request.stream:
        logger.warning(
            "streaming_not_supported",
            request_id=request_id,
        )

    try:
        # 内容安全过滤（前置）：命中敏感内容直接拒绝，不发往 Provider
        get_content_filter().check_messages(request.messages, request_id)

        # 响应缓存：低温度非流式请求命中缓存直接返回
        cache = get_response_cache()
        cacheable = cache.is_cacheable(request.temperature, request.stream)
        if cacheable:
            cached = await cache.get(
                request.model, request.messages, request.temperature, request.max_tokens
            )
            if cached:
                logger.info("request_served_from_cache", request_id=request_id)
                return ChatResponse(**cached)

        # 获取模型路由器
        model_router = get_model_router()

        # 构建请求对象
        chat_request = ChatCompletionRequest(
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in request.messages
            ],
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )

        # 路由到最优模型
        provider, model_name, circuit_breaker = await model_router.route(chat_request)

        logger.info(
            "model_routed",
            request_id=request_id,
            requested_model=request.model,
            actual_model=model_name,
            provider=provider.provider_name,
        )

        # 执行模型调用
        response = await provider.chat_completion(chat_request)

        # 记录成功
        circuit_breaker.record_success()

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "request_completed",
            endpoint="/v1/chat/completions",
            request_id=request_id,
            model=response.model,
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )

        chat_response = ChatResponse(
            id=response.id,
            created=response.created,
            model=response.model,
            choices=[
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content,
                    },
                    "finish_reason": choice.finish_reason,
                }
                for choice in response.choices
            ],
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

        # 写入响应缓存（低温度非流式请求）
        if cacheable:
            await cache.set(
                request.model, request.messages, request.temperature,
                request.max_tokens, chat_response.model_dump(),
            )

        return chat_response

    except ModelContentFilteredError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            "content_filtered_rejected",
            request_id=request_id,
            latency_ms=latency_ms,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ERR_MODEL_CONTENT_FILTERED",
                "message": "输入内容未通过安全审查，请调整后重试",
                "request_id": request_id,
            },
        )

    except AllProvidersDownError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "all_providers_down",
            request_id=request_id,
            latency_ms=latency_ms,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_MODEL_ALL_PROVIDERS_DOWN",
                "message": "所有模型提供商暂时不可用，请稍后重试",
                "request_id": request_id,
            },
        )

    except ModelTimeoutError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "model_timeout",
            request_id=request_id,
            timeout_s=e.timeout_s,
            latency_ms=latency_ms,
        )
        raise HTTPException(
            status_code=504,
            detail={
                "error": "ERR_MODEL_TIMEOUT",
                "message": f"模型响应超时 ({e.timeout_s}秒)",
                "request_id": request_id,
            },
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "request_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            latency_ms=latency_ms,
        )

        # 尝试记录熔断器失败
        try:
            if "circuit_breaker" in dir() and circuit_breaker:
                circuit_breaker.record_failure()
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "error": "ERR_INTERNAL_ERROR",
                "message": "内部服务错误",
                "request_id": request_id,
            },
        )
