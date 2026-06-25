# 数据设计 — 完整 DDL、迁移策略与多租户扩展

> **版本**：v2.1 | **状态**：已实施 | **对应审查项**：P-04, M-02
>
> **实施状态更新（2026-06-25）**：
> - ✅ 核心表 DDL（shared/sql 已定义）
> - ✅ Alembic 迁移（orchestrator-python/knowledge-python 已配置）
> - ✅ pgvector 向量索引（HNSW 已配置）
> - ✅ 多租户 RLS 策略（V002 迁移已实现）

---

## 1. 核心表完整 DDL（含审查修正）

### 修正说明（P-04）

原始方案中 `agent_run` 表使用 `(metadata->>'tenant_id')` 建索引，存在以下问题：
- 从 JSONB 中提取值建索引，每次查询都需类型转换
- 对 planner 不友好，维护成本高
- **修正：所有核心业务表的 tenant_id 必须作为独立列（first-class column）**

### 1.1 agent_session（会话表）

```sql
CREATE TABLE agent_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    session_type    VARCHAR(32) NOT NULL DEFAULT 'chat',  -- chat / task / workflow
    title           VARCHAR(256),
    status          VARCHAR(32) NOT NULL DEFAULT 'active', -- active / archived / closed
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

CREATE INDEX idx_session_tenant_user ON agent_session(tenant_id, user_id);
CREATE INDEX idx_session_created ON agent_session(created_at DESC);
CREATE INDEX idx_session_status ON agent_session(status) WHERE status = 'active';
```

### 1.2 agent_run（运行实例表 — **已修正**）

```sql
CREATE TABLE agent_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- ====== 关联 ======
    session_id      UUID NOT NULL REFERENCES agent_session(id),
    
    -- ====== 租户信息（独立列，非 JSONB 内嵌） ======
    tenant_id       VARCHAR(64) NOT NULL,        -- ✅ P-04 修正: 独立列
    user_id         VARCHAR(128) NOT NULL,        -- ✅ 补充: 方便按用户直接查询
    
    -- ====== 运行状态 ======
    run_number      INT NOT NULL,
    input_message   TEXT NOT NULL,
    output_message  TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'running',
    error_message   TEXT,
    error_code      VARCHAR(64),                 -- 统一错误码
    
    -- ====== 模型与资源消耗 ======
    model_used      VARCHAR(64),
    total_tokens    INT DEFAULT 0,
    total_cost_usd  DECIMAL(10,6) DEFAULT 0,
    duration_ms     INT,
    
    -- ====== 扩展字段 ======
    metadata        JSONB DEFAULT '{}',          -- 仅存放真正的非结构化扩展数据
    
    -- ====== 时间戳 ======
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    
    UNIQUE(session_id, run_number)
);

-- ✅ P-04 修正: 使用独立列的普通复合索引（高效得多）
CREATE INDEX idx_run_tenant_created ON agent_run(tenant_id, started_at DESC);
CREATE INDEX idx_run_user ON agent_run(user_id, started_at DESC);
CREATE INDEX idx_run_session ON agent_run(session_id);
CREATE INDEX idx_run_status ON agent_run(status);
CREATE INDEX idx_run_model ON agent_run(model_used);  -- 按模型统计用

-- 注释: metadata JSONB 不再存储 tenant_id/user_id，仅用于运行时动态属性
```

### 1.3 agent_step（执行步骤表 — 含分区策略）

