"""弹性模式模块 - 熔断器、重试、降级策略

提供生产级弹性能力，防止下游服务故障时雪崩。
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar

import httpx
import structlog
from circuitbreaker import CircuitBreakerError, circuit
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import config

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


class ModelGatewayCircuitBreaker:
    """ModelGateway 熔断器

    当连续失败达到阈值时，熔断器打开，快速失败。
    经过恢复超时后，进入半开状态，尝试恢复。
    """

    def __init__(
        self,
        name: str = "model_gateway",
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold or config.circuit_failure_threshold
        self.recovery_timeout = recovery_timeout or config.circuit_recovery_timeout
        self._circuit = circuit(
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout,
            name=self.name,
        )
        self._state = "closed"  # closed, open, half-open

    def __call__(self, func: F) -> F:
        """装饰器模式"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # 使用 circuit breaker
                @self._circuit
                async def _execute():
                    return await func(*args, **kwargs)

                return await _execute()
            except CircuitBreakerError:
                logger.warning(
                    "Circuit breaker is open",
                    circuit_name=self.name,
                    state=self._state,
                )
                raise CircuitBreakerOpenError(self.name)

        return wrapper  # type: ignore

    @property
    def state(self) -> str:
        """获取当前状态"""
        return self._state

    def is_open(self) -> bool:
        """熔断器是否打开"""
        return self._circuit._state == "open"


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    def __init__(self, circuit_name: str):
        self.circuit_name = circuit_name
        super().__init__(f"Circuit breaker '{circuit_name}' is open")


class AsyncRetryPolicy:
    """异步重试策略

    支持指数退避重试，适用于网络瞬态故障。
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        retry_exceptions: tuple[type[Exception], ...] | None = None,
    ):
        self.max_attempts = max_attempts or config.retry_max_attempts
        self.min_wait = min_wait or config.retry_min_wait
        self.max_wait = max_wait or config.retry_max_wait
        self.retry_exceptions = retry_exceptions or (httpx.NetworkError, httpx.TimeoutException)

    def __call__(self, func: F) -> F:
        """装饰器模式"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retryer = AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self.min_wait,
                    max=self.max_wait,
                ),
                retry=retry_if_exception_type(self.retry_exceptions),
                reraise=True,
            )

            async for attempt in retryer:
                with attempt:
                    return await func(*args, **kwargs)

            # 不应该到达这里
            raise RuntimeError("Retry policy exhausted without result")

        return wrapper  # type: ignore


def with_retry_and_circuit(
    circuit_breaker: ModelGatewayCircuitBreaker,
    retry_policy: AsyncRetryPolicy | None = None,
):
    """组合熔断器和重试的装饰器

    先重试，后熔断。
    """
    retry = retry_policy or AsyncRetryPolicy()

    def decorator(func: F) -> F:
        @circuit_breaker
        @retry
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


class FallbackStrategy:
    """降级策略

    当主逻辑失败时，尝试备用方案。
    """

    def __init__(self, fallback_func: Callable[..., Any]):
        self.fallback_func = fallback_func

    def __call__(self, func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Primary function failed, executing fallback",
                    error=str(e),
                    fallback_func=self.fallback_func.__name__,
                )
                if asyncio.iscoroutinefunction(self.fallback_func):
                    return await self.fallback_func(*args, **kwargs)
                return self.fallback_func(*args, **kwargs)

        return wrapper  # type: ignore


# 全局熔断器实例
model_gateway_circuit = ModelGatewayCircuitBreaker(name="model_gateway")
tool_bus_circuit = ModelGatewayCircuitBreaker(name="tool_bus")

# 全局重试策略
model_retry_policy = AsyncRetryPolicy()
tool_retry_policy = AsyncRetryPolicy(
    retry_exceptions=(Exception,),  # gRPC 异常
)


def get_circuit_state_metric(circuit_name: str) -> int:
    """获取熔断器状态用于 metrics

    Returns:
        0: closed, 1: open, 2: half-open
    """
    if circuit_name == "model_gateway":
        circuit = model_gateway_circuit
    elif circuit_name == "tool_bus":
        circuit = tool_bus_circuit
    else:
        return 0

    state = circuit.state
    if state == "closed":
        return 0
    elif state == "open":
        return 1
    else:
        return 2
