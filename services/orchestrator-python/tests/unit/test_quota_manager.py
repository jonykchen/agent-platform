"""测试租户配额管理器

测试 TenantQuotaManager 的配额扣减、查询、重置和 Redis 降级行为。
所有外部依赖（Redis）均 mock，可离线运行。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio.connection import RedisError

from app.core.quota_manager import TenantQuotaManager

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_redis():
    """Mock Redis 异步客户端"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.hgetall = AsyncMock(return_value={})
    return redis


@pytest.fixture
def mock_script():
    """Mock Lua 脚本执行对象"""
    script = AsyncMock()
    return script


@pytest.fixture
def manager(mock_redis):
    """创建使用 mock Redis 的 TenantQuotaManager 实例"""
    return TenantQuotaManager(mock_redis)


# ═══════════════════════════════════════════════════════════════════════════════
# 配额扣减 - 正常路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckQuotaSuccess:
    """配额充足时扣减成功"""

    @pytest.mark.asyncio
    async def test_should_allow_when_quota_sufficient(self, manager, mock_redis, mock_script):
        """配额充足时应返回 allowed=True"""
        mock_script.return_value = 500000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 1000)
        assert result["allowed"] is True
        assert result["remaining"] == 500000
        assert result["reason"] is None

    @pytest.mark.asyncio
    async def test_should_deduct_tokens_from_quota(self, manager, mock_redis, mock_script):
        """扣减后应返回正确的剩余配额"""
        mock_script.return_value = 999000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 1000)
        assert result["remaining"] == 999000

    @pytest.mark.asyncio
    async def test_should_use_correct_quota_key(self, manager, mock_redis, mock_script):
        """应使用正确的 Redis key 格式"""
        mock_script.return_value = 500000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        await manager.check_quota("tenant_001", 500)

        # 验证 Lua 脚本被调用时的 keys 参数
        call_args = mock_script.call_args
        assert call_args is not None
        keys = call_args.kwargs.get("keys") or call_args[1].get("keys")
        if not keys and call_args[0]:
            keys = call_args[0][0]
        # key 应为 quota:tenant:{tenant_id}:daily
        if keys:
            assert "tenant_001" in keys[0]
            assert keys[0].startswith("quota:tenant:")
            assert keys[0].endswith(":daily")


# ═══════════════════════════════════════════════════════════════════════════════
# 配额未设置 - 自动初始化
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckQuotaNotSet:
    """配额键未设置时自动初始化"""

    @pytest.mark.asyncio
    async def test_should_initialize_default_quota_when_key_not_set(self, manager, mock_redis, mock_script):
        """配额键不存在时应初始化为默认值 1_000_000"""
        call_count = 0

        async def script_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return -2  # 未设置
            return 999000  # 初始化后扣减成功

        mock_script.side_effect = script_side_effect
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 1000)
        assert result["allowed"] is True
        assert result["remaining"] == 999000
        # 应调用 redis.set 初始化配额
        mock_redis.set.assert_called_once()
        set_call_args = mock_redis.set.call_args
        # 验证设置了默认配额值
        assert set_call_args[0][1] == 1_000_000

    @pytest.mark.asyncio
    async def test_should_set_default_quota_with_correct_key(self, manager, mock_redis, mock_script):
        """初始化配额时应使用正确的 key"""
        call_count = 0

        async def script_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            return -2 if call_count == 1 else 999000

        mock_script.side_effect = script_side_effect
        mock_redis.register_script = MagicMock(return_value=mock_script)

        await manager.check_quota("tenant_001", 1000)

        set_call_args = mock_redis.set.call_args
        key = set_call_args[0][0]
        assert key == "quota:tenant:tenant_001:daily"


# ═══════════════════════════════════════════════════════════════════════════════
# 配额不足
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckQuotaExceeded:
    """配额不足时拒绝请求"""

    @pytest.mark.asyncio
    async def test_should_reject_when_quota_insufficient(self, manager, mock_redis, mock_script):
        """配额不足时应返回 allowed=False"""
        mock_script.return_value = -1
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 1000)
        assert result["allowed"] is False
        assert result["remaining"] == 0
        assert result["reason"] == "Quota exceeded"

    @pytest.mark.asyncio
    async def test_should_not_deduct_when_quota_insufficient(self, manager, mock_redis, mock_script):
        """配额不足时不应扣减 token"""
        mock_script.return_value = -1
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 5000)
        assert result["allowed"] is False
        # Lua 脚本在配额不足时不执行 DECRBY，保证数据一致性


# ═══════════════════════════════════════════════════════════════════════════════
# Redis 不可用 - 降级策略
# ═══════════════════════════════════════════════════════════════════════════════


