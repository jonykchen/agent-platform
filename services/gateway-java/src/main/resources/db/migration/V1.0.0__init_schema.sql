-- ============================================================
-- V1.0.0__init_schema.sql
-- Agent Platform Gateway 数据库初始化脚本
-- ============================================================

-- ====== 租户表 ======
CREATE TABLE IF NOT EXISTS tenant (
    id              VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(256) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    quota_config    JSONB DEFAULT '{}',
    feature_flags   JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====== 租户用户表 ======
CREATE TABLE IF NOT EXISTS tenant_user (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           VARCHAR(64) NOT NULL,
    user_id             VARCHAR(128) NOT NULL,
    username            VARCHAR(64) NOT NULL,
    email               VARCHAR(256),
    password            VARCHAR(256) NOT NULL,
    role                VARCHAR(32) NOT NULL DEFAULT 'viewer',
    quota_daily         INT NOT NULL DEFAULT 100000,
    quota_used_today    INT NOT NULL DEFAULT 0,
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    last_login_at       TIMESTAMPTZ,
    last_login_ip       VARCHAR(64),
    login_count         INT DEFAULT 0,
    failed_login_count  INT DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uk_tenant_user UNIQUE (tenant_id, user_id),
    CONSTRAINT uk_tenant_username UNIQUE (tenant_id, username)
);

-- ====== Agent Session 表 ======
CREATE TABLE IF NOT EXISTS agent_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    session_type    VARCHAR(32) NOT NULL DEFAULT 'chat',
    title           VARCHAR(256),
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

-- ====== Agent Run 表 ======
CREATE TABLE IF NOT EXISTS agent_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES agent_session(id),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    run_number      INT NOT NULL,
    input_message   TEXT NOT NULL,
    output_message  TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'running',
    error_message   TEXT,
    error_code      VARCHAR(64),
    model_used      VARCHAR(64),
    total_tokens    INT DEFAULT 0,
    total_cost_usd  DECIMAL(10,6) DEFAULT 0,
    duration_ms     INT,
    metadata        JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,

    CONSTRAINT uk_session_run_number UNIQUE (session_id, run_number)
);

-- ====== Agent Step 表 ======
CREATE TABLE IF NOT EXISTS agent_step (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES agent_run(id),
    tenant_id       VARCHAR(64) NOT NULL,
    step_order      INT NOT NULL,
    step_type       VARCHAR(32) NOT NULL,
    content         TEXT NOT NULL,
    tool_name       VARCHAR(128),
    tool_input      JSONB,
    tool_output     JSONB,
    thinking        TEXT,
    token_count     INT DEFAULT 0,
    duration_ms     INT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====== Tool Invocation 表 ======
CREATE TABLE IF NOT EXISTS tool_invocation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id             UUID REFERENCES agent_step(id),
    run_id              UUID NOT NULL REFERENCES agent_run(id),
    tool_name           VARCHAR(128) NOT NULL,
    tool_category       VARCHAR(32),
    tool_version        VARCHAR(16) DEFAULT '1.0',
    risk_level          VARCHAR(16) NOT NULL DEFAULT 'low',
    input_schema        JSONB,
    input_data          JSONB NOT NULL,
    output_data         JSONB,
    status              VARCHAR(32) NOT NULL,
    error_code          VARCHAR(64),
    error_message       TEXT,
    approval_id         UUID,
    was_cached          BOOLEAN DEFAULT FALSE,
    duration_ms         INT,
    provider_latency_ms INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

-- ====== Approval Task 表 ======
CREATE TABLE IF NOT EXISTS approval_task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES agent_run(id),
    tool_invocation_id  UUID REFERENCES tool_invocation(id),
    tenant_id           VARCHAR(64) NOT NULL,
    task_type           VARCHAR(32) NOT NULL,
    title               VARCHAR(256) NOT NULL,
    description         TEXT NOT NULL,
    request_context     JSONB NOT NULL,
    requester_id        VARCHAR(128) NOT NULL,
    assignee_id         VARCHAR(128),
    priority            VARCHAR(16) DEFAULT 'normal',
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewer_id         VARCHAR(128),
    review_comment      TEXT,
    reviewed_at         TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ NOT NULL,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====== 索引 ======

-- tenant_user 索引
CREATE INDEX IF NOT EXISTS idx_user_tenant_status ON tenant_user(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_user_tenant_role ON tenant_user(tenant_id, role);

-- agent_session 索引
CREATE INDEX IF NOT EXISTS idx_session_tenant_user ON agent_session(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_session_created ON agent_session(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_status ON agent_session(status) WHERE status = 'active';

-- agent_run 索引
CREATE INDEX IF NOT EXISTS idx_run_tenant_created ON agent_run(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_user ON agent_run(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_session ON agent_run(session_id);
CREATE INDEX IF NOT EXISTS idx_run_status ON agent_run(status);
CREATE INDEX IF NOT EXISTS idx_run_model ON agent_run(model_used);

-- agent_step 索引
CREATE INDEX IF NOT EXISTS idx_step_run ON agent_step(run_id, step_order);
CREATE INDEX IF NOT EXISTS idx_step_tenant ON agent_step(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_step_type ON agent_step(step_type);

-- tool_invocation 索引
CREATE INDEX IF NOT EXISTS idx_tool_invocation_run ON tool_invocation(run_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocation_tool ON tool_invocation(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_invocation_status ON tool_invocation(status);
CREATE INDEX IF NOT EXISTS idx_tool_invocation_created ON tool_invocation(created_at);
CREATE INDEX IF NOT EXISTS idx_tool_invocation_risk ON tool_invocation(risk_level) WHERE risk_level IN ('high', 'critical');
CREATE INDEX IF NOT EXISTS idx_tool_invocation_cached ON tool_invocation(was_cached) WHERE was_cached = true;

-- approval_task 索引
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_task(status);
CREATE INDEX IF NOT EXISTS idx_approval_tenant ON approval_task(tenant_id);
CREATE INDEX IF NOT EXISTS idx_approval_assignee ON approval_task(assignee_id, status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_approval_requester ON approval_task(requester_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_expires ON approval_task(expires_at) WHERE status = 'pending' AND expires_at > NOW();