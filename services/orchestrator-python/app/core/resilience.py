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

【技术选型】重试库对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 功能完整度    │ 代码复杂度    │ 可维护性      │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ 手写重试循环       │ 低           │ 高（重复代码）│ 低           │
│ ✓ tenacity 库     │ 高           │ 低（装饰器）  │ 高           │
│ backoff 库         │ 中           │ 低            │ 中           │
│ retrying 库        │ 中           │ 低            │ 低（已停止维护）│
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择 tenacity 的原因：
1. 功能完整：支持指数退避、抖动、条件重试、回调等
2. API 优雅：使用装饰器，不侵入业务代码
3. 社区活跃：GitHub 5k+ stars，持续维护
4. 文档完善：https://tenacity.readthedocs.io/

【最佳实践】重试参数推荐（附依据）
┌────────────────────┬───────────────┬─────────────────────────────────┐
│ 参数               │ 推荐值        │ 依据                            │
├────────────────────┼───────────────┼─────────────────────────────────┤
│ max_attempts       │ 3             │ 超过 3 次通常是真实故障         │
│ min_wait           │ 1s            │ 给服务恢复时间                  │
│ max_wait           │ 10s           │ 避免用户等待过久                │
│ 指数退避基数        │ 2             │ 1s → 2s → 4s，渐进式            │
│ 抖动（Jitter）     │ ±50%          │ 分散重试时间，避免惊群效应      │
└────────────────────┴───────────────┴─────────────────────────────────┘

【设计原则】为什么"先重试，后熔断"？
┌────────────────────┬─────────────────────────────────────────────────┐
│ 顺序               │ 原因                                            │
├────────────────────┼─────────────────────────────────────────────────┤
│ 请求 → 重试（局部） │ 重试恢复临时故障（网络抖动、超时）              │
│ → 熔断（全局）     │ 熔断隔离持续故障（服务宕机）                    │
└────────────────────┴─────────────────────────────────────────────────┘

理由：
1. 临时故障概率 > 持续故障，先重试可以快速恢复
2. 避免熔断器频繁切换状态
3. 重试失败后再熔断，给下游服务喘息时间