```sql
-- 使用原生分区表（PostgreSQL 10+）
CREATE TABLE agent_step (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    run_id          UUID NOT NULL REFERENCES agent_run(id),
    tenant_id       VARCHAR(64) NOT NULL,        -- 冗余存储，避免 JOIN 查询
    
    step_order      INT NOT NULL,
    step_type       VARCHAR(32) NOT NULL,  -- thinking / tool_call / observation / final_answer / intent_classify / retrieve / risk_check / approval_wait
    content         TEXT NOT NULL,
    
    tool_name       VARCHAR(128),
    tool_input      JSONB,
    tool_output     JSONB,
    thinking        TEXT,                   -- CoT 推理过程
    token_count     INT DEFAULT 0,
    duration_ms     INT,
    
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 月度分区
CREATE TABLE agent_step_2026_05 PARTITION OF agent_step
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE agent_step_2026_06 PARTITION OF agent_step
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_step_run ON agent_step(run_id, step_order);
CREATE INDEX idx_step_tenant ON agent_step(tenant_id, created_at DESC);  -- 分区表上可正常建索引
CREATE INDEX idx_step_type ON agent_step(step_type);
```

### 1.4 tool_invocation（工具调用明细表）

```sql
CREATE TABLE tool_invocation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id             UUID NOT NULL REFERENCES agent_step(id),
    run_id              UUID NOT NULL REFERENCES agent_run(id),
    
    tool_name           VARCHAR(128) NOT NULL,
    tool_category       VARCHAR(32),            -- query / write / external
    tool_version        VARCHAR(16) DEFAULT '1.0',
    risk_level          VARCHAR(16) NOT NULL DEFAULT 'low',
    
    input_schema        JSONB,                  -- 工具入参 schema 定义快照
    input_data          JSONB NOT NULL,
    output_data         JSONB,
    
    status              VARCHAR(32) NOT NULL,   -- pending / success / failed / rejected / timeout
    error_code          VARCHAR(64),
    error_message       TEXT,
    
    approval_id         UUID REFERENCES approval_task(id),
    was_cached          BOOLEAN DEFAULT FALSE,
    
    duration_ms         INT,
    provider_latency_ms INT,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_tool_invocation_run ON tool_invocation(run_id);
CREATE INDEX idx_tool_invocation_tool ON tool_invocation(tool_name);
CREATE INDEX idx_tool_invocation_status ON tool_invocation(status);
CREATE INDEX idx_tool_invocation_risk ON tool_invocation(risk_level) WHERE risk_level IN ('high', 'critical');
CREATE INDEX idx_tool_invocation_cached ON tool_invocation(was_cached) WHERE was_cached = true;
```

### 1.5 approval_task（审批任务表）

```sql
CREATE TABLE approval_task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    run_id              UUID NOT NULL REFERENCES agent_run(id),
    tool_invocation_id  UUID REFERENCES tool_invocation(id),
    tenant_id           VARCHAR(64) NOT NULL,  -- 冗余存储
    
    task_type           VARCHAR(32) NOT NULL,   -- tool_approval / sensitive_action / high_value_transaction
    title               VARCHAR(256) NOT NULL,
    description         TEXT NOT NULL,
    request_context     JSONB NOT NULL,         -- 待审批内容快照（不可变）
    
    requester_id        VARCHAR(128) NOT NULL,
    assignee_id         VARCHAR(128),           -- 空=按规则路由
    
    priority            VARCHAR(16) DEFAULT 'normal',
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewer_id         VARCHAR(128),
    review_comment      TEXT,
    reviewed_at         TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ NOT NULL,    -- 审批过期时间
    
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approval_status ON approval_task(status);
CREATE INDEX idx_approval_assignee ON approval_task(assignee_id, status)
    WHERE status = 'pending';
CREATE INDEX idx_approval_expires ON approval_task(expires_at)
    WHERE status = 'pending' AND expires_at > NOW();
CREATE INDEX idx_approval_tenant ON approval_task(tenant_id);
CREATE INDEX idx_approval_requester ON approval_task(requester_id, created_at DESC);
```

#### approval_task 实体类说明

