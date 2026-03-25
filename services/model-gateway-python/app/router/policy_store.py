"""路由策略存储

【核心概念】模型路由策略
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

模型网关需要根据不同条件选择最合适的 LLM 提供商：

1. 租户级策略：不同租户使用不同的模型
   - VIP 租户：使用 qwen-max（高准确率）
   - 普通租户：使用 qwen-plus（性价比）

2. 降级策略：主模型故障时自动切换备用模型
   - primary_model 故障 → fallback_models[0] → fallback_models[1]

3. 灰度发布：新模型先给小部分用户使用
   - 10% 流量 → 新模型 qwen-max-latest
   - 90% 流量 → 稳定版本 qwen-max

【技术选型】多级缓存设计
┌─────────────────────────────────────────────────────────────────────────┐
│                          请求获取策略                                    │
│                                                                         │
│   ┌─────────────┐                                                      │
│   │ 内存缓存 L1 │ ← 最快，进程内                        │
│   └─────────────┘                                                      │
│         │ miss                                                         │
│         ▼                                                              │
│   ┌─────────────┐                                                      │
│   │ Redis L2    │ ← 共享，跨进程                        │
│   └─────────────┘                                                      │
│         │ miss                                                         │
│         ▼                                                              │
│   ┌─────────────┐                                                      │
│   │ 默认策略    │ ← 兜底                        │
│   └─────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘

为什么需要两级缓存？
- 内存缓存：避免每次请求都访问 Redis，减少网络延迟
- Redis 缓存：多实例共享策略，支持动态更新

【策略结构】
{
    "primary_model": "qwen-max",           # 主模型
    "fallback_models": ["qwen-plus"],      # 备用模型列表
    "rate_limit": 100,                     # 每分钟请求限制
    "config": {                            # 模型参数
        "temperature": 0.7,
        "max_tokens": 2000
    },
    "routing_rules": [                     # 路由规则（可选）
        {"pattern": "代码.*", "model": "deepseek-coder"},
        {"pattern": "长文本.*", "model": "kimi"}
    ]
}

【参考】
- 多租户 SaaS 架构: https://docs.microsoft.com/en-us/azure/architecture/guide/saas-multitenant/
- 灰度发布策略: https://martinfowler.com/bliki/CanaryRelease.html
"""

import json
from datetime import datetime

import structlog

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = structlog.get_logger()


class PolicyStore:
    """路由策略存储

    【设计模式】Repository Pattern + Multi-level Cache

    职责：
    1. 策略持久化：Redis 存储
    2. 缓存管理：内存缓存 + Redis 双层
    3. 默认策略：兜底配置

    使用场景：
    - 模型网关根据 tenant_id 获取路由策略
    - 运维后台更新租户策略
    - 灰度发布时动态调整路由规则
    """

    def __init__(self, redis_url: str | None = None):
        """初始化策略存储

        Args:
            redis_url: Redis 连接 URL，为 None 时仅使用内存缓存
        """
        self.redis_url = redis_url
        self._client = None

        # 内存缓存 - L1 缓存
        # 使用场景：高频访问的租户策略，避免每次都访问 Redis
        # 缓存失效策略：依赖 Redis 过期时间或手动清除
        self._cache: dict[str, dict] = {}

        # 默认策略 - 兜底配置
        # 当租户未配置策略或 Redis 不可用时使用
        self._default_policy = {
            "primary_model": "qwen-max",           # 主力模型
            "fallback_models": ["qwen-plus", "qwen-turbo"],  # 备选模型
            "rate_limit": 100,                     # 每分钟请求数
            "config": {
                "temperature": 0.7,                # 模型温度参数
                "max_tokens": 2000,                # 最大输出 token
            },
        }

    async def _get_client(self):
        """获取 Redis 客户端（懒加载）

        【懒加载模式】
        不在 __init__ 中创建连接的原因：
        - 避免同步代码中创建异步资源
        - 支持无 Redis 环境运行（纯内存模式）
        """
        if not HAS_REDIS:
            return None

        if self._client is None and self.redis_url:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,  # 自动解码为字符串
            )
        return self._client

    async def get_policy(self, tenant_id: str | None) -> dict:
        """获取租户策略

        【多级缓存查找】
        1. 检查内存缓存（最快）
        2. 检查 Redis 缓存（共享）
        3. 返回默认策略（兜底）

        Args:
            tenant_id: 租户 ID，为 None 时返回默认策略

        Returns:
            路由策略字典
        """
        if not tenant_id:
            return self._default_policy

        # L1: 检查内存缓存
        if tenant_id in self._cache:
            logger.debug("policy_cache_hit", level="memory", tenant_id=tenant_id)
            return self._cache[tenant_id]

        # L2: 尝试从 Redis 加载
        client = await self._get_client()
        if client:
            try:
                key = f"model_policy:{tenant_id}"
                data = await client.get(key)
                if data:
                    policy = json.loads(data)
                    # 回填内存缓存
                    self._cache[tenant_id] = policy
                    logger.debug("policy_cache_hit", level="redis", tenant_id=tenant_id)
                    return policy
            except Exception as e:
                logger.warning("Failed to load policy from Redis", error=str(e))

        # L3: 返回默认策略
        logger.debug("policy_cache_miss", tenant_id=tenant_id)
        return self._default_policy

    async def set_policy(
        self,
        tenant_id: str,
        policy: dict,
        ttl_seconds: int = 300,
    ) -> None:
        """设置租户策略

        【写穿透策略】
        同时更新内存缓存和 Redis，保证一致性。

        Args:
            tenant_id: 租户 ID
            policy: 策略配置
            ttl_seconds: 缓存 TTL（默认 5 分钟）
        """
        # 更新内存缓存
        self._cache[tenant_id] = policy

        # 写入 Redis
        client = await self._get_client()
        if client:
            try:
                key = f"model_policy:{tenant_id}"
                await client.set(key, json.dumps(policy), ex=ttl_seconds)
                logger.info("Policy saved", tenant_id=tenant_id)
            except Exception as e:
                logger.warning("Failed to save policy to Redis", error=str(e))

    async def delete_policy(self, tenant_id: str) -> None:
        """删除租户策略

        【缓存失效】
        同时删除内存和 Redis 中的缓存。
        """
        # 清除内存缓存
        self._cache.pop(tenant_id, None)

        # 删除 Redis
        client = await self._get_client()
        if client:
            try:
                key = f"model_policy:{tenant_id}"
                await client.delete(key)
                logger.info("Policy deleted", tenant_id=tenant_id)
            except Exception as e:
                logger.warning("Failed to delete policy from Redis", error=str(e))

    def set_default_policy(self, policy: dict) -> None:
        """设置默认策略

        用于运维后台动态调整全局默认策略。
        """
        self._default_policy = policy
        logger.info("Default policy updated")


# ═══════════════════════════════════════════════════════════════════════════
# 全局实例 - 单例模式
# ═══════════════════════════════════════════════════════════════════════════

_store = None


def get_policy_store() -> PolicyStore:
    """获取策略存储实例（单例）

    【单例模式】
    使用模块级变量实现单例的原因：
    - 简单直接，无需引入单例库
    - Python 模块天然单例
    - 测试时可直接替换 _store 变量
    """
    global _store
    if _store is None:
        _store = PolicyStore()
    return _store