【风险与缓解】
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 风险               │ 影响                        │ 缓解措施                    │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 重试风暴           │ 大量请求同时重试            │ 添加抖动（Jitter），分散重试时间│
│ 重试加剧故障       │ 下游服务无法恢复            │ 熔断器限制重试总量          │
│ 幂等性要求         │ 重试可能导致重复操作        │ 只对幂等操作重试            │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【演进历史】
- v1.0: 手写重试循环，代码重复，难以维护
- v2.0: 使用 tenacity 库，统一重试策略
- v2.1: 添加熔断器集成（当前版本）

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

    【熔断器参数说明】
    ┌────────────────────┬─────────────────────────────────────────────────┐
    │ 参数               │ 说明                                            │
    ├────────────────────┼─────────────────────────────────────────────────┤
    │ failure_threshold  │ 连续失败次数阈值，超过后触发熔断（默认 5 次）   │
    │ recovery_timeout   │ 熔断后等待时间，超过后进入半开状态（默认 30s）│
    │ name               │ 熔断器名称，用于日志和监控标识                  │
    └────────────────────┴─────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        name: str = "model_gateway",
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
    ):
        """初始化熔断器

        Args:
            name: 熔断器名称，用于日志标识
            failure_threshold: 失败阈值，超过后触发熔断
            recovery_timeout: 恢复超时，熔断后等待多久尝试恢复
        """
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
        """装饰器模式

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 获取锁检查状态                                                   │
        │     │                                                               │
        │     ├─ state == OPEN → 抛出 CircuitBreakerOpenError                │
        │     │                                                               │
        │  2. 执行请求（释放锁后）                                            │
        │     │                                                               │
        │     ├─ 成功 → 获取锁，重置状态为 CLOSED                            │
        │     │                                                               │
        │     └─ 失败（CircuitBreakerError）→ 获取锁，设置状态为 OPEN        │
        │                                                                     │
        │  3. 返回结果或抛出异常                                              │
        └─────────────────────────────────────────────────────────────────────┘
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 先获取锁检查状态
            async with self._lock:
                if self._state == "open":
                    logger.warning(
                        "Circuit breaker is open, rejecting request",
                        circuit_name=self.name,
                        state=self._state,
                        failure_threshold=self.failure_threshold,
                        recovery_timeout=self.recovery_timeout,
                        hint="下游服务持续不可用，等待恢复超时后重试",
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
                            "Circuit breaker recovered, state changed to CLOSED",
                            circuit_name=self.name,
                            previous_state=self._state,
                            current_state="closed",
                            message="下游服务恢复正常，熔断器关闭",
                        )
                    self._state = "closed"
                return result
            except CircuitBreakerError:
                async with self._lock:
                    previous_state = self._state
                    self._state = "open"
                    logger.warning(
                        "Circuit breaker tripped, state changed to OPEN",
                        circuit_name=self.name,
                        previous_state=previous_state,
                        current_state="open",
                        failure_threshold=self.failure_threshold,
                        recovery_timeout=self.recovery_timeout,
                        message=f"连续失败超过阈值 {self.failure_threshold} 次，熔断器打开",
                        hint=f"等待 {self.recovery_timeout} 秒后尝试恢复",
                    )
                raise CircuitBreakerOpenError(self.name)

        return wrapper  # type: ignore

    @property
    def state(self) -> str:
        """获取当前状态（线程安全读取）

        【状态说明】
        - closed: 正常状态，所有请求通过
        - open: 熔断状态，快速失败
        - half-open: 试探性恢复，允许少量请求
        """
        return self._state

    def is_open(self) -> bool:
        """熔断器是否打开"""
        return self._state == "open"

    async def get_state_async(self) -> str:
        """异步获取当前状态（加锁）

        使用场景：需要确保状态一致性的监控场景
        """
        async with self._lock:
            return self._state

    async def reset(self) -> None:
        """手动重置熔断器状态

        【使用场景】
        - 运维手动恢复服务后，主动重置熔断器
        - 测试环境中重置状态
        """
        async with self._lock:
            previous_state = self._state
            self._state = "closed"
            logger.info(
                "Circuit breaker manually reset",
                circuit_name=self.name,
                previous_state=previous_state,
                current_state="closed",
                operator="manual_reset",
            )


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常

    【异常含义】
    当熔断器处于 OPEN 状态时抛出，表示下游服务持续不可用。

    【处理建议】
    1. 返回降级响应（推荐）
    2. 等待 recovery_timeout 后重试
    3. 告警通知运维人员
    """

    def __init__(self, circuit_name: str):
        self.circuit_name = circuit_name
        super().__init__(f"Circuit breaker '{circuit_name}' is open")


