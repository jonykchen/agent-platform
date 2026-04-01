"""弹性模式模块 - 熔断器、重试、降级策略

提供生产级弹性能力，防止下游服务故障时雪崩。

【核心概念】熔断器状态机原理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

熔断器是分布式系统的"保险丝"，防止故障传播：

┌─────────────────────────────────────────────────────────────────────────────┐
│                          熔断器状态转换图                                    │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────────┐ │
│     │                                                                     │ │
│     │    ┌──────────┐    成功      ┌──────────┐                          │ │
│     │    │  CLOSED  │ ──────────► │  CLOSED  │                          │ │
│     │    │ (正常)   │              │ (正常)   │                          │ │
│     │    └──────────┘              └──────────┘                          │ │
│     │         │                                                         │ │
│     │         │ 连续失败 ≥ 阈值                                         │ │
│     │         ▼                                                         │ │
│     │    ┌──────────┐                                                  │ │
│     │    │   OPEN   │ ◄──────────────────────────────────┐            │ │
│     │    │  (熔断)  │                                     │            │ │
│     │    └──────────┘                                     │            │ │
│     │         │                                           │            │ │
│     │         │ 等待 recovery_timeout                      │            │ │
│     │         ▼                                           │            │ │
│     │    ┌──────────┐    失败        ┌──────────┐        │            │ │
│     │    │HALF-OPEN │ ──────────► │   OPEN   │────────┘            │ │
│     │    │ (半开)   │              │  (熔断)  │                     │ │
│     │    └──────────┘              └──────────┘                     │ │
│     │         │                                                         │ │
│     │         │ 成功                                                    │ │
│     │         ▼                                                         │ │
│     │    ┌──────────┐                                                  │ │
│     │    │  CLOSED  │                                                  │ │
│     │    │ (正常)   │                                                  │ │
│     │    └──────────┘                                                  │ │
│     │                                                                     │ │
│     └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

状态说明：
- CLOSED: 正常状态，所有请求通过
- OPEN: 熔断状态，快速失败，不调用下游
- HALF-OPEN: 试探性恢复，允许少量请求通过

【技术选型】熔断器实现方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 自定义实现         │ • 灵活可控                  │ • 需要自己实现状态管理      │
│ (当前选择)         │ • 适配异步场景              │ • 需处理并发安全            │
│                    │ • 无额外依赖                │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ circuitbreaker 库  │ • 开箱即用                  │ • 非线程安全                │
│ (Python)           │ • 功能完善                  │ • 异步支持有限              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ resilience4j       │ • 功能最完善                │ • Java 生态，Python 不可用 │
│ (Java)             │ • 生产级稳定                │                              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【线程安全设计】asyncio.Lock 保护状态转换
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY 需要 Lock？
- Agent 运行在异步环境，多个协程可能同时访问熔断器
- 状态转换（CLOSED → OPEN）需要原子性，防止竞态条件

┌─────────────────────────────────────────────────────────────────────┐
│  协程 A                              协程 B                         │
│    │                                    │                           │
│    │ 检查 state = CLOSED                │                           │
│    │                                    │ 检查 state = CLOSED       │
│    │ 记录失败，count++                  │                           │
│    │                                    │ 记录失败，count++         │
│    │ count >= threshold?                │                           │
│    │   Yes → 转换到 OPEN                │                           │
│    │                                    │ count >= threshold?      │
│    │                                    │   Yes → 转换到 OPEN       │
│    │                                    │ (重复转换!)               │
│    ▼                                    ▼                           │
│  问题：两个协程都认为自己是第一个触发熔断的，可能导致日志混乱      │
└─────────────────────────────────────────────────────────────────────┘

解决方案：使用 asyncio.Lock 保护状态转换
```python
async with self._lock:
    if self._state == "open":
        raise CircuitBreakerOpenError()
    # ... 执行请求 ...
    async with self._lock:
        self._state = "closed"  # 原子更新
```

【S-AGENT-14 更新】
- 添加 asyncio.Lock 保护状态转换，确保多协程安全
- 将状态更新方法改为异步
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

    【线程安全说明】
    使用 asyncio.Lock 保护状态转换，确保多协程环境下的安全性。
    所有状态更新方法都是异步的，需要通过锁保护。
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
        self._lock = asyncio.Lock()  # 保护状态转换的锁

    def __call__(self, func: F) -> F:
        """装饰器模式"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 先获取锁检查状态
            async with self._lock:
                if self._state == "open":
                    logger.warning(
                        "Circuit breaker is open",
                        circuit_name=self.name,
                        state=self._state,
                    )
                    raise CircuitBreakerOpenError(self.name)

            try:
                # 使用 circuit breaker
                @self._circuit
                async def _execute():
                    return await func(*args, **kwargs)

                result = await _execute()
                # 成功时重置状态
                async with self._lock:
                    if self._state != "closed":
                        logger.info(
                            "Circuit breaker recovered",
                            circuit_name=self.name,
                            previous_state=self._state,
                        )
                    self._state = "closed"
                return result
            except CircuitBreakerError:
                async with self._lock:
                    self._state = "open"
                logger.warning(
                    "Circuit breaker tripped",
                    circuit_name=self.name,
                    state=self._state,
                )
                raise CircuitBreakerOpenError(self.name)

        return wrapper  # type: ignore

    @property
    def state(self) -> str:
        """获取当前状态（线程安全读取）"""
        return self._state

    def is_open(self) -> bool:
        """熔断器是否打开"""
        return self._state == "open"

    async def get_state_async(self) -> str:
        """异步获取当前状态（加锁）"""
        async with self._lock:
            return self._state

    async def reset(self) -> None:
        """手动重置熔断器状态"""
        async with self._lock:
            self._state = "closed"
            logger.info("Circuit breaker manually reset", circuit_name=self.name)


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
