"""GLM (智谱 AI) 提供商实现

智谱 GLM 提供 OpenAI 兼容 API（v4），集成重试和熔断机制。

【支持的模型】
- glm-4-plus: 旗舰模型，128K 上下文，能力最强
- glm-4-air: 性价比均衡，128K 上下文
- glm-4-flash: 速度最快，免费额度大，适合高频简单任务

参考：https://open.bigmodel.cn/dev/api
"""

from typing import AsyncIterator

import httpx
import structlog

from app.providers.base import (
    BaseLLMProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
    ModelInfo,
)
from app.resilience.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger()


class GLMProvider(BaseLLMProvider):
    """GLM (智谱) 提供商

    特性：
    - 熔断保护：连续失败 10 次后熔断
    - 重试机制：网络错误指数退避重试
    - 超时控制：防止无限阻塞
    - 健康检查：支持主动健康探测

    【兼容性说明】
    GLM v4 API 兼容 OpenAI 格式。注意点：
    - created 字段历史上可能返回字符串，这里统一转为 int
    - usage 可能为空，填充默认值 0
    """

    # 【模型元信息】
    # 价格参考: https://open.bigmodel.cn/pricing
    MODEL_INFOS: list[ModelInfo] = [
        ModelInfo(
            name="glm-4-plus",
            provider="glm",
            input_cost_per_1k=0.05,
            output_cost_per_1k=0.05,
            context_window=131072,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="glm-4-air",
            provider="glm",
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.001,
            context_window=131072,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
        ),
        ModelInfo(
            name="glm-4-flash",
            provider="glm",
            input_cost_per_1k=0.0,  # 免费
            output_cost_per_1k=0.0,
            context_window=131072,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
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
            name="glm",
            failure_threshold=self.CIRCUIT_FAILURE_THRESHOLD,
            timeout_seconds=self.CIRCUIT_TIMEOUT_SECONDS,
        )

    @property
    def provider_name(self) -> str:
        return "glm"

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

    @staticmethod
    def _normalize_created(value) -> int:
        """GLM 的 created 字段可能为字符串，统一转为 int 时间戳"""
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    async def health_check(self) -> bool:
        """健康检查（调用 models 接口）"""
        if not self._circuit_breaker.is_available():
            logger.warning("glm_health_check_circuit_open", provider=self.provider_name)
            return False

        try:
            async with httpx.AsyncClient(timeout=float(self.HEALTH_CHECK_TIMEOUT_SECONDS)) as client:
                response = await client.get(f"{self.base_url}/models", headers=self.headers)
                if response.status_code == 200:
                    logger.info("glm_health_check_success", provider=self.provider_name)
                    return True
                logger.warning(
                    "glm_health_check_unexpected_status",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )
                return False

        except httpx.TimeoutException:
            logger.warning("glm_health_check_timeout", provider=self.provider_name)
            self._circuit_breaker.record_failure()
            return False
        except httpx.NetworkError as e:
            logger.warning("glm_health_check_network_error", provider=self.provider_name, error=str(e))
            self._circuit_breaker.record_failure()
            return False
        except Exception as e:
            logger.error("glm_health_check_error", provider=self.provider_name, error=str(e))
            return False

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全（带重试和熔断）"""
        model = request.model or "glm-4-air"

        if not self._circuit_breaker.is_available():
            logger.warning(
                "glm_circuit_open",
                model=model,
                circuit_state=self._circuit_breaker.state.value,
            )
            raise CircuitBreakerOpenError("glm")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        response = await self._call_with_retry(payload)
        data = response.json()
        self._circuit_breaker.record_success()

        usage = data.get("usage") or {}
        return ChatCompletionResponse(
            id=data.get("id", ""),
            created=self._normalize_created(data.get("created", 0)),
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
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )

    async def _call_with_retry(self, payload: dict) -> httpx.Response:
        """带重试的 HTTP 调用"""
        from tenacity import (
            AsyncRetrying,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
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
                        "glm_call_retry",
                        attempt=attempt.retry_state.attempt_number,
                        error=str(e),
                    )
                    self._circuit_breaker.record_failure()
                    raise

                except httpx.HTTPStatusError as e:
                    self._circuit_breaker.record_failure()
                    logger.error(
                        "glm_http_error",
                        status_code=e.response.status_code,
                        error=str(e),
                    )
                    raise

        raise RuntimeError("Retry exhausted without result")

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全"""
        model = request.model or "glm-4-air"

        if not self._circuit_breaker.is_available():
            raise CircuitBreakerOpenError("glm")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            yield line

            self._circuit_breaker.record_success()

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error("glm_stream_error", error=str(e))
            raise


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"Circuit breaker for '{provider_name}' is open")
