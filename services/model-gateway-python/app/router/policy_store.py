"""路由策略存储

从数据库/Redis 加载租户级路由策略。
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
    """路由策略存储"""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._client = None

        # 内存缓存
        self._cache: dict[str, dict] = {}

        # 默认策略
        self._default_policy = {
            "primary_model": "qwen-max",
            "fallback_models": ["qwen-plus", "qwen-turbo"],
            "rate_limit": 100,
            "config": {
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        }

    async def _get_client(self):
        if not HAS_REDIS:
            return None

        if self._client is None and self.redis_url:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get_policy(self, tenant_id: str | None) -> dict:
        """获取租户策略

        Args:
            tenant_id: 租户 ID

        Returns:
            路由策略
        """
        if not tenant_id:
            return self._default_policy

        # 检查内存缓存
        if tenant_id in self._cache:
            return self._cache[tenant_id]

        # 尝试从 Redis 加载
        client = await self._get_client()
        if client:
            try:
                key = f"model_policy:{tenant_id}"
                data = await client.get(key)
                if data:
                    policy = json.loads(data)
                    self._cache[tenant_id] = policy
                    return policy
            except Exception as e:
                logger.warning("Failed to load policy from Redis", error=str(e))

        # 返回默认策略
        return self._default_policy

    async def set_policy(
        self,
        tenant_id: str,
        policy: dict,
        ttl_seconds: int = 300,
    ) -> None:
        """设置租户策略

        Args:
            tenant_id: 租户 ID
            policy: 策略配置
            ttl_seconds: 缓存 TTL
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
        """删除租户策略"""
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
        """设置默认策略"""
        self._default_policy = policy
        logger.info("Default policy updated")


# 全局实例
_store = None


def get_policy_store() -> PolicyStore:
    """获取策略存储实例"""
    global _store
    if _store is None:
        _store = PolicyStore()
    return _store