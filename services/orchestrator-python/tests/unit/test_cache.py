"""测试双层缓存"""

from unittest.mock import AsyncMock

import pytest

from app.core.cache import (
    CacheManager,
    DualLayerCache,
    get_cache_manager,
    init_cache_manager,
)


class TestDualLayerCache:
    """测试双层缓存"""

    @pytest.fixture
    def mock_redis(self):
        """创建 Mock Redis"""
        return AsyncMock()

    @pytest.fixture
    def cache(self, mock_redis):
        """创建缓存实例"""
        return DualLayerCache(
            redis=mock_redis,
            name="test",
            local_maxsize=100,
            ttl=60,
        )

    def test_hash_key(self):
        """测试键哈希"""
        key1 = DualLayerCache._hash_key("test query")
        key2 = DualLayerCache._hash_key({"query": "test", "param": 1})

        assert len(key1) == 16
        assert len(key2) == 16
        assert key1 != key2

    def test_same_dict_hash(self):
        """测试相同字典生成相同哈希"""
        key1 = DualLayerCache._hash_key({"a": 1, "b": 2})
        key2 = DualLayerCache._hash_key({"b": 2, "a": 1})  # 顺序不同

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_get_l1_hit(self, cache, mock_redis):
        """测试 L1 缓存命中"""
        # 设置 L1 缓存
        cache._local_cache["test_key"] = {"data": "value"}

        result = await cache.get("test_key")

        assert result == {"data": "value"}
        # 不应该调用 Redis
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_l2_hit(self, cache, mock_redis):
        """测试 L2 缓存命中"""
        import json

        # L1 没有，L2 有
        mock_redis.get = AsyncMock(return_value=json.dumps({"data": "from_redis"}))

        result = await cache.get("test_key")

        assert result == {"data": "from_redis"}
        # 应该回填 L1
        assert cache._local_cache.get("test_key") == {"data": "from_redis"}

    @pytest.mark.asyncio
    async def test_get_miss(self, cache, mock_redis):
        """测试缓存未命中"""
        mock_redis.get = AsyncMock(return_value=None)

        result = await cache.get("missing_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set(self, cache, mock_redis):
        """测试设置缓存"""
        await cache.set("new_key", {"data": "new_value"})

        # 检查 L1
        assert cache._local_cache.get("new_key") == {"data": "new_value"}

        # 检查 L2
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, cache, mock_redis):
        """测试删除缓存"""
        # 先设置
        cache._local_cache["delete_key"] = {"data": "value"}

        await cache.delete("delete_key")

        # 检查 L1
        assert "delete_key" not in cache._local_cache

        # 检查 L2
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_set_existing(self, cache, mock_redis):
        """测试 get_or_set 已存在"""
        cache._local_cache["existing"] = {"data": "cached"}

        result = await cache.get_or_set("existing", lambda: {"new": "data"})

        assert result == {"data": "cached"}

    @pytest.mark.asyncio
    async def test_get_or_set_new(self, cache, mock_redis):
        """测试 get_or_set 新值"""
        mock_redis.get = AsyncMock(return_value=None)

        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"computed": "value"}

        result = await cache.get_or_set("new_key", factory)

        assert result == {"computed": "value"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_or_set_async_factory(self, cache, mock_redis):
        """测试 get_or_set 异步工厂"""
        mock_redis.get = AsyncMock(return_value=None)

        async def async_factory():
            return {"async": "result"}

        result = await cache.get_or_set("async_key", async_factory)

        assert result == {"async": "result"}

    def test_get_stats(self, cache):
        """测试获取统计"""
        cache._hit_count = 10
        cache._miss_count = 5

        stats = cache.get_stats()

        assert stats["hit_count"] == 10
        assert stats["miss_count"] == 5
        assert abs(stats["hit_rate"] - 10 / 15) < 0.001
        assert stats["name"] == "test"

    def test_clear(self, cache):
        """测试清空缓存"""
        cache._local_cache["key1"] = "value1"
        cache._local_cache["key2"] = "value2"

        cache.clear()

        assert len(cache._local_cache) == 0


class TestCacheManager:
    """测试缓存管理器"""

    @pytest.fixture
    def manager(self):
        """创建缓存管理器"""
        mock_redis = AsyncMock()
        return CacheManager(mock_redis)

    def test_get_cache_creates_new(self, manager):
        """测试创建新缓存"""
        cache = manager.get_cache("new_cache")

        assert cache is not None
        assert cache._name == "new_cache"

    def test_get_cache_reuses_existing(self, manager):
        """测试复用已存在的缓存"""
        cache1 = manager.get_cache("shared")
        cache2 = manager.get_cache("shared")

        assert cache1 is cache2

    def test_get_rag_cache(self, manager):
        """测试获取 RAG 缓存"""
        cache = manager.get_rag_cache()

        assert cache._name == "rag"

    def test_get_tool_schema_cache(self, manager):
        """测试获取工具 Schema 缓存"""
        cache = manager.get_tool_schema_cache()

        assert cache._name == "tool_schema"

    def test_get_model_list_cache(self, manager):
        """测试获取模型列表缓存"""
        cache = manager.get_model_list_cache()

        assert cache._name == "model_list"

    def test_get_all_stats(self, manager):
        """测试获取所有缓存统计"""
        manager.get_cache("cache1")
        manager.get_cache("cache2")

        stats = manager.get_all_stats()

        assert "cache1" in stats
        assert "cache2" in stats


class TestGlobalFunctions:
    """测试全局函数"""

    def test_init_cache_manager(self):
        """测试初始化缓存管理器"""
        mock_redis = AsyncMock()
        manager = init_cache_manager(mock_redis)

        assert manager is not None

    def test_get_cache_manager(self):
        """测试获取缓存管理器"""
        mock_redis = AsyncMock()
        init_cache_manager(mock_redis)

        manager = get_cache_manager()

        assert manager is not None
