-- ============================================================
--  Agent Platform - 长时记忆表 + 向量维度统一
--  版本: V005
--  说明:
--    1. 新建 agent_memory 表（长时记忆，pgvector + HNSW）
--       表结构与 orchestrator alembic 迁移 0001_agent_memory 完全一致，
--       两套迁移（postgres initdb / alembic）产出相同的表，避免分歧。
--    2. 统一全平台 embedding 维度为 1024（通义千问 text-embedding-v3）
--       将 knowledge_chunk.embedding 从 VECTOR(1536) 迁移到 VECTOR(1024)
--  背景:
--    - docker-compose 将 shared/sql 挂载到 /docker-entrypoint-initdb.d，
--      在 postgres 首次初始化时按文件名顺序执行；agent_memory 此前缺失。
--    - 平台改用国内 LLM（Qwen），embedding 统一为 text-embedding-v3（1024 维）。
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
--  1. agent_memory - 长时记忆表（与 alembic 0001 一致）
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_memory (
    id                      BIGSERIAL PRIMARY KEY,
    entry_id                VARCHAR(128) NOT NULL UNIQUE,
    session_id              VARCHAR(128) NOT NULL,
    tenant_id               VARCHAR(64) NOT NULL,
    user_id                 VARCHAR(128) NOT NULL,
    user_query              TEXT NOT NULL,
    agent_response_summary  TEXT,
    key_entities            JSONB,
    timestamp               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    importance_score        REAL DEFAULT 0.5,
    embedding               VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS idx_memory_tenant_user
    ON agent_memory(tenant_id, user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_memory_session
    ON agent_memory(session_id);

-- 向量相似度索引（HNSW，余弦距离），与 knowledge_chunk 参数一致
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON agent_memory
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE agent_memory IS '长时记忆表（跨会话语义记忆，pgvector 检索）';

-- 多租户行级安全
ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_memory' AND policyname = 'tenant_isolation_memory'
    ) THEN
        CREATE POLICY tenant_isolation_memory ON agent_memory
            FOR ALL TO app_user
            USING (tenant_id = current_tenant_id());
    END IF;
END $$;

-- ============================================================
--  2. 统一 knowledge_chunk 向量维度为 1024
--  注意: 改变向量维度需重建列与索引；存量 embedding 将被清空，
--        需重新对知识库做向量化（dev/预发环境无影响）。
-- ============================================================

-- 先删除依赖该列的向量索引
DROP INDEX IF EXISTS idx_chunk_embedding;

-- 重新定义为 1024 维（empty/dev 数据可直接 TYPE 转换；存量数据应先清空 embedding）
ALTER TABLE knowledge_chunk ALTER COLUMN embedding TYPE VECTOR(1024) USING NULL;

-- 重建 HNSW 索引
CREATE INDEX idx_chunk_embedding ON knowledge_chunk
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ============================================================
--  3. knowledge_chunk 全文检索索引（GIN + tsvector）
--  支撑混合检索（hybrid_retriever）的 BM25/ts_rank 关键词召回，
--  避免 to_tsvector('simple', content) 查询退化为全表扫描。
--  与 knowledge-python alembic 0001 的 idx_chunk_content_fts 一致。
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_chunk_content_fts ON knowledge_chunk
    USING gin (to_tsvector('simple', content));
