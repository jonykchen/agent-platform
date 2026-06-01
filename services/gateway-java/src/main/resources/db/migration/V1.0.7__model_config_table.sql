-- ============================================================
-- V1.0.7__model_config_table.sql
-- 模型配置表：存储平台支持的 LLM 模型信息
-- ============================================================

CREATE TABLE IF NOT EXISTS model_config (
    id                  VARCHAR(64) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    provider            VARCHAR(64) NOT NULL,
    type                VARCHAR(32) NOT NULL DEFAULT 'chat',

    -- 能力参数
    context_window      INT NOT NULL,
    max_output_tokens   INT NOT NULL,
    capabilities        JSONB DEFAULT '[]',

    -- 成本配置（USD per 1K tokens）
    cost_per_1k_input   DECIMAL(10,6) NOT NULL DEFAULT 0,
    cost_per_1k_output  DECIMAL(10,6) NOT NULL DEFAULT 0,

    -- 元数据
    description         TEXT,
    enabled             BOOLEAN NOT NULL DEFAULT true,
    display_order       INT NOT NULL DEFAULT 100,

    -- 审计
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_model_provider ON model_config(provider);
CREATE INDEX IF NOT EXISTS idx_model_enabled ON model_config(enabled) WHERE enabled = true;

-- 种子数据：国内 LLM 模型配置
INSERT INTO model_config (id, name, provider, type, context_window, max_output_tokens, capabilities, cost_per_1k_input, cost_per_1k_output, description, display_order) VALUES
('qwen-max', '通义千问 Max', 'qwen', 'chat', 128000, 8000,
 '["function_call", "streaming", "multi_turn"]',
 0.02, 0.06, '通义千问旗舰模型，适合复杂推理任务', 1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO model_config (id, name, provider, type, context_window, max_output_tokens, capabilities, cost_per_1k_input, cost_per_1k_output, description, display_order) VALUES
('qwen-plus', '通义千问 Plus', 'qwen', 'chat', 32000, 4000,
 '["function_call", "streaming"]',
 0.008, 0.02, '通义千问高性价比模型，适合日常对话', 2)
ON CONFLICT (id) DO NOTHING;

INSERT INTO model_config (id, name, provider, type, context_window, max_output_tokens, capabilities, cost_per_1k_input, cost_per_1k_output, description, display_order) VALUES
('deepseek-chat', 'DeepSeek Chat', 'deepseek', 'chat', 64000, 4000,
 '["function_call", "streaming"]',
 0.001, 0.002, '深度求索通用对话模型', 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO model_config (id, name, provider, type, context_window, max_output_tokens, capabilities, cost_per_1k_input, cost_per_1k_output, description, display_order) VALUES
('glm-4', 'GLM-4', 'zhipu', 'chat', 128000, 4096,
 '["function_call", "streaming"]',
 0.1, 0.1, '智谱AI通用对话模型', 4)
ON CONFLICT (id) DO NOTHING;

-- 文档化
COMMENT ON TABLE model_config IS '模型配置表：存储平台支持的 LLM 模型信息和成本配置';
