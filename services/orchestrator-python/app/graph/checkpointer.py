from __future__ import annotations

"""Redis Checkpointer - 生产环境状态持久化

使用 LangGraph 官方 langgraph-checkpoint-redis 包的 AsyncRedisSaver，
替代此前自定义的 RedisSaver（未继承 BaseCheckpointSaver，导致 graph.compile 校验失败）。

特性：
- 多实例共享状态（支持水平扩展）
- 审批流程中断后恢复
- TTL 自动清理过期状态
- 异步非阻塞操作
"""

import structlog

logger = structlog.get_logger()


def get_checkpointer(environment: str, redis_url: str | None = None):
    """获取合适的 checkpointer

    当前所有环境统一使用 InMemorySaver。
    AsyncRedisSaver 需要 RedisJSON 模块（标准 Redis Alpine 不包含），
    后续可通过以下方案实现持久化：
    1. 使用 redis/redis-stack 镜像（包含 RedisJSON）
    2. 使用 AsyncPostgresSaver（基于 PostgreSQL）
    3. 使用 SQLite checkpointer

    Args:
        environment: 环境标识（local/dev/test/staging/prod）
        redis_url: Redis 连接 URL（当前未使用，保留接口兼容性）

    Returns:
        InMemorySaver
    """
    from langgraph.checkpoint.memory import InMemorySaver

    if redis_url:
        logger.info(
            "redis_checkpointer_skipped",
            reason="RedisJSON not available, using InMemorySaver",
            environment=environment,
        )
    logger.info("using_memory_checkpointer", environment=environment)
    return InMemorySaver()
