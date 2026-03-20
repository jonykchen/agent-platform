-- ============================================================
--  Agent Platform - 初始化 Schema
--  版本: V001
--  对应文档: 04-data-design-complete.md
--  对应改进项: P-04, S-01, M-02
-- ============================================================

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- ============================================================
--  1. agent_session - 会话表
-- ============================================================
CREATE TABLE agent_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    session_type    VARCHAR(32) NOT NULL DEFAULT 'chat',  -- chat / task / workflow
    title           VARCHAR(256),
    status          VARCHAR(32) NOT NULL DEFAULT 'active', -- active / archived / closed
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

CREATE INDEX idx_session_tenant_user ON agent_session(tenant_id, user_id);
CREATE INDEX idx_session_created ON agent_session(created_at DESC);
CREATE INDEX idx_session_status ON agent_session(status) WHERE status = 'active';

COMMENT ON TABLE agent_session IS 'Agent 会话表';
COMMENT ON COLUMN agent_session.session_type IS '会话类型: chat/task/workflow';
COMMENT ON COLUMN agent_session.status IS '会话状态: active/archived/closed';

-- ============================================================
--  2. agent_run - 运行实例表
--  P-04 修正: tenant_id 作为独立列，非 JSONB 内嵌
-- ============================================================
CREATE TABLE agent_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联
    session_id      UUID NOT NULL REFERENCES agent_session(id),

    -- 租户信息（独立列）
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,

    -- 运行状态
    run_number      INT NOT NULL,
    input_message   TEXT NOT NULL,
    output_message  TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'running', -- running / completed / failed / cancelled / pending_approval
    error_message   TEXT,
    error_code      VARCHAR(64),

    -- 模型与资源消耗
    model_used      VARCHAR(64),
    total_tokens    INT DEFAULT 0,
    total_cost_usd  DECIMAL(10,6) DEFAULT 0,
    duration_ms     INT,

    -- 扩展字段
    metadata        JSONB DEFAULT '{}',

    -- 时间戳
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,

    UNIQUE(session_id, run_number)
);

-- P-04 修正: 使用独立列的普通复合索引
CREATE INDEX idx_run_tenant_created ON agent_run(tenant_id, started_at DESC);
CREATE INDEX idx_run_user ON agent_run(user_id, started_at DESC);
CREATE INDEX idx_run_session ON agent_run(session_id);
CREATE INDEX idx_run_status ON agent_run(status);
CREATE INDEX idx_run_model ON agent_run(model_used);

COMMENT ON TABLE agent_run IS 'Agent 运行实例表';
COMMENT ON COLUMN agent_run.status IS '运行状态: running/completed/failed/cancelled/pending_approval';