> **⚠️ 当前实现差异**
> 
> 由于 `gateway-java` 和 `governance-java` 服务对审批任务有不同的职责划分，
> 两个服务中的 `ApprovalTask` 实体类字段存在差异：
> 
> | 字段 | gateway-java | governance-java | 说明 |
> |------|:------------:|:---------------:|------|
> | `title` | ✅ | ❌ | 审批标题（gateway 创建时设置） |
> | `description` | ✅ | ❌ | 审批描述（gateway 创建时设置） |
> | `request_context` | ✅ | ❌ | 请求上下文快照（JSONB） |
> | `priority` | ✅ | ❌ | 优先级（normal/high/urgent） |
> | `tool_name` | ❌ | ✅ | 关联的工具名称 |
> | `approver_id` | ❌ | ✅ | 审批人 ID |
> | `approver_email` | ❌ | ✅ | 审批人邮箱 |
> | `reason` | ❌ | ✅ | 审批原因 |
> | `approval_reason` | ❌ | ✅ | 审批结果原因 |
> | `processed_at` | ❌ | ✅ | 处理时间 |
> 
> **设计意图**：
> - `gateway-java`：负责审批任务的创建、查询、基础管理，存储完整的请求上下文
> - `governance-java`：负责审批流程执行、通知、结果回调，关注审批流转信息
> 
> **后续优化方向**：
> 计划创建 `shared/java-entities` 模块，定义 `BaseApprovalTask` 基类，
> 包含公共字段（id, runId, tenantId, status, expiresAt 等），
> 各服务继承基类并添加特有字段。

### 1.6 audit_event（审计事件表 — **增强版**）

```sql
CREATE TABLE audit_event (
    id              BIGSERIAL PRIMARY KEY,
    event_id        VARCHAR(128) UNIQUE NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    event_category  VARCHAR(32) NOT NULL,   -- lifecycle / security / business / system
    severity        VARCHAR(16) DEFAULT 'info',  -- info / warn / error / critical
    
    -- 主体信息
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    
    -- 资源信息
    resource_type   VARCHAR(64),
    resource_id     VARCHAR(128),
    
    -- 操作详情
    action          VARCHAR(64) NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    details         JSONB DEFAULT '{}',
    
    -- 追踪信息
    request_id      VARCHAR(128),
    trace_id        VARCHAR(128),
    
    -- 来源信息
    ip_address      INET,
    user_agent      TEXT,
    source_service  VARCHAR(32),
    
    -- 时间戳
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 分区定义
CREATE TABLE audit_event_2026_05 PARTITION OF audit_event
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 索引（分区表上创建）
CREATE INDEX idx_audit_tenant_time ON audit_event(tenant_id, created_at DESC);
CREATE INDEX idx_audit_event_type ON audit_event(event_type);
CREATE INDEX idx_audit_user_time ON audit_event(user_id, created_at DESC);
CREATE INDEX idx_audit_severity ON audit_event(severity)
    WHERE severity IN ('error', 'critical');
CREATE INDEX idx_audit_request ON audit_event(request_id);

-- ====== 安全防护（S-01 增强） ======

-- 1. 触发器：禁止 DELETE 和 UPDATE
CREATE OR REPLACE FUNCTION block_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '[SECURITY] audit_event 表禁止 % 操作 (event_id=%, operator=%)',
        TG_OP, COALESCE(OLD.event_id, 'N/A'), current_user;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_modify_on_audit
    BEFORE DELETE OR UPDATE ON audit_event
    FOR EACH ROW
EXECUTE FUNCTION block_audit_modification();

-- 2. 触发器：禁止 TRUNCATE
CREATE OR REPLACE FUNCTION block_audit_truncate()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '[SECURITY] audit_event 表禁止 TRUNCATE 操作';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_trunc_on_audit
    BEFORE TRUNCATE ON audit_event
    FOR STATEMENT
EXECUTE FUNCTION block_audit_truncate();

-- 3. RLS（可选）：限制应用层只能 INSERT
ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_insert_only ON audit_event
    FOR INSERT WITH CHECK (true);
-- 注意: RLS 不能替代触发器，两者配合使用
```

### 1.7 prompt_template（Prompt 模板版本表）

