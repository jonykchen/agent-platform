-- ============================================================
-- V1.0.1__seed_initial_data.sql
-- 初始化种子数据：租户、用户等
-- ============================================================

-- ====== 租户数据 ======
INSERT INTO tenant (id, name, status, quota_config, feature_flags, created_at, updated_at) VALUES
('default', '默认租户', 'active', '{"daily_tokens": 10000000, "max_sessions": 1000}', '{"rag_enabled": true, "multi_modal_enabled": true}', NOW(), NOW()),
('tenant_001', '示例企业', 'active', '{"daily_tokens": 10000000, "max_sessions": 1000}', '{"rag_enabled": true, "multi_modal_enabled": true}', NOW(), NOW()),
('tenant_002', '测试租户', 'active', '{"daily_tokens": 5000000, "max_sessions": 500}', '{"rag_enabled": false, "multi_modal_enabled": false}', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ====== 用户数据 ======
-- 密码使用 BCrypt(cost=10) 加密，原始密码分别是 admin123, operator123, viewer123
-- 租户 ID 统一使用 'default'，与 AuthService 默认值对齐（前端不传 tenant_id 时走 default）
INSERT INTO tenant_user (tenant_id, user_id, username, email, password, role, quota_daily, quota_used_today, status, login_count, failed_login_count, created_at, updated_at) VALUES
('default', 'user_admin', 'admin', 'admin@example.com', '$2a$10$Gds.4fJJDr/JA0sBlY5nX.Ju2fJ3c9EYyQEn9e9hM.zqjNN1jxLgO', 'admin', 100000, 0, 'active', 0, 0, NOW(), NOW()),
('default', 'user_operator', 'operator', 'operator@example.com', '$2a$10$x36AYbQxYUYicRVYzcQH4.1luF13kshA.2pLNd/xduNZoZGmeEAYq', 'operator', 50000, 0, 'active', 0, 0, NOW(), NOW()),
('default', 'user_viewer', 'viewer', 'viewer@example.com', '$2a$10$QNI4J1/3j3Hw1Nz05ntyZe9LyPmry1MyswydGlobyEIlAqazI4//u', 'viewer', 20000, 0, 'active', 0, 0, NOW(), NOW())
ON CONFLICT ON CONSTRAINT uk_tenant_user DO NOTHING;