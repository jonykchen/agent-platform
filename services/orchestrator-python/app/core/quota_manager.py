"""租户配额管理服务"""

from __future__ import annotations

import time

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()


class TenantQuotaManager:
    """租户配额管理

    管理租户级别的 Token 配额和功能开关。
    使用 Redis Lua 脚本保证原子性。
    """

    # Lua 脚本：原子化配额扣减
    QUOTA_DECR_SCRIPT = """
    local key = KEYS[1]
    local amount = tonumber(ARGV[1])
    local budget = tonumber(redis.call('GET', key) or '-1')
    if budget < 0 then
        return -2  -- 配额未设置
    end
    if budget < amount then
        return -1  -- 配额不足
    end
    return redis.call('DECRBY', key, amount)
    """

    def __init__(self, redis: Redis):
        self.redis = redis
        self._scripts = {}

    async def _get_script(self, script: str) -> str:
        """缓存 Lua 脚本"""
        if script not in self._scripts:
            self._scripts[script] = self.redis.register_script(script)
        return self._scripts[script]

    async def check_quota(self, tenant_id: str, tokens: int) -> dict:
        """检查并扣减配额

        Args:
            tenant_id: 租户 ID
            tokens: 需要消耗的 token 数

        Returns:
            {"allowed": bool, "remaining": int, "reason": str}
        """
        key = f"quota:tenant:{tenant_id}:daily"

        script = await self._get_script(self.QUOTA_DECR_SCRIPT)
        result = await script(keys=[key], args=[tokens])

        if result == -2:
            # 配额未设置，使用默认值
            default_quota = 1_000_000
            await self.redis.set(key, default_quota)
            result = await script(keys=[key], args=[tokens])

        if result == -1:
            return {
                "allowed": False,
                "remaining": 0,
                "reason": "Quota exceeded",
            }

        return {
            "allowed": True,
            "remaining": result,
            "reason": None,
        }

    async def get_quota(self, tenant_id: str) -> dict:
        """获取租户配额信息"""
        key = f"quota:tenant:{tenant_id}:daily"
        remaining = await self.redis.get(key)

        # 获取总配额（从租户配置中）
        config_key = f"config:tenant:{tenant_id}"
        config = await self.redis.hgetall(config_key)
        budget = int(config.get(b"daily_tokens"], 1_000_000))

        return {
            "budget": budget,
            "used": budget - int(remaining or 0),
            "remaining": int(remaining or 0),
        }

    async def reset_quota(self, tenant_id: str, daily_tokens: int):
        """重置租户配额（每天 00:00 UTC 执行）"""
        key = f"quota:tenant:{tenant_id}:daily"

        # 设置配额，TTL 为 24 小时 + 5 分钟
        ttl = 86400 + 300
        await self.redis.set(key, daily_tokens, ex=ttl)

        logger.info("Quota reset", tenant_id=tenant_id, daily_tokens=daily_tokens)
