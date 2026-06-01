-- ============================================================
-- V1.0.5__tenant_enhancement.sql
-- 租户表扩展：新增 tier 等级字段和 settings_config 配置字段
-- ============================================================

-- 1. 添加租户等级字段
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS tier VARCHAR(32) NOT NULL DEFAULT 'standard';

-- 2. 添加设置配置字段（存储 default_model, allowed_models 等运行时配置）
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS settings_config JSONB DEFAULT '{}';

-- 3. 添加 CHECK 约束
ALTER TABLE tenant ADD CONSTRAINT chk_tenant_tier
    CHECK (tier IN ('free', 'standard', 'premium', 'enterprise'));

-- 4. 索引
CREATE INDEX IF NOT EXISTS idx_tenant_tier ON tenant(tier);
CREATE INDEX IF NOT EXISTS idx_tenant_status_tier ON tenant(status, tier);

-- 5. 更新种子数据的 tier
UPDATE tenant SET tier = 'enterprise' WHERE id = 'tenant_001';
UPDATE tenant SET tier = 'standard' WHERE id = 'tenant_002';

-- 6. 更新种子数据的 settings_config
UPDATE tenant SET settings_config = '{
    "default_model": "qwen-plus",
    "allowed_models": ["qwen-max", "qwen-plus", "deepseek-chat", "glm-4"],
    "data_retention_days": 90,
    "max_concurrent_runs": 50
}' WHERE id = 'tenant_001';

UPDATE tenant SET settings_config = '{
    "default_model": "qwen-plus",
    "allowed_models": ["qwen-plus", "deepseek-chat"],
    "data_retention_days": 30,
    "max_concurrent_runs": 20
}' WHERE id = 'tenant_002';

-- 7. 文档化 JSONB 字段结构
COMMENT ON COLUMN tenant.quota_config IS 'JSONB 配额配置: {"daily_tokens": 10000000, "monthly_cost_usd": 1000.0, "max_sessions": 1000, "max_users": 100, "max_api_keys": 10}';
COMMENT ON COLUMN tenant.feature_flags IS 'JSONB 功能开关: {"rag_enabled": true, "multi_agent_enabled": true, "audit_enabled": true, "approval_workflow": true}';
COMMENT ON COLUMN tenant.settings_config IS 'JSONB 运行配置: {"default_model": "qwen-plus", "allowed_models": [...], "data_retention_days": 90, "max_concurrent_runs": 50}';
