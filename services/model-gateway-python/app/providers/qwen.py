"""Qwen (通义千问) 提供商实现

集成重试和熔断机制，防止无限阻塞。
"""

from collections.abc import AsyncIterator

import httpx
import structlog

from app.providers.base import (
    BaseLLMProvider,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelInfo,
)
from app.resilience.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger()


class QwenProvider(BaseLLMProvider):
    """Qwen 提供商

    特性：
    - 熔断保护：连续失败 10 次后熔断
    - 重试机制：网络错误指数退避重试
    - 超时控制：防止无限阻塞
    - 健康检查：支持主动健康探测

    【支持的模型】
    - qwen-max: 32K 上下文，支持工具调用
    - qwen-plus: 32K 上下文，性价比高
    - qwen-turbo: 8K 上下文，速度最快
    - qwen-long: 1M 上下文，长文本处理
    """

    # 【模型元信息】
    # 价格参考: https://help.aliyun.com/zh/dashscope/developer-reference/billing
    MODEL_INFOS: list[ModelInfo] = [
        ModelInfo(
            name="qwen-max",
            provider="qwen",
            input_cost_per_1k=0.02,  # ¥0.02/千token
            output_cost_per_1k=0.06,  # ¥0.06/千token
            context_window=32768,
            max_output_tokens=2000,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="qwen-plus",
            provider="qwen",
            input_cost_per_1k=0.004,  # ¥0.004/千token
            output_cost_per_1k=0.012,  # ¥0.012/千token
            context_window=32768,
            max_output_tokens=2000,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="qwen-turbo",
            provider="qwen",
            input_cost_per_1k=0.002,  # ¥0.002/千token
            output_cost_per_1k=0.006,  # ¥0.006/千token
            context_window=8192,
            max_output_tokens=1500,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="qwen-long",
            provider="qwen",
            input_cost_per_1k=0.0005,  # ¥0.0005/千token
            output_cost_per_1k=0.002,  # ¥0.002/千token
            context_window=1000000,  # 1M tokens
            max_output_tokens=2000,
            supports_streaming=True,
            supports_tools=False,
        ),
    ]

    # 模型名称列表（从 MODEL_INFOS 提取）
    PROVIDER_MODELS = [m.name for m in MODEL_INFOS]

    # 支持的 embedding 模型（DashScope 通义千问向量模型）
    EMBEDDING_MODELS = ["text-embedding-v3", "text-embedding-v2", "text-embedding-v1"]
    DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"

    # 熔断器配置
    CIRCUIT_FAILURE_THRESHOLD = 10
    CIRCUIT_TIMEOUT_SECONDS = 30

    # 重试配置
    RETRY_MAX_ATTEMPTS = 3
    RETRY_MIN_WAIT = 1.0
    RETRY_MAX_WAIT = 10.0

    # 健康检查配置
    HEALTH_CHECK_TIMEOUT_SECONDS = 5

    def __init__(self, api_key: str, base_url: str):
        super().__init__(api_key, base_url)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 熔断器
        self._circuit_breaker = CircuitBreaker(
            name="qwen",
            failure_threshold=self.CIRCUIT_FAILURE_THRESHOLD,
            timeout_seconds=self.CIRCUIT_TIMEOUT_SECONDS,
        )

    @property
    def provider_name(self) -> str:
        return "qwen"

    @property
    def supported_models(self) -> list[str]:
        return self.PROVIDER_MODELS

    @property
    def _model_infos(self) -> list[ModelInfo]:
        """返回 Qwen 模型信息列表"""
        return self.MODEL_INFOS

    @property
    def circuit_state(self) -> CircuitState:
        """获取熔断器状态"""
        return self._circuit_breaker.state

    @property
    def is_available(self) -> bool:
        """检查提供商是否可用"""
        return self._circuit_breaker.is_available()

    async def health_check(self) -> bool:
        """健康检查

        通过调用 models 接口检查服务是否可用。
        如果 models 接口不可用，则尝试简单补全请求。

        Returns:
            True 表示健康，False 表示不健康
        """
        # 如果熔断器打开，直接返回不健康
        if not self._circuit_breaker.is_available():
            logger.warning(
                "qwen_health_check_circuit_open",
                provider=self.provider_name,
            )
            return False

        try:
            async with httpx.AsyncClient(timeout=float(self.HEALTH_CHECK_TIMEOUT_SECONDS)) as client:
                # 尝试调用 models 接口
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    logger.info(
                        "qwen_health_check_success",
                        provider=self.provider_name,
                    )
                    return True

                # 非 200 状态码
                logger.warning(
                    "qwen_health_check_unexpected_status",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )
                return False

        except httpx.TimeoutException:
            logger.warning(
                "qwen_health_check_timeout",
                provider=self.provider_name,
                timeout_seconds=self.HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            self._circuit_breaker.record_failure()
            return False

        except httpx.NetworkError as e:
            logger.warning(
                "qwen_health_check_network_error",
                provider=self.provider_name,
                error=str(e),
            )
            self._circuit_breaker.record_failure()
            return False

        except Exception as e:
            logger.error(
                "qwen_health_check_error",
                provider=self.provider_name,
                error=str(e),
            )
            return False

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全（带重试和熔断）"""
        model = request.model or "qwen-max"

        # 检查熔断器状态
        if not self._circuit_breaker.is_available():
            logger.warning(
                "qwen_circuit_open",
                model=model,
                circuit_state=self._circuit_breaker.state.value,
            )
            raise CircuitBreakerOpenError("qwen")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # 带重试的调用
        response = await self._call_with_retry(payload)

        # 解析响应
        data = response.json()

        # 成功时重置熔断器
        self._circuit_breaker.record_success()

        return ChatCompletionResponse(
            id=data.get("id", ""),
            created=data.get("created", 0),
            model=data.get("model", model),
            choices=[
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=ChatMessage(
                        role=c["message"]["role"],
                        content=c["message"]["content"],
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
                for c in data.get("choices", [])
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    async def _call_with_retry(self, payload: dict) -> httpx.Response:
        """带重试的 HTTP 调用"""
        from tenacity import (
            AsyncRetrying,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        # 【P2-配置统一化】从配置读取超时值
        try:
            from app.core.config import config as gateway_config

            timeout_seconds = getattr(gateway_config, "model_call_timeout_s", 30)
        except ImportError:
            timeout_seconds = 30

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=self.RETRY_MIN_WAIT,
                max=self.RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                try:
                    async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self.headers,
                            json=payload,
                        )
                        response.raise_for_status()
                        return response

                except (httpx.NetworkError, httpx.TimeoutException) as e:
                    logger.warning(
                        "qwen_call_retry",
                        attempt=attempt.retry_state.attempt_number,
                        error=str(e),
                    )
                    self._circuit_breaker.record_failure()
                    raise

                except httpx.HTTPStatusError as e:
                    # HTTP 错误不重试
                    self._circuit_breaker.record_failure()
                    logger.error(
                        "qwen_http_error",
                        status_code=e.response.status_code,
                        error=str(e),
                    )
                    raise

        raise RuntimeError("Retry exhausted without result")

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全"""
        model = request.model or "qwen-max"

        # 检查熔断器状态
        if not self._circuit_breaker.is_available():
            raise CircuitBreakerOpenError("qwen")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
            # 要求 Provider 在流末尾多发一个含 usage 的 chunk，用于精确计费
            "stream_options": {"include_usage": True},
        }

        try:
            async with (
                httpx.AsyncClient(timeout=60.0) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line

            self._circuit_breaker.record_success()

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error("qwen_stream_error", error=str(e))
            raise

    @property
    def supports_embeddings(self) -> bool:
        return True

    async def create_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """生成文本向量（通义千问 text-embedding 系列）

        调用 DashScope OpenAI 兼容的 /embeddings 接口，返回 OpenAI 格式响应。
        带熔断保护与重试，失败显式抛错（绝不返回零向量等降级值）。
        """
        model = request.model or self.DEFAULT_EMBEDDING_MODEL

        if not self._circuit_breaker.is_available():
            raise CircuitBreakerOpenError("qwen")

        # 读取目标维度（与数据库 vector(dim) 对齐）
        try:
            from app.core.config import config as gateway_config

            dimension = getattr(gateway_config, "embedding_dimension", 1024)
            timeout_seconds = getattr(gateway_config, "model_call_timeout_s", 30)
        except ImportError:
            dimension = 1024
            timeout_seconds = 30

        payload = {
            "model": model,
            "input": request.input,
            "encoding_format": "float",
        }
        # text-embedding-v3 支持自定义维度
        if model == "text-embedding-v3":
            payload["dimension"] = dimension

        from tenacity import (
            AsyncRetrying,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=self.RETRY_MIN_WAIT, max=self.RETRY_MAX_WAIT),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                try:
                    async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                        # DashScope embedding 使用兼容模式端点
                        embedding_url = self.base_url.replace("/api/v1", "/compatible-mode/v1") + "/embeddings"
                        response = await client.post(
                            embedding_url,
                            headers=self.headers,
                            json=payload,
                        )
                        response.raise_for_status()
                        data = response.json()

                        self._circuit_breaker.record_success()

                        embeddings = [
                            EmbeddingData(
                                index=item.get("index", i),
                                embedding=item["embedding"],
                            )
                            for i, item in enumerate(data.get("data", []))
                        ]
                        if not embeddings:
                            raise ValueError("embedding response contains no data")

                        return EmbeddingResponse(
                            data=embeddings,
                            model=data.get("model", model),
                            usage=data.get("usage", {}),
                        )

                except (httpx.NetworkError, httpx.TimeoutException) as e:
                    logger.warning(
                        "qwen_embedding_retry",
                        attempt=attempt.retry_state.attempt_number,
                        error=str(e),
                    )
                    self._circuit_breaker.record_failure()
                    raise
                except httpx.HTTPStatusError as e:
                    self._circuit_breaker.record_failure()
                    logger.error(
                        "qwen_embedding_http_error",
                        status_code=e.response.status_code,
                        error=str(e),
                    )
                    raise

        raise RuntimeError("Embedding retry exhausted without result")


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"Circuit breaker for '{provider_name}' is open")
