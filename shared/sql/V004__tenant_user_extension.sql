-- ============================================================
--  Agent Platform - Schema 扩展
--  版本: V004
--  补充 tenant_user 表字段以支持用户管理
-- ============================================================

-- 扩展 tenant_user 表字段
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS username VARCHAR(64) NOT NULL DEFAULT 'user';
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS email VARCHAR(256);
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS password VARCHAR(256) NOT NULL DEFAULT '';
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(64);
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS login_count INT DEFAULT 0;
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS failed_login_count INT DEFAULT 0;

-- 添加唯一约束（租户内用户名唯一）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uk_tenant_username'
    ) THEN
        ALTER TABLE tenant_user ADD CONSTRAINT uk_tenant_username UNIQUE (tenant_id, username);
    END IF;
END $$;

-- 更新索引
DROP INDEX IF EXISTS idx_user_tenant_status;
CREATE INDEX IF NOT EXISTS idx_user_tenant_status ON tenant_user(tenant_id, status);

DROP INDEX IF EXISTS idx_user_tenant_role;
CREATE INDEX IF NOT EXISTS idx_user_tenant_role ON tenant_user(tenant_id, role);

-- 初始化测试用户（密码: admin123/operator123/viewer123 的 BCrypt(cost=10) hash）
INSERT INTO tenant_user (id, tenant_id, user_id, username, email, password, role, quota_daily, quota_used_today, status, login_count, failed_login_count, created_at, updated_at)
SELECT gen_random_uuid(), 'default', 'user_admin', 'admin', 'admin@example.com',
       '$2a$10$Gds.4fJJDr/JA0sBlY5nX.Ju2fJ3c9EYyQEn9e9hM.zqjNN1jxLgO', 'admin', 100000, 0, 'active', 0, 0, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM tenant_user WHERE tenant_id = 'default' AND username = 'admin');

INSERT INTO tenant_user (id, tenant_id, user_id, username, email, password, role, quota_daily, quota_used_today, status, login_count, failed_login_count, created_at, updated_at)
SELECT gen_random_uuid(), 'default', 'user_operator', 'operator', 'operator@example.com',
       '$2a$10$x36AYbQxYUYicRVYzcQH4.1luF13kshA.2pLNd/xduNZoZGmeEAYq', 'operator', 100000, 0, 'active', 0, 0, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM tenant_user WHERE tenant_id = 'default' AND username = 'operator');

INSERT INTO tenant_user (id, tenant_id, user_id, username, email, password, role, quota_daily, quota_used_today, status, login_count, failed_login_count, created_at, updated_at)
SELECT gen_random_uuid(), 'default', 'user_viewer', 'viewer', 'viewer@example.com',
       '$2a$10$QNI4J1/3j3Hw1Nz05ntyZe9LyPmry1MyswydGlobyEIlAqazI4//u', 'viewer', 100000, 0, 'active', 0, 0, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM tenant_user WHERE tenant_id = 'default' AND username = 'viewer');

COMMENT ON COLUMN tenant_user.username IS '用户名';
COMMENT ON COLUMN tenant_user.email IS '邮箱地址';
COMMENT ON COLUMN tenant_user.password IS '密码（BCrypt hash）';
COMMENT ON COLUMN tenant_user.last_login_at IS '最后登录时间';
COMMENT ON COLUMN tenant_user.last_login_ip IS '最后登录IP';
COMMENT ON COLUMN tenant_user.login_count IS '登录次数';
COMMENT ON COLUMN tenant_user.failed_login_count IS '失败登录次数';
