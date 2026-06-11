"""DeepSeek (深度求索) 提供商实现

DeepSeek 采用 OpenAI 兼容 API 格式，集成重试和熔断机制。

【支持的模型】
- deepseek-chat: 通用对话模型，64K 上下文，性价比高
- deepseek-reasoner: 推理增强模型（R1），适合复杂推理任务

参考：https://api-docs.deepseek.com/
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
    ModelInfo,
)
from app.resilience.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger()


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek 提供商

    特性：
    - 熔断保护：连续失败 10 次后熔断
    - 重试机制：网络错误指数退避重试
    - 超时控制：防止无限阻塞
    - 健康检查：支持主动健康探测

    DeepSeek API 与 OpenAI 完全兼容，请求/响应格式无需特殊转换。
    """

    # 【模型元信息】
    # 价格参考: https://api-docs.deepseek.com/quick_start/pricing
    MODEL_INFOS: list[ModelInfo] = [
        ModelInfo(
            name="deepseek-chat",
            provider="deepseek",
            input_cost_per_1k=0.001,  # ¥0.001/千token（缓存未命中）
            output_cost_per_1k=0.002,  # ¥0.002/千token
            context_window=65536,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="deepseek-reasoner",
            provider="deepseek",
            input_cost_per_1k=0.004,
            output_cost_per_1k=0.016,
            context_window=65536,
            max_output_tokens=8192,
            supports_streaming=True,
            supports_tools=False,  # R1 推理模型暂不支持工具调用
        ),
    ]

    PROVIDER_MODELS = [m.name for m in MODEL_INFOS]

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
        self._circuit_breaker = CircuitBreaker(
            name="deepseek",
            failure_threshold=self.CIRCUIT_FAILURE_THRESHOLD,
            timeout_seconds=self.CIRCUIT_TIMEOUT_SECONDS,
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"

    @property
    def supported_models(self) -> list[str]:
        return self.PROVIDER_MODELS

    @property
    def _model_infos(self) -> list[ModelInfo]:
        return self.MODEL_INFOS

    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit_breaker.state

    @property
    def is_available(self) -> bool:
        return self._circuit_breaker.is_available()

    async def health_check(self) -> bool:
        """健康检查（调用 models 接口）"""
        if not self._circuit_breaker.is_available():
            logger.warning("deepseek_health_check_circuit_open", provider=self.provider_name)
            return False

        try:
            async with httpx.AsyncClient(timeout=float(self.HEALTH_CHECK_TIMEOUT_SECONDS)) as client:
                response = await client.get(f"{self.base_url}/models", headers=self.headers)
                if response.status_code == 200:
                    logger.info("deepseek_health_check_success", provider=self.provider_name)
                    return True
                logger.warning(
                    "deepseek_health_check_unexpected_status",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )
                return False

        except httpx.TimeoutException:
            logger.warning("deepseek_health_check_timeout", provider=self.provider_name)
            self._circuit_breaker.record_failure()
            return False
        except httpx.NetworkError as e:
            logger.warning("deepseek_health_check_network_error", provider=self.provider_name, error=str(e))
            self._circuit_breaker.record_failure()
            return False
        except Exception as e:
            logger.error("deepseek_health_check_error", provider=self.provider_name, error=str(e))
            return False

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全（带重试和熔断）"""
        model = request.model or "deepseek-chat"

        if not self._circuit_breaker.is_available():
            logger.warning(
                "deepseek_circuit_open",
                model=model,
                circuit_state=self._circuit_breaker.state.value,
            )
            raise CircuitBreakerOpenError("deepseek")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        response = await self._call_with_retry(payload)
        data = response.json()
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

        try:
            from app.core.config import config as gateway_config

            timeout_seconds = getattr(gateway_config, "model_call_timeout_s", 30)
        except ImportError:
            timeout_seconds = 30

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=self.RETRY_MIN_WAIT, max=self.RETRY_MAX_WAIT),
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
                        "deepseek_call_retry",
                        attempt=attempt.retry_state.attempt_number,
                        error=str(e),
                    )
                    self._circuit_breaker.record_failure()
                    raise

                except httpx.HTTPStatusError as e:
                    self._circuit_breaker.record_failure()
                    logger.error(
                        "deepseek_http_error",
                        status_code=e.response.status_code,
                        error=str(e),
                    )
                    raise

        raise RuntimeError("Retry exhausted without result")

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全"""
        model = request.model or "deepseek-chat"

        if not self._circuit_breaker.is_available():
            raise CircuitBreakerOpenError("deepseek")

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
            logger.error("deepseek_stream_error", error=str(e))
            raise


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"Circuit breaker for '{provider_name}' is open")
