"""分布式限流器（Redis 滑动窗口）

【设计目标】
Model Gateway 是所有模型调用的统一入口，必须防止单个租户/Provider
在短时间内打爆下游 LLM 服务（触发 Provider 侧限流、拖垮整体可用性）。

【算法选型】滑动窗口日志（Sliding Window Log）
┌────────────────────┬──────────────────────────────┬──────────────────────────┐
│ 算法               │ 优点                         │ 缺点                     │
├────────────────────┼──────────────────────────────┼──────────────────────────┤
│ 固定窗口 INCR      │ 实现简单、内存小             │ 窗口边界突刺（2 倍流量） │
│ ✓ 滑动窗口 ZSET    │ 精确、无边界突刺             │ 内存随请求数增长         │
│ 令牌桶             │ 平滑限流、支持突发           │ 实现稍复杂               │
└────────────────────┴──────────────────────────────┴──────────────────────────┘

选择滑动窗口日志：实现可控、计数精确，配合 Lua 脚本保证原子性
（去除过期记录 + 计数 + 写入 在单次往返内完成，避免并发竞态）。

【容错】fail-open
限流器自身依赖 Redis，若 Redis 故障，默认放行（fail-open），
避免限流组件成为新的单点故障。可通过配置切换为 fail-close。
"""

from __future__ import annotations

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()

# 滑动窗口 Lua 脚本：原子地清理过期成员、统计当前窗口内请求数、按需写入新请求。
# KEYS[1] = 限流键
# ARGV[1] = 当前时间戳（毫秒）
# ARGV[2] = 窗口大小（毫秒）
# ARGV[3] = 上限
# ARGV[4] = 唯一成员（请求 ID，去重用）
# 返回: {allowed(0/1), current_count, limit}
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, window)
    return {1, count + 1, limit}
else
    redis.call('PEXPIRE', key, window)
    return {0, count, limit}
end
"""


class RateLimitResult:
    """限流判定结果"""

    def __init__(self, allowed: bool, current: int, limit: int, retry_after_s: int):
        self.allowed = allowed
        self.current = current
        self.limit = limit
        self.retry_after_s = retry_after_s


class DistributedRateLimiter:
    """基于 Redis 的分布式滑动窗口限流器"""

    def __init__(
        self,
        redis: Redis,
        window_s: int = 60,
        default_limit: int = 120,
        fail_open: bool = True,
    ):
        self._redis = redis
        self._window_ms = window_s * 1000
        self._window_s = window_s
        self._default_limit = default_limit
        self._fail_open = fail_open
        self._script_sha: str | None = None

    async def _ensure_script(self) -> str:
        """惰性注册 Lua 脚本，返回其 SHA。"""
        if self._script_sha is None:
            self._script_sha = await self._redis.script_load(_SLIDING_WINDOW_LUA)
        return self._script_sha

    async def check(
        self,
        scope: str,
        request_id: str,
        limit: int | None = None,
        now_ms: int | None = None,
    ) -> RateLimitResult:
        """检查并消费一次配额。

        Args:
            scope: 限流维度键（如 "tenant:t1:provider:qwen"）
            request_id: 唯一请求标识（用于滑动窗口去重）
            limit: 本次使用的上限，None 则用默认值
            now_ms: 当前时间戳（毫秒），便于测试注入；生产由调用方传入

        Returns:
            RateLimitResult（allowed 表示是否放行）
        """
        effective_limit = limit if limit is not None else self._default_limit
        key = f"ratelimit:{scope}"

        # 时间戳由调用方注入（避免在限流器内部直接调用时间函数，便于测试）
        if now_ms is None:
            import time

            now_ms = int(time.time() * 1000)

        try:
            sha = await self._ensure_script()
            result = await self._redis.evalsha(
                sha,
                1,
                key,
                str(now_ms),
                str(self._window_ms),
                str(effective_limit),
                request_id,
            )
            allowed = bool(result[0])
            current = int(result[1])
            return RateLimitResult(
                allowed=allowed,
                current=current,
                limit=effective_limit,
                retry_after_s=self._window_s,
            )
        except Exception as e:
            # Redis 故障：按配置 fail-open / fail-close
            logger.warning(
                "rate_limiter_backend_error",
                scope=scope,
                error=str(e),
                fail_open=self._fail_open,
            )
            return RateLimitResult(
                allowed=self._fail_open,
                current=0,
                limit=effective_limit,
                retry_after_s=self._window_s,
            )


_rate_limiter: DistributedRateLimiter | None = None


def init_rate_limiter(redis: Redis) -> DistributedRateLimiter:
    """初始化全局限流器（在应用启动时调用）。"""
    global _rate_limiter
    from app.core.config import config

    _rate_limiter = DistributedRateLimiter(
        redis=redis,
        window_s=getattr(config, "rate_limit_window_s", 60),
        default_limit=getattr(config, "rate_limit_default_rpm", 120),
        fail_open=getattr(config, "rate_limit_fail_open", True),
    )
    return _rate_limiter


def get_rate_limiter() -> DistributedRateLimiter | None:
    """获取全局限流器（未初始化返回 None）。"""
    return _rate_limiter
