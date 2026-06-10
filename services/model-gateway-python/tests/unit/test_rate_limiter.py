"""分布式限流器单元测试"""

from unittest.mock import AsyncMock

import pytest

from app.core.rate_limiter import DistributedRateLimiter


@pytest.fixture
def redis_mock():
    redis = AsyncMock()
    redis.script_load = AsyncMock(return_value="sha123")
    return redis


async def test_allows_within_limit(redis_mock):
    """窗口内未超限应放行。"""
    # Lua 返回 [allowed, current, limit]
    redis_mock.evalsha = AsyncMock(return_value=[1, 3, 120])
    limiter = DistributedRateLimiter(redis_mock, window_s=60, default_limit=120)

    result = await limiter.check("tenant:t1:model:qwen-max", "req-1", now_ms=1000)

    assert result.allowed is True
    assert result.current == 3
    assert result.limit == 120


async def test_blocks_when_over_limit(redis_mock):
    """超过上限应拒绝并给出 retry_after。"""
    redis_mock.evalsha = AsyncMock(return_value=[0, 120, 120])
    limiter = DistributedRateLimiter(redis_mock, window_s=60, default_limit=120)

    result = await limiter.check("tenant:t1:model:qwen-max", "req-2", now_ms=2000)

    assert result.allowed is False
    assert result.retry_after_s == 60


async def test_custom_limit_overrides_default(redis_mock):
    """显式 limit 应覆盖默认值并传给脚本。"""
    redis_mock.evalsha = AsyncMock(return_value=[1, 1, 10])
    limiter = DistributedRateLimiter(redis_mock, window_s=60, default_limit=120)

    result = await limiter.check("scope", "req-3", limit=10, now_ms=3000)

    assert result.limit == 10
    # 校验脚本入参中的 limit
    args = redis_mock.evalsha.call_args.args
    assert "10" in args


async def test_fail_open_on_redis_error(redis_mock):
    """Redis 故障且 fail_open=True 时应放行。"""
    redis_mock.evalsha = AsyncMock(side_effect=ConnectionError("redis down"))
    limiter = DistributedRateLimiter(redis_mock, window_s=60, default_limit=120, fail_open=True)

    result = await limiter.check("scope", "req-4", now_ms=4000)

    assert result.allowed is True


async def test_fail_close_on_redis_error(redis_mock):
    """Redis 故障且 fail_open=False 时应拒绝。"""
    redis_mock.evalsha = AsyncMock(side_effect=ConnectionError("redis down"))
    limiter = DistributedRateLimiter(redis_mock, window_s=60, default_limit=120, fail_open=False)

    result = await limiter.check("scope", "req-5", now_ms=5000)

    assert result.allowed is False
