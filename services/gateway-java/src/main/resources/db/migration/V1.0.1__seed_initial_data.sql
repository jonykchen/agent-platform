-- ============================================================
-- V1.0.1__seed_initial_data.sql
-- 初始化种子数据：租户、用户等
-- ============================================================

-- ====== 租户数据 ======
INSERT INTO tenant (id, name, status, quota_config, feature_flags, created_at, updated_at) VALUES
('tenant_001', '示例企业', 'active', '{"daily_tokens": 10000000, "max_sessions": 1000}', '{"rag_enabled": true, "multi_modal_enabled": true}', NOW(), NOW()),
('tenant_002', '测试租户', 'active', '{"daily_tokens": 5000000, "max_sessions": 500}', '{"rag_enabled": false, "multi_modal_enabled": false}', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ====== 用户数据 ======
-- 密码使用 BCrypt 加密，原始密码分别是 admin123, operator123, viewer123
INSERT INTO tenant_user (tenant_id, user_id, username, email, password, role, quota_daily, quota_used_today, status, login_count, failed_login_count, created_at, updated_at) VALUES
('tenant_001', 'user_001', 'admin', 'admin@example.com', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOa4u4y4Y4Y4Y', 'admin', 100000, 0, 'active', 0, 0, NOW(), NOW()),
('tenant_001', 'user_002', 'operator', 'operator@example.com', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOa4u4y4Y4Y4Y', 'operator', 50000, 0, 'active', 0, 0, NOW(), NOW()),
('tenant_001', 'user_003', 'viewer', 'viewer@example.com', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOa4u4y4Y4Y4Y', 'viewer', 20000, 0, 'active', 0, 0, NOW(), NOW())
ON CONFLICT (tenant_id, user_id) DO NOTHING
ON CONFLICT (tenant_id, username) DO NOTHING;