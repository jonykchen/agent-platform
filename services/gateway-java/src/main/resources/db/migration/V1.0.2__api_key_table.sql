-- V1.0.2__api_key_table.sql
-- API Key 认证凭证表

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash VARCHAR(64) NOT NULL UNIQUE,     -- SHA-256 哈希值
    key_prefix VARCHAR(8) NOT NULL,           -- 前缀用于快速查找
    tenant_id VARCHAR(32) NOT NULL,
    user_id VARCHAR(32),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(16) NOT NULL,                -- service/external/test
    rate_limit INT DEFAULT 1000,              -- 每小时请求限制
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(32)
);

-- 权限范围关联表
CREATE TABLE api_key_scopes (
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    scope VARCHAR(64) NOT NULL,
    PRIMARY KEY (api_key_id, scope)
);

-- 索引
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);

-- 注释
COMMENT ON TABLE api_keys IS 'API Key 认证凭证表';
COMMENT ON COLUMN api_keys.key_hash IS 'API Key 的 SHA-256 哈希值';
COMMENT ON COLUMN api_keys.key_prefix IS 'API Key 前缀（前8个字符），用于快速定位';
COMMENT ON COLUMN api_keys.type IS 'API Key 类型：service（服务间）、external（外部系统）、test（测试）';
COMMENT ON COLUMN api_keys.rate_limit IS '每小时请求限制';

-- 初始化测试数据（仅开发环境）
INSERT INTO api_keys (key_hash, key_prefix, tenant_id, name, type, is_active, created_at, updated_at)
SELECT
    encode(sha256('test_external_key_001'::bytea), 'hex'),
    'test_ext',
    'tenant_001',
    'Test External API Key',
    'test',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM api_keys WHERE key_prefix = 'test_ext');

-- 插入测试权限范围
INSERT INTO api_key_scopes (api_key_id, scope)
SELECT id, 'operator' FROM api_keys WHERE key_prefix = 'test_ext'
ON CONFLICT DO NOTHING;
