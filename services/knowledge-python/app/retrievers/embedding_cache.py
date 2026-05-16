"""Embedding 缓存层

【核心概念】Embedding 缓存
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Embedding 计算是 RAG 系统的主要延迟来源之一（约 100-500ms）。
对于高频查询，缓存 Embedding 可显著降低延迟和成本。

【缓存策略】
┌─────────────────────────────────────────────────────────────────────────┐
│  场景                │  缓存策略           │  TTL                    │
├─────────────────────┼─────────────────────┼─────────────────────────┤
│  精确匹配查询        │  Key: query hash    │  30 天（长周期）         │
│  改写后查询          │  缓存改写结果        │  7 天                   │
│  向量相似查询        │  不缓存（语义变化大）│  -                      │
└─────────────────────────────────────────────────────────────────────────┘

【Key 设计】
- Key: `embedding:SHA256(query)`
- 原因：查询文本可能包含敏感信息，hash 后脱敏
- 好处：固定长度，避免 Redis Key 过长

【TTL 选择】
- 30 天：Embedding 模型稳定后，相同 query 的向量不变
- 足够长：覆盖常见查询的周期性变化（如月度报表）

【参考】
- Redis 缓存最佳实践: https://redis.io/docs/manual/patterns/
- Embedding 缓存分析: https://www.pinecone.io/learn/vector-embeddings/
"""

from __future__ import annotations

import hashlib
import json
import structlog
from typing import Any

import redis.asyncio as redis

from app.core.config import config

logger = structlog.get_logger()

# 缓存配置
EMBEDDING_CACHE_PREFIX = "embedding:"
EMBEDDING_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 天


class EmbeddingCache:
    """Embedding 缓存层

    功能：
    - 缓存查询向量，避免重复计算
    - Key 脱敏：使用 SHA256 哈希
    - TTL：30 天

    使用示例：
        cache = EmbeddingCache()

        # 获取缓存
        embedding = await cache.get("用户查询文本")
        if embedding is None:
            embedding = await compute_embedding("用户查询文本")
            await cache.set("用户查询文本", embedding)
    """

    def __init__(self, redis_url: str | None = None):
        """初始化缓存

        Args:
            redis_url: Redis 连接 URL，默认从配置读取
        """
        self.redis_url = redis_url or config.redis_url
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        """获取 Redis 客户端（延迟初始化）"""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # 保持 bytes 以存储向量
            )
        return self._client

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._client:
            await self._client.close()
            self._client = None

    def _make_key(self, query: str) -> str:
        """生成缓存 Key

        使用 SHA256 哈希查询文本：
        - 脱敏：避免敏感信息泄露到 Redis
        - 固定长度：避免 Key 过长问题

        Args:
            query: 原始查询文本

        Returns:
            缓存 Key，格式：embedding:SHA256(query)
        """
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return f"{EMBEDDING_CACHE_PREFIX}{query_hash}"

    async def get(self, query: str) -> list[float] | None:
        """获取缓存的 Embedding

        Args:
            query: 查询文本

        Returns:
            Embedding 向量，如未缓存返回 None
        """
        try:
            client = await self._get_client()
            key = self._make_key(query)

            data = await client.get(key)
            if data is None:
                logger.debug(
                    "embedding_cache_miss",
                    query_hash=key[-16:],  # 只记录后 16 位
                )
                return None

            # 解析 JSON（向量存储为 JSON 数组）
            embedding = json.loads(data.decode("utf-8"))
            logger.debug(
                "embedding_cache_hit",
                query_hash=key[-16:],
                embedding_dim=len(embedding),
            )
            return embedding

        except redis.RedisError as e:
            # 缓存失败不应影响业务
            logger.warning(
                "embedding_cache_read_failed",
                error=str(e),
            )
            return None

    async def set(self, query: str, embedding: list[float]) -> bool:
        """缓存 Embedding

        Args:
            query: 查询文本
            embedding: Embedding 向量

        Returns:
            是否成功
        """
        try:
            client = await self._get_client()
            key = self._make_key(query)

            # 存储 JSON 格式的向量
            data = json.dumps(embedding)

            await client.setex(key, EMBEDDING_CACHE_TTL_SECONDS, data.encode("utf-8"))

            logger.debug(
                "embedding_cache_set",
                query_hash=key[-16:],
                embedding_dim=len(embedding),
                ttl_days=30,
            )
            return True

        except redis.RedisError as e:
            # 缓存失败不应影响业务
            logger.warning(
                "embedding_cache_write_failed",
                error=str(e),
            )
            return False

    async def delete(self, query: str) -> bool:
        """删除缓存的 Embedding

        用于：
        - Embedding 模型升级后清除旧缓存
        - 特定查询需要强制重新计算

        Args:
            query: 查询文本

        Returns:
            是否成功删除（False 可能是 Key 不存在）
        """
        try:
            client = await self._get_client()
            key = self._make_key(query)

            result = await client.delete(key)

            logger.debug(
                "embedding_cache_delete",
                query_hash=key[-16:],
                deleted=result > 0,
            )
            return result > 0

        except redis.RedisError as e:
            logger.warning(
                "embedding_cache_delete_failed",
                error=str(e),
            )
            return False

    async def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息

        Returns:
            统计信息字典
        """
        try:
            client = await self._get_client()

            # 扫描所有 embedding 缓存 Key
            keys = []
            async for key in client.scan_iter(match=f"{EMBEDDING_CACHE_PREFIX}*"):
                keys.append(key)

            return {
                "cache_type": "embedding",
                "key_count": len(keys),
                "ttl_seconds": EMBEDDING_CACHE_TTL_SECONDS,
            }

        except redis.RedisError as e:
            logger.warning(
                "embedding_cache_stats_failed",
                error=str(e),
            )
            return {
                "cache_type": "embedding",
                "error": str(e),
            }


# 全局实例
_cache: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    """获取 Embedding 缓存实例"""
    global _cache
    if _cache is None:
        _cache = EmbeddingCache()
    return _cache
