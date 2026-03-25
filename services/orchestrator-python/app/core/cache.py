"""双层缓存模块

L1: 进程内 TTLCache（cachetools）
L2: Redis 分布式缓存

特性:
- 自动回填 L1
- 缓存穿透保护
- 指标上报
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, TypeVar

import structlog
from cachetools import TTLCache
from redis.asyncio import Redis

from app.core.config import config
from app.core.metrics import CACHE_HITS, CACHE_MISSES, CACHE_SIZE

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


class DualLayerCache:
    """双层缓存

    L1: 进程内缓存，毫秒级延迟
    L2: Redis 分布式缓存，多实例共享
    """

    def __init__(
        self,
        redis: Redis,
        name: str = "default",
        local_maxsize: int | None = None,
        ttl: int | None = None,
    ):
        self._redis = redis
        self._name = name
        self._local_maxsize = local_maxsize or config.cache_local_maxsize
        self._ttl = ttl or config.cache_default_ttl
        self._local_cache = TTLCache(maxsize=self._local_maxsize, ttl=self._ttl)
        self._hit_count = 0
        self._miss_count = 0

    def _make_key(self, key: str) -> str:
        """生成 Redis 键"""
        return f"cache:{self._name}:{key}"

    @staticmethod
    def _hash_key(data: str | dict) -> str:
        """生成哈希键（用于查询缓存）"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:16]

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        full_key = self._make_key(key)

        # L1 查询
        if key in self._local_cache:
            self._hit_count += 1
            CACHE_HITS.labels(cache_name=self._name).inc()
            logger.debug("Cache L1 hit", cache=self._name, key=key)
            return self._local_cache[key]

        # L2 查询
        try:
            data = await self._redis.get(full_key)
            if data:
                value = json.loads(data)
                self._local_cache[key] = value  # 回填 L1
                self._hit_count += 1
                CACHE_HITS.labels(cache_name=self._name).inc()
                logger.debug("Cache L2 hit", cache=self._name, key=key)
                return value
        except Exception as e:
            logger.warning("Redis cache read failed", error=str(e))

        self._miss_count += 1
        CACHE_MISSES.labels(cache_name=self._name).inc()
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None):
        """设置缓存值"""
        full_key = self._make_key(key)
        actual_ttl = ttl or self._ttl

        # 设置 L1
        self._local_cache[key] = value

        # 设置 L2
        try:
            await self._redis.setex(
                full_key,
                actual_ttl,
                json.dumps(value, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning("Redis cache write failed", error=str(e))

        # 更新指标
        CACHE_SIZE.labels(cache_name=self._name).set(len(self._local_cache))

    async def delete(self, key: str):
        """删除缓存值"""
        full_key = self._make_key(key)

        # 删除 L1
        if key in self._local_cache:
            del self._local_cache[key]

        # 删除 L2
        try:
            await self._redis.delete(full_key)
        except Exception as e:
            logger.warning("Redis cache delete failed", error=str(e))

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int | None = None,
    ) -> Any:
        """获取或计算缓存值

        Args:
            key: 缓存键
            factory: 值生成函数（可以是异步函数）
            ttl: 缓存 TTL

        Returns:
            缓存值或计算结果
        """
        value = await self.get(key)
        if value is not None:
            return value

        # 计算新值
        import asyncio

        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0

        return {
            "name": self._name,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(hit_rate, 4),
            "local_size": len(self._local_cache),
            "local_maxsize": self._local_maxsize,
            "ttl": self._ttl,
        }

    def clear(self):
        """清空本地缓存"""
        self._local_cache.clear()
        CACHE_SIZE.labels(cache_name=self._name).set(0)


class CacheManager:
    """缓存管理器

    管理多个命名缓存实例。
    """

    def __init__(self, redis: Redis):
        self._redis = redis
        self._caches: dict[str, DualLayerCache] = {}

    def get_cache(
        self,
        name: str,
        ttl: int | None = None,
        local_maxsize: int | None = None,
    ) -> DualLayerCache:
        """获取或创建命名缓存"""
        if name not in self._caches:
            self._caches[name] = DualLayerCache(
                redis=self._redis,
                name=name,
                ttl=ttl,
                local_maxsize=local_maxsize,
            )
        return self._caches[name]

    def get_rag_cache(self) -> DualLayerCache:
        """获取 RAG 结果缓存"""
        return self.get_cache(
            name="rag",
            ttl=config.cache_rag_ttl,
            local_maxsize=500,
        )

    def get_tool_schema_cache(self) -> DualLayerCache:
        """获取工具 Schema 缓存"""
        return self.get_cache(
            name="tool_schema",
            ttl=config.cache_tool_schema_ttl,
            local_maxsize=200,
        )

    def get_model_list_cache(self) -> DualLayerCache:
        """获取模型列表缓存"""
        return self.get_cache(
            name="model_list",
            ttl=config.cache_model_list_ttl,
            local_maxsize=10,
        )

    def get_all_stats(self) -> dict[str, dict]:
        """获取所有缓存统计"""
        return {name: cache.get_stats() for name, cache in self._caches.items()}


# 全局缓存管理器实例
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        raise RuntimeError("Cache manager not initialized")
    return _cache_manager


def init_cache_manager(redis: Redis) -> CacheManager:
    """初始化缓存管理器"""
    global _cache_manager
    _cache_manager = CacheManager(redis)
    return _cache_manager


def cached(
    cache_name: str,
    key_builder: Callable[..., str] | None = None,
    ttl: int | None = None,
):
    """缓存装饰器

    Args:
        cache_name: 缓存名称
        key_builder: 键生成函数
        ttl: 缓存 TTL

    用法:
        @cached("rag", key_builder=lambda q: DualLayerCache._hash_key(q))
        async def search(query: str) -> list:
            ...
    """
    from functools import wraps

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager().get_cache(cache_name, ttl=ttl)

            # 生成键
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = DualLayerCache._hash_key({"args": args, "kwargs": kwargs})

            return await cache.get_or_set(key, lambda: func(*args, **kwargs), ttl)

        return wrapper  # type: ignore

    return decorator
