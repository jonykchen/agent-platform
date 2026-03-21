"""Feature Flag 客户端测试"""

import pytest

from app.core.feature_flags import FeatureFlagClient, StrategyResult


class MockRedis:
    """Mock Redis 客户端"""

    def __init__(self):
        self.data = {}
        self._scan_iter_data = []

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)

    async def scan_iter(self, match=None):
        for key in self._scan_iter_data:
            if match and match.replace("*", "") in key:
                yield key

    def set_data(self, key, value):
        self.data[key] = value.encode() if isinstance(value, str) else value
        self._scan_iter_data.append(key)


@pytest.fixture
def mock_redis():
    return MockRedis()


@pytest.fixture
async def ff_client(mock_redis):
    return FeatureFlagClient(mock_redis, config_cache_ttl=60)


class TestFeatureFlagClient:
    """FeatureFlagClient 测试"""

    @pytest.mark.asyncio
    async def test_is_enabled_default(self, ff_client, mock_redis):
        """测试默认行为（flag 不存在）"""
        result = await ff_client.is_enabled("nonexistent_flag", default=False)
        assert result is False

        result = await ff_client.is_enabled("nonexistent_flag", default=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_enabled_disabled(self, ff_client, mock_redis):
        """测试禁用的 flag"""
        mock_redis.set_data("ff:test_flag", '{"enabled": false}')
        result = await ff_client.is_enabled("test_flag")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_enabled_default_strategy(self, ff_client, mock_redis):
        """测试 default 策略"""
        mock_redis.set_data("ff:test_flag", '{"enabled": true, "strategies": [{"name": "default"}]}')
        result = await ff_client.is_enabled("test_flag")
        assert result is True

    @pytest.mark.asyncio
    async def test_gradual_rollout(self, ff_client, mock_redis):
        """测试百分比灰度"""
        mock_redis.set_data("ff:test_flag", """{
            "enabled": true,
            "strategies": [{"name": "gradualRollout", "parameters": {"rolloutPercentage": 50}}]
        }""")

        # 同一用户应该得到一致结果
        context = {"user_id": "user_001"}
        result1 = await ff_client.is_enabled("test_flag", context)
        result2 = await ff_client.is_enabled("test_flag", context)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_specific_tenant(self, ff_client, mock_redis):
        """测试租户白名单"""
        mock_redis.set_data("ff:test_flag", """{
            "enabled": true,
            "strategies": [{"name": "specificTenant", "parameters": {"tenantIds": ["tenant_001", "tenant_002"]}}]
        }""")

        # 白名单租户
        result = await ff_client.is_enabled("test_flag", {"tenant_id": "tenant_001"})
        assert result is True

        # 非白名单租户
        result = await ff_client.is_enabled("test_flag", {"tenant_id": "tenant_999"})
        assert result is False

    @pytest.mark.asyncio
    async def test_specific_users(self, ff_client, mock_redis):
        """测试用户白名单"""
        mock_redis.set_data("ff:test_flag", """{
            "enabled": true,
            "strategies": [{"name": "specificUsers", "parameters": {"userIds": ["admin_001"]}}]
        }""")

        result = await ff_client.is_enabled("test_flag", {"user_id": "admin_001"})
        assert result is True

        result = await ff_client.is_enabled("test_flag", {"user_id": "normal_user"})
        assert result is False

    @pytest.mark.asyncio
    async def test_set_flag(self, ff_client, mock_redis):
        """测试设置 flag"""
        await ff_client.set_flag("new_flag", {"enabled": True})

        result = await ff_client.is_enabled("new_flag")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_flag(self, ff_client, mock_redis):
        """测试删除 flag"""
        mock_redis.set_data("ff:test_flag", '{"enabled": true}')
        await ff_client.delete_flag("test_flag")

        result = await ff_client.is_enabled("test_flag", default=False)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_variant(self, ff_client, mock_redis):
        """测试 A/B 变体获取"""
        mock_redis.set_data("ff:ab_test", """{
            "enabled": true,
            "variants": {
                "control": {"weight": 50},
                "treatment": {"weight": 50}
            }
        }""")

        context = {"user_id": "user_001"}
        variant = await ff_client.get_variant("ab_test", context)

        # 应该返回 control 或 treatment
        assert variant in ["control", "treatment"]

        # 同一用户应该得到一致结果
        variant2 = await ff_client.get_variant("ab_test", context)
        assert variant == variant2