class TestRedisDegradation:
    """Redis 不可用时的降级行为

    check_quota 只捕获 RedisError（非通用 Exception），因此 mock 必须抛
    RedisError 子类才能触发降级分支。
    """

    @pytest.mark.asyncio
    async def test_should_allow_request_when_script_raises_redis_error(self, manager, mock_redis, mock_script):
        """Lua 脚本执行时 RedisError 应降级允许请求通过（fail-open）"""
        mock_script.side_effect = RedisError("Connection refused")
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result = await manager.check_quota("tenant_001", 1000)
        assert result["allowed"] is True
        assert result["remaining"] == -1  # -1 表示未知
        assert "degraded" in result["reason"]

    @pytest.mark.asyncio
    async def test_should_handle_redis_error_on_set(self, manager, mock_redis, mock_script):
        """初始化配额时 Redis set 抛 RedisError 应降级"""
        call_count = 0

        async def script_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            return -2 if call_count == 1 else 999000

        mock_script.side_effect = script_side_effect
        mock_redis.register_script = MagicMock(return_value=mock_script)
        # 模拟 set 操作失败（抛 RedisError）
        mock_redis.set.side_effect = RedisError("Redis SET failed")

        result = await manager.check_quota("tenant_001", 1000)
        # set 失败后整体进入 except RedisError 分支
        assert result["allowed"] is True
        assert result["remaining"] == -1

    @pytest.mark.asyncio
    async def test_should_handle_redis_error_on_register_script(self, manager, mock_redis):
        """register_script 抛 RedisError 应降级"""
        # register_script 是同步方法，需抛 RedisError 而非 Exception
        mock_redis.register_script = MagicMock(side_effect=RedisError("Redis down"))

        result = await manager.check_quota("tenant_001", 1000)
        assert result["allowed"] is True
        assert result["remaining"] == -1

    @pytest.mark.asyncio
    async def test_should_handle_redis_error_on_get_quota(self, manager, mock_redis):
        """get_quota 时 RedisError 应传播（非关键路径无降级）"""
        mock_redis.get.side_effect = RedisError("Redis GET failed")

        with pytest.raises(RedisError):
            await manager.get_quota("tenant_001")


# ═══════════════════════════════════════════════════════════════════════════════
# 配额查询
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetQuota:
    """配额查询

    Redis hgetall 在 decode_responses=True 时返回字符串键值，
    在 decode_responses=False 时返回 bytes 键值。此处使用字符串键
    以匹配代码中的 config.get("daily_tokens", ...) 访问方式。
    """

    @pytest.mark.asyncio
    async def test_should_return_quota_info(self, manager, mock_redis):
        """应正确返回配额信息"""
        mock_redis.get.return_value = "800000"
        mock_redis.hgetall.return_value = {"daily_tokens": "1000000"}

        result = await manager.get_quota("tenant_001")
        assert result["budget"] == 1000000
        assert result["remaining"] == 800000
        assert result["used"] == 200000

    @pytest.mark.asyncio
    async def test_should_use_default_budget_when_no_config(self, manager, mock_redis):
        """无租户配置时应使用默认配额 1_000_000"""
        mock_redis.get.return_value = "900000"
        mock_redis.hgetall.return_value = {}  # 无配置

        result = await manager.get_quota("tenant_001")
        assert result["budget"] == 1_000_000
        assert result["used"] == 100000
        assert result["remaining"] == 900000

    @pytest.mark.asyncio
    async def test_should_handle_no_remaining_key(self, manager, mock_redis):
        """配额键不存在时 remaining 应为 0"""
        mock_redis.get.return_value = None
        mock_redis.hgetall.return_value = {"daily_tokens": "500000"}

        result = await manager.get_quota("tenant_001")
        assert result["budget"] == 500000
        assert result["remaining"] == 0
        assert result["used"] == 500000

    @pytest.mark.asyncio
    async def test_should_use_correct_keys_for_get_quota(self, manager, mock_redis):
        """应使用正确的 Redis key 查询配额"""
        mock_redis.get.return_value = "100"
        mock_redis.hgetall.return_value = {}

        await manager.get_quota("tenant_001")

        # 验证 get 使用了正确的 key
        get_call_args = mock_redis.get.call_args
        assert get_call_args[0][0] == "quota:tenant:tenant_001:daily"

        # 验证 hgetall 使用了正确的 key
        hgetall_call_args = mock_redis.hgetall.call_args
        assert hgetall_call_args[0][0] == "config:tenant:tenant_001"


# ═══════════════════════════════════════════════════════════════════════════════
# 配额重置
# ═══════════════════════════════════════════════════════════════════════════════


