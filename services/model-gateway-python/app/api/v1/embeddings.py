"""Embeddings API - 文本向量化

提供 OpenAI 兼容的 /v1/embeddings 接口，供 Knowledge 服务（RAG）与
Orchestrator（长时记忆）调用，将文本转为向量用于相似度检索。

设计要点：
- OpenAI 兼容请求/响应格式，下游无需特殊适配
- 通过 ModelRouter 选择支持 embedding 且可用的 Provider，带熔断保护
- 失败显式返回错误（503/500），绝不返回零向量等静默降级值
"""

import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import config
from app.providers.base import EmbeddingRequest as ProviderEmbeddingRequest
from app.providers.qwen import CircuitBreakerOpenError
from app.router.model_router import get_model_router

router = APIRouter()
logger = structlog.get_logger()


class EmbeddingApiRequest(BaseModel):
    """Embedding 请求（OpenAI 兼容）

    input 支持字符串或字符串数组，统一规整为数组处理。
    """

    input: str | list[str]
    model: str | None = Field(default=None, description="embedding 模型，缺省用网关默认")


@router.post("/embeddings", tags=["embeddings"])
async def create_embeddings(request: EmbeddingApiRequest):
    """生成文本向量 - OpenAI 兼容接口

    Returns:
        {
          "object": "list",
          "data": [{"object": "embedding", "index": 0, "embedding": [...]}],
          "model": "...",
          "usage": {...}
        }
    """
    request_id = f"emb-{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    # 规整 input 为列表
    inputs = [request.input] if isinstance(request.input, str) else list(request.input)
    if not inputs or all(not s for s in inputs):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ERR_INVALID_MODEL_REQUEST",
                "message": "input 不能为空",
                "request_id": request_id,
            },
        )

    # 批量上限保护
    max_batch = getattr(config, "embedding_max_batch", 10)
    if len(inputs) > max_batch:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ERR_INVALID_MODEL_REQUEST",
                "message": f"单次 embedding 文本数不能超过 {max_batch}",
                "request_id": request_id,
            },
        )

    model = request.model or config.embedding_model

    # 选择 embedding Provider
    model_router = get_model_router()
    selected = model_router.get_embedding_provider(model)
    if selected is None:
        logger.error("embedding_no_provider", request_id=request_id, model=model)
        from app.metrics.prometheus_metrics import EMBEDDING_CALL_TOTAL

        EMBEDDING_CALL_TOTAL.labels(provider="none", model=model, status="unavailable").inc()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_MODEL_ALL_PROVIDERS_DOWN",
                "message": "暂无可用的向量化服务",
                "request_id": request_id,
            },
        )

    provider, circuit_breaker = selected

    try:
        provider_response = await provider.create_embeddings(ProviderEmbeddingRequest(input=inputs, model=model))
        circuit_breaker.record_success()

        latency_ms = int((time.time() - start_time) * 1000)
        from app.metrics.prometheus_metrics import EMBEDDING_CALL_TOTAL

        EMBEDDING_CALL_TOTAL.labels(provider=provider.provider_name, model=model, status="success").inc()

        logger.info(
            "embedding_completed",
            request_id=request_id,
            provider=provider.provider_name,
            model=model,
            count=len(inputs),
            latency_ms=latency_ms,
        )

        return {
            "object": "list",
            "data": [
                {"object": "embedding", "index": d.index, "embedding": d.embedding} for d in provider_response.data
            ],
            "model": provider_response.model,
            "usage": provider_response.usage,
        }

    except CircuitBreakerOpenError:
        logger.warning("embedding_circuit_open", request_id=request_id)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_PROVIDER_UNAVAILABLE",
                "message": "向量化服务暂时不可用，请稍后重试",
                "request_id": request_id,
            },
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ERR_MODEL_ALL_PROVIDERS_DOWN",
                "message": "暂无可用的向量化服务",
                "request_id": request_id,
            },
        )
    except Exception as e:
        circuit_breaker.record_failure()
        from app.metrics.prometheus_metrics import EMBEDDING_CALL_TOTAL

        EMBEDDING_CALL_TOTAL.labels(provider=provider.provider_name, model=model, status="error").inc()
        logger.error(
            "embedding_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ERR_INTERNAL_ERROR",
                "message": "向量化失败",
                "request_id": request_id,
            },
        )
