"""测试知识库核心功能"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np


class TestPgVectorIndexer:
    """向量索引器测试"""

    @pytest.mark.asyncio
    async def test_create_document(self):
        """测试创建文档记录"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        ))

        with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
            from app.indexers.vector_indexer import PgVectorIndexer

            indexer = PgVectorIndexer("postgresql://test")
            indexer._pool = mock_pool

            doc_id = await indexer.create_document(
                tenant_id="tenant_001",
                name="test.pdf",
                file_type="pdf",
                file_size=1024,
            )

            assert doc_id is not None
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_chunks(self):
        """测试索引文档块"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(),
            __aexit__=AsyncMock(),
        ))

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        ))
        mock_pool.execute = AsyncMock()

        # Mock embedding client
        mock_embedding = np.random.rand(1536)
        mock_embedding_client = AsyncMock()
        mock_embedding_client.embed_batch = AsyncMock(return_value=[mock_embedding, mock_embedding])

        from app.indexers.vector_indexer import PgVectorIndexer

        indexer = PgVectorIndexer("postgresql://test")
        indexer._pool = mock_pool
        indexer._embedding_client = mock_embedding_client

        chunks = [
            {"content": "这是第一段内容", "metadata": {}},
            {"content": "这是第二段内容", "metadata": {}},
        ]

        chunk_ids = await indexer.index(
            document_id="doc_001",
            tenant_id="tenant_001",
            chunks=chunks,
        )

        assert len(chunk_ids) == 2

    @pytest.mark.asyncio
    async def test_search(self):
        """测试向量检索"""
        mock_result = MagicMock()
        mock_result.__getitem__ = lambda self, key: {
            "chunk_id": "chunk_001",
            "document_id": "doc_001",
            "document_name": "test.pdf",
            "chunk_index": 0,
            "content": "测试内容",
            "score": 0.95,
            "metadata": "{}",
        }[key]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_result])

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        ))

        from app.indexers.vector_indexer import PgVectorIndexer

        indexer = PgVectorIndexer("postgresql://test")
        indexer._pool = mock_pool

        query_embedding = np.random.rand(1536)
        results = await indexer.search(
            query_embedding=query_embedding,
            tenant_id="tenant_001",
            top_k=10,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk_001"

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """测试删除文档"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(),
            __aexit__=AsyncMock(),
        ))

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        ))

        from app.indexers.vector_indexer import PgVectorIndexer

        indexer = PgVectorIndexer("postgresql://test")
        indexer._pool = mock_pool

        result = await indexer.delete_document("doc_001", "tenant_001")

        assert result is True


class TestEmbeddingClient:
    """Embedding 客户端测试"""

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """测试批量 Embedding"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": [
                {"index": 0, "embedding": [0.1] * 1536},
                {"index": 1, "embedding": [0.2] * 1536},
            ]
        })
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", MagicMock(return_value=mock_client)):
            from app.indexers.vector_indexer import EmbeddingClient

            client = EmbeddingClient("http://localhost:8001", "text-embedding-ada-002")
            embeddings = await client.embed_batch(["text1", "text2"])

            assert len(embeddings) == 2
            assert len(embeddings[0]) == 1536


class TestDocumentAPI:
    """文档 API 测试"""

    def test_chunk_text(self):
        """测试文本分块"""
        from app.api.v1.documents import _chunk_text

        text = "这是第一段内容。\n\n这是第二段内容。\n\n这是第三段内容。"
        chunks = _chunk_text(text, chunk_size=50, overlap=10)

        assert len(chunks) > 0
        assert all("content" in c for c in chunks)


class TestSearchAPI:
    """检索 API 测试"""

    @pytest.mark.asyncio
    async def test_search_query(self):
        """测试检索请求"""
        # Mock embedding client
        mock_embedding = np.random.rand(1536)

        with patch(
            "app.api.v1.search._get_query_embedding",
            AsyncMock(return_value=mock_embedding.tolist()),
        ):
            with patch(
                "app.api.v1.search.get_vector_indexer",
                MagicMock(return_value=AsyncMock()),
            ):
                from app.api.v1.search import SearchRequest

                request = SearchRequest(
                    query="测试查询",
                    top_k=10,
                )

                assert request.query == "测试查询"
                assert request.top_k == 10
