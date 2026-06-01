-- ============================================================
-- V1.0.6__usage_log_table.sql
-- 用量日志表：记录按小时聚合的 Token/成本/请求数据
-- ============================================================

CREATE TABLE IF NOT EXISTS usage_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128),
    log_date        DATE NOT NULL,
    log_hour        SMALLINT NOT NULL DEFAULT 0,

    -- Token 统计
    input_tokens    BIGINT NOT NULL DEFAULT 0,
    output_tokens   BIGINT NOT NULL DEFAULT 0,
    total_tokens    BIGINT NOT NULL DEFAULT 0,

    -- 成本统计（USD）
    cost_usd        DECIMAL(12,6) NOT NULL DEFAULT 0,

    -- 请求统计
    request_count   INT NOT NULL DEFAULT 0,
    success_count   INT NOT NULL DEFAULT 0,
    failure_count   INT NOT NULL DEFAULT 0,

    -- 模型维度聚合
    model_used      VARCHAR(64),

    -- 元数据
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 唯一约束：同租户同日同时段同模型只有一条记录
    CONSTRAINT uk_usage_log UNIQUE (tenant_id, log_date, log_hour, model_used)
);

-- 索引设计（支持高频聚合查询）
CREATE INDEX IF NOT EXISTS idx_usage_log_tenant_date ON usage_log(tenant_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_usage_log_tenant_date_model ON usage_log(tenant_id, log_date, model_used);
CREATE INDEX IF NOT EXISTS idx_usage_log_tenant_user ON usage_log(tenant_id, user_id, log_date);

-- 文档化
COMMENT ON TABLE usage_log IS '用量日志表：按小时聚合的 Token、成本、请求统计数据';
