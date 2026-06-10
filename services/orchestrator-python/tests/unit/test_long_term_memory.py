"""长时记忆存储单元测试（内存回退路径 + 时间衰减）

对应 P2-17：长时记忆存储验证。

验证不依赖真实数据库的核心逻辑：
- 内存存储的保存/检索往返
- 租户隔离
- 时间衰减评分（importance * decay_factor^days）
- 衰减因子从配置注入
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.memory.long_term_memory import LongTermMemoryStore, MemoryEntry


def _entry(query: str, tenant: str = "t1", user: str = "u1",
           importance: float = 0.5, days_ago: int = 0) -> MemoryEntry:
    return MemoryEntry(
        entry_id=f"e_{query}_{tenant}_{user}",
        session_id="s1",
        tenant_id=tenant,
        user_id=user,
        user_query=query,
        agent_response_summary="...",
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
        importance_score=importance,
    )


@pytest.fixture(autouse=True)
def _clear_store():
    # 内存存储是类级字典，测试间清理避免串扰
    LongTermMemoryStore._in_memory_store.clear()
    yield
    LongTermMemoryStore._in_memory_store.clear()


@pytest.fixture
def store():
    # 不传 db_url → 触发 in_memory 回退（无 SQLAlchemy 引擎依赖）
    s = LongTermMemoryStore(decay_factor=0.9)
    s._pool = "in_memory"  # 强制内存路径
    return s


class TestInMemoryRoundtrip:
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self, store):
        await store.save(_entry("查询订单状态"))
        results = await store.retrieve("订单", tenant_id="t1", user_id="u1")
        assert len(results) == 1
        assert results[0].user_query == "查询订单状态"

    @pytest.mark.asyncio
    async def test_retrieve_miss(self, store):
        await store.save(_entry("查询订单状态"))
        results = await store.retrieve("天气", tenant_id="t1", user_id="u1")
        assert results == []

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, store):
        await store.save(_entry("机密信息", tenant="t1"))
        # 另一个租户不应检索到 t1 的记忆
        results = await store.retrieve("机密", tenant_id="t2", user_id="u1")
        assert results == []


class TestTimeDecay:
    def test_decay_reduces_score_over_time(self, store):
        fresh = _entry("a", importance=1.0, days_ago=0)
        old = _entry("b", importance=1.0, days_ago=10)
        decayed = store._apply_time_decay([fresh, old])
        # 新记忆排前面，旧记忆分数被衰减
        assert decayed[0].user_query == "a"
        assert decayed[1].importance_score < 1.0
        # decay_factor=0.9，10 天 → 0.9^10 ≈ 0.349
        assert decayed[1].importance_score == pytest.approx(0.9 ** 10, rel=1e-6)

    def test_decay_factor_from_config(self):
        # 工厂从 config.memory_decay_factor 注入衰减系数
        from app.memory.long_term_memory import get_long_term_memory
        from app.core.config import config

        store = get_long_term_memory()
        assert store.decay_factor == config.memory_decay_factor


class TestEmbedding:
    """embedding 获取与解析（P0：修复零向量静默降级）"""

    @pytest.fixture
    def store(self):
        return LongTermMemoryStore(
            embedding_dim=4,
            embedding_service_url="http://model-gateway:8002/v1",
            embedding_model="text-embedding-v3",
        )

    def test_vector_literal_format(self, store):
        # 浮点列表转 pgvector 文本字面量
        assert store._to_vector_literal([1.0, 2.5, 3.0]) == "[1.0,2.5,3.0]"
        assert store._to_vector_literal([]) == "[]"
        assert store._to_vector_literal(None) == "[]"

    async def test_get_embedding_parses_openai_response(self, store, monkeypatch):
        """正确解析 OpenAI 兼容 {"data":[{"embedding":[...]}]} 响应。"""
        import httpx

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]}

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        vec = await store._get_embedding("你好")
        assert vec == [0.1, 0.2, 0.3, 0.4]

    async def test_get_embedding_raises_no_zero_vector_on_failure(self, store, monkeypatch):
        """服务失败时显式抛错，绝不返回零向量。"""
        import httpx

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        with pytest.raises(RuntimeError):
            await store._get_embedding("你好")

    async def test_get_embedding_raises_on_dim_mismatch(self, store, monkeypatch):
        """维度不匹配时抛错（防止脏向量写入）。"""
        import httpx

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": [{"embedding": [0.1, 0.2]}]}  # dim=2 != 4

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        with pytest.raises(RuntimeError):
            await store._get_embedding("你好")
