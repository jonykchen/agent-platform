"""Token 计数器

统计 Token 使用量，支持多层级配额检查。
"""

import time
from datetime import datetime, date

import structlog

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = structlog.get_logger()


class TokenCounter:
    """Token 计数器"""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._client = None

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

    def _today(self) -> str:
        return date.today().isoformat()

    async def record_usage(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """记录 Token 使用

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            session_id: 会话 ID
            model: 模型名称
            prompt_tokens: 输入 token
            completion_tokens: 输出 token
        """
        total_tokens = prompt_tokens + completion_tokens
        today = self._today()

        client = await self._get_client()
        if client:
            try:
                # 租户日用量
                await client.incrby(f"tokens:tenant:{tenant_id}:{today}", total_tokens)

                # 用户日用量
                await client.incrby(f"tokens:user:{tenant_id}:{user_id}:{today}", total_tokens)

                # 会话用量
                if session_id:
                    await client.incrby(f"tokens:session:{session_id}", total_tokens)

                # 模型用量
                await client.incrby(f"tokens:model:{model}:{today}", total_tokens)

                # 设置过期时间（30 天）
                for key in [
                    f"tokens:tenant:{tenant_id}:{today}",
                    f"tokens:user:{tenant_id}:{user_id}:{today}",
                    f"tokens:model:{model}:{today}",
                ]:
                    await client.expire(key, 86400 * 30)

            except Exception as e:
                logger.warning("Failed to record token usage", error=str(e))

        logger.debug(
            "Token usage recorded",
            tenant_id=tenant_id,
            user_id=user_id,
            model=model,
            total_tokens=total_tokens,
        )

    async def get_tenant_usage(self, tenant_id: str, day: str | None = None) -> int:
        """获取租户日用量"""
        day = day or self._today()
        client = await self._get_client()

        if client:
            try:
                key = f"tokens:tenant:{tenant_id}:{day}"
                value = await client.get(key)
                return int(value) if value else 0
            except Exception as e:
                logger.warning("Failed to get tenant usage", error=str(e))

        return 0

    async def get_user_usage(
        self,
        tenant_id: str,
        user_id: str,
        day: str | None = None,
    ) -> int:
        """获取用户日用量"""
        day = day or self._today()
        client = await self._get_client()

        if client:
            try:
                key = f"tokens:user:{tenant_id}:{user_id}:{day}"
                value = await client.get(key)
                return int(value) if value else 0
            except Exception as e:
                logger.warning("Failed to get user usage", error=str(e))

        return 0

    async def check_quota(
        self,
        tenant_id: str,
        user_id: str,
        estimated_tokens: int,
        tenant_quota: int = 10_000_000,
        user_quota: int = 100_000,
    ) -> tuple[bool, str]:
        """检查配额

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            estimated_tokens: 预估 token
            tenant_quota: 租户配额
            user_quota: 用户配额

        Returns:
            (是否通过, 错误消息)
        """
        # 检查租户配额
        tenant_usage = await self.get_tenant_usage(tenant_id)
        if tenant_usage + estimated_tokens > tenant_quota:
            return False, f"租户配额已用尽 ({tenant_usage}/{tenant_quota})"

        # 检查用户配额
        user_usage = await self.get_user_usage(tenant_id, user_id)
        if user_usage + estimated_tokens > user_quota:
            return False, f"今日配额已用尽 ({user_usage}/{user_quota})"

        return True, ""


# 全局实例
_counter = None


def get_token_counter() -> TokenCounter:
    """获取 Token 计数器实例"""
    global _counter
    if _counter is None:
        _counter = TokenCounter()
    return _counter