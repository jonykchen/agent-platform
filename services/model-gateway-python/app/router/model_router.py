"""模型路由器

智能选择最优模型，支持：
- 租户级策略
- Fallback 机制
- 熔断保护
"""

import structlog

from app.providers.base import BaseLLMProvider, ChatCompletionRequest
from app.resilience.circuit_breaker import CircuitBreaker
from app.core.exceptions import AllProvidersDownError

logger = structlog.get_logger()


class ModelRouter:
    """模型路由器"""

    def __init__(self):
        # 提供商注册表
        self._providers: dict[str, BaseLLMProvider] = {}

        # 熔断器注册表
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # 默认路由策略
        self._default_policy = {
            "primary_model": "qwen-max",
            "fallback_models": ["qwen-plus", "qwen-turbo"],
        }

    def register_provider(self, name: str, provider: BaseLLMProvider) -> None:
        """注册提供商"""
        self._providers[name] = provider
        self._circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=10,
            timeout_seconds=30,
        )
        logger.info("Provider registered", name=name, models=provider.supported_models)

    def get_provider(self, name: str) -> BaseLLMProvider | None:
        """获取提供商"""
        return self._providers.get(name)

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        """获取熔断器"""
        return self._circuit_breakers.get(name)

    async def route(
        self,
        request: ChatCompletionRequest,
        tenant_id: str | None = None,
    ) -> tuple[BaseLLMProvider, str, CircuitBreaker]:
        """路由到最优模型

        Args:
            request: 请求
            tenant_id: 租户 ID（用于策略查询）

        Returns:
            (provider, model_name, circuit_breaker)

        Raises:
            AllProvidersDownError: 所有提供商不可用
        """
        # 获取策略
        policy = await self._get_policy(tenant_id)

        # 指定模型
        if request.model:
            provider = self._providers.get(request.model)
            if provider:
                cb = self._circuit_breakers.get(request.model)
                if cb and cb.is_available():
                    return provider, request.model, cb
                logger.warning(
                    "Specified model circuit open",
                    model=request.model,
                )

        # 主模型
        primary_model = policy.get("primary_model", "qwen-max")
        provider = self._providers.get(primary_model)
        cb = self._circuit_breakers.get(primary_model)

        if provider and cb and cb.is_available():
            logger.info("Routing to primary model", model=primary_model)
            return provider, primary_model, cb

        # Fallback
        fallback_models = policy.get("fallback_models", [])
        for fallback_model in fallback_models:
            provider = self._providers.get(fallback_model)
            cb = self._circuit_breakers.get(fallback_model)

            if provider and cb and cb.is_available():
                logger.warning(
                    "Fallback to backup model",
                    primary=primary_model,
                    fallback=fallback_model,
                )
                return provider, fallback_model, cb

        # 全部不可用
        logger.error("All providers down")
        raise AllProvidersDownError()

    async def _get_policy(self, tenant_id: str | None) -> dict:
        """获取路由策略

        TODO: 从数据库或 Redis 加载租户策略
        """
        # 当前返回默认策略
        return self._default_policy

    def set_default_policy(self, policy: dict) -> None:
        """设置默认策略"""
        self._default_policy = policy
        logger.info("Default policy updated", policy=policy)

    def list_available_models(self) -> list[dict]:
        """列出可用模型"""
        models = []
        for name, provider in self._providers.items():
            cb = self._circuit_breakers.get(name)
            models.append({
                "name": name,
                "provider": provider.provider_name,
                "available": cb.is_available() if cb else False,
                "supported": provider.supported_models,
            })
        return models

    def get_health_status(self) -> dict:
        """获取健康状态"""
        status = {}
        for name, cb in self._circuit_breakers.items():
            status[name] = {
                "state": cb.state.value,
                "failures": cb._stats.failures,
                "successes": cb._stats.successes,
            }
        return status


# 全局实例
_router = None


def get_model_router() -> ModelRouter:
    """获取模型路由器实例"""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router