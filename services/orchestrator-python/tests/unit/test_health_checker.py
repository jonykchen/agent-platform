"""测试健康检查器"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.health_checker import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
    get_health_checker,
)


class TestHealthChecker:
    """测试健康检查器"""

    def test_health_status_enum(self):
        """测试健康状态枚举"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_component_health_to_dict(self):
        """测试组件健康状态转换"""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.5,
            details={"key": "value"},
        )
        result = health.to_dict()

        assert result["name"] == "test"
        assert result["status"] == "healthy"
        assert result["message"] == "OK"
        assert result["latency_ms"] == 10.5
        assert result["details"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_check_redis_healthy(self):
        """测试 Redis 健康检查成功"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        checker = HealthChecker(redis_client=mock_redis)
        result = await checker.check_redis()

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Connected"

    @pytest.mark.asyncio
    async def test_check_redis_unhealthy(self):
        """测试 Redis 健康检查失败"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection refused"))

        checker = HealthChecker(redis_client=mock_redis)
        result = await checker.check_redis()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_check_redis_not_initialized(self):
        """测试 Redis 未初始化"""
        checker = HealthChecker()
        result = await checker.check_redis()

        assert result.status == HealthStatus.DEGRADED
        assert "not initialized" in result.message

    @pytest.mark.asyncio
    async def test_check_model_gateway_healthy(self):
        """测试 ModelGateway 健康检查成功"""
        checker = HealthChecker()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            checker,
            "_get_http_client",
            return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
        ):
            result = await checker.check_model_gateway()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_model_gateway_timeout(self):
        """测试 ModelGateway 超时"""
        import httpx

        checker = HealthChecker()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch.object(checker, "_get_http_client", return_value=mock_client):
            result = await checker.check_model_gateway()

        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_readiness(self):
        """测试就绪检查"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        checker = HealthChecker(redis_client=mock_redis)

        is_ready, details = await checker.check_readiness()

        assert is_ready is True or is_ready is False
        assert "redis" in details
        assert "model_gateway" in details

    @pytest.mark.asyncio
    async def test_check_all(self):
        """测试检查所有依赖"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        checker = HealthChecker(redis_client=mock_redis)

        result = await checker.check_all()

        assert "status" in result
        assert "total_latency_ms" in result
        assert "components" in result
        assert len(result["components"]) == 4


class TestGetHealthChecker:
    """测试全局健康检查器"""

    def test_get_health_checker_creates_instance(self):
        """测试获取健康检查器实例"""
        checker = get_health_checker()
        assert checker is not None
