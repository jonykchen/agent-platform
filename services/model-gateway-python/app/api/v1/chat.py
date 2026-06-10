"""Chat API - 对话补全

核心职责：
1. 接收 OpenAI 兼容格式的对话请求（支持流式 / 非流式）
2. 分布式限流（租户 + Provider 维度）
3. 调用模型路由器选择最优模型并执行调用
4. 内容安全过滤（前置本地词表 + Provider 侧 finish_reason）
5. 成本与延迟指标上报
"""

import json
import time
import uuid

import structlog
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.content_filter import get_content_filter
from app.core.exceptions import (
    AllProvidersDownError,
    ModelContentFilteredError,
    ModelTimeoutError,
)
from app.core.rate_limiter import get_rate_limiter
from app.core.response_cache import get_response_cache
from app.metrics.cost_calculator import calculate_cost
from app.metrics.prometheus_metrics import (
    CONTENT_FILTERED_TOTAL,
    MODEL_CALL_LATENCY,
    MODEL_CALL_TOTAL,
    RATE_LIMITED_TOTAL,
    record_cost,
)
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


async def _enforce_rate_limit(tenant_id: str, model: str, request_id: str) -> None:
    """执行分布式限流，超限抛 429。"""
    limiter = get_rate_limiter()
    if limiter is None:
        return
    scope = f"tenant:{tenant_id}:model:{model}"
    result = await limiter.check(scope=scope, request_id=request_id)
    if not result.allowed:
        RATE_LIMITED_TOTAL.labels(tenant_id=tenant_id).inc()
        logger.warning(
            "rate_limited",
            request_id=request_id,
            tenant_id=tenant_id,
            current=result.current,
            limit=result.limit,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "ERR_RATE_LIMIT_EXCEEDED",
                "message": "请求过于频繁，请稍后重试",
                "request_id": request_id,
            },
            headers={"Retry-After": str(result.retry_after_s)},
        )


@router.post("/chat/completions")
async def chat_completion(
    request: ChatRequest,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
):
    """对话补全 - OpenAI 兼容接口（支持流式与非流式）"""
    request_id = f"chat-{uuid.uuid4().hex[:8]}"
    tenant_id = x_tenant_id or "default"
    start_time = time.time()

    logger.info(
        "request_received",
        endpoint="/v1/chat/completions",
        request_id=request_id,
        tenant_id=tenant_id,
        model=request.model,
        message_count=len(request.messages),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=request.stream,
    )

    # 内容安全过滤（前置）：命中敏感内容直接拒绝，不发往 Provider
    try:
        get_content_filter().check_messages(request.messages, request_id)
    except ModelContentFilteredError:
        CONTENT_FILTERED_TOTAL.labels(category="input", source="local").inc()
        logger.warning("content_filtered_rejected", request_id=request_id)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ERR_MODEL_CONTENT_FILTERED",
                "message": "输入内容未通过安全审查，请调整后重试",
                "request_id": request_id,
            },
        )

    # 分布式限流
    await _enforce_rate_limit(tenant_id, request.model, request_id)

    if request.stream:
        return await _handle_stream(request, tenant_id, request_id, start_time)
    return await _handle_sync(request, tenant_id, request_id, start_time)