```sql
CREATE TABLE prompt_template (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key        VARCHAR(128) UNIQUE NOT NULL,
    name                VARCHAR(256) NOT NULL,
    description         TEXT,
    version             INT NOT NULL DEFAULT 1,
    
    system_prompt       TEXT NOT NULL,
    user_prompt_template TEXT,                    -- 支持 {{variable}} 模板变量
    few_shot_examples   JSONB DEFAULT '[]',
    parameters          JSONB DEFAULT '[]',       -- 参数定义 [{"name": "max_steps", "type": "int", "default": 10}]
    model_hints         JSONB DEFAULT '{}',
    
    status              VARCHAR(32) NOT NULL DEFAULT 'draft',  -- draft / active / archived
    created_by          VARCHAR(128),
    tags                TEXT[] DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prompt_key_version ON prompt_template(template_key, version DESC);
CREATE INDEX idx_prompt_status ON prompt_template(status) WHERE status = 'active';
CREATE INDEX idx_prompt_tags ON prompt_template USING GIN(tags);
```

### 1.8 model_route_policy（模型路由策略表）

```sql
CREATE TABLE model_route_policy (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name         VARCHAR(128) UNIQUE NOT NULL,
    description         TEXT,
    priority            INT NOT NULL DEFAULT 0,
    
    match_rules         JSONB NOT NULL,         -- 匹配规则 {"tenant_ids": [...], "user_roles": [...], "scene": "chat"}
    primary_model       VARCHAR(64) NOT NULL,
    fallback_models     JSONB DEFAULT '[]',
    config              JSONB DEFAULT '{}',     -- temperature / max_tokens / timeout
    
    rate_limit_rpm      INT DEFAULT 100,        -- RPM 限制
    rate_limit_tpm      INT DEFAULT 50000,      -- TPM 限制
    cost_budget_daily   DECIMAL(12,4),
    
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    effective_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until     TIMESTAMPTZ,
    
    created_by          VARCHAR(128),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_policy_priority ON model_route_policy(priority DESC) WHERE status = 'active';
CREATE INDEX idx_policy_model ON model_route_policy(primary_model);
```

### 1.9 knowledge_document & knowledge_chunk（知识库表）

