"""测试数据库连接池和 gRPC 客户端"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDatabasePool:
    """数据库连接池测试"""

    @pytest.mark.asyncio
    async def test_init_database_pool_success(self):
        """测试连接池初始化成功"""
        mock_pool = MagicMock()
        mock_pool.get_size = MagicMock(return_value=20)

        with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
            from app.infrastructure.database import init_database_pool

            pool = await init_database_pool()

            assert pool is not None
            assert pool.get_size() == 20

    @pytest.mark.asyncio
    async def test_init_database_pool_with_url(self):
        """测试使用 URL 创建连接池"""
        mock_pool = MagicMock()

        with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)) as mock_create:
            # 清除全局池
            import app.infrastructure.database as db_module
            from app.infrastructure.database import init_database_pool

            db_module._pool = None

            await init_database_pool()

            # 验证调用参数
            call_args = mock_create.call_args
            assert "dsn" in call_args[1]

    @pytest.mark.asyncio
    async def test_close_database_pool(self):
        """测试关闭连接池"""
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        mock_pool.get_size = MagicMock(return_value=10)
        mock_pool.get_idle_size = MagicMock(return_value=8)

        import app.infrastructure.database as db_module

        db_module._pool = mock_pool

        from app.infrastructure.database import close_database_pool

        await close_database_pool()

        mock_pool.close.assert_called_once()
        assert db_module._pool is None

    @pytest.mark.asyncio
    async def test_get_connection_context(self):
        """测试获取连接上下文"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(),
            )
        )

        import app.infrastructure.database as db_module

        db_module._pool = mock_pool

        from app.infrastructure.database import get_connection

        async with get_connection() as conn:
            assert conn is not None

    @pytest.mark.asyncio
    async def test_fetch_one(self):
        """测试查询单行"""
        mock_record = {"id": 1, "name": "test"}
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(),
            )
        )

        import app.infrastructure.database as db_module

        db_module._pool = mock_pool

        from app.infrastructure.database import fetch_one

        result = await fetch_one("SELECT * FROM users WHERE id = $1", 1)

        assert result == mock_record

    @pytest.mark.asyncio
    async def test_execute_many(self):
        """测试批量执行"""
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(),
            )
        )

        import app.infrastructure.database as db_module

        db_module._pool = mock_pool

        from app.infrastructure.database import execute_many

        args_list = [(1, "a"), (2, "b")]
        await execute_many("INSERT INTO users (id, name) VALUES ($1, $2)", args_list)

        mock_conn.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        """测试健康检查 - 健康"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool = MagicMock()
        mock_pool.get_size = MagicMock(return_value=20)
        mock_pool.get_idle_size = MagicMock(return_value=15)
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(),
            )
        )

        import app.infrastructure.database as db_module

        db_module._pool = mock_pool

        from app.infrastructure.database import check_database_health

        result = await check_database_health()

        assert result["status"] == "healthy"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """测试健康检查 - 不健康"""
        import app.infrastructure.database as db_module

        db_module._pool = None

        from app.infrastructure.database import check_database_health

        result = await check_database_health()

        assert result["status"] == "unhealthy"


class TestGrpcClient:
    """gRPC 客户端测试"""

    @pytest.mark.asyncio
    async def test_init_grpc_client_success(self):
        """测试 gRPC 客户端初始化"""
        mock_channel = AsyncMock()
        mock_channel.channel_ready = AsyncMock()

        with patch("grpc.aio.insecure_channel", MagicMock(return_value=mock_channel)):
            import app.infrastructure.grpc_client as grpc_module

            grpc_module._channel = None

            from app.infrastructure.grpc_client import init_grpc_client

            channel = await init_grpc_client()

            assert channel is not None

    @pytest.mark.asyncio
    async def test_close_grpc_client(self):
        """测试关闭 gRPC 客户端"""
        mock_channel = AsyncMock()
        mock_channel.close = AsyncMock()

        import app.infrastructure.grpc_client as grpc_module

        grpc_module._channel = mock_channel
        grpc_module._stub_cache = {"test_stub": MagicMock()}

        from app.infrastructure.grpc_client import close_grpc_client

        await close_grpc_client()

        mock_channel.close.assert_called_once()
        assert grpc_module._stub_cache == {}

    def test_get_stub_caches(self):
        """测试 Stub 缓存"""
        mock_channel = MagicMock()
        mock_stub_class = MagicMock()
        mock_stub_instance = MagicMock()
        mock_stub_class.__name__ = "TestStub"
        mock_stub_class.return_value = mock_stub_instance

        import app.infrastructure.grpc_client as grpc_module

        grpc_module._channel = mock_channel
        grpc_module._stub_cache = {}

        from app.infrastructure.grpc_client import get_stub

        # 第一次调用创建
        stub1 = get_stub(mock_stub_class)
        assert stub1 == mock_stub_instance
        assert "TestStub" in grpc_module._stub_cache

        # 第二次调用复用
        stub2 = get_stub(mock_stub_class)
        assert stub2 == stub1

    @pytest.mark.asyncio
    async def test_check_grpc_health_healthy(self):
        """测试 gRPC 健康检查 - 健康"""
        import grpc

        mock_channel = MagicMock()
        mock_channel.get_state = MagicMock(return_value=grpc.ChannelConnectivity.READY)

        import app.infrastructure.grpc_client as grpc_module

        grpc_module._channel = mock_channel

        from app.infrastructure.grpc_client import check_grpc_health

        result = await check_grpc_health()

        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_grpc_health_unhealthy(self):
        """测试 gRPC 健康检查 - 不健康"""
        import app.infrastructure.grpc_client as grpc_module

        grpc_module._channel = None

        from app.infrastructure.grpc_client import check_grpc_health

        result = await check_grpc_health()

        assert result["status"] == "unhealthy"
