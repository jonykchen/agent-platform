"""Redis Checkpointer - 生产环境状态持久化

替代 MemorySaver，支持：
- 多实例共享状态
- 审批流程恢复
- 状态 TTL 自动清理

【设计原则】
LangGraph 的 checkpointer 接口要求实现 get/put/list 方法。
Redis 作为持久化存储，支持分布式部署场景。
"""

import json
from typing import Any

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()


class RedisSaver:
    """Redis Checkpoint 存储器

    用于生产环境，替代开发环境的 MemorySaver。

    特性：
    - 多实例共享状态（支持水平扩展）
    - 审批流程中断后恢复
    - TTL 自动清理过期状态
    - 异步非阻塞操作

    使用方式：
        checkpointer = RedisSaver(redis_url="redis://localhost:6379")
        graph.compile(checkpointer=checkpointer, interrupt_before=["approval_wait"])

    存储格式：
        Key: checkpoint:{thread_id}
        Value: JSON 序列化的 checkpoint 数据
        TTL: 默认 1 小时（可配置）
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl_seconds: int = 3600,
        key_prefix: str = "checkpoint",
    ):
        """初始化 Redis Checkpointer

        Args:
            redis_url: Redis 连接 URL
            ttl_seconds: 状态过期时间（秒），默认 1 小时
            key_prefix: 键名前缀
        """
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._key_prefix = key_prefix
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis:
        """获取 Redis 连接（懒加载）"""
        if self._redis is None:
            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _get_key(self, thread_id: str) -> str:
        """生成存储键"""
        return f"{self._key_prefix}:{thread_id}"

    async def aget(self, config: dict) -> dict | None:
        """异步获取 checkpoint

        Args:
            config: LangGraph 配置，包含 configurable.thread_id

        Returns:
            checkpoint 数据，不存在则返回 None
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            logger.warning("get_checkpoint_missing_thread_id")
            return None

        try:
            redis = await self._get_redis()
            key = self._get_key(thread_id)
            data = await redis.get(key)

            if data:
                checkpoint = json.loads(data)
                logger.debug(
                    "checkpoint_loaded",
                    thread_id=thread_id,
                    key=key,
                )
                return checkpoint

            return None

        except Exception as e:
            logger.error(
                "checkpoint_load_failed",
                thread_id=thread_id,
                error=str(e),
            )
            return None

    async def aput(self, config: dict, checkpoint: dict, metadata: dict | None = None) -> None:
        """异步存储 checkpoint

        Args:
            config: LangGraph 配置，包含 configurable.thread_id
            checkpoint: 要存储的 checkpoint 数据
            metadata: 可选的元数据
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            logger.warning("put_checkpoint_missing_thread_id")
            return

        try:
            redis = await self._get_redis()
            key = self._get_key(thread_id)

            # 序列化存储
            data = json.dumps({
                "checkpoint": checkpoint,
                "metadata": metadata,
            })

            await redis.setex(key, self._ttl, data)

            logger.debug(
                "checkpoint_saved",
                thread_id=thread_id,
                key=key,
                ttl=self._ttl,
            )

        except Exception as e:
            logger.error(
                "checkpoint_save_failed",
                thread_id=thread_id,
                error=str(e),
            )

    # 同步接口（LangGraph 兼容）
    def get(self, config: dict) -> dict | None:
        """同步获取 checkpoint（内部调用异步方法）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步上下文中，创建新任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.aget(config))
                    return future.result()
            else:
                return loop.run_until_complete(self.aget(config))
        except RuntimeError:
            return asyncio.run(self.aget(config))

    def put(self, config: dict, checkpoint: dict, metadata: dict | None = None) -> None:
        """同步存储 checkpoint（内部调用异步方法）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.aput(config, checkpoint, metadata))
                    future.result()
            else:
                loop.run_until_complete(self.aput(config, checkpoint, metadata))
        except RuntimeError:
            asyncio.run(self.aput(config, checkpoint, metadata))

    def list(self, config: dict, limit: int = 10) -> list[dict]:
        """列出所有 checkpoint（可选实现）"""
        # LangGraph 默认不使用此方法
        return []

    async def delete(self, thread_id: str) -> bool:
        """删除指定 checkpoint

        Args:
            thread_id: 会话线程 ID

        Returns:
            是否删除成功
        """
        try:
            redis = await self._get_redis()
            key = self._get_key(thread_id)
            result = await redis.delete(key)

            if result:
                logger.info("checkpoint_deleted", thread_id=thread_id)
                return True
            return False

        except Exception as e:
            logger.error(
                "checkpoint_delete_failed",
                thread_id=thread_id,
                error=str(e),
            )
            return False

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


def get_checkpointer(environment: str, redis_url: str | None = None) -> RedisSaver | "MemorySaver":
    """获取合适的 checkpointer

    Args:
        environment: 环境标识（development / production）
        redis_url: Redis 连接 URL（生产环境必需）

    Returns:
        RedisSaver（生产）或 MemorySaver（开发）
    """
    if environment == "production" and redis_url:
        logger.info("using_redis_checkpointer", redis_url=redis_url[:50] + "...")
        return RedisSaver(redis_url=redis_url)
    else:
        from app.graph.builder import MemorySaver
        logger.info("using_memory_checkpointer", reason="non_production_environment")
        return MemorySaver()
