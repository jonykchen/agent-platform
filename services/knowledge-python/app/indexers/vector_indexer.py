"""向量索引器 - pgvector 实现

【核心概念】向量数据库索引
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pgvector 是 PostgreSQL 的向量扩展，支持：
1. 向量存储：embedding 列存储向量
2. 相似度搜索：余弦相似度、欧氏距离、内积
3. 索引加速：IVFFlat、HNSW 索引

【数据库 Schema】
CREATE TABLE knowledge_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(32),
    file_size BIGINT,
    status VARCHAR(32) DEFAULT 'processing',
    chunk_count INT DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE knowledge_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_document(id),
    tenant_id VARCHAR(64) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunk_embedding ON knowledge_chunk
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

【参考】
- pgvector 文档: https://github.com/pgvector/pgvector
- 向量索引算法: https://github.com/pgvector/pgvector#indexing
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

import asyncpg
import numpy as np
import structlog

from app.core.config import config
from app.core.exceptions import EmbeddingServiceError

logger = structlog.get_logger()


class PgVectorIndexer:
    """pgvector 向量索引器

    功能：
    - 文档块索引（插入数据库）
    - 向量相似度检索
    - 批量操作优化
    """

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or config.database_url.replace("+asyncpg", "")
        self._pool: asyncpg.Pool | None = None
        self._embedding_client: EmbeddingClient | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        """获取数据库连接池"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=config.database_pool_size,
                command_timeout=30.0,
            )
        return self._pool

    async def _get_embedding_client(self) -> EmbeddingClient:
        """获取 Embedding 客户端"""
        if self._embedding_client is None:
            self._embedding_client = EmbeddingClient(
                base_url=config.embedding_service_url,
                model=config.embedding_model,
            )
        return self._embedding_client

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def create_document(
        self,
        tenant_id: str,
        name: str,
        file_type: str,
        file_size: int,
        metadata: dict | None = None,
    ) -> str:
        """创建文档记录

        Args:
            tenant_id: 租户 ID
            name: 文档名称
            file_type: 文件类型
            file_size: 文件大小（字节）
            metadata: 元数据

        Returns:
            文档 ID
        """
        pool = await self._get_pool()
        doc_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_document
                    (id, tenant_id, name, file_type, file_size_bytes, status, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                doc_id,
                tenant_id,
                name,
                file_type,
                file_size,
                "processing",
                json.dumps(metadata or {}),
                datetime.utcnow(),
            )

        logger.info(
            "document_created",
            document_id=doc_id,
            tenant_id=tenant_id,
            name=name,
        )

        return doc_id

    async def index(
        self,
        document_id: str,
        tenant_id: str,
        chunks: list[dict],
    ) -> list[str]:
        """索引文档块

        【处理流程】
        1. 批量生成 Embedding
        2. 批量插入数据库
        3. 更新文档状态

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID
            chunks: 文档块列表 [{"content": "...", "metadata": {...}}, ...]

        Returns:
            块 ID 列表
        """
        if not chunks:
            return []

        pool = await self._get_pool()
        embedding_client = await self._get_embedding_client()

        # 批量生成 Embedding
        contents = [c["content"] for c in chunks]

        try:
            embeddings = await embedding_client.embed_batch(contents)
        except Exception as e:
            logger.error(
                "embedding_failed",
                document_id=document_id,
                error=str(e),
            )
            raise EmbeddingServiceError(str(e))

        # 维度校验：embedding 维度必须与平台统一维度 (config.embedding_dimension)
        # 及数据库 VECTOR(dim) 一致，否则写入会触发 pgvector 维度错误或数据损坏。
        # 在写库前快速失败，避免脏数据穿透到数据库。
        expected_dim = config.embedding_dimension
        for idx, embedding in enumerate(embeddings):
            actual_dim = len(embedding)
            if actual_dim != expected_dim:
                logger.error(
                    "embedding_dimension_mismatch",
                    document_id=document_id,
                    chunk_index=idx,
                    expected_dim=expected_dim,
                    actual_dim=actual_dim,
                )
                raise EmbeddingServiceError(
                    f"Embedding 维度不匹配：期望 {expected_dim} 维（config.embedding_dimension），"
                    f"实际 {actual_dim} 维（chunk #{idx}）。请检查 embedding 模型与平台配置是否一致。"
                )

        # 批量插入 + 文档状态更新在同一事务内，保证原子性：
        # 避免 chunks 已写入但文档状态仍为 'processing' 的数据不一致。
        chunk_ids = []
        async with pool.acquire() as conn, conn.transaction():
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)

                # pgvector 期望字符串格式 "[0.1, 0.2, ...]"
                embedding_str = "[" + ",".join(str(x) for x in embedding.tolist()) + "]"
                content_hash = hashlib.md5(chunk["content"].encode()).hexdigest()
                await conn.execute(
                    """
                        INSERT INTO knowledge_chunk
                            (id, document_id, tenant_id, chunk_index, content, content_hash, embedding, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8, $9)
                        """,
                    chunk_id,
                    document_id,
                    tenant_id,
                    i,
                    chunk["content"],
                    content_hash,
                    embedding_str,
                    json.dumps(chunk.get("metadata", {})),
                    datetime.utcnow(),
                )

            # 更新文档状态（同一事务内，与 chunk 写入保持原子性）
            await conn.execute(
                """
                UPDATE knowledge_document
                SET status = $1, chunk_count = $2, updated_at = $3
                WHERE id = $4
                """,
                "ready",
                len(chunks),
                datetime.utcnow(),
                document_id,
            )

        logger.info(
            "document_indexed",
            document_id=document_id,
            chunk_count=len(chunks),
        )

        return chunk_ids

    async def search(
        self,
        query_embedding: np.ndarray,
        tenant_id: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[dict]:
        """向量相似度检索

        【检索算法】
        使用余弦相似度（1 - 余弦距离）

        Args:
            query_embedding: 查询向量
            tenant_id: 租户 ID
            doc_ids: 可选，限定文档范围
            top_k: 返回数量
            threshold: 相似度阈值

        Returns:
            检索结果列表
        """
        pool = await self._get_pool()

        # 构建查询
        sql = """
            SELECT
                c.id as chunk_id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.metadata,
                d.name as document_name,
                1 - (c.embedding <=> $1::vector) as score
            FROM knowledge_chunk c
            JOIN knowledge_document d ON c.document_id = d.id
            WHERE c.tenant_id = $2
                AND d.status = 'ready'
        """

        params = [query_embedding.tolist(), tenant_id]
        param_idx = 3

        if doc_ids:
            sql += f" AND c.document_id = ANY(${param_idx})"
            params.append(doc_ids)
            param_idx += 1

        if threshold > 0:
            sql += f" AND 1 - (c.embedding <=> $1::vector) >= ${param_idx}"
            params.append(threshold)
            param_idx += 1

        sql += f" ORDER BY c.embedding <=> $1::vector LIMIT ${param_idx}"
        params.append(top_k)

        try:
            results = await pool.fetch(sql, *params)

            return [
                {
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "document_name": r["document_name"],
                    "chunk_index": r["chunk_index"],
                    "content": r["content"],
                    "score": float(r["score"]),
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                }
                for r in results
            ]

        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            return []

    async def delete_document(self, document_id: str, tenant_id: str) -> bool:
        """删除文档及其所有块

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            是否成功
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.transaction():
            # 删除块
            await conn.execute(
                "DELETE FROM knowledge_chunk WHERE document_id = $1 AND tenant_id = $2",
                document_id,
                tenant_id,
            )

            # 删除文档
            result = await conn.execute(
                "DELETE FROM knowledge_document WHERE id = $1 AND tenant_id = $2",
                document_id,
                tenant_id,
            )

        logger.info(
            "document_deleted",
            document_id=document_id,
            tenant_id=tenant_id,
        )

        return True

    async def get_document_info(self, document_id: str, tenant_id: str) -> dict | None:
        """获取文档信息"""
        pool = await self._get_pool()

        result = await pool.fetchrow(
            """
            SELECT id, tenant_id, name, file_type, file_size, status, chunk_count, metadata, created_at
            FROM knowledge_document
            WHERE id = $1 AND tenant_id = $2
            """,
            document_id,
            tenant_id,
        )

        if not result:
            return None

        return {
            "document_id": result["id"],
            "tenant_id": result["tenant_id"],
            "name": result["name"],
            "file_type": result["file_type"],
            "file_size": result["file_size"],
            "status": result["status"],
            "chunk_count": result["chunk_count"],
            "metadata": json.loads(result["metadata"]) if result["metadata"] else {},
            "created_at": result["created_at"].isoformat(),
        }


class EmbeddingClient:
    """Embedding 服务客户端"""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, text: str) -> np.ndarray:
        """单个文本 Embedding"""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """批量 Embedding

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        import httpx

        # 分批处理（避免请求过大）
        batch_size = config.embedding_batch_size
        all_embeddings = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                try:
                    response = await client.post(
                        f"{self.base_url}/v1/embeddings",
                        json={
                            "model": self.model,
                            "input": batch,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                    # 按 index 排序
                    embeddings = sorted(data["data"], key=lambda x: x["index"])
                    all_embeddings.extend([np.array(e["embedding"]) for e in embeddings])

                except Exception as e:
                    logger.error(
                        "embedding_batch_failed",
                        batch_index=i // batch_size,
                        error=str(e),
                    )
                    raise

        return all_embeddings


# 全局实例
_indexer: PgVectorIndexer | None = None


def get_vector_indexer() -> PgVectorIndexer:
    """获取向量索引器实例"""
    global _indexer
    if _indexer is None:
        _indexer = PgVectorIndexer()
    return _indexer