-- ============================================================
--  3. agent_step - 执行步骤表（分区表）
-- ============================================================
CREATE TABLE agent_step (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    run_id          UUID NOT NULL REFERENCES agent_run(id),
    tenant_id       VARCHAR(64) NOT NULL,

    step_order      INT NOT NULL,
    step_type       VARCHAR(32) NOT NULL,  -- thinking / tool_call / observation / final_answer / intent_classify / retrieve / risk_check / approval_wait
    content         TEXT NOT NULL,

    tool_name       VARCHAR(128),
    tool_input      JSONB,
    tool_output     JSONB,
    thinking        TEXT,
    token_count     INT DEFAULT 0,
    duration_ms     INT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 月度分区
CREATE TABLE agent_step_2026_05 PARTITION OF agent_step
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE agent_step_2026_06 PARTITION OF agent_step
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_step_run ON agent_step(run_id, step_order);
CREATE INDEX idx_step_tenant ON agent_step(tenant_id, created_at DESC);
CREATE INDEX idx_step_type ON agent_step(step_type);

COMMENT ON TABLE agent_step IS 'Agent 执行步骤表';
COMMENT ON COLUMN agent_step.step_type IS '步骤类型: thinking/tool_call/observation/final_answer/intent_classify/retrieve/risk_check/approval_wait';

-- ============================================================
--  4. tool_invocation - 工具调用明细表
-- ============================================================
CREATE TABLE tool_invocation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id             UUID REFERENCES agent_step(id),
    run_id              UUID NOT NULL REFERENCES agent_run(id),

    tool_name           VARCHAR(128) NOT NULL,
    tool_category       VARCHAR(32),            -- query / write / external
    tool_version        VARCHAR(16) DEFAULT '1.0',
    risk_level          VARCHAR(16) NOT NULL DEFAULT 'low', -- low / medium / high / critical

    input_schema        JSONB,
    input_data          JSONB NOT NULL,
    output_data         JSONB,

    status              VARCHAR(32) NOT NULL,   -- pending / success / failed / rejected / timeout
    error_code          VARCHAR(64),
    error_message       TEXT,

    approval_id         UUID,
    was_cached          BOOLEAN DEFAULT FALSE,

    duration_ms         INT,
    provider_latency_ms INT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_tool_invocation_run ON tool_invocation(run_id);
CREATE INDEX idx_tool_invocation_tool ON tool_invocation(tool_name);
CREATE INDEX idx_tool_invocation_status ON tool_invocation(status);
CREATE INDEX idx_tool_invocation_risk ON tool_invocation(risk_level) WHERE risk_level IN ('high', 'critical');
CREATE INDEX idx_tool_invocation_cached ON tool_invocation(was_cached) WHERE was_cached = true;

COMMENT ON TABLE tool_invocation IS '工具调用明细表';

-- ============================================================
--  5. approval_task - 审批任务表
-- ============================================================
CREATE TABLE approval_task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    run_id              UUID NOT NULL REFERENCES agent_run(id),
    tool_invocation_id  UUID REFERENCES tool_invocation(id),
    tenant_id           VARCHAR(64) NOT NULL,

    task_type           VARCHAR(32) NOT NULL,   -- tool_approval / sensitive_action / high_value_transaction
    title               VARCHAR(256) NOT NULL,
    description         TEXT NOT NULL,
    request_context     JSONB NOT NULL,

    requester_id        VARCHAR(128) NOT NULL,
    assignee_id         VARCHAR(128),

    priority            VARCHAR(16) DEFAULT 'normal', -- low / normal / high / urgent
    status              VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending / approved / rejected / expired / cancelled
    reviewer_id         VARCHAR(128),
    review_comment      TEXT,
    reviewed_at         TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ NOT NULL,

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approval_status ON approval_task(status);
CREATE INDEX idx_approval_assignee ON approval_task(assignee_id, status) WHERE status = 'pending';
CREATE INDEX idx_approval_expires ON approval_task(expires_at) WHERE status = 'pending' AND expires_at > NOW();
CREATE INDEX idx_approval_tenant ON approval_task(tenant_id);
CREATE INDEX idx_approval_requester ON approval_task(requester_id, created_at DESC);

COMMENT ON TABLE approval_task IS '审批任务表';

-- ============================================================
--  6. audit_event - 审计事件表（含安全防护 S-01）
-- ============================================================
CREATE TABLE audit_event (
    id              BIGSERIAL PRIMARY KEY,
    event_id        VARCHAR(128) UNIQUE NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    event_category  VARCHAR(32) NOT NULL,   -- lifecycle / security / business / system
    severity        VARCHAR(16) DEFAULT 'info',  -- info / warn / error / critical

    -- 主体信息
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,

    -- 资源信息
    resource_type   VARCHAR(64),
    resource_id     VARCHAR(128),

    -- 操作详情
    action          VARCHAR(64) NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    details         JSONB DEFAULT '{}',

    -- 追踪信息
    request_id      VARCHAR(128),
    trace_id        VARCHAR(128),

    -- 来源信息
    ip_address      INET,
    user_agent      TEXT,
    source_service  VARCHAR(32),

    -- 时间戳
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 分区定义
CREATE TABLE audit_event_2026_05 PARTITION OF audit_event
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 索引
CREATE INDEX idx_audit_tenant_time ON audit_event(tenant_id, created_at DESC);
CREATE INDEX idx_audit_event_type ON audit_event(event_type);
CREATE INDEX idx_audit_user_time ON audit_event(user_id, created_at DESC);
CREATE INDEX idx_audit_severity ON audit_event(severity) WHERE severity IN ('error', 'critical');
CREATE INDEX idx_audit_request ON audit_event(request_id);

COMMENT ON TABLE audit_event IS '审计事件表';

-- ====== S-01: 审计表安全防护 ======

-- 1. 触发器：禁止 DELETE 和 UPDATE
CREATE OR REPLACE FUNCTION block_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '[SECURITY] audit_event 表禁止 % 操作 (event_id=%, operator=%)',
        TG_OP, COALESCE(OLD.event_id, 'N/A'), current_user;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_modify_on_audit
    BEFORE DELETE OR UPDATE ON audit_event
    FOR EACH ROW
EXECUTE FUNCTION block_audit_modification();

-- 2. 触发器：禁止 TRUNCATE
CREATE OR REPLACE FUNCTION block_audit_truncate()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '[SECURITY] audit_event 表禁止 TRUNCATE 操作';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_trunc_on_audit
    BEFORE TRUNCATE ON audit_event
    FOR STATEMENT
EXECUTE FUNCTION block_audit_truncate();

-- 3. RLS：限制应用层只能 INSERT
ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_insert_only ON audit_event
    FOR INSERT WITH CHECK (true);

-- ============================================================
--  7. prompt_template - Prompt 模板版本表
-- ============================================================
CREATE TABLE prompt_template (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key        VARCHAR(128) UNIQUE NOT NULL,
    name                VARCHAR(256) NOT NULL,
    description         TEXT,
    version             INT NOT NULL DEFAULT 1,

    system_prompt       TEXT NOT NULL,
    user_prompt_template TEXT,
    few_shot_examples   JSONB DEFAULT '[]',
    parameters          JSONB DEFAULT '[]',
    model_hints         JSONB DEFAULT '{}',

    status              VARCHAR(32) NOT NULL DEFAULT 'draft', -- draft / active / archived
    created_by          VARCHAR(128),
    tags                TEXT[] DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prompt_key_version ON prompt_template(template_key, version DESC);
CREATE INDEX idx_prompt_status ON prompt_template(status) WHERE status = 'active';
CREATE INDEX idx_prompt_tags ON prompt_template USING GIN(tags);

COMMENT ON TABLE prompt_template IS 'Prompt 模板版本表';

-- ============================================================
--  8. model_route_policy - 模型路由策略表
-- ============================================================
CREATE TABLE model_route_policy (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name         VARCHAR(128) UNIQUE NOT NULL,
    description         TEXT,
    priority            INT NOT NULL DEFAULT 0,

    match_rules         JSONB NOT NULL,
    primary_model       VARCHAR(64) NOT NULL,
    fallback_models     JSONB DEFAULT '[]',
    config              JSONB DEFAULT '{}',

    rate_limit_rpm      INT DEFAULT 100,
    rate_limit_tpm      INT DEFAULT 50000,
    cost_budget_daily   DECIMAL(12,4),

    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    effective_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until     TIMESTAMPTZ,

    created_by          VARCHAR(128),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_policy_priority ON model_route_policy(priority DESC) WHERE status = 'active';
CREATE INDEX idx_policy_model ON model_route_policy(primary_model);

COMMENT ON TABLE model_route_policy IS '模型路由策略表';

-- ============================================================
--  9. knowledge_document - 知识库文档表
-- ============================================================
CREATE TABLE knowledge_document (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           VARCHAR(64) NOT NULL,
    name                VARCHAR(512) NOT NULL,
    file_path           VARCHAR(1024),
    file_type           VARCHAR(32),
    file_size_bytes     BIGINT,

    status              VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending / processing / ready / failed
    chunk_count         INT DEFAULT 0,

    embedding_model     VARCHAR(64) DEFAULT 'bge-large-zh-v1.5',

    access_control      JSONB DEFAULT '{"level": "tenant"}',

    metadata            JSONB DEFAULT '{}',
    created_by          VARCHAR(128),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kd_doc_tenant ON knowledge_document(tenant_id);
CREATE INDEX idx_kd_doc_status ON knowledge_document(status);

COMMENT ON TABLE knowledge_document IS '知识库文档表';

-- ============================================================
--  10. knowledge_chunk - 知识库切片/向量表
-- ============================================================
CREATE TABLE knowledge_chunk (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES knowledge_document(id),
    tenant_id           VARCHAR(64) NOT NULL,

    chunk_index         INT NOT NULL,
    content             TEXT NOT NULL,
    content_hash        VARCHAR(64) NOT NULL,
    token_count         INT,

    embedding           VECTOR(1536),
    embedding_model     VARCHAR(64),

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunk_doc ON knowledge_chunk(document_id, chunk_index);
CREATE INDEX idx_chunk_tenant ON knowledge_chunk(tenant_id);

-- 向量相似度索引 (HNSW，v2.1 修正)
CREATE INDEX idx_chunk_embedding ON knowledge_chunk
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE knowledge_chunk IS '知识库切片/向量表';

-- ============================================================
--  11. tenant - 租户表
-- ============================================================
CREATE TABLE tenant (
    id                  VARCHAR(64) PRIMARY KEY,
    name                VARCHAR(256) NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'active', -- active / suspended / deleted

    -- 配额配置
    quota_config        JSONB DEFAULT '{}',

    -- 功能开关
    feature_flags       JSONB DEFAULT '{}',

    -- 时间
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE tenant IS '租户表';

-- ============================================================
--  12. tenant_user - 租户用户表
-- ============================================================
CREATE TABLE tenant_user (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           VARCHAR(64) NOT NULL REFERENCES tenant(id),
    user_id             VARCHAR(128) NOT NULL,
    role                VARCHAR(32) NOT NULL DEFAULT 'member', -- admin / member / viewer

    -- 配额
    quota_daily         INT DEFAULT 100000,
    quota_used_today    INT DEFAULT 0,

    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_tenant_user_user ON tenant_user(user_id);

COMMENT ON TABLE tenant_user IS '租户用户表';

-- ============================================================
--  初始化数据
-- ============================================================

-- 插入默认租户
INSERT INTO tenant (id, name, status, quota_config, feature_flags)
VALUES ('default', '默认租户', 'active',
    '{"daily_tokens": 10000000, "max_sessions": 1000}',
    '{"rag_enabled": true, "multi_modal_enabled": false}'
);

-- 插入默认 Prompt 模板
INSERT INTO prompt_template (template_key, name, version, system_prompt, status)
VALUES ('default_system', '默认系统提示词', 1,
    '你是一个智能助手，专注于帮助用户解决问题。请用清晰、准确的语言回答用户的问题。',
    'active');

INSERT INTO prompt_template (template_key, name, version, system_prompt, status)
VALUES ('react_system', 'ReAct 模式系统提示词', 1,
    '你是一个智能助手，使用 ReAct 模式工作。当需要使用工具时，请按照以下格式：

Thought: 思考当前情况
Action: 工具名称
Action Input: 工具参数（JSON 格式）

观察工具返回结果后，继续思考和行动，直到完成任务。',
    'active');
