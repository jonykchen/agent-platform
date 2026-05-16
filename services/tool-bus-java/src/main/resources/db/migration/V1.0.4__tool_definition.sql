-- ============================================================
-- V1.0.4__tool_definition.sql
-- 工具定义表（动态注册支持）
-- ============================================================

-- ============================================================
--  1. tool_definition - 工具定义表
-- ============================================================
CREATE TABLE IF NOT EXISTS tool_definition (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(128) NOT NULL,
    version         VARCHAR(16) NOT NULL DEFAULT '1.0',
    category        VARCHAR(32) NOT NULL,            -- query / write / external
    description     TEXT,
    input_schema    JSONB,
    output_schema   JSONB,
    risk_level      VARCHAR(16) NOT NULL DEFAULT 'low',  -- low / medium / high / critical
    requires_approval BOOLEAN NOT NULL DEFAULT false,
    approval_condition JSONB,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(name, version)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tool_def_name ON tool_definition(name);
CREATE INDEX IF NOT EXISTS idx_tool_def_category ON tool_definition(category);
CREATE INDEX IF NOT EXISTS idx_tool_def_enabled ON tool_definition(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_tool_def_risk ON tool_definition(risk_level) WHERE risk_level IN ('high', 'critical');

-- 表注释
COMMENT ON TABLE tool_definition IS '工具定义表 - 支持动态注册';
COMMENT ON COLUMN tool_definition.name IS '工具名称，命名规范：verb_noun';
COMMENT ON COLUMN tool_definition.version IS '语义化版本，如 1.0, 2.1.0';
COMMENT ON COLUMN tool_definition.category IS '工具类别：query（查询）/ write（写操作）/ external（外部服务）';
COMMENT ON COLUMN tool_definition.input_schema IS '输入参数 JSON Schema';
COMMENT ON COLUMN tool_definition.output_schema IS '输出参数 JSON Schema（可选）';
COMMENT ON COLUMN tool_definition.risk_level IS '风险等级：low / medium / high / critical';
COMMENT ON COLUMN tool_definition.requires_approval IS '是否需要人工审批';
COMMENT ON COLUMN tool_definition.approval_condition IS '审批触发条件，JSON 格式，如 {"amount": {"$gt": 10000}}';
COMMENT ON COLUMN tool_definition.enabled IS '是否启用，禁用的工具不会出现在工具列表中';

-- ============================================================
--  2. 初始工具数据
-- ============================================================

-- 查询订单状态 - 低风险只读工具
INSERT INTO tool_definition (name, version, category, description, input_schema, risk_level, requires_approval, enabled) VALUES
('query_order_status', '1.0', 'query', '查询订单状态',
'{
    "type": "object",
    "properties": {
        "order_id": {"type": "string", "description": "订单 ID"}
    },
    "required": ["order_id"]
}',
'low', false, true);

-- 获取用户信息 - 低风险只读工具
INSERT INTO tool_definition (name, version, category, description, input_schema, risk_level, requires_approval, enabled) VALUES
('get_user_info', '1.0', 'query', '获取用户基本信息',
'{
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "description": "用户 ID"}
    },
    "required": ["user_id"]
}',
'low', false, true);

-- 模拟写操作 - 高风险工具
INSERT INTO tool_definition (name, version, category, description, input_schema, risk_level, requires_approval, approval_condition, enabled) VALUES
('mock_write_operation', '1.0', 'write', '模拟写操作（高风险）',
'{
    "type": "object",
    "properties": {
        "operation": {"type": "string", "description": "操作类型"},
        "amount": {"type": "number", "description": "金额"}
    },
    "required": ["operation"]
}',
'high', true, '{"amount": {"$gt": 10000}}', true);

-- ============================================================
--  3. 触发器：自动更新 updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_tool_definition_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tool_definition_updated_at ON tool_definition;
CREATE TRIGGER trg_tool_definition_updated_at
    BEFORE UPDATE ON tool_definition
    FOR EACH ROW
    EXECUTE FUNCTION update_tool_definition_updated_at();