-- ============================================================
--  Agent Platform - 生产环境初始化数据（基于实际表结构）
-- ============================================================

BEGIN;

-- ====== 1. 租户配置更新 ======
UPDATE tenant SET
    quota_config = '{"daily_tokens": 1000000, "max_users": 100, "max_tools": 50}'::jsonb,
    feature_flags = '{"chat": true, "knowledge": true, "tools": true, "approval": true}'::jsonb,
    updated_at = now()
WHERE id = 'default';

-- ====== 2. API Key（开发测试用） ======
DELETE FROM api_keys WHERE name LIKE '%测试Key%';
INSERT INTO api_keys (id, tenant_id, key_hash, key_prefix, name, type, is_active, user_id, created_at, updated_at, expires_at)
VALUES
    (gen_random_uuid(), 'default', encode(sha256('sk-test-admin-key-2026'::bytea), 'hex'), 'sk-test', '管理员测试Key', 'EXTERNAL', true, 'user_admin', now(), now(), now() + interval '365 days'),
    (gen_random_uuid(), 'default', encode(sha256('sk-test-user-key-2026'::bytea), 'hex'), 'sk-test', '普通用户测试Key', 'EXTERNAL', true, 'user_operator', now(), now(), now() + interval '365 days'),
    (gen_random_uuid(), 'default', encode(sha256('sk-test-readonly-key-2026'::bytea), 'hex'), 'sk-test', '只读测试Key', 'EXTERNAL', true, 'user_viewer', now(), now(), now() + interval '365 days');

-- ====== 3. 模型配置 ======
DELETE FROM model_config WHERE id LIKE 'model_%';
INSERT INTO model_config (id, name, provider, type, description, context_window, max_output_tokens, cost_per_1k_input, cost_per_1k_output, enabled, display_order, created_at, updated_at)
VALUES
    ('model_qwen_max', 'qwen-max', 'dashscope', 'chat', '通义千问-Max，最强中文理解能力', 32768, 8192, 0.04, 0.12, true, 1, now(), now()),
    ('model_qwen_plus', 'qwen-plus', 'dashscope', 'chat', '通义千问-Plus，性价比之选', 131072, 8192, 0.008, 0.02, true, 2, now(), now()),
    ('model_qwen_turbo', 'qwen-turbo', 'dashscope', 'chat', '通义千问-Turbo，快速响应', 131072, 8192, 0.003, 0.006, true, 3, now(), now()),
    ('model_deepseek_v3', 'deepseek-chat', 'deepseek', 'chat', 'DeepSeek-V3，强大推理能力', 65536, 8192, 0.002, 0.008, true, 4, now(), now());

-- ====== 4. 工具定义 ======
DELETE FROM tool_definition WHERE name IN ('query_order_status', 'create_order', 'send_email', 'query_database', 'web_search', 'transfer_money');
INSERT INTO tool_definition (id, name, category, description, risk_level, requires_approval, input_schema, output_schema, version, enabled, created_at, updated_at)
VALUES
    (gen_random_uuid(), 'query_order_status', 'business', '根据订单号查询订单状态和物流信息', 'low', false,
     '{"type":"object","properties":{"order_id":{"type":"string","description":"订单号"}},"required":["order_id"]}'::jsonb,
     '{"type":"object","properties":{"status":{"type":"string"},"tracking":{"type":"string"}}}'::jsonb,
     '1.0', true, now(), now()),
    (gen_random_uuid(), 'create_order', 'business', '创建新的业务订单', 'medium', false,
     '{"type":"object","properties":{"product_id":{"type":"string"},"quantity":{"type":"integer"},"customer_id":{"type":"string"}},"required":["product_id","quantity","customer_id"]}'::jsonb,
     '{"type":"object","properties":{"order_id":{"type":"string"},"status":{"type":"string"}}}'::jsonb,
     '1.0', true, now(), now()),
    (gen_random_uuid(), 'send_email', 'communication', '发送电子邮件通知', 'medium', false,
     '{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}'::jsonb,
     '{"type":"object","properties":{"message_id":{"type":"string"},"status":{"type":"string"}}}'::jsonb,
     '1.0', true, now(), now()),
    (gen_random_uuid(), 'query_database', 'data', '执行只读SQL查询（仅SELECT）', 'low', false,
     '{"type":"object","properties":{"sql":{"type":"string","description":"SELECT查询语句"}},"required":["sql"]}'::jsonb,
     '{"type":"object","properties":{"rows":{"type":"array"},"columns":{"type":"array"}}}'::jsonb,
     '1.0', true, now(), now()),
    (gen_random_uuid(), 'web_search', 'utility', '搜索互联网获取最新信息', 'low', false,
     '{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":5}},"required":["query"]}'::jsonb,
     '{"type":"object","properties":{"results":{"type":"array"}}}'::jsonb,
     '1.0', true, now(), now()),
    (gen_random_uuid(), 'transfer_money', 'finance', '执行资金转账操作（需要审批）', 'critical', true,
     '{"type":"object","properties":{"from_account":{"type":"string"},"to_account":{"type":"string"},"amount":{"type":"number"},"currency":{"type":"string","default":"CNY"}},"required":["from_account","to_account","amount"]}'::jsonb,
     '{"type":"object","properties":{"transaction_id":{"type":"string"},"status":{"type":"string"}}}'::jsonb,
     '1.0', true, now(), now());

COMMIT;

-- ====== 验证数据 ======
SELECT '=== 初始化完成 ===' as info;
SELECT '租户: ' || COUNT(*) FROM tenant WHERE id = 'default';
SELECT '用户: ' || COUNT(*) FROM tenant_user;
SELECT 'API Key: ' || COUNT(*) FROM api_keys;
SELECT '模型: ' || COUNT(*) FROM model_config;
SELECT '工具: ' || COUNT(*) FROM tool_definition;
