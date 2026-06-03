"""Redis 客户端管理

提供全局 Redis 客户端访问，避免循环导入问题。

【设计说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

问题：main.py 导入 api.v1.agent，agent.py 需要导入 get_redis
解决：将 Redis 客户端管理独立到此模块

使用方式：
```python
from app.infrastructure.redis_client import get_redis, init_redis, close_redis

# 初始化（在 main.py lifespan 中调用）
await init_redis(config.redis_url)

# 使用
redis = get_redis()
await redis.set("key", "value")

# 关闭
await close_redis()
```
"""

from __future__ import annotations

from redis.asyncio import Redis

# 全局 Redis 客户端
_redis_client: Redis | None = None


async def init_redis(redis_url: str) -> Redis:
    """初始化 Redis 客户端

    Args:
        redis_url: Redis 连接 URL

    Returns:
        Redis 客户端实例
    """
    global _redis_client
    _redis_client = Redis.from_url(redis_url)
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 客户端"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def get_redis() -> Redis:
    """获取 Redis 客户端

    Raises:
        RuntimeError: 如果 Redis 未初始化

    Returns:
        Redis 客户端实例
    """
    if _redis_client is None:
        raise RuntimeError("Redis not initialized")
    return _redis_client


def is_redis_initialized() -> bool:
    """检查 Redis 是否已初始化"""
    return _redis_client is not None