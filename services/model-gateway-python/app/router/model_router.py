"""模型路由器

智能选择最优模型，支持：
- 租户级策略
- Fallback 机制
- 熔断保护

路由决策流程：
┌─────────────────────────────────────────────────────────┐
│                    请求进入                              │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 获取租户策略    │                     │
│                  │ (或使用默认)    │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 检查指定模型    │                     │
│                  └─────────────────┘                    │
│                           │                             │
│           ┌───────────────┼───────────────┐            │
│           │               │               │            │
│       [指定可用]       [指定不可用]     [无指定]         │
│           │               │               │            │
│           ▼               │               ▼            │
│      直接使用            │         使用 primary_model  │
│                         │                              │
│                         │    ┌─────────────────┐       │
│                         │    │ 检查熔断器状态  │        │
│                         │    └─────────────────┘       │
│                         │          │                   │
│                         │          ▼                   │
│                         │    [可用]  [熔断]            │
│                         │      │       │               │
│                         │   使用   Fallback            │
│                         │      │       │               │
│                         │      ▼       ▼               │
│                         │   主模型  备用模型           │
│                         │                              │
│                         └──► 所有备用不可用             │
│                              │                         │
│                              ▼                         │
│                      AllProvidersDownError              │
└─────────────────────────────────────────────────────────┘

路由策略：
- primary_model: 主模型（如 qwen-max）
- fallback_models: 备用模型列表（如 qwen-plus, qwen-turbo）

熔断器状态：
- CLOSED: 正常状态，允许调用
- OPEN: 熔断状态，拒绝调用（等待恢复）
- HALF_OPEN: 半开状态，试探性恢复

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

        路由决策优先级：
        1. 用户指定的模型（如果可用且未熔断）
        2. 租户策略中的主模型
        3. Fallback 备用模型列表

        Args:
            request: ChatCompletionRequest 请求对象
            tenant_id: 租户 ID（用于获取租户级策略）

        Returns:
            tuple[provider, model_name, circuit_breaker]

        Raises:
            AllProvidersDownError: 所有提供商都不可用
        """
        # 获取路由策略
        policy = await self._get_policy(tenant_id)
        logger.debug(
            "route_started",
            requested_model=request.model,
            tenant_id=tenant_id,
            primary_model=policy.get("primary_model"),
        )

        # 尝试使用用户指定的模型
        if request.model:
            provider = self._providers.get(request.model)
            if provider:
                cb = self._circuit_breakers.get(request.model)
                if cb and cb.is_available():
                    logger.info(
                        "route_decision",
                        model=request.model,
                        source="user_specified",
                        circuit_state=cb.state.value,
                    )
                    return provider, request.model, cb

                logger.warning(
                    "route_specified_unavailable",
                    model=request.model,
                    reason="circuit_open",
                    circuit_state=cb.state.value if cb else "not_found",
                )

        # 尝试使用主模型
        primary_model = policy.get("primary_model", "qwen-max")
        provider = self._providers.get(primary_model)
        cb = self._circuit_breakers.get(primary_model)

        if provider and cb and cb.is_available():
            logger.info(
                "route_decision",
                model=primary_model,
                source="primary",
                circuit_state=cb.state.value,
            )
            return provider, primary_model, cb

        # 尝试 Fallback 备用模型
        fallback_models = policy.get("fallback_models", [])
        logger.warning(
            "route_fallback_started",
            primary_model=primary_model,
            reason="primary_unavailable",
            fallback_models=fallback_models,
        )

        for fallback_model in fallback_models:
            provider = self._providers.get(fallback_model)
            cb = self._circuit_breakers.get(fallback_model)

            if provider and cb and cb.is_available():
                logger.warning(
                    "route_decision",
                    model=fallback_model,
                    source="fallback",
                    primary_failed=primary_model,
                    circuit_state=cb.state.value,
                )
                return provider, fallback_model, cb

        # 所有模型都不可用
        logger.error(
            "route_failed",
            reason="all_providers_down",
            tried_models=[request.model, primary_model] + fallback_models,
        )
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