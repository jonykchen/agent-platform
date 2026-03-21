"""测试熔断器"""

import pytest
import asyncio
from unittest.mock import AsyncMock

from app.resilience.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError


@pytest.fixture
def circuit_breaker():
    """创建熔断器实例"""
    return CircuitBreaker(
        name="test-breaker",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=1,
        half_open_max_calls=2,
    )


class TestCircuitBreaker:
    """熔断器测试"""

    def test_initial_state(self, circuit_breaker):
        """测试初始状态"""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._stats.failures == 0
        assert circuit_breaker._stats.successes == 0

    def test_record_failure(self, circuit_breaker):
        """测试记录失败"""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker._stats.failures == 3
        assert circuit_breaker.state == CircuitState.OPEN

    def test_record_success(self, circuit_breaker):
        """测试记录成功"""
        for _ in range(5):
            circuit_breaker.record_success()

        assert circuit_breaker._stats.successes == 5
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_open_to_half_open(self, circuit_breaker):
        """测试从 OPEN 到 HALF_OPEN"""
        # 触发熔断
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

        # 等待超时时间
        import time
        time.sleep(1.1)

        # 状态应该变为 HALF_OPEN
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed(self, circuit_breaker):
        """测试从 HALF_OPEN 到 CLOSED"""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 0

        # 成功次数达到阈值
        for _ in range(2):
            circuit_breaker.record_success()

        assert circuit_breaker.state == CircuitState.CLOSED

    def test_half_open_to_open(self, circuit_breaker):
        """测试从 HALF_OPEN 到 OPEN"""
        circuit_breaker._state = CircuitState.HALF_OPEN

        # 失败后回到 OPEN
        circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

    def test_is_available_closed(self, circuit_breaker):
        """测试 CLOSED 状态下可用"""
        assert circuit_breaker.is_available() is True

    def test_is_available_open(self, circuit_breaker):
        """测试 OPEN 状态下不可用"""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.is_available() is False

    def test_is_available_half_open(self, circuit_breaker):
        """测试 HALF_OPEN 状态下的可用性"""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 0

        assert circuit_breaker.is_available() is True

        # 达到最大调用次数后不可用
        circuit_breaker._half_open_calls = 2
        assert circuit_breaker.is_available() is False

    @pytest.mark.asyncio
    async def test_call_success(self, circuit_breaker):
        """测试成功调用"""
        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker._stats.successes == 1

    @pytest.mark.asyncio
    async def test_call_failure(self, circuit_breaker):
        """测试失败调用"""
        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await circuit_breaker.call(fail_func)

        assert circuit_breaker._stats.failures == 1

    @pytest.mark.asyncio
    async def test_call_when_open(self, circuit_breaker):
        """测试 OPEN 状态下调用"""
        # 触发熔断
        for _ in range(3):
            circuit_breaker.record_failure()

        async def func():
            return "result"

        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(func)

    def test_reset(self, circuit_breaker):
        """测试重置熔断器"""
        # 先触发一些失败
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

        # 手动重置到 CLOSED
        circuit_breaker._transition_to_closed()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._stats.failures == 0
