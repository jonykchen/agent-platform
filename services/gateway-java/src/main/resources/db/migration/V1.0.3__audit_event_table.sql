-- ============================================================
-- V1.0.3__audit_event_table.sql
-- 审计事件表（匹配 AuditEvent 实体定义）
-- ============================================================

-- 先删除旧表（如果存在）
DROP TABLE IF EXISTS audit_event;

CREATE TABLE audit_event (
    id              BIGSERIAL PRIMARY KEY,
    event_id        VARCHAR(128) NOT NULL UNIQUE,
    event_type      VARCHAR(64) NOT NULL,
    event_category  VARCHAR(32) NOT NULL,
    severity        VARCHAR(16) DEFAULT 'info',
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    resource_type   VARCHAR(64),
    resource_id     VARCHAR(128),
    action          VARCHAR(64) NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    details         JSONB,
    request_id      VARCHAR(128),
    trace_id        VARCHAR(128),
    ip_address      VARCHAR(64),  -- 简化存储，INET 改为 VARCHAR
    user_agent      TEXT,
    source_service  VARCHAR(32),
    created_at      TIMESTAMZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_event(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_event(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_id ON audit_event(event_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_event(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_event(event_category);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_event(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_event(request_id);
