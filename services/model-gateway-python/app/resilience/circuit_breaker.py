"""熔断器实现 (P-02)"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常
    OPEN = "open"      # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitStats:
    """熔断器统计"""
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0


class CircuitBreaker:
    """熔断器 - 完整状态机实现

    状态转换：
    CLOSED --[失败次数达到阈值]--> OPEN
    OPEN --[超时时间后]--> HALF_OPEN
    HALF_OPEN --[成功]--> CLOSED
    HALF_OPEN --[失败]--> OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 10,
        success_threshold: int = 5,
        timeout_seconds: int = 30,
        half_open_max_calls: int = 3,
    ):
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
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._stats.last_failure_time >= self.timeout_seconds:
                self._transition_to_half_open()
        return self._state

    def _transition_to_open(self) -> None:
        """转换到熔断状态"""
        if self._state != CircuitState.OPEN:
            logger.warning("Circuit breaker OPENED", name=self.name)
            self._state = CircuitState.OPEN
            self._stats.last_failure_time = time.time()

    def _transition_to_half_open(self) -> None:
        """转换到半开状态"""
        if self._state != CircuitState.HALF_OPEN:
            logger.info("Circuit breaker HALF_OPEN", name=self.name)
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """转换到关闭状态"""
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit breaker CLOSED", name=self.name)
            self._state = CircuitState.CLOSED
            self._stats = CircuitStats()

    def record_success(self) -> None:
        """记录成功"""
        self._stats.successes += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.success_threshold:
                self._transition_to_closed()

    def record_failure(self) -> None:
        """记录失败"""
        self._stats.failures += 1
        self._stats.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            if self._stats.failures >= self.failure_threshold:
                self._transition_to_open()

    def is_available(self) -> bool:
        """检查是否可用"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False  # OPEN

    async def call(self, func: Callable[[], T]) -> T:
        """执行带熔断保护的调用"""
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
    """熔断器打开异常"""
    pass
