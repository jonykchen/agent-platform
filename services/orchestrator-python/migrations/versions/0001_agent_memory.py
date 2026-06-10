"""orchestrator 初始 schema：长时记忆表 agent_memory（pgvector）

将 long_term_memory 使用的 agent_memory 表收敛为受版本管理的迁移。
支持向量相似度检索 + 按 tenant_id/user_id 过滤 + 重要性衰减排序。

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
    # 启用 pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 长时记忆表
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_memory (
            id BIGSERIAL PRIMARY KEY,
            entry_id VARCHAR(128) NOT NULL UNIQUE,
            session_id VARCHAR(128) NOT NULL,
            tenant_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(128) NOT NULL,
            user_query TEXT NOT NULL,
            agent_response_summary TEXT,
            key_entities JSONB,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            importance_score REAL DEFAULT 0.5,
            embedding VECTOR(1536)
        )
        """
    )
    # 租户/用户过滤索引
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_tenant_user "
        "ON agent_memory(tenant_id, user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_session ON agent_memory(session_id)"
    )
    # 向量相似度索引（IVFFlat + 余弦距离）
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_embedding ON agent_memory
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_memory")
