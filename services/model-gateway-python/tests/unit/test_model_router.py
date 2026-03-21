"""测试模型路由器"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.router.model_router import ModelRouter
from app.resilience.circuit_breaker import CircuitState
from app.core.exceptions import AllProvidersDownError


@pytest.fixture
def mock_provider():
    """创建 Mock 提供商"""
    provider = MagicMock()
    provider.provider_name = "qwen"
    provider.supported_models = ["qwen-max", "qwen-plus"]
    return provider


@pytest.fixture
def router():
    """创建路由器实例"""
    return ModelRouter()


class TestModelRouter:
    """模型路由器测试"""

    def test_register_provider(self, router, mock_provider):
        """测试注册提供商"""
        router.register_provider("qwen-max", mock_provider)

        assert "qwen-max" in router._providers
        assert "qwen-max" in router._circuit_breakers

    def test_get_provider(self, router, mock_provider):
        """测试获取提供商"""
        router.register_provider("qwen-max", mock_provider)

        provider = router.get_provider("qwen-max")
        assert provider == mock_provider

    def test_get_provider_not_found(self, router):
        """测试获取不存在的提供商"""
        provider = router.get_provider("nonexistent")
        assert provider is None

    def test_list_available_models(self, router, mock_provider):
        """测试列出可用模型"""
        router.register_provider("qwen-max", mock_provider)

        models = router.list_available_models()

        assert len(models) == 1
        assert models[0]["name"] == "qwen-max"
        assert models[0]["provider"] == "qwen"
        assert models[0]["available"] is True

    def test_set_default_policy(self, router):
        """测试设置默认策略"""
        new_policy = {
            "primary_model": "qwen-plus",
            "fallback_models": ["qwen-turbo"],
        }

        router.set_default_policy(new_policy)

        assert router._default_policy["primary_model"] == "qwen-plus"

    def test_get_health_status(self, router, mock_provider):
        """测试获取健康状态"""
        router.register_provider("qwen-max", mock_provider)

        status = router.get_health_status()

        assert "qwen-max" in status
        assert status["qwen-max"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_route_to_primary(self, router, mock_provider):
        """测试路由到主模型"""
        router.register_provider("qwen-max", mock_provider)

        request = MagicMock()
        request.model = None

        provider, model, cb = await router.route(request, tenant_id="tenant-001")

        assert model == "qwen-max"
        assert provider == mock_provider

    @pytest.mark.asyncio
    async def test_route_to_specified_model(self, router, mock_provider):
        """测试路由到指定模型"""
        router.register_provider("qwen-plus", mock_provider)

        request = MagicMock()
        request.model = "qwen-plus"

        provider, model, cb = await router.route(request)

        assert model == "qwen-plus"

    @pytest.mark.asyncio
    async def test_route_to_fallback(self, router, mock_provider):
        """测试路由到备用模型"""
        # 注册两个提供商
        primary_provider = MagicMock()
        primary_provider.provider_name = "qwen"
        primary_provider.supported_models = ["qwen-max"]

        fallback_provider = MagicMock()
        fallback_provider.provider_name = "qwen"
        fallback_provider.supported_models = ["qwen-plus"]

        router.register_provider("qwen-max", primary_provider)
        router.register_provider("qwen-plus", fallback_provider)

        # 让主模型熔断
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()
        router._circuit_breakers["qwen-max"].record_failure()

        request = MagicMock()
        request.model = None

        provider, model, cb = await router.route(request)

        # 应该路由到备用模型
        assert model == "qwen-plus"

    @pytest.mark.asyncio
    async def test_route_all_providers_down(self, router, mock_provider):
        """测试所有提供商不可用"""
        router.register_provider("qwen-max", mock_provider)

        # 让所有提供商熔断
        cb = router._circuit_breakers["qwen-max"]
        for _ in range(15):
            cb.record_failure()

        request = MagicMock()
        request.model = None

        with pytest.raises(AllProvidersDownError):
            await router.route(request)

    @pytest.mark.asyncio
    async def test_get_policy(self, router):
        """测试获取策略"""
        policy = await router._get_policy("tenant-001")

        assert "primary_model" in policy
        assert "fallback_models" in policy