async def _handle_sync(request: ChatRequest, tenant_id: str, request_id: str, start_time: float):
    """非流式对话补全。"""
    circuit_breaker = None
    try:
        # 响应缓存：低温度非流式请求命中缓存直接返回
        cache = get_response_cache()
        cacheable = cache.is_cacheable(request.temperature, request.stream)
        if cacheable:
            cached = await cache.get(request.model, request.messages, request.temperature, request.max_tokens)
            if cached:
                logger.info("request_served_from_cache", request_id=request_id)
                return ChatResponse(**cached)

        model_router = get_model_router()
        chat_request = ChatCompletionRequest(
            messages=[{"role": m["role"], "content": m["content"]} for m in request.messages],
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )

        provider, model_name, circuit_breaker = await model_router.route(chat_request, tenant_id=tenant_id)
        logger.info(
            "model_routed",
            request_id=request_id,
            requested_model=request.model,
            actual_model=model_name,
            provider=provider.provider_name,
        )

        response = await provider.chat_completion(chat_request)
        circuit_breaker.record_success()

        # Provider 侧内容过滤：finish_reason=content_filter 转标准错误
        for choice in response.choices:
            if choice.finish_reason == "content_filter":
                CONTENT_FILTERED_TOTAL.labels(category="output", source="provider").inc()
                raise ModelContentFilteredError(reason="provider_content_filter")

        latency_ms = int((time.time() - start_time) * 1000)
        _record_success_metrics(
            provider.provider_name,
            response.model,
            tenant_id,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            latency_ms,
            stream=False,
        )

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

        if cacheable:
            await cache.set(
                request.model,
                request.messages,
                request.temperature,
                request.max_tokens,
                chat_response.model_dump(),
            )

        return chat_response

    except ModelContentFilteredError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning("content_filtered_rejected", request_id=request_id, latency_ms=latency_ms)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ERR_MODEL_CONTENT_FILTERED",
                "message": "内容未通过安全审查，请调整后重试",
                "request_id": request_id,
            },
        )
    except AllProvidersDownError:
        logger.error("all_providers_down", request_id=request_id)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_MODEL_ALL_PROVIDERS_DOWN",
                "message": "所有模型提供商暂时不可用，请稍后重试",
                "request_id": request_id,
            },
        )
    except ModelTimeoutError as e:
        logger.error("model_timeout", request_id=request_id, timeout_s=e.timeout_s)
        raise HTTPException(
            status_code=504,
            detail={
                "error": "ERR_MODEL_TIMEOUT",
                "message": f"模型响应超时 ({e.timeout_s}秒)",
                "request_id": request_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "request_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            latency_ms=latency_ms,
        )
        if circuit_breaker is not None:
            try:
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


async def _handle_stream(request: ChatRequest, tenant_id: str, request_id: str, start_time: float):
    """流式对话补全：转发 Provider 的 SSE 流，并在结束时上报指标。"""
    model_router = get_model_router()
    chat_request = ChatCompletionRequest(
        messages=[{"role": m["role"], "content": m["content"]} for m in request.messages],
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=True,
    )

    try:
        provider, model_name, circuit_breaker = await model_router.route(chat_request, tenant_id=tenant_id)
    except AllProvidersDownError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_MODEL_ALL_PROVIDERS_DOWN",
                "message": "所有模型提供商暂时不可用，请稍后重试",
                "request_id": request_id,
            },
        )

    logger.info(
        "model_routed",
        request_id=request_id,
        actual_model=model_name,
        provider=provider.provider_name,
        stream=True,
    )

    async def event_generator():
        completion_chars = 0
        content_filtered = False
        try:
            async for line in provider.stream_chat_completion(chat_request):
                # provider 产出形如 "data: {...}" 的 SSE 行
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :].strip()
                if payload == "[DONE]":
                    break

                # 解析以检测 content_filter 并累计输出长度
                try:
                    chunk = json.loads(payload)
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta", {})
                        if delta.get("content"):
                            completion_chars += len(delta["content"])
                        if choice.get("finish_reason") == "content_filter":
                            content_filtered = True
                except (json.JSONDecodeError, AttributeError):
                    pass

                # 原样转发上游 chunk（已是 OpenAI delta 格式）
                yield f"data: {payload}\n\n"

            if content_filtered:
                CONTENT_FILTERED_TOTAL.labels(category="output", source="provider").inc()
                error_event = {
                    "error": "ERR_MODEL_CONTENT_FILTERED",
                    "request_id": request_id,
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
            circuit_breaker.record_success()

            # 流式结束后上报指标（completion token 用字符数近似）
            latency_ms = int((time.time() - start_time) * 1000)
            _record_success_metrics(
                provider.provider_name,
                model_name,
                tenant_id,
                prompt_tokens=0,
                completion_tokens=completion_chars,
                latency_ms=latency_ms,
                stream=True,
            )
            logger.info(
                "stream_completed",
                request_id=request_id,
                provider=provider.provider_name,
                model=model_name,
                completion_chars=completion_chars,
                latency_ms=latency_ms,
            )

        except Exception as e:
            try:
                circuit_breaker.record_failure()
            except Exception:
                pass
            MODEL_CALL_TOTAL.labels(
                provider=provider.provider_name,
                model=model_name,
                status="error",
                stream="true",
            ).inc()
            logger.error(
                "stream_interrupted",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            error_event = {
                "error": "ERR_STREAM_INTERRUPTED",
                "message": "流式响应中断",
                "request_id": request_id,
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲，保证实时下发
        },
    )


def _record_success_metrics(
    provider: str,
    model: str,
    tenant_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    stream: bool,
) -> None:
    """统一上报成功调用的指标（次数、延迟、token、成本）。"""
    stream_label = "true" if stream else "false"
    MODEL_CALL_TOTAL.labels(provider=provider, model=model, status="success", stream=stream_label).inc()
    MODEL_CALL_LATENCY.labels(provider=provider, model=model, stream=stream_label).observe(latency_ms / 1000.0)
    cost = calculate_cost(model, prompt_tokens, completion_tokens)
    record_cost(
        provider=provider,
        model=model,
        tenant_id=tenant_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost,
    )
