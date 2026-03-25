"""熔断器实现 (P-02)

【核心概念】熔断器模式 (Circuit Breaker Pattern)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

熔断器是微服务架构中的核心容错模式，用于防止级联故障。

【问题场景】
当某个下游服务（如 LLM API）出现故障时：
1. 请求持续失败，占用连接池和线程
2. 失败请求堆积，导致上游服务也崩溃
3. 故障在服务链中传播，引发雪崩效应

【熔断器解决方案】
┌─────────────────────────────────────────────────────────────────────────┐
│                          熔断器状态机                                    │
│                                                                         │
│   ┌─────────┐    失败次数 ≥ 阈值    ┌─────────┐                         │
│   │ CLOSED  │ ───────────────────► │  OPEN   │                         │
│   │ (正常)  │                       │ (熔断)  │                         │
│   └─────────┘                       └─────────┘                         │
│        ▲                                 │                              │
│        │                                 │ 超时后                        │
│   成功次数 │                                 ▼                              │
│    ≥ 阈值  │                          ┌───────────┐                     │
│        │                          │ HALF_OPEN │                     │
│        └───────────────────────── │  (半开)   │                     │
│                    成功            └───────────┘                     │
│                                        │                              │
│                                  失败  │ 成功                         │
│                                        ▼                              │
│                                   回到 OPEN    回到 CLOSED             │
└─────────────────────────────────────────────────────────────────────────┘

【三种状态】
1. CLOSED（正常）：请求正常通过，统计失败次数
2. OPEN（熔断）：快速失败，直接抛异常，不发起实际请求
3. HALF_OPEN（半开）：允许少量请求通过，测试服务是否恢复

【技术选型】为什么自实现而非使用库？
┌─────────────────────────────────────────────────────────────────────────┐
│  方案              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  pybreaker        │  成熟稳定                 │  功能固定、定制难      │
│  tenacity         │  重试+熔断一体化          │  熔断功能较弱          │
│  ✓ 自实现          │  完全可控、符合业务需求    │  需要自测              │
└─────────────────────────────────────────────────────────────────────────┘

【生产调优建议】
- failure_threshold: 根据服务 SLA 设置，一般 5-10 次失败后熔断
- timeout_seconds: 给服务恢复时间，一般 30-60 秒
- half_open_max_calls: 半开状态最多允许 3 个探测请求
- 监控指标：熔断次数、半开转换次数、平均恢复时间

【参考】
- Martin Fowler 文章: https://martinfowler.com/bliki/CircuitBreaker.html
- Netflix Hystrix: https://github.com/Netflix/Hystrix/wiki/How-it-Works
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态枚举

    【状态说明】
    - CLOSED: 熔断器关闭（正常状态），请求正常通过
    - OPEN: 熔断器打开（熔断状态），请求快速失败
    - HALF_OPEN: 半开状态，允许少量探测请求

    命名由来：类似电路熔断器
    - CLOSED = 电路接通 = 请求可以通过
    - OPEN = 电路断开 = 请求被阻断
    """
    CLOSED = "closed"  # 正常
    OPEN = "open"      # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitStats:
    """熔断器统计数据

    【统计指标】
    - failures: 连续失败次数（成功后重置）
    - successes: 半开状态下的成功次数
    - last_failure_time: 最后一次失败时间（用于超时判断）
    """
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0


