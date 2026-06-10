"""knowledge 初始 schema：pgvector 扩展 + 文档/分块表

将此前内嵌在 vector_indexer 中的建表 DDL 收敛为受版本管理的迁移，
schema 变更从此可追溯、可回滚。

Revision ID: 0001
Revises:
Create Date: 2026-06-16
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


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
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_tenant ON knowledge_document(tenant_id)"
    )

    # 分块表（含 1536 维向量列）
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunk (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
            tenant_id VARCHAR(64) NOT NULL,
            chunk_index INT NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(1536),
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunk_tenant ON knowledge_chunk(tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunk_document ON knowledge_chunk(document_id)"
    )
    # 向量索引（IVFFlat + 余弦距离）
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON knowledge_chunk
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_chunk")
    op.execute("DROP TABLE IF EXISTS knowledge_document")
