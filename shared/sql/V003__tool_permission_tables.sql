-- ============================================================
--  工具权限表 (S-04)
--  实现五层权限检查：RBAC → 租户开关 → ABAC → 频率 → 风险
-- ============================================================

-- ============================================================
--  1. tool_permission - 工具权限映射表（角色 ↔ 工具）
-- ============================================================
CREATE TABLE tool_permission (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name       VARCHAR(128) NOT NULL,
    role_name       VARCHAR(64) NOT NULL,        -- admin / operator / viewer / custom
    allowed_actions VARCHAR(32) NOT NULL DEFAULT 'execute',  -- execute / read_only / approve
    conditions      JSONB DEFAULT '{}',          -- ABAC 条件
    -- conditions 示例: {"max_amount": 10000, "allowed_departments": ["sales", "finance"]}
    conditions_schema JSONB DEFAULT NULL,         -- 可选：ABAC 条件的 JSON Schema 定义
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(tool_name, role_name)
);

CREATE INDEX idx_tool_perm_role ON tool_permission(role_name);
CREATE INDEX idx_tool_perm_tool ON tool_permission(tool_name);

COMMENT ON TABLE tool_permission IS '工具权限映射表（角色 ↔ 工具）';
COMMENT ON COLUMN tool_permission.allowed_actions IS '允许的操作: execute/read_only/approve';
COMMENT ON COLUMN tool_permission.conditions IS 'ABAC 动态条件，如金额上限、部门限制';

-- ============================================================
--  2. tenant_tool_config - 租户级工具开关与配额表
-- ============================================================
CREATE TABLE tenant_tool_config (
    tenant_id       VARCHAR(64) NOT NULL,
    tool_name       VARCHAR(128) NOT NULL,
    is_enabled      BOOLEAN NOT NULL DEFAULT false,
    daily_quota     INT DEFAULT NULL,            -- 每日调用上限（NULL = 无限制）
    monthly_quota   INT DEFAULT NULL,            -- 每月调用上限
    config          JSONB DEFAULT '{}',          -- 工具特有配置参数
    -- config 示例: {"allowed_sku_categories": ["electronics"], "max_refund_amount": 5000}
    enabled_by      VARCHAR(128),                -- 开通人
    enabled_at      TIMESTAMPTZ,
    disabled_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (tenant_id, tool_name)
);

CREATE INDEX idx_ttc_tenant ON tenant_tool_config(tenant_id);
CREATE INDEX idx_ttc_enabled ON tenant_tool_config(is_enabled) WHERE is_enabled = true;
CREATE INDEX idx_ttc_tool ON tenant_tool_config(tool_name);

COMMENT ON TABLE tenant_tool_config IS '租户级工具开关与配额表';
COMMENT ON COLUMN tenant_tool_config.daily_quota IS '每日调用上限，NULL表示无限制';
COMMENT ON COLUMN tenant_tool_config.config IS '工具特有配置参数，如金额上限、SKU类别限制';

-- ============================================================
--  3. tool_usage_daily - 工具日用量统计表（配额检查用）
-- ============================================================
CREATE TABLE tool_usage_daily (
    id              BIGSERIAL PRIMARY KEY,
    stat_date       DATE NOT NULL,
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128),
    tool_name       VARCHAR(128) NOT NULL,

    total_calls     BIGINT DEFAULT 0,
    success_calls   BIGINT DEFAULT 0,
    failed_calls    BIGINT DEFAULT 0,

    avg_latency_ms  DECIMAL(10,2),
    p95_latency_ms  DECIMAL(10,2),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(stat_date, tenant_id, COALESCE(user_id, ''), tool_name)
);

CREATE INDEX idx_usage_daily_date ON tool_usage_daily(stat_date DESC);
CREATE INDEX idx_usage_daily_tenant ON tool_usage_daily(tenant_id, stat_date DESC);
CREATE INDEX idx_usage_daily_tool ON tool_usage_daily(tool_name, stat_date DESC);

COMMENT ON TABLE tool_usage_daily IS '工具日用量统计表';

-- ============================================================
--  4. 初始权限数据
-- ============================================================

-- 查询类工具 - 所有角色可用
INSERT INTO tool_permission (tool_name, role_name, allowed_actions) VALUES
    ('query_order_status', 'admin', 'execute'),
    ('query_order_status', 'operator', 'execute'),
    ('query_order_status', 'viewer', 'read_only'),
    ('get_user_info', 'admin', 'execute'),
    ('get_user_info', 'operator', 'execute'),
    ('get_user_info', 'viewer', 'read_only');

-- 写操作类工具 - 仅 admin 和 operator 可用
INSERT INTO tool_permission (tool_name, role_name, allowed_actions) VALUES
    ('create_order', 'admin', 'execute'),
    ('create_order', 'operator', 'execute'),
    ('update_order', 'admin', 'execute'),
    ('update_order', 'operator', 'execute');

-- 高风险工具 - 需要 approval
INSERT INTO tool_permission (tool_name, role_name, allowed_actions, conditions) VALUES
    ('payment_tool', 'admin', 'execute', '{"max_amount": 50000}'),
    ('payment_tool', 'operator', 'execute', '{"max_amount": 10000, "requires_approval": true}'),
    ('refund_payment', 'admin', 'execute', '{"max_amount": 10000, "requires_approval": true}'),
    ('delete_record', 'admin', 'execute', '{"requires_approval": true}');

-- ============================================================
--  5. 租户默认工具配置
-- ============================================================

-- 为默认租户开通常用工具
INSERT INTO tenant_tool_config (tenant_id, tool_name, is_enabled, daily_quota, enabled_by, enabled_at) VALUES
    ('default', 'query_order_status', true, 1000, 'system', NOW()),
    ('default', 'get_user_info', true, 500, 'system', NOW()),
    ('default', 'create_order', true, 100, 'system', NOW()),
    ('default', 'payment_tool', true, 50, 'system', NOW());