class CircuitBreaker:
    """熔断器 - 完整状态机实现

    【设计模式】State Pattern + Observer

    状态转换规则：
    ┌─────────────────────────────────────────────────────────────────────┐
    │  当前状态    │  触发条件                  │  目标状态               │
    ├──────────────┼────────────────────────────┼────────────────────────┤
    │  CLOSED      │  failures >= threshold     │  OPEN                  │
    │  OPEN        │  timeout 后首次请求        │  HALF_OPEN             │
    │  HALF_OPEN   │  成功次数 >= success_thres │  CLOSED                │
    │  HALF_OPEN   │  任何失败                  │  OPEN                  │
    └─────────────────────────────────────────────────────────────────────┘

    【使用示例】
        # 创建熔断器
        cb = CircuitBreaker(
            name="llm_provider",
            failure_threshold=5,   # 5 次失败后熔断
            timeout_seconds=30,    # 30 秒后尝试恢复
        )

        # 使用熔断器保护调用
        try:
            result = await cb.call(lambda: call_llm_api())
        except CircuitBreakerOpenError:
            # 熔断状态，快速失败
            return fallback_response()

    【线程安全说明】
    当前实现为单线程设计，多线程环境需要加锁。
    异步环境中建议每个任务使用独立实例或使用 asyncio.Lock。
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 10,
        success_threshold: int = 5,
        timeout_seconds: int = 30,
        half_open_max_calls: int = 3,
    ):
        """初始化熔断器

        Args:
            name: 熔断器名称，用于日志标识（如 "llm_qwen", "tool_bus"）
            failure_threshold: 失败次数阈值，达到后触发熔断（默认 10）
            success_threshold: 半开状态下成功次数阈值，达到后恢复正常（默认 5）
            timeout_seconds: 熔断超时时间，多久后尝试恢复（默认 30 秒）
            half_open_max_calls: 半开状态最大探测请求数（默认 3）

        调优建议：
        - 高可靠服务（如自建数据库）：failure_threshold=3, timeout=10
        - 外部 API（如 LLM）：failure_threshold=10, timeout=60
        - 关键服务：设置较小阈值，快速熔断保护系统
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """获取当前状态（自动处理超时转换）

        【惰性状态转换】
        OPEN → HALF_OPEN 的转换不使用定时器，
        而在每次检查状态时判断是否超时。

        原因：
        - 避免定时器线程管理复杂性
        - 减少资源占用
        - 与异步调用模式兼容

        Returns:
            当前熔断器状态
        """
        if self._state == CircuitState.OPEN:
            # 检查是否超时，自动转换到半开
            if time.time() - self._stats.last_failure_time >= self.timeout_seconds:
                self._transition_to_half_open()
        return self._state

    def _transition_to_open(self) -> None:
        """转换到熔断状态

        触发条件：失败次数达到阈值
        效果：后续请求快速失败，不发起实际调用
        """
        if self._state != CircuitState.OPEN:
            logger.warning("Circuit breaker OPENED", name=self.name)
            self._state = CircuitState.OPEN
            self._stats.last_failure_time = time.time()

    def _transition_to_half_open(self) -> None:
        """转换到半开状态

        触发条件：熔断超时后首次状态检查
        效果：允许少量探测请求通过，测试服务恢复
        """
        if self._state != CircuitState.HALF_OPEN:
            logger.info("Circuit breaker HALF_OPEN", name=self.name)
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """转换到正常状态

        触发条件：半开状态下成功次数达到阈值
        效果：恢复正常请求处理，重置统计
        """
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit breaker CLOSED", name=self.name)
            self._state = CircuitState.CLOSED
            self._stats = CircuitStats()

    def record_success(self) -> None:
        """记录成功调用

        【成功处理】
        - CLOSED 状态：只统计，不改变状态
        - HALF_OPEN 状态：成功计数，达到阈值后恢复 CLOSED
        """
        self._stats.successes += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.success_threshold:
                self._transition_to_closed()

    def record_failure(self) -> None:
        """记录失败调用

        【失败处理】
        - HALF_OPEN 状态：立即回到 OPEN（服务未恢复）
        - CLOSED 状态：累计失败，达到阈值后熔断
        """
        self._stats.failures += 1
        self._stats.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            if self._stats.failures >= self.failure_threshold:
                self._transition_to_open()

    def is_available(self) -> bool:
        """检查熔断器是否可用

        【可用性判断】
        - CLOSED：完全可用
        - HALF_OPEN：部分可用（限制请求数）
        - OPEN：不可用（快速失败）

        Returns:
            True 表示可以发起请求，False 表示应该快速失败
        """
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            # 半开状态限制探测请求数量
            return self._half_open_calls < self.half_open_max_calls
        return False  # OPEN

    async def call(self, func: Callable[[], T]) -> T:
        """执行带熔断保护的异步调用

        【使用模式】
        这是熔断器的主要使用入口，封装调用流程：

        1. 检查熔断状态（is_available）
        2. 执行实际调用（func）
        3. 根据结果更新状态（record_success/failure）
        4. 熔断时抛出 CircuitBreakerOpenError

        Args:
            func: 异步调用函数，返回 T 类型结果

        Returns:
            调用函数的结果

        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出

        使用示例：
            breaker = CircuitBreaker("llm_api")

            try:
                result = await breaker.call(lambda: call_llm(prompt))
            except CircuitBreakerOpenError:
                # 熔断状态，返回降级响应
                return fallback_response()
            except Exception as e:
                # 其他异常（如网络错误），正常处理
                raise
        """
        if not self.is_available():
            raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常

    【异常含义】
    当熔断器处于 OPEN 状态时抛出，
    表示下游服务故障，应该快速失败。

    处理建议：
    - 返回降级响应（如缓存数据、默认值）
    - 记录日志，监控熔断次数
    - 不重试（熔断状态下重试无效）
    """
    pass
