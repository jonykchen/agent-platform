"""全局 Redis 客户端（进程内单例）

【设计目标】
此前多个模块（model_router 的租户策略加载、response_cache）各自用
`Redis.from_url(...)` 临时创建连接后再 close，高并发下会反复创建/销毁连接，
甚至泄漏连接（异常路径未 close）。本模块提供进程内单例 + 连接池复用，
所有需要 Redis 的组件统一通过 `get_redis()` 获取同一实例。

【生命周期】
- 首次 `get_redis()` 时基于 `redis.asyncio.from_url` 创建带连接池的客户端
- 进程内复用，不在每次调用时重建
- 应用关闭时由 main.py lifespan 调用 `close_redis()` 释放连接池
"""

from __future__ import annotations

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()

# 连接池上限：与 main.py lifespan 注释中描述的 max_connections=100 对齐
_MAX_CONNECTIONS = 100

_redis: Redis | None = None


def get_redis() -> Redis:
    """获取全局 Redis 客户端单例（进程内复用同一连接池）。

    首次调用时基于配置的 redis_url 创建带连接池的客户端，后续调用复用。
    禁止在业务代码中直接 `Redis.from_url(...)`，统一走此函数避免连接泄漏。
    """
    global _redis
    if _redis is None:
        from app.core.config import config

        _redis = Redis.from_url(
            config.redis_url,
            max_connections=_MAX_CONNECTIONS,
        )
        logger.info("Global Redis client initialized", max_connections=_MAX_CONNECTIONS)
    return _redis


def set_redis(client: Redis) -> None:
    """注入已创建的 Redis 客户端作为全局单例（供 lifespan 复用同一连接）。"""
    global _redis
    _redis = client


async def close_redis() -> None:
    """关闭全局 Redis 客户端（应用关闭时调用）。"""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
        logger.info("Global Redis client closed")
