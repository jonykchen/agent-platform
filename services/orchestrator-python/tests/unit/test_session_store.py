"""测试 Redis 会话存储"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.memory.session_store import SessionStore


@pytest.fixture
def mock_redis():
    """Mock Redis 客户端"""
    redis = MagicMock()
    redis.rpush = AsyncMock()
    redis.llen = AsyncMock(return_value=10)
    redis.ltrim = AsyncMock()
    redis.expire = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    redis.exists = AsyncMock(return_value=1)
    redis.ttl = AsyncMock(return_value=3600)
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def session_store():
    """创建会话存储实例"""
    return SessionStore(redis_url="redis://localhost:6379")


class TestSessionStore:
    """会话存储测试"""

    @pytest.mark.asyncio
    async def test_append_message(self, session_store, mock_redis):
        """测试追加消息"""
        with patch.object(session_store, "_get_client", return_value=mock_redis):
            await session_store.append_message(
                session_id="session-001",
                role="user",
                content="你好",
            )

            mock_redis.rpush.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_message_with_limit(self, session_store, mock_redis):
        """测试追加消息并限制数量"""
        mock_redis.llen.return_value = 50  # 超过限制

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            await session_store.append_message(
                session_id="session-001",
                role="user",
                content="你好",
                max_turns=10,
            )

            mock_redis.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_history(self, session_store, mock_redis):
        """测试获取历史"""
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "你好", "timestamp": "2024-01-01T00:00:00"}),
            json.dumps({"role": "assistant", "content": "你好！", "timestamp": "2024-01-01T00:00:01"}),
        ]

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            history = await session_store.get_history("session-001")

            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[1]["role"] == "assistant"
            # 不应包含 timestamp
            assert "timestamp" not in history[0]

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, session_store, mock_redis):
        """测试限制历史数量"""
        with patch.object(session_store, "_get_client", return_value=mock_redis):
            await session_store.get_history("session-001", limit=5)

            mock_redis.lrange.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_session(self, session_store, mock_redis):
        """测试清空会话"""
        with patch.object(session_store, "_get_client", return_value=mock_redis):
            await session_store.clear("session-001")

            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_exists(self, session_store, mock_redis):
        """测试检查会话是否存在"""
        mock_redis.exists.return_value = 1

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            exists = await session_store.exists("session-001")

            assert exists is True

    @pytest.mark.asyncio
    async def test_session_not_exists(self, session_store, mock_redis):
        """测试会话不存在"""
        mock_redis.exists.return_value = 0

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            exists = await session_store.exists("session-nonexistent")

            assert exists is False

    @pytest.mark.asyncio
    async def test_get_session_info(self, session_store, mock_redis):
        """测试获取会话信息"""
        mock_redis.exists.return_value = 1
        mock_redis.llen.return_value = 10
        mock_redis.ttl.return_value = 3600

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            info = await session_store.get_session_info("session-001")

            assert info["exists"] is True
            assert info["message_count"] == 10
            assert info["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_get_session_info_not_exists(self, session_store, mock_redis):
        """测试获取不存在会话的信息"""
        mock_redis.exists.return_value = 0

        with patch.object(session_store, "_get_client", return_value=mock_redis):
            info = await session_store.get_session_info("session-nonexistent")

            assert info["exists"] is False

    @pytest.mark.asyncio
    async def test_close(self, session_store, mock_redis):
        """测试关闭连接"""
        session_store._client = mock_redis

        await session_store.close()

        mock_redis.aclose.assert_called_once()
        assert session_store._client is None

    def test_key_generation(self, session_store):
        """测试 Redis 键生成"""
        key = session_store._key("session-001")

        assert key == "session:session-001:history"