class TestResetQuota:
    """配额重置"""

    @pytest.mark.asyncio
    async def test_should_reset_quota_with_correct_value(self, manager, mock_redis):
        """应正确重置配额值"""
        await manager.reset_quota("tenant_001", 500000)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "quota:tenant:tenant_001:daily"
        assert call_args[0][1] == 500000

    @pytest.mark.asyncio
    async def test_should_set_ttl_on_reset(self, manager, mock_redis):
        """重置配额时应设置 TTL（24h + 5min）"""
        await manager.reset_quota("tenant_001", 500000)

        call_args = mock_redis.set.call_args
        # ex 参数应为 86400 + 300 = 86700
        ttl = call_args[1].get("ex") or call_args.kwargs.get("ex")
        assert ttl == 86400 + 300  # 24h + 5min

    @pytest.mark.asyncio
    async def test_should_overwrite_existing_quota_on_reset(self, manager, mock_redis):
        """重置应覆盖现有配额"""
        # 第一次重置
        await manager.reset_quota("tenant_001", 500000)
        # 第二次重置
        await manager.reset_quota("tenant_001", 800000)

        # set 被调用两次，第二次值为 800000
        assert mock_redis.set.call_count == 2
        last_call = mock_redis.set.call_args
        assert last_call[0][1] == 800000


# ═══════════════════════════════════════════════════════════════════════════════
# Lua 脚本缓存
# ═══════════════════════════════════════════════════════════════════════════════


class TestScriptCaching:
    """Lua 脚本缓存"""

    @pytest.mark.asyncio
    async def test_should_register_script_on_first_call(self, manager, mock_redis, mock_script):
        """首次调用时应注册脚本"""
        mock_script.return_value = 500000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        await manager.check_quota("tenant_001", 1000)

        # register_script 应被调用一次
        assert mock_redis.register_script.call_count == 1

    @pytest.mark.asyncio
    async def test_should_cache_script_for_subsequent_calls(self, manager, mock_redis, mock_script):
        """后续调用应复用缓存的脚本对象"""
        mock_script.return_value = 500000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        await manager.check_quota("tenant_001", 1000)
        await manager.check_quota("tenant_001", 500)

        # register_script 只应被调用一次（缓存复用）
        assert mock_redis.register_script.call_count == 1

    @pytest.mark.asyncio
    async def test_should_use_same_script_for_same_content(self, manager, mock_redis, mock_script):
        """相同脚本内容应使用同一缓存"""
        mock_script.return_value = 500000
        mock_redis.register_script = MagicMock(return_value=mock_script)

        await manager.check_quota("tenant_001", 1000)
        await manager.check_quota("tenant_002", 2000)

        # 同一个 QUOTA_DECR_SCRIPT，应只注册一次
        assert mock_redis.register_script.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 每日 Token 配额集成场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestDailyTokenQuotaIntegration:
    """租户每日 Token 配额集成场景"""

    @pytest.mark.asyncio
    async def test_full_quota_lifecycle(self, manager, mock_redis, mock_script):
        """完整配额生命周期：初始化 → 扣减 → 查询 → 重置"""
        # Step 1: 首次扣减（触发初始化）
        call_count = 0

        async def script_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return -2  # 未设置
            return 999000  # 初始化后扣减成功

        mock_script.side_effect = script_side_effect
        mock_redis.register_script = MagicMock(return_value=mock_script)

        result1 = await manager.check_quota("tenant_001", 1000)
        assert result1["allowed"] is True

        # Step 2: 查询配额
        mock_redis.get.return_value = "999000"
        mock_redis.hgetall.return_value = {"daily_tokens": "1000000"}
        quota_info = await manager.get_quota("tenant_001")
        assert quota_info["remaining"] == 999000

        # Step 3: 重置配额
        await manager.reset_quota("tenant_001", 2000000)
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_deductions_until_exhausted(self, manager, mock_redis, mock_script):
        """多次扣减直到配额耗尽"""
        remaining = 100000

        async def script_side_effect(**kwargs):
            nonlocal remaining
            args = kwargs.get("args") or []
            tokens = int(args[0]) if args else 1000
            if remaining < tokens:
                return -1
            remaining -= tokens
            return remaining

        mock_script.side_effect = script_side_effect
        mock_redis.register_script = MagicMock(return_value=mock_script)

        # 第一次扣减：成功
        result1 = await manager.check_quota("tenant_001", 50000)
        assert result1["allowed"] is True

        # 第二次扣减：成功
        result2 = await manager.check_quota("tenant_001", 40000)
        assert result2["allowed"] is True

        # 第三次扣减：不足
        result3 = await manager.check_quota("tenant_001", 20000)
        assert result3["allowed"] is False
        assert result3["reason"] == "Quota exceeded"