class AsyncRetryPolicy:
    """异步重试策略

    支持指数退避重试，适用于网络瞬态故障。

    【重试策略参数说明】
    ┌────────────────────┬─────────────────────────────────────────────────┐
    │ 参数               │ 说明                                            │
    ├────────────────────┼─────────────────────────────────────────────────┤
    │ max_attempts       │ 最大重试次数（含首次），默认 3 次              │
    │ min_wait           │ 最小等待时间，指数退避的起点（默认 1s）        │
    │ max_wait           │ 最大等待时间，指数退避的上限（默认 10s）       │
    │ retry_exceptions   │ 触发重试的异常类型（默认网络错误和超时）       │
    └────────────────────┴─────────────────────────────────────────────────┘

    【指数退避算法】
    等待时间 = min(max_wait, base * (2 ^ attempt))

    示例（min_wait=1, max_wait=10）：
    - 第 1 次重试：1s
    - 第 2 次重试：2s
    - 第 3 次重试：4s（如果 max_attempts > 3）

    【为什么使用指数退避？】
    1. 避免重试风暴：大量请求同时重试会加剧故障
    2. 给服务恢复时间：逐渐增加间隔
    3. 提升用户体验：快速重试小故障，慢速重试大故障
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        retry_exceptions: tuple[type[Exception], ...] | None = None,
    ):
        """初始化重试策略

        Args:
            max_attempts: 最大重试次数
            min_wait: 最小等待时间（秒）
            max_wait: 最大等待时间（秒）
            retry_exceptions: 触发重试的异常类型元组
        """
        self.max_attempts = max_attempts or config.retry_max_attempts
        self.min_wait = min_wait or config.retry_min_wait
        self.max_wait = max_wait or config.retry_max_wait
        self.retry_exceptions = retry_exceptions or (httpx.NetworkError, httpx.TimeoutException)

    def __call__(self, func: F) -> F:
        """装饰器模式

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  for attempt in 1..max_attempts:                                    │
        │      │                                                              │
        │      ├─ 执行请求                                                    │
        │      │                                                              │
        │      ├─ 成功 → 返回结果                                             │
        │      │                                                              │
        │      └─ 失败且异常类型匹配 →                                        │
        │           │                                                        │
        │           ├─ 记录重试日志（含等待时间）                             │
        │           │                                                        │
        │           └─ 等待指数退避时间后继续                                │
        │                                                                     │
        │  所有重试失败 → 抛出 RetryError                                    │
        └─────────────────────────────────────────────────────────────────────┘
        """

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

            attempt_number = 0
            last_exception = None

            async for attempt in retryer:
                attempt_number += 1
                with attempt:
                    try:
                        result = await func(*args, **kwargs)
                        # 成功时记录（如果有重试）
                        if attempt_number > 1:
                            logger.info(
                                "Retry succeeded after previous failures",
                                attempt_number=attempt_number,
                                function_name=func.__name__,
                                total_attempts=attempt_number,
                            )
                        return result
                    except self.retry_exceptions as e:
                        last_exception = e
                        # 计算下次等待时间
                        wait_time = min(
                            self.max_wait,
                            self.min_wait * (2 ** (attempt_number - 1))
                        )
                        logger.warning(
                            "Request failed, will retry",
                            attempt_number=attempt_number,
                            max_attempts=self.max_attempts,
                            wait_seconds=wait_time,
                            error_type=type(e).__name__,
                            error_message=str(e),
                            function_name=func.__name__,
                            retry_exceptions=[exc.__name__ for exc in self.retry_exceptions],
                            hint=f"等待 {wait_time:.1f}s 后进行第 {attempt_number + 1} 次重试",
                        )
                        raise

            # 不应该到达这里
            raise RuntimeError(
                f"Retry policy exhausted without result. "
                f"Last error: {last_exception}"
            )

        return wrapper  # type: ignore


def with_retry_and_circuit(
    circuit_breaker: ModelGatewayCircuitBreaker,
    retry_policy: AsyncRetryPolicy | None = None,
):
    """组合熔断器和重试的装饰器

    【执行顺序】先重试，后熔断（由外到内）

    ┌─────────────────────────────────────────────────────────────────────┐
    │                         请求进入                                    │
    │                              │                                      │
    │                              ▼                                      │
    │  ┌───────────────────────────────────────────────────────────────┐  │
    │  │  熔断器检查（外层）                                            │  │
    │  │    │                                                          │  │
    │  │    ├─ OPEN → 快速失败                                          │  │
    │  │    │                                                          │  │
    │  │    └─ CLOSED/HALF-OPEN → 继续                                 │  │
    │  └───────────────────────────────────────────────────────────────┘  │
    │                              │                                      │
    │                              ▼                                      │
    │  ┌───────────────────────────────────────────────────────────────┐  │
    │  │  重试策略（内层）                                              │  │
    │  │    │                                                          │  │
    │  │    ├─ 尝试 1 → 失败 → 等待退避时间                            │  │
    │  │    │                                                          │  │
    │  │    ├─ 尝试 2 → 失败 → 等待退避时间                            │  │
    │  │    │                                                          │  │
    │  │    └─ 尝试 3 → 成功/失败                                       │  │
    │  └───────────────────────────────────────────────────────────────┘  │
    │                              │                                      │
    │                              ▼                                      │
    │  ┌───────────────────────────────────────────────────────────────┐  │
    │  │  熔断器状态更新                                                │  │
    │  │    │                                                          │  │
    │  │    ├─ 成功 → 重置为 CLOSED                                    │  │
    │  │    │                                                          │  │
    │  │    └─ 失败 → 累计计数，可能触发 OPEN                          │  │
    │  └───────────────────────────────────────────────────────────────┘  │
    │                              │                                      │
    │                              ▼                                      │
    │                         返回结果                                    │
    └─────────────────────────────────────────────────────────────────────┘

    【为什么是"先重试，后熔断"？】
    装饰器执行顺序：外层先执行，内层后执行
    - 外层：熔断器（先检查状态）
    - 内层：重试（在允许的情况下重试）

    实际效果：
    1. 熔断器检查状态，OPEN 则直接失败
    2. 熔断器允许请求，进入重试逻辑
    3. 重试执行请求，失败则重试
    4. 重试结果返回给熔断器，更新状态

    【关键设计】
    - 熔断器在外层：快速失败，避免无效重试
    - 重试在内层：在允许的情况下恢复临时故障
    - 状态更新：所有重试都失败才计入熔断器失败计数

    Args:
        circuit_breaker: 熔断器实例
        retry_policy: 重试策略，默认使用 AsyncRetryPolicy()
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

    当主逻辑失败时，执行备用方案，保证服务可用性。

    【触发条件】
    ┌─────────────────────────────────────────────────────────────────────┐
    │  任何未捕获的异常都会触发降级                                       │
    │  包括：                                                            │
    │  - 网络错误（httpx.NetworkError）                                  │
    │  - 超时错误（httpx.TimeoutException）                              │
    │  - 熔断器打开（CircuitBreakerOpenError）                          │
    │  - 业务异常（任何 Exception 子类）                                 │
    └─────────────────────────────────────────────────────────────────────┘

    【降级函数设计约束】
    ┌────────────────────┬─────────────────────────────────────────────────┐
    │ 约束               │ 说明                                            │
    ├────────────────────┼─────────────────────────────────────────────────┤
    │ 不能抛异常         │ 降级函数必须返回有效结果或 None                │
    │ 签名一致           │ 参数必须与主函数相同                            │
    │ 返回类型兼容       │ 返回值必须与主函数返回类型兼容                  │
    │ 快速执行           │ 降级函数应该快速返回，避免阻塞                  │
    │ 无状态依赖         │ 不应依赖外部状态（如数据库），可能也已不可用   │
    └────────────────────┴─────────────────────────────────────────────────┘

    【降级响应格式建议】
    ```python
    {
        "success": False,
        "fallback": True,
        "message": "服务暂时不可用，已返回缓存数据",
        "data": {...}  # 缓存数据或默认值
    }
    ```

    【典型降级场景】
    ┌────────────────────┬─────────────────────────────────────────────────┐
    │ 场景               │ 降级方案                                        │
    ├────────────────────┼─────────────────────────────────────────────────┤
    │ AI 模型调用失败    │ 返回预设回复或规则引擎结果                      │
    │ 数据库查询失败     │ 返回缓存数据或空列表                            │
    │ 外部 API 调用失败  │ 返回本地缓存或默认配置                          │
    │ 搜索服务不可用     │ 返回简化搜索结果或热门推荐                      │
    └────────────────────┴─────────────────────────────────────────────────┘
    """

    def __init__(self, fallback_func: Callable[..., Any]):
        """初始化降级策略

        Args:
            fallback_func: 降级函数，必须与被装饰函数有相同的参数签名

        【注意事项】
        - fallback_func 必须是可调用对象
        - 支持同步和异步函数
        - 建议在降级函数中添加日志记录
        """
        self.fallback_func = fallback_func

    def __call__(self, func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 记录详细的降级日志
                logger.warning(
                    "Primary function failed, executing fallback",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    function_name=func.__name__,
                    fallback_func=self.fallback_func.__name__,
                    # 脱敏的请求参数（避免泄露敏感信息）
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys()),
                    hint="降级函数被执行，请检查主服务状态",
                )
                # 执行降级函数
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

    【使用场景】
    - Prometheus 指标导出
    - 健康检查端点
    - 监控面板展示

    Returns:
        0: closed (正常)
        1: open (熔断)
        2: half-open (半开)

    【监控告警建议】
    ┌────────────────────┬─────────────────────────────────────────────────┐
    │ 状态               │ 告警级别                                        │
    ├────────────────────┼─────────────────────────────────────────────────┤
    │ CLOSED (0)         │ 无需告警                                        │
    │ OPEN (1)           │ 严重 - 服务不可用                               │
    │ HALF-OPEN (2)      │ 警告 - 服务正在恢复                             │
    │ 持续 OPEN > 5min   │ 严重 - 需要人工介入                             │
    └────────────────────┴─────────────────────────────────────────────────┘
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
