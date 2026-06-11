"""knowledge 初始 schema：pgvector 扩展 + 文档/分块表

将此前内嵌在 vector_indexer 中的建表 DDL 收敛为受版本管理的迁移，
schema 变更从此可追溯、可回滚。

维度与索引与平台权威 schema（shared/sql V001+V005）保持完全一致：
  - embedding 统一为 1024 维（通义千问 text-embedding-v3）
  - 向量索引使用 HNSW（m=16, ef_construction=64，余弦距离）
  - content 建立 GIN 全文索引，支撑混合检索的 BM25/ts_rank 关键词召回
两套初始化路径（postgres initdb / alembic）产出相同的表结构，避免分歧。

Revision ID: 0001
Revises:
Create Date: 2026-06-16
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# 与 shared/sql 统一的向量维度（Qwen text-embedding-v3）
EMBEDDING_DIM = 1024


def upgrade() -> None:
    # 启用 pgvector 扩展（向量相似度检索依赖）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 文档表
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_document (
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
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_tenant ON knowledge_document(tenant_id)")

    # 分块表（含 1024 维向量列，与平台 embedding 模型对齐）
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS knowledge_chunk (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
            tenant_id VARCHAR(64) NOT NULL,
            chunk_index INT NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR({EMBEDDING_DIM}),
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_tenant ON knowledge_chunk(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_document ON knowledge_chunk(document_id)")
    # 向量索引（HNSW + 余弦距离），参数与 shared/sql V005 / agent_memory 一致
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON knowledge_chunk
        USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)
        """
    )
    # 全文检索索引（GIN + tsvector），支撑混合检索 BM25 关键词召回，
    # 避免 hybrid_retriever 的 to_tsvector(...) 查询退化为全表扫描。
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_content_fts ON knowledge_chunk
        USING gin (to_tsvector('simple', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunk_content_fts")
    op.execute("DROP TABLE IF EXISTS knowledge_chunk")
    op.execute("DROP TABLE IF EXISTS knowledge_document")
