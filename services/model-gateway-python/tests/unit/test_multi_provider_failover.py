"""多 Provider 故障转移测试

验证 Qwen / DeepSeek / GLM 多 Provider 注册后，主 Provider 熔断时
ModelRouter 能正确故障转移到备用 Provider，避免 AllProvidersDownError。

对应 P0-5：第二、三个 LLM Provider（DeepSeek + GLM）。
"""

import pytest
from unittest.mock import MagicMock

from app.router.model_router import ModelRouter
from app.core.exceptions import AllProvidersDownError
from app.providers.deepseek import DeepSeekProvider
from app.providers.glm import GLMProvider


@pytest.fixture
def router():
    return ModelRouter()


@pytest.fixture
def deepseek_provider():
    return DeepSeekProvider(api_key="test-key", base_url="https://api.deepseek.com/v1")


@pytest.fixture
def glm_provider():
    return GLMProvider(api_key="test-key", base_url="https://open.bigmodel.cn/api/paas/v4")


class TestProviderMetadata:
    """Provider 元信息正确性"""

    def test_deepseek_supported_models(self, deepseek_provider):
        assert "deepseek-chat" in deepseek_provider.supported_models
        assert deepseek_provider.provider_name == "deepseek"

    def test_glm_supported_models(self, glm_provider):
        assert "glm-4-air" in glm_provider.supported_models
        assert glm_provider.provider_name == "glm"

    def test_glm_normalize_created_handles_string(self, glm_provider):
        """GLM created 字段可能为字符串，应被规范化为 int"""
        assert glm_provider._normalize_created("1700000000") == 1700000000
        assert glm_provider._normalize_created(1700000000) == 1700000000
        assert glm_provider._normalize_created(None) == 0
        assert glm_provider._normalize_created("not-a-number") == 0


class TestCrossProviderFailover:
    """跨 Provider 故障转移"""

    @pytest.mark.asyncio
    async def test_failover_qwen_to_deepseek(self, router, deepseek_provider):
        """主模型（qwen-max）的 Provider 熔断时，故障转移到 DeepSeek 备用模型。

        默认策略 primary_model=qwen-max，fallback_models=[qwen-plus, qwen-turbo]，
        这里把 fallback 设为 deepseek-chat，验证跨 Provider 转移。
        """
        # 主 Provider：仅支持 qwen-max（用 mock 模拟 Qwen 已熔断的场景）
        qwen_like = MagicMock()
        qwen_like.provider_name = "qwen"
        qwen_like.supported_models = ["qwen-max"]

        router.register_provider("qwen", qwen_like)
        router.register_provider("deepseek", deepseek_provider)

        # 设置策略：主模型 qwen-max，备用 deepseek-chat
        router.set_default_policy({
            "primary_model": "qwen-max",
            "fallback_models": ["deepseek-chat"],
        })

        # 让 Qwen 的熔断器打开（默认阈值 10）
        for _ in range(10):
            router._circuit_breakers["qwen"].record_failure()

        request = MagicMock()
        request.model = None

        provider, model, cb = await router.route(request)

        # 应故障转移到 DeepSeek
        assert model == "deepseek-chat"
        assert provider is deepseek_provider

    @pytest.mark.asyncio
    async def test_all_down_raises(self, router, deepseek_provider, glm_provider):
        """所有 Provider 熔断时抛出 AllProvidersDownError"""
        router.register_provider("deepseek", deepseek_provider)
        router.register_provider("glm", glm_provider)
        router.set_default_policy({
            "primary_model": "deepseek-chat",
            "fallback_models": ["glm-4-air"],
        })

        for name in ("deepseek", "glm"):
            for _ in range(10):
                router._circuit_breakers[name].record_failure()

        request = MagicMock()
        request.model = None

        with pytest.raises(AllProvidersDownError):
            await router.route(request)

    @pytest.mark.asyncio
    async def test_user_specified_model_routes_to_glm(self, router, glm_provider):
        """用户显式指定 glm-4-flash 时路由到 GLM Provider"""
        router.register_provider("glm", glm_provider)

        request = MagicMock()
        request.model = "glm-4-flash"

        provider, model, cb = await router.route(request)

        assert model == "glm-4-flash"
        assert provider is glm_provider
