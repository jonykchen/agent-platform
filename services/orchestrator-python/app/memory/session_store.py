"""Redis 会话存储

管理用户会话历史，支持滑动窗口和摘要压缩。
"""

import json
from datetime import datetime

import redis.asyncio as redis
import structlog

from app.core.config import config

logger = structlog.get_logger()


class SessionStore:
    """Redis 会话存储"""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or config.redis_url
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _key(self, session_id: str) -> str:
        """生成 Redis 键"""
        return f"session:{session_id}:history"

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        max_turns: int = 20,
    ) -> None:
        """追加消息到会话历史

        Args:
            session_id: 会话 ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            max_turns: 最大保留轮数
        """
        client = await self._get_client()
        key = self._key(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 追加消息
        await client.rpush(key, json.dumps(message))

        # 保持最大轮数（每轮包含 user + assistant）
        # 使用 LTRIM 保留最新的 N 条消息
        length = await client.llen(key)
        if length > max_turns * 2:
            await client.ltrim(key, -(max_turns * 2), -1)

        # 设置过期时间
        await client.expire(key, 86400)  # 24 小时

        logger.debug(
            "Message appended to session",
            session_id=session_id,
            role=role,
            content_length=len(content),
        )

    async def get_history(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict]:
        """获取会话历史

        Args:
            session_id: 会话 ID
            limit: 限制消息数量

        Returns:
            消息列表
        """
        client = await self._get_client()
        key = self._key(session_id)

        # 获取消息列表
        if limit:
            messages_raw = await client.lrange(key, -limit, -1)
        else:
            messages_raw = await client.lrange(key, 0, -1)

        messages = [json.loads(m) for m in messages_raw]

        # 移除 timestamp 字段，只返回 role 和 content
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def clear(self, session_id: str) -> None:
        """清空会话历史"""
        client = await self._get_client()
        key = self._key(session_id)
        await client.delete(key)
        logger.info("Session cleared", session_id=session_id)

    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        client = await self._get_client()
        key = self._key(session_id)
        return await client.exists(key) > 0

    async def get_session_info(self, session_id: str) -> dict:
        """获取会话信息"""
        client = await self._get_client()
        key = self._key(session_id)

        exists = await client.exists(key) > 0
        if not exists:
            return {"exists": False}

        length = await client.llen(key)
        ttl = await client.ttl(key)

        return {
            "exists": True,
            "message_count": length,
            "ttl_seconds": ttl,
        }


# 全局实例
_store = None


def get_session_store() -> SessionStore:
    """获取会话存储实例"""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store