```sql
-- 文档主表
CREATE TABLE knowledge_document (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           VARCHAR(64) NOT NULL,
    name                VARCHAR(512) NOT NULL,
    file_path           VARCHAR(1024),
    file_type           VARCHAR(32),            -- pdf / word / txt / html / md
    file_size_bytes     BIGINT,
    
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    chunk_count         INT DEFAULT 0,
    
    embedding_model     VARCHAR(64) DEFAULT 'text-embedding-v3',
    
    access_control      JSONB DEFAULT '{"level": "tenant"}',  -- tenant / department / custom
    
    metadata            JSONB DEFAULT '{}',
    created_by          VARCHAR(128),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kd_doc_tenant ON knowledge_document(tenant_id);
CREATE INDEX idx_kd_doc_status ON knowledge_document(status);

-- 文档切片/向量表
CREATE TABLE knowledge_chunk (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES knowledge_document(id),
    tenant_id           VARCHAR(64) NOT NULL,
    
    chunk_index         INT NOT NULL,
    content             TEXT NOT NULL,
    content_hash        VARCHAR(64) NOT NULL,   -- 用于去重
    token_count         INT,
    
    embedding           VECTOR(1024),           -- pgvector 类型，1024 维（text-embedding-v3）
    embedding_model     VARCHAR(64),
    
    metadata            JSONB DEFAULT '{}',
    -- metadata 可包含: {"title": "...", "page_num": 3, "section": "第二章"}
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunk_doc ON knowledge_chunk(document_id, chunk_index);
CREATE INDEX idx_chunk_tenant ON knowledge_chunk(tenant_id);
-- 向量相似度索引（v2.1 修正：使用 HNSW 替代 IVFFlat）
-- HNSW 精度更好，查询更快；构建更慢但适合增量更新场景
-- 当单租户数据 > 150 万条时需评估迁移至 Qdrant
CREATE INDEX idx_chunk_embedding ON knowledge_chunk
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

### 1.10 辅助表（补充建议）

```sql
-- 错误日志表（根因分析）
CREATE TABLE agent_error_log (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID REFERENCES agent_run(id),
    step_id         UUID REFERENCES agent_step(id),
    
    error_type      VARCHAR(64) NOT NULL,    -- model_error / tool_error / validation_error / timeout / unknown
    error_code      VARCHAR(64),             -- 统一错误码
    error_message   TEXT NOT NULL,
    stack_trace    TEXT,
    
    context_snapshot JSONB,                  -- 错误发生时的上下文快照
    -- 包含: state summary, last messages, active tools 等
    
    resolved       BOOLEAN DEFAULT FALSE,
    resolution_note TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_err_log_run ON agent_error_log(run_id, created_at DESC);
CREATE INDEX idx_err_log_type ON agent_error_log(error_type);
CREATE INDEX idx_err_log_unresolved ON agent_error_log(resolved) WHERE resolved = false;

-- 模型日用量统计表（成本治理）
CREATE TABLE model_usage_daily (
    id                  BIGSERIAL PRIMARY KEY,
    stat_date           DATE NOT NULL,
    tenant_id           VARCHAR(64) NOT NULL,
    user_id             VARCHAR(128),
    model_name          VARCHAR(64) NOT NULL,
    
    total_requests      BIGINT DEFAULT 0,
    total_input_tokens  BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_cost_usd      DECIMAL(12,6) DEFAULT 0,
    
    avg_latency_ms      DECIMAL(10,2),
    p95_latency_ms      DECIMAL(10,2),
    p99_latency_ms      DECIMAL(10,2),
    
    error_count         BIGINT DEFAULT 0,
    cache_hit_rate      DECIMAL(5,4) DEFAULT 0,
    
    UNIQUE(stat_date, tenant_id, COALESCE(user_id, ''), model_name)
);

CREATE INDEX idx_usage_daily_date ON model_usage_daily(stat_date DESC);
CREATE INDEX idx_usage_daily_tenant ON model_usage_daily(tenant_id, stat_date DESC);
CREATE INDEX idx_usage_daily_model ON model_usage_daily(model_name, stat_date DESC);

-- 用户反馈表（评测闭环）
CREATE TABLE feedback_record (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES agent_run(id),
    step_id         UUID REFERENCES agent_step(id),
    
    user_id         VARCHAR(128) NOT NULL,
    feedback_type   VARCHAR(32) NOT NULL,    -- thumbs_up / thumbs_down / correction / report
    feedback_text   TEXT,
    corrected_answer TEXT,                   -- 用户提供的正确答案
    rating          SMALLINT CHECK (rating >= 1 AND rating <= 5),  -- 1-5 星评分
    
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_feedback_run ON feedback_record(run_id);
CREATE INDEX idx_feedback_user ON feedback_record(user_id, created_at DESC);
CREATE INDEX idx_feedback_type ON feedback_record(feedback_type);

-- 实验配置表（A/B 测试 / 灰度发布）
CREATE TABLE experiment_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_key  VARCHAR(128) UNIQUE NOT NULL,
    name            VARCHAR(256) NOT NULL,
    description     TEXT,
    
    type            VARCHAR(32) NOT NULL,    -- prompt_ab / model_routing / feature_flag
    
    config_a        JSONB NOT NULL DEFAULT '{}',  -- 对照组配置
    config_b        JSONB NOT NULL DEFAULT '{}',  -- 实验组配置
    
    traffic_split   NUMERIC(4,3) DEFAULT 0.5,      -- B 组流量比例 (0.0~1.0)
    
    target_criteria JSONB DEFAULT '{}',            -- 实验目标受众条件
    
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',  -- draft / running / paused / completed
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,
    
    results_summary JSONB,                         -- 最终结果摘要
    
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_experiment_status ON experiment_config(status) WHERE status IN ('running', 'paused');
```

---

## 2. 多租户扩展表（E-01 补充）

### 租户配额管理表

```sql
-- 租户资源配额表
CREATE TABLE tenant_quota (
    tenant_id           VARCHAR(64) PRIMARY KEY,
    
    tier                VARCHAR(16) NOT NULL DEFAULT 'basic',   -- basic / pro / enterprise / custom
    
    -- 并发控制
    max_concurrent_sessions  INT DEFAULT 100,
    max_concurrent_runs      INT DEFAULT 50,
    
    -- 日用量限额
    max_daily_api_calls      BIGINT DEFAULT 10000,
    max_daily_tokens         BIGINT DEFAULT 1000000,
    max_daily_cost_usd       DECIMAL(10,2) DEFAULT 50.00,
    
    -- 模型访问白名单（空=全部可用）
    allowed_models           TEXT[] DEFAULT '{}',
    -- 工具访问白名单（空=全部可用）
    allowed_tools            TEXT[] DEFAULT '{}',
    
    -- 自定义限流
    custom_rate_limit_rpm    INT DEFAULT 60,
    
    -- 管控状态
    is_suspended             BOOLEAN DEFAULT FALSE,
    suspended_reason         TEXT,
    suspended_at             TIMESTAMPTZ,
    suspended_by             VARCHAR(128),
    
    -- 合同信息
    contract_start           DATE,
    contract_end             DATE,
    contact_person           VARCHAR(128),
    contact_email            VARCHAR(256),
    
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Row Level Security（RLS）自动注入方案

```sql
-- 为所有核心业务表启用 RLS
DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename IN (
            'agent_session', 'agent_run', 'agent_step', 
            'tool_invocation', 'approval_task', 
            'audit_event', 'feedback_record',
            'knowledge_document', 'knowledge_chunk'
        )
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL_security', tbl.tablename);
        
        -- 创建 RLS 策略：自动过滤当前租户的数据
        EXECUTE format('
            CREATE POLICY tenant_isolation_%I ON %I
                FOR ALL
                TO app_user
                USING (tenant_id = current_setting(''app.current_tenant'', true))
        ', tbl.tablename, tbl.tablename);
    END LOOP;
END $$;

-- 应用层设置会话级变量（每个 DB 连接建立时执行一次）
-- SET app.current_tenant = 'tenant_001';
-- 之后该连接的所有 SQL 都会自动带上 WHERE tenant_id = 'tenant_001'

-- Python 侧实现（在连接池获取连接时设置）
# async def get_db_connection():
#     conn = await pool.acquire()
#     await conn.execute("SET app.current_tenant = $1", get_current_tenant())
#     return conn
```

---

## 3. 数据库迁移策略（M-02 补充）

### 选型决策

| 决策 | 选择 | 理由 |
|---|---|---|
| **统一迁移工具** | **Flyway（Java 驱动）** | 所有 SQL 变更集中在一个地方管理，避免 Java/Python 双轨迁移冲突 |
| **Python ORM** | SQLAlchemy 2.0（仅查询） | 不使用 Alembic auto-migration，避免与 Flyway 冲突 |
| **变更流程** | PR 中提交 `.sql` → CI 验证 → Flyway 自动执行 | 标准化、可回溯 |
| **回滚策略** | 手写 `V{N}__rollback.sql` + 在 `afterMigrate` 中记录 | Flyway 不支持自动回滚 |

### 目录结构

```
shared/sql/
├── migrations/
│   ├── V1.0.0__init_schema.sql              # 所有基础表 + 索引 + 触发器
│   ├── V1.1.0__add_tool_permission.sql      # 新增权限表
│   ├── V1.1.0__add_tool_permission_rollback.sql  # 回滚脚本
│   ├── V1.2.0__add_indexes_and_partitions.sql # 补充索引和分区
│   ├── V1.2.0__rollback_indexes_and_partitions.sql
│   ├── V1.3.0__add_tenant_quota_and_rls.sql  # 多租户扩展
│   └── ...
├── seeds/
│   └── V1.0.0__seed_default_data.sql        # 初始数据（角色、默认策略等）
└── README.md                                # 迁移规范文档
```

### Flyway 配置

```yaml
# gateway-java/src/main/resources/application.yml（或 application-prod.yml）
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true          # 允许对已有数据库启用迁移
    validate-on-migrate: true          # 迁移前校验 checksum
    out-of-order: false                # ⚠️ 严格禁止乱序迁移！
    clean-disabled: true               # ⚠️ 生产环境绝对禁用 flyway clean
    table: schema_history              # 迁移记录表名（默认）
    sql-migration-prefix: V
    sql-migration-separator: __
    sql-migration-suffixes: .sql
    encoding: UTF-8
    
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:agent_platform}
    username: ${DB_USER:app_flyway}
    password: ${DB_PASSWORD}
    hikari:
      pool-name: FlywayPool
      maximum-pool-size: 2              # Flyway 只需要少量连接
```

### 迁移规范 README.md

```markdown
# Database Migration Guide

## 变更流程

1. **编写迁移 SQL**: 创建 `V{X.Y.Z}__{描述}.sql`
2. **编写回滚 SQL** (必须): 创建 `V{X.Y.Z}__{描述}_rollback.sql`
3. **本地验证**: `mvnw flyway:migrate -P local`
4. **PR 提交**: CI 会自动运行迁移到测试库
5. **Code Review**: 必须有人 Review DDL 变更
6. **合并后自动部署**

## 命名规范

- 版本号: `V{major}.{minor}.{patch}` (如 `V1.2.0`)
- 描述: snake_case (如 `add_user_avatar_column`)
- 示例文件名: `V1.2.0__add_user_avatar_column.sql`

## 注意事项

- ❌ 禁止修改已发布的迁移文件（会导致 checksum 失败）
- ❌ 禁止在生产环境执行 `flyway clean`
- ❌ 禁止在迁移中使用 `DROP TABLE` / `DROP COLUMN`（用 ALTER 替代）
- ✅ 大表变更必须在低峰期执行
- ✅ 涉及数据的迁移脚本必须支持重复执行（幂等）
- ✅ 新增的表必须有正确的 tenant_id 列和索引
```

---

## 4. 索引策略总结

| 表 | 主索引 | 查询模式优化索引 | 条件索引 |
|---|---|---|---|
| **agent_session** | PK (uuid) | (tenant_id, user_id), (created_at) | status='active' |
| **agent_run** | PK (uuid) | **(tenant_id, created_at)** ✅修正 | (status), (model_used) |
| **agent_step** | PK (uuid) | (run_id, step_order) | (step_type) |
| **tool_invocation** | PK (uuid) | (run_id), (tool_name), (created_at) | (risk_level IN ('high','critical')), was_cached=true |
| **approval_task** | PK (uuid) | (assignee_id, status), (expires_at) | status='pending' |
| **audit_event** | PK (bigserial) | **(tenant_id, created_at)**, (event_type), (request_id) | severity IN ('error','critical') |
| **knowledge_chunk** | PK (uuid) | (document_id, chunk_index), (tenant_id) | **HNSW 向量索引** |
| **model_usage_daily** | UK (date,tenant,user,model) | (stat_date), (tenant_id), (model_name) | — |

---

## 5. 数据生命周期管理（从原方案保留并整理）

### 分区归档自动化

参见原方案 §12.5 的分区管理和冷数据归档脚本。

### 数据保留合规要求

| 数据类型 | 最短保留期 | 最长保留期 | 删除触发条件 | 合规依据 |
|---|---|---|---|---|
| audit_event | 180 天 | 按合同约定 | 合同到期后 30 天 | 企业审计合规 |
| agent_session | 90 天 | 365 天 | 用户请求删除 / 合规到期 | 个保法 |
| 用户个人信息字段 | — | — | 用户请求删除后 15 天 | GDPR / 个保法 |
| knowledge_chunk | 按业务需求 | — | 文档删除时同步删除 | 数据一致性 |

### CronJob 定时任务

参见原方案 §12.5 末尾的 Kubernetes CronJob YAML。
