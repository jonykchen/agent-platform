"""模型路由器

智能选择最优模型，支持：
- 租户级策略
- Fallback 机制
- 熔断保护

【核心概念】模型路由的作用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在多模型环境下，路由器决定使用哪个模型：
- 性能优先：选择响应最快的模型
- 成本优先：选择最便宜的可用模型
- 可靠性优先：自动 Fallback 到备用模型

【技术选型】路由策略方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 固定模型 (简单)    │ • 配置简单                  │ • 单点故障                  │
│                    │                             │ • 无法适应负载变化          │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 轮询 (Round Robin) │ • 负载均衡                  │ • 无性能感知                │
│                    │                             │ • 故障节点影响请求          │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 主备 Fallback (选)│ • 高可用                    │ • 主模型压力集中            │
│                    │ • 故障自动切换              │ • 备用模型闲置浪费          │
│                    │ • 配置直观                  │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 加权随机           │ • 可控制流量分配            │ • 需维护权重配置            │
│                    │ • 支持灰度发布              │ • 无实时性能感知            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 智能路由 (复杂)    │ • 实时性能感知              │ • 实现复杂                  │
│                    │ • 最优模型选择              │ • 监控依赖                  │
│                    │ • 自适应负载                │ • 可能过度设计              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择主备 Fallback 的原因】
1. 本项目模型数量少（3-5 个），复杂路由收益有限
2. 主备模式简单可靠，运维成本低
3. Fallback 机制保证高可用

【路由决策流程】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

【租户级策略】
租户可自定义路由策略（存储在 Redis）：
- primary_model: 主模型
- fallback_models: 备用模型列表
- rate_limit: 调用频率限制
- cost_budget: 日成本预算

【熔断器状态】
- CLOSED: 正常，允许调用
- OPEN: 熔断，拒绝调用（等待恢复超时）
- HALF_OPEN: 试探，允许少量请求测试恢复

"""

import structlog

from app.core.exceptions import AllProvidersDownError
from app.providers.base import BaseLLMProvider, ChatCompletionRequest
from app.resilience.circuit_breaker import CircuitBreaker

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
            "primary_model": "deepseek-chat",
            "fallback_models": ["deepseek-chat"],
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

    def get_embedding_provider(self, model: str | None = None) -> tuple[BaseLLMProvider, "CircuitBreaker"] | None:
        """获取一个支持 embedding 且当前可用的 Provider。

        优先选择支持指定 embedding 模型的 Provider，否则返回首个可用的
        embedding Provider。全部不可用时返回 None。

        Args:
            model: embedding 模型名称（可选）

        Returns:
            (provider, circuit_breaker) 或 None
        """
        fallback: tuple[BaseLLMProvider, CircuitBreaker] | None = None
        for name, provider in self._providers.items():
            if not getattr(provider, "supports_embeddings", False):
                continue
            cb = self._circuit_breakers.get(name)
            if not (cb and cb.is_available()):
                continue
            # 记录首个可用的 embedding Provider 作为兜底
            if fallback is None:
                fallback = (provider, cb)
            # 优先返回支持指定模型的 Provider
            if model:
                embedding_models = getattr(provider, "EMBEDDING_MODELS", [])
                if embedding_models and model not in embedding_models:
                    continue
            return provider, cb
        # 无 Provider 精确支持该模型时，回退到任一可用 embedding Provider
        return fallback

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

        # 尝试使用用户指定的模型（遍历 providers 查找支持该模型的提供商）
        if request.model:
            for name, provider in self._providers.items():
                if request.model in provider.supported_models:
                    cb = self._circuit_breakers.get(name)
                    if cb and cb.is_available():
                        logger.info(
                            "route_decision",
                            model=request.model,
                            source="user_specified",
                            provider=name,
                            circuit_state=cb.state.value,
                        )
                        return provider, request.model, cb

                    logger.warning(
                        "route_specified_unavailable",
                        model=request.model,
                        reason="circuit_open",
                        provider=name,
                        circuit_state=cb.state.value if cb else "not_found",
                    )
                    break

        # 尝试使用主模型（遍历 providers 查找支持该模型的提供商）
        primary_model = policy.get("primary_model", "qwen-max")
        primary_provider = None
        primary_name = None
        for name, provider in self._providers.items():
            if primary_model in provider.supported_models:
                primary_provider = provider
                primary_name = name
                break

        cb = self._circuit_breakers.get(primary_name) if primary_name else None

        if primary_provider and cb and cb.is_available():
            logger.info(
                "route_decision",
                model=primary_model,
                source="primary",
                provider=primary_name,
                circuit_state=cb.state.value,
            )
            return primary_provider, primary_model, cb

        # 尝试 Fallback 备用模型
        fallback_models = policy.get("fallback_models", [])
        logger.warning(
            "route_fallback_started",
            primary_model=primary_model,
            reason="primary_unavailable",
            fallback_models=fallback_models,
        )

        for fallback_model in fallback_models:
            for name, provider in self._providers.items():
                if fallback_model in provider.supported_models:
                    cb = self._circuit_breakers.get(name)
                    if cb and cb.is_available():
                        logger.warning(
                            "route_decision",
                            model=fallback_model,
                            source="fallback",
                            primary_failed=primary_model,
                            provider=name,
                            circuit_state=cb.state.value,
                        )
                        return provider, fallback_model, cb
                    break

        # 所有模型都不可用
        logger.error(
            "route_failed",
            reason="all_providers_down",
            tried_models=[request.model, primary_model] + fallback_models,
        )
        raise AllProvidersDownError()

    async def _get_policy(self, tenant_id: str | None) -> dict:
        """获取路由策略

        【策略加载流程】
        1. 从 Redis 加载租户级策略（如有）
        2. 使用默认策略作为后备

        【租户策略格式】（存储在 Redis）
        Key: model_policy:{tenant_id}
        Value: {
            "primary_model": "qwen-max",
            "fallback_models": ["qwen-plus", "qwen-turbo"],
            "rate_limit": 100,  # 每分钟最大调用数
            "cost_budget": 10.0  # 日成本预算（美元）
        }
        """
        # 如果有租户 ID，尝试从 Redis 加载
        if tenant_id:
            try:
                from app.core.redis_client import get_redis

                # 复用全局 Redis 连接池，避免每次缓存未命中都新建连接导致泄漏
                redis = get_redis()
                policy_key = f"model_policy:{tenant_id}"

                policy_data = await redis.get(policy_key)
                if policy_data:
                    import json

                    policy = json.loads(policy_data)

                    logger.debug(
                        "tenant_policy_loaded",
                        tenant_id=tenant_id,
                        primary_model=policy.get("primary_model"),
                    )
                    return policy

            except Exception as e:
                logger.warning(
                    "tenant_policy_load_failed",
                    tenant_id=tenant_id,
                    error=str(e),
                )

        # 返回默认策略
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
            models.append(
                {
                    "name": name,
                    "provider": provider.provider_name,
                    "available": cb.is_available() if cb else False,
                    "supported": provider.supported_models,
                }
            )
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
