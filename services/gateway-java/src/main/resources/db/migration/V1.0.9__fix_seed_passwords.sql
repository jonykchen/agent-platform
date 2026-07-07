-- ============================================================
-- V1.0.2__fix_seed_passwords.sql
-- 修复种子用户密码：原始种子数据中的 BCrypt hash 是占位符，无法匹配真实密码
-- 同时统一 tenant_id 为 'default'（与 AuthService 默认值对齐）
-- ============================================================

-- 修复 default 租户下的测试用户密码
UPDATE tenant_user SET password = '$2a$10$Gds.4fJJDr/JA0sBlY5nX.Ju2fJ3c9EYyQEn9e9hM.zqjNN1jxLgO'
WHERE tenant_id = 'default' AND username = 'admin' AND user_id = 'user_admin';

UPDATE tenant_user SET password = '$2a$10$x36AYbQxYUYicRVYzcQH4.1luF13kshA.2pLNd/xduNZoZGmeEAYq'
WHERE tenant_id = 'default' AND username = 'operator' AND user_id = 'user_operator';

UPDATE tenant_user SET password = '$2a$10$QNI4J1/3j3Hw1Nz05ntyZe9LyPmry1MyswydGlobyEIlAqazI4//u'
WHERE tenant_id = 'default' AND username = 'viewer' AND user_id = 'user_viewer';

-- 将 tenant_001 下的测试用户迁移到 default 租户（前端不传 tenant_id 时走 default）
-- 先删除 default 租户下的同名用户（避免唯一约束冲突），再迁移
DELETE FROM tenant_user WHERE tenant_id = 'default' AND username IN ('admin', 'operator', 'viewer')
    AND user_id IN ('user_001', 'user_002', 'user_003');

UPDATE tenant_user SET
    tenant_id = 'default',
    password = CASE
        WHEN username = 'admin' THEN '$2a$10$Gds.4fJJDr/JA0sBlY5nX.Ju2fJ3c9EYyQEn9e9hM.zqjNN1jxLgO'
        WHEN username = 'operator' THEN '$2a$10$x36AYbQxYUYicRVYzcQH4.1luF13kshA.2pLNd/xduNZoZGmeEAYq'
        WHEN username = 'viewer' THEN '$2a$10$QNI4J1/3j3Hw1Nz05ntyZe9LyPmry1MyswydGlobyEIlAqazI4//u'
    END
WHERE tenant_id = 'tenant_001' AND username IN ('admin', 'operator', 'viewer')
    AND user_id IN ('user_001', 'user_002', 'user_003');

-- 确保 default 租户存在
INSERT INTO tenant (id, name, status, quota_config, feature_flags, created_at, updated_at)
SELECT 'default', '默认租户', 'active', '{"daily_tokens": 10000000, "max_sessions": 1000}',
       '{"rag_enabled": true, "multi_modal_enabled": true}', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM tenant WHERE id = 'default');
