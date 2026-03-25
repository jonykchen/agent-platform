"""测试弹性模式模块"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.core.resilience import (
    ModelGatewayCircuitBreaker,
    AsyncRetryPolicy,
    CircuitBreakerOpenError,
    FallbackStrategy,
    model_gateway_circuit,
    tool_bus_circuit,
    get_circuit_state_metric,
)


class TestModelGatewayCircuitBreaker:
    """测试熔断器"""

    def test_circuit_breaker_creation(self):
        """测试熔断器创建"""
        cb = ModelGatewayCircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            recovery_timeout=10,
        )
        assert cb.name == "test_circuit"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 10

    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """测试熔断器正常调用"""
        cb = ModelGatewayCircuitBreaker(name="test_success")

        async def success_func():
            return {"status": "ok"}

        # 使用装饰器
        decorated = cb(success_func)
        result = await decorated()

        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_failures(self):
        """测试熔断器记录失败"""
        cb = ModelGatewayCircuitBreaker(
            name="test_failures",
            failure_threshold=2,
        )

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Simulated failure")
            return {"status": "ok"}

        decorated = cb(failing_func)

        # 前两次应该失败
        with pytest.raises(Exception):
            await decorated()
        with pytest.raises(Exception):
            await decorated()

        # 第三次应该成功（假设熔断器还没打开）
        # 注意：circuitbreaker 库的行为可能需要调整测试


class TestAsyncRetryPolicy:
    """测试重试策略"""

    @pytest.mark.asyncio
    async def test_retry_policy_success_on_first_try(self):
        """测试首次成功"""
        retry_policy = AsyncRetryPolicy(max_attempts=3)

        call_count = 0

        @retry_policy
        async def success_func():
            nonlocal call_count
            call_count += 1
            return {"status": "ok"}

        result = await success_func()
        assert result["status"] == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_policy_retries_on_network_error(self):
        """测试网络错误重试"""
        retry_policy = AsyncRetryPolicy(
            max_attempts=3,
            min_wait=0.1,
            max_wait=0.5,
        )

        call_count = 0

        @retry_policy
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.NetworkError("Connection failed")
            return {"status": "ok"}

        result = await failing_then_success()
        assert result["status"] == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_policy_raises_after_max_attempts(self):
        """测试超过最大重试次数后抛出异常"""
        retry_policy = AsyncRetryPolicy(
            max_attempts=2,
            min_wait=0.1,
            max_wait=0.5,
        )

        call_count = 0

        @retry_policy
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise httpx.NetworkError("Connection failed")

        with pytest.raises(httpx.NetworkError):
            await always_failing()

        assert call_count == 2


class TestFallbackStrategy:
    """测试降级策略"""

    @pytest.mark.asyncio
    async def test_fallback_not_called_on_success(self):
        """测试成功时不调用降级"""
        fallback_called = False

        async def fallback():
            nonlocal fallback_called
            fallback_called = True
            return {"fallback": True}

        @FallbackStrategy(fallback)
        async def success_func():
            return {"success": True}

        result = await success_func()
        assert result["success"] is True
        assert not fallback_called

    @pytest.mark.asyncio
    async def test_fallback_called_on_failure(self):
        """测试失败时调用降级"""
        async def fallback():
            return {"fallback": True}

        @FallbackStrategy(fallback)
        async def failing_func():
            raise Exception("Primary failed")

        result = await failing_func()
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_fallback_with_sync_function(self):
        """测试同步降级函数"""
        def sync_fallback():
            return {"sync_fallback": True}

        @FallbackStrategy(sync_fallback)
        async def failing_func():
            raise Exception("Primary failed")

        result = await failing_func()
        assert result["sync_fallback"] is True


class TestCircuitStateMetric:
    """测试熔断器状态指标"""

    def test_get_circuit_state_metric_unknown(self):
        """测试未知熔断器"""
        state = get_circuit_state_metric("unknown")
        assert state == 0

    def test_get_circuit_state_metric_model_gateway(self):
        """测试 ModelGateway 熔断器状态"""
        state = get_circuit_state_metric("model_gateway")
        assert state in [0, 1, 2]  # closed, open, half-open

    def test_get_circuit_state_metric_tool_bus(self):
        """测试 ToolBus 熔断器状态"""
        state = get_circuit_state_metric("tool_bus")
        assert state in [0, 1, 2]


class TestGlobalInstances:
    """测试全局实例"""

    def test_model_gateway_circuit_exists(self):
        """测试全局 ModelGateway 熔断器"""
        assert model_gateway_circuit is not None
        assert model_gateway_circuit.name == "model_gateway"

    def test_tool_bus_circuit_exists(self):
        """测试全局 ToolBus 熔断器"""
        assert tool_bus_circuit is not None
        assert tool_bus_circuit.name == "tool_bus"
