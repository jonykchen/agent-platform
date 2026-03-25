"""ModelGateway HTTP 客户端

通过 HTTP 调用 ModelGateway 服务进行模型推理。
支持熔断器、重试、连接池优化。
"""

import asyncio
import json
import time
from typing import Any

import httpx
import structlog

from app.core.config import config
from app.core.exceptions import AllProvidersDownError, ModelTimeoutError
from app.core.resilience import (
    CircuitBreakerOpenError,
    model_gateway_circuit,
    model_retry_policy,
)

logger = structlog.get_logger()

# 默认模型列表（用于降级）
DEFAULT_MODELS = [
    {"id": "qwen-max", "provider": "qwen"},
    {"id": "qwen-plus", "provider": "qwen"},
    {"id": "deepseek-v3", "provider": "deepseek"},
]

# 模型降级顺序
MODEL_FALLBACK_ORDER = ["qwen-max", "deepseek-v3", "qwen-plus"]


class ModelGatewayClient:
    """ModelGateway HTTP 客户端

    特性:
    - 连接池优化
    - 熔断器保护
    - 指数退避重试
    - 模型降级策略
    - 流式响应超时保护
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or config.model_gateway_url
        self._client: httpx.AsyncClient | None = None
        self._call_stats: dict[str, dict[str, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=config.model_call_timeout_s,
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=config.http_max_connections,
                    max_keepalive_connections=config.http_max_keepalive,
                    keepalive_expiry=config.http_keepalive_expiry,
                ),
            )
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @model_gateway_circuit
    @model_retry_policy
    async def _do_chat_completion(
        self,
        client: httpx.AsyncClient,
        payload: dict,
    ) -> dict:
        """执行对话补全（带熔断器和重试）"""
        response = await client.post(
            "/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        fallback: bool = True,
        **kwargs,
    ) -> dict:
        """对话补全

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称（可选，由网关路由）
            temperature: 温度参数
            max_tokens: 最大输出 token
            stream: 是否流式输出
            fallback: 是否启用降级策略

        Returns:
            OpenAI 兼容格式的响应
        """
        client = await self._get_client()

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if model:
            payload["model"] = model

        payload.update(kwargs)

        start_time = time.monotonic()
        models_to_try = [model] if model else [None]

        if fallback and model:
            models_to_try = MODEL_FALLBACK_ORDER

        last_error = None

        for try_model in models_to_try:
            if try_model:
                payload["model"] = try_model

            try:
                result = await self._do_chat_completion(client, payload)
                duration = time.monotonic() - start_time

                logger.info(
                    "Chat completion success",
                    model=try_model,
                    duration_ms=int(duration * 1000),
                )

                # 记录统计
                self._update_stats(try_model or "default", success=True, duration=duration)

                return result

            except CircuitBreakerOpenError as e:
                logger.warning(
                    "Circuit breaker open, skipping model",
                    model=try_model,
                    circuit=e.circuit_name,
                )
                last_error = e
                continue

            except httpx.TimeoutException as e:
                logger.warning(
                    "Model gateway timeout, trying fallback",
                    model=try_model,
                    error=str(e),
                )
                last_error = ModelTimeoutError(timeout_s=config.model_call_timeout_s)
                self._update_stats(try_model or "default", success=False)
                continue

            except httpx.HTTPStatusError as e:
                logger.error(
                    "Model gateway error",
                    model=try_model,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                self._update_stats(try_model or "default", success=False)

                if e.response.status_code == 503:
                    last_error = AllProvidersDownError()
                    continue

                try:
                    error_data = e.response.json()
                    return {
                        "error": error_data.get("error", "unknown"),
                        "message": error_data.get("message", str(e)),
                    }
                except Exception:
                    return {
                        "error": "http_error",
                        "message": str(e),
                    }

            except Exception as e:
                logger.error("Unexpected error in chat completion", error=str(e))
                self._update_stats(try_model or "default", success=False)
                last_error = e
                continue

        # 所有模型都失败
        if last_error:
            raise last_error

        raise AllProvidersDownError()

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ):
        """流式对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token
            timeout: 总超时时间（秒）

        Yields:
            SSE 格式的数据块
        """
        client = await self._get_client()

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if model:
            payload["model"] = model

        try:
            async with asyncio.timeout(timeout):
                async with client.stream(
                    "POST",
                    "/v1/chat/completions",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue

        except asyncio.TimeoutError:
            logger.error("Stream chat completion timeout", timeout=timeout)
            raise ModelTimeoutError(timeout_s=timeout)

        except httpx.TimeoutException as e:
            logger.error("Model gateway stream timeout", error=str(e))
            raise ModelTimeoutError(timeout_s=config.model_call_timeout_s)

    async def list_models(self, use_cache: bool = True) -> list[dict]:
        """获取可用模型列表

        Args:
            use_cache: 是否使用缓存结果（降级时）
        """
        client = await self._get_client()

        try:
            response = await client.get("/v1/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

        except Exception as e:
            logger.warning(
                "List models failed, using fallback",
                error=str(e),
            )
            if use_cache:
                return DEFAULT_MODELS
            return []

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """带工具调用的对话

        Args:
            messages: 消息列表
            tools: 工具定义列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token

        Returns:
            包含 tool_calls 的响应
        """
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice="auto",
        )

    def _update_stats(self, model: str, success: bool, duration: float = 0.0):
        """更新调用统计"""
        if model not in self._call_stats:
            self._call_stats[model] = {
                "total": 0,
                "success": 0,
                "failure": 0,
                "total_duration": 0.0,
            }

        stats = self._call_stats[model]
        stats["total"] += 1
        if success:
            stats["success"] += 1
            stats["total_duration"] += duration
        else:
            stats["failure"] += 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """获取调用统计"""
        return self._call_stats.copy()


# 全局客户端实例
_client = None


def get_model_gateway_client() -> ModelGatewayClient:
    """获取 ModelGateway 客户端实例"""
    global _client
    if _client is None:
        _client = ModelGatewayClient()
    return